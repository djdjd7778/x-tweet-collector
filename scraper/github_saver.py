"""
github_saver.py
取得したツイートを GitHub リポジトリに JSON としてコミット・保存する。
GITHUB_TOKEN と GITHUB_REPO 環境変数が必要。

使い方:
  python github_saver.py <username>
  python github_saver.py elonmusk --max 40
"""

import os
import sys
import json
import base64
import argparse
from datetime import datetime, timezone

import httpx

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")   # 例: "your-name/tweet-archive"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN environment variable is not set.")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_file_sha(repo: str, path: str, branch: str) -> str | None:
    """既存ファイルの SHA を取得（上書き更新に必要）。"""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    try:
        with httpx.Client(headers=_headers(), timeout=10) as client:
            resp = client.get(url, params={"ref": branch})
            if resp.status_code == 200:
                return resp.json()["sha"]
    except Exception:
        pass
    return None


def push_to_github(
    username: str,
    tweets: list[dict],
    repo: str | None = None,
    branch: str | None = None,
) -> str:
    """
    ツイートデータを GitHub リポジトリの
    `data/<username>/YYYY-MM-DD.json` に保存する。

    Returns
    -------
    str : コミット URL
    """
    repo = repo or GITHUB_REPO
    branch = branch or GITHUB_BRANCH

    if not repo:
        raise RuntimeError("GITHUB_REPO environment variable is not set.")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_path = f"data/{username}/{today}.json"

    payload = {
        "username": username,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(tweets),
        "tweets": tweets,
    }
    content_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    content_b64 = base64.b64encode(content_bytes).decode()

    sha = _get_file_sha(repo, file_path, branch)

    body: dict = {
        "message": f"chore: update tweets for @{username} ({today})",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha  # 既存ファイルを上書き

    url = f"{GITHUB_API}/repos/{repo}/contents/{file_path}"
    with httpx.Client(headers=_headers(), timeout=20) as client:
        resp = client.put(url, json=body)
        resp.raise_for_status()
        commit_url = resp.json()["commit"]["html_url"]

    print(f"[OK] Pushed {len(tweets)} tweets -> {file_path}")
    print(f"   Commit: {commit_url}")
    return commit_url


# ───────────────────────────────────────────
# 単体実行（スクレイパーと組み合わせ）
# ───────────────────────────────────────────

if __name__ == "__main__":
    # scraper パッケージを親ディレクトリから参照できるようにする
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scraper.tweet_scraper import fetch_tweets

    parser = argparse.ArgumentParser(description="Fetch tweets and save to GitHub")
    parser.add_argument("username", help="X username (without @)")
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--replies", action="store_true")
    parser.add_argument("--repo", default="", help="GitHub repo (owner/name)")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()

    tweets = fetch_tweets(args.username, max_tweets=args.max, include_replies=args.replies)
    push_to_github(
        args.username,
        tweets,
        repo=args.repo or None,
        branch=args.branch,
    )
