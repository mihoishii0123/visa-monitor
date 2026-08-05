import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

URL = "https://digital.diplo.de/arbeitsaufnahme-akademiker"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
SCHEDULE = os.environ.get("GITHUB_EVENT_SCHEDULE", "")
IS_HOURLY_RUN = SCHEDULE.strip() == "0 * * * *"

STATE_FILE = Path("state.json")
LOG_FILE = Path("monitor.log")
SCREENSHOT_FILE = Path("tokyo-status.png")

UNAVAILABLE_TEXTS = (
    "Online application currently not available",
    "Online application not available",
)


def now_jst() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tokyo"))


def log(message: str) -> None:
    line = f"{now_jst():%Y-%m-%d %H:%M:%S JST} | {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_discord(message: str) -> None:
    if not WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL が設定されていません。")
    response = requests.post(
        WEBHOOK_URL,
        json={"content": message},
        timeout=20,
    )
    response.raise_for_status()


def load_previous_status() -> str:
    if not STATE_FILE.exists():
        return "UNKNOWN"
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return str(data.get("status", "UNKNOWN"))
    except (OSError, json.JSONDecodeError):
        return "UNKNOWN"


def save_status(status: str, detail: str) -> None:
    data = {
        "status": status,
        "detail": detail,
        "checked_at_jst": now_jst().isoformat(),
    }
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def select_japan(page) -> None:
    # Native <select> の場合
    comboboxes = page.get_by_role("combobox")
    if comboboxes.count() > 0:
        box = comboboxes.first
        try:
            box.select_option(label="Japan")
            return
        except Exception:
            try:
                box.click()
                page.get_by_text("Japan", exact=True).last.click()
                return
            except Exception:
                pass

    # カスタムドロップダウンの場合
    candidates = [
        page.get_by_text("Select country", exact=False),
        page.get_by_text("In which country are you resident?", exact=False),
    ]
    for candidate in candidates:
        if candidate.count() > 0:
            candidate.last.click()
            page.wait_for_timeout(500)
            japan = page.get_by_text("Japan", exact=True)
            if japan.count() > 0:
                japan.last.click()
                return

    raise RuntimeError("国選択欄で Japan を選択できませんでした。")


def inspect_tokyo() -> tuple[str, str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            locale="en-US",
        )
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(3_000)
            select_japan(page)
            page.wait_for_timeout(3_000)

            body_text = page.locator("body").inner_text(timeout=30_000)
            page.screenshot(path=str(SCREENSHOT_FILE), full_page=True)

            normalized = " ".join(body_text.split())

            if "Tokyo" not in normalized:
                return "ERROR", "ページ内に Tokyo が見つかりませんでした。"

            if any(text in normalized for text in UNAVAILABLE_TEXTS):
                return "NOT_AVAILABLE", "Tokyo: Online application currently not available"

            return "AVAILABLE", "Tokyo の利用不可表示が消えています。申請ページをすぐ確認してください。"
        finally:
            browser.close()


def main() -> int:
    previous = load_previous_status()

    try:
        status, detail = inspect_tokyo()
        log(f"{status} | {detail}")
        save_status(status, detail)

        if status == "AVAILABLE" and previous != "AVAILABLE":
            send_discord(
                "🚨 **Tokyoのオンライン申請が利用可能になった可能性があります！**\n"
                f"{URL}\n"
                f"確認時刻：{now_jst():%Y-%m-%d %H:%M JST}\n"
                "すぐにページを開いて確認してください。"
            )

        if IS_HOURLY_RUN:
            icon = {
                "NOT_AVAILABLE": "🟡",
                "AVAILABLE": "🟢",
                "ERROR": "🔴",
            }.get(status, "⚪")
            send_discord(
                f"{icon} **Visa Monitor 稼働中**\n"
                f"Tokyo：{status}\n"
                f"確認時刻：{now_jst():%Y-%m-%d %H:%M JST}"
            )

        if status == "ERROR":
            send_discord(
                "⚠️ **Visa Monitorで確認エラーが発生しました**\n"
                f"{detail}\n"
                f"確認時刻：{now_jst():%Y-%m-%d %H:%M JST}"
            )
            return 1

        return 0

    except PlaywrightTimeoutError as exc:
        message = f"ページ読み込みがタイムアウトしました：{exc}"
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"

    log(f"ERROR | {message}")
    save_status("ERROR", message)

    try:
        send_discord(
            "⚠️ **Visa Monitorでエラーが発生しました**\n"
            f"{message}\n"
            f"確認時刻：{now_jst():%Y-%m-%d %H:%M JST}"
        )
    except Exception as notify_error:
        log(f"Discord通知にも失敗しました：{notify_error}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
