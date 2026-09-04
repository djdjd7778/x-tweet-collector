"""
app.py
Flask Web API サーバー。Render にそのままデプロイ可能。

エンドポイント:
  GET /tweets/<username>?max=20&replies=false
  GET /health
"""

import os
import json
from datetime import datetime, timezone

from flask import Flask, jsonify, request, abort
from scraper.tweet_scraper import fetch_tweets

app = Flask(__name__)

# Render の環境変数でアクセストークンを設定すると簡易認証が有効になる
API_TOKEN = os.environ.get("API_TOKEN", "")


def _check_token():
    if not API_TOKEN:
        return  # トークン未設定 → 認証なし（開発用）
    token = request.headers.get("X-API-Token", "")
    if token != API_TOKEN:
        abort(401, description="Invalid or missing X-API-Token header.")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@app.route("/tweets/<username>")
def get_tweets(username: str):
    _check_token()

    max_tweets = min(int(request.args.get("max", 20)), 100)
    include_replies = request.args.get("replies", "false").lower() == "true"

    tweets = fetch_tweets(
        username,
        max_tweets=max_tweets,
        include_replies=include_replies,
    )

    return jsonify(
        {
            "username": username,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "count": len(tweets),
            "tweets": tweets,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
