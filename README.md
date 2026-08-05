# Tokyo Visa Monitor

ドイツ領事サービスポータルの「Japan → Tokyo」を10分ごとに確認し、
利用不可表示が消えたときにDiscordへ通知します。

## 初回設定

1. 公開してしまった古いDiscord Webhookは削除し、新しく作り直す。
2. GitHubリポジトリで `Settings` を開く。
3. 左側の `Secrets and variables` → `Actions` を開く。
4. `New repository secret` を押す。
5. Nameに `DISCORD_WEBHOOK_URL` と入力する。
6. Secretに新しいWebhook URLを貼り付けて保存する。
7. `Actions` タブを開き、`Tokyo Visa Monitor` を選ぶ。
8. `Run workflow` → `Run workflow` を押してテストする。

## 通知

- Tokyoが利用可能に変わったとき：緊急通知
- 1時間ごと：稼働確認通知
- エラー時：エラー通知

## ログ

各実行のログとスクリーンショットは、Actionsの実行画面下部の
`Artifacts` に30日間保存されます。

## 注意

GitHub Actionsのスケジュール実行は混雑時に遅れる場合があります。
この設定での「即時」は、通常は次の10分チェック以内という意味です。
