# Tweet Scraper（API不要）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇺🇸 [English version available → README_EN.md](README_EN.md)

X (Twitter) の公式 API を一切使わずに、特定アカウントのツイートを自動取得・保存するツールです。  
**このリポジトリを Fork するだけで、自分の GitHub に定期取得環境が作れます。**

---

## Fork して使う手順

### Step 1 — リポジトリを Fork する

1. このページ右上の **Fork** ボタンをクリック
2. Fork 先のアカウントを選んで **Create fork**

![Fork ボタンの場所](https://docs.github.com/assets/cb-79331/mw-1440/images/help/repository/fork-button.webp)

---

### Step 2 — Actions を有効にする

Fork したリポジトリでは GitHub Actions がデフォルトで無効になっています。

1. Fork 先のリポジトリの **Actions** タブを開く
2. 「**I understand my workflows, go ahead and enable them**」ボタンをクリック

---

### Step 3 — 監視したいアカウントを設定する

[`.github/workflows/fetch_tweets.yml`](.github/workflows/fetch_tweets.yml) を開いて、  
`USERNAME` の部分を監視したい X のユーザー名に変更します。

```yaml
# 変更前
USERNAME: ${{ github.event.inputs.username || 'elonmusk' }}

# 変更後（例：@hogehoge を監視したい場合）
USERNAME: ${{ github.event.inputs.username || 'hogehoge' }}
```

変更したら **Commit changes** で保存します。

---

### Step 4 — 手動で動作確認する

1. **Actions** タブ → 左の **Fetch Tweets & Save to GitHub** をクリック
2. 右側の **Run workflow** ボタンをクリック
3. `username` 欄にユーザー名を入力して **Run workflow**

しばらくすると `data/<username>/YYYY-MM-DD.json` が作成されます。

---

### Step 5 — 自動実行を確認する（毎日 JST 9:00）

設定を変更しなければ、毎日 **JST 9:00（UTC 0:00）** に自動実行されます。  
スケジュールを変えたい場合は `fetch_tweets.yml` の以下の行を編集してください：

```yaml
# 例：毎日 JST 18:00（UTC 9:00）に変更
- cron: "0 9 * * *"
```

---

## 取得データの見方

取得されたデータは `data/<username>/YYYY-MM-DD.json` に保存されます。

```
data/
└── elonmusk/
    ├── 2026-09-03.json
    ├── 2026-09-04.json
    └── ...
```

JSON の構造：

```json
{
  "username": "elonmusk",
  "fetched_at": "2026-09-03T00:00:00+00:00",
  "count": 20,
  "tweets": [
    {
      "id": "1234567890",
      "text": "ツイート本文",
      "published_at": "Thu Sep 03 00:00:00 +0000 2026",
      "url": "https://twitter.com/elonmusk/status/1234567890",
      "stats": {
        "reply_count": 123,
        "retweet_count": 456,
        "like_count": 7890,
        "quote_count": 12
      },
      "images": []
    }
  ]
}
```

---

## （オプション）Render に API サーバーをデプロイする

Fork したリポジトリを REST API として公開したい場合：

### Render へのデプロイ手順

1. [render.com](https://render.com) でアカウント作成（無料）
2. **New → Web Service** をクリック
3. **Connect a repository** で Fork 先のリポジトリを選択
4. `render.yaml` が自動検出されるのでそのまま **Deploy**

デプロイ完了後、以下のような URL でアクセスできます：

```bash
# ツイートを取得（JSON が返る）
curl https://your-app.onrender.com/tweets/elonmusk?max=20

# ヘルスチェック
curl https://your-app.onrender.com/health
```

### API に認証をかけたい場合

Render ダッシュボード → **Environment** → 以下の環境変数を追加：

| 変数名 | 値 |
|--------|-----|
| `API_TOKEN` | 任意の秘密のトークン文字列 |

設定後はリクエスト時にヘッダーが必要になります：

```bash
curl -H "X-API-Token: YOUR_SECRET_TOKEN" \
     https://your-app.onrender.com/tweets/elonmusk
```

---

## （オプション）ローカルで動かす

```bash
# 1. Clone（Fork したリポジトリを使う場合）
git clone https://github.com/YOUR_NAME/REPO_NAME.git
cd REPO_NAME

# 2. 依存パッケージをインストール
pip install -r requirements.txt

# 3. ツイートを取得して JSON に保存
python -m scraper.tweet_scraper elonmusk --max 20 --out tweets.json

# 4. Flask サーバーを起動
python app.py
# → http://localhost:5000/tweets/elonmusk
```

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| ツイートが 0 件しか取れない | X 側の対策で syndication エンドポイントがブロックされた可能性があります。[Issues](../../issues) で報告してください |
| Actions が実行されない | リポジトリの **Actions** タブで有効化されているか確認 |
| `data/` フォルダが作られない | Actions の **権限** が `contents: write` になっているか確認 |
| Nitter が応答しない | [nitter インスタンスステータス](https://status.d420.de/) で生きているインスタンスを確認し、[`tweet_scraper.py`](scraper/tweet_scraper.py) の `NITTER_INSTANCES` リストを更新 |

---

## 仕組み（技術的な詳細）

```
1st: syndication.twitter.com
      ↓ X公式の埋め込みウィジェット用エンドポイント
      ↓ ゲストトークンを自動取得（API Key不要）
      ↓ 失敗したら...

2nd: Nitter インスタンス群
      ↓ オープンソースの Twitter フロントエンド
      ↓ 複数インスタンスをランダムに試してフォールバック
```

---

## ⚠️ 注意事項

- このツールは X の利用規約に反する可能性があります。**自己責任でご使用ください。**
- X 側の仕様変更により、予告なく動作しなくなることがあります。
- 大量取得・高頻度アクセスはアカウント BANや IP ブロックの原因になります。

## コンテンツ削除依頼について

X (Twitter) またはコンテンツの権利者から削除依頼があった場合は、**遅延なく対応します。**  
Fork 先のリポジトリに保存されたデータの削除を希望される場合は、以下のいずれかの方法でご連絡ください：

- Fork 先リポジトリの **Issues** にてご連絡
- GitHub の [プライバシー侵害報告フォーム](https://support.github.com/contact/privacy) を利用

連絡を受けた後、**速やかに該当データを削除**します。
