"""
tweet_scraper.py
X(Twitter) の公式 API を使わずにツイートを取得する。

戦略（上から順に試みる）:
  1. syndication.twitter.com  - Xが公式サイト向けに提供する埋め込みエンドポイント
  2. Nitter インスタンス群     - 死活チェックしながらフォールバック
"""

import os
import re
import time
import json
import random
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

# ───────────────────────────────────────────
# 設定
# ───────────────────────────────────────────

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.tiekoetter.com",
    "https://nitter.poast.org",
    "https://nitter.woodland.cafe",
    "https://nitter.fdn.fr",
    "https://nitter.rawbit.ninja",
    "https://n.opnxng.com",
]

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Mode": "navigate",
}

HEADERS_JSON = {
    **HEADERS_BROWSER,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://twitter.com/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ───────────────────────────────────────────
# 戦略 1: syndication.twitter.com
# ───────────────────────────────────────────

def _fetch_syndication(username: str, max_tweets: int = 20) -> list[dict]:
    """
    Xの公式埋め込みウィジェット用エンドポイントからツイートを取得。
    API キー不要・ログイン不要（2024年時点で有効なケースあり）。
    """
    # まず guest_token を取得
    guest_token = _get_guest_token()
    if not guest_token:
        logger.warning("[syndication] Could not obtain guest token.")
        return []

    # タイムラインをリクエスト
    url = (
        f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
        f"?withReplies=false"
    )
    headers = {
        **HEADERS_JSON,
        "x-guest-token": guest_token,
    }

    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
            resp = client.get(url)
            logger.info(f"[syndication] status={resp.status_code}")
            if resp.status_code != 200:
                return []

            # HTML の中に埋め込み JSON がある場合
            text = resp.text
            if text.strip().startswith("{"):
                data = resp.json()
            else:
                # HTML から JSON を抽出
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
                if not m:
                    return []
                data = json.loads(m.group(1))

            return _parse_syndication_json(data, max_tweets)
    except Exception as e:
        logger.warning(f"[syndication] Error: {e}")
        return []


def _get_guest_token() -> Optional[str]:
    """Twitter/X のゲストトークンを取得する。"""
    # Bearer トークンは公開されている固定値（X の公式 web クライアントと同じ）
    BEARER = (
        "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
        "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
    )
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                "https://api.twitter.com/1.1/guest/activate.json",
                headers={
                    "Authorization": f"Bearer {BEARER}",
                    "User-Agent": HEADERS_BROWSER["User-Agent"],
                },
            )
            if resp.status_code == 200:
                token = resp.json().get("guest_token")
                logger.info(f"[syndication] guest_token obtained: {token[:8]}...")
                return token
    except Exception as e:
        logger.warning(f"[syndication] guest token error: {e}")
    return None


def _parse_syndication_json(data: dict, max_tweets: int) -> list[dict]:
    """syndication レスポンス JSON からツイートリストを抽出する。"""
    tweets = []
    try:
        # __NEXT_DATA__ 形式
        props = data.get("props", {}).get("pageProps", {})
        timeline = props.get("timeline", {})
        entries = timeline.get("entries", [])

        for entry in entries[:max_tweets]:
            content = entry.get("content", {})
            tweet_data = content.get("tweet", content)

            text = tweet_data.get("full_text") or tweet_data.get("text", "")
            tid = tweet_data.get("id_str", "")
            created_at = tweet_data.get("created_at", "")
            user = tweet_data.get("user", {})
            screen_name = user.get("screen_name", "")

            # メディア
            images = []
            media_list = (
                tweet_data.get("extended_entities", {}).get("media")
                or tweet_data.get("entities", {}).get("media")
                or []
            )
            for m in media_list:
                if m.get("type") == "photo":
                    images.append(m.get("media_url_https", ""))

            tweets.append(
                {
                    "id": tid,
                    "text": text,
                    "published_at": created_at,
                    "url": f"https://twitter.com/{screen_name}/status/{tid}" if tid else "",
                    "stats": {
                        "reply_count": tweet_data.get("reply_count", 0),
                        "retweet_count": tweet_data.get("retweet_count", 0),
                        "like_count": tweet_data.get("favorite_count", 0),
                        "quote_count": tweet_data.get("quote_count", 0),
                    },
                    "images": images,
                }
            )
    except Exception as e:
        logger.warning(f"[syndication] parse error: {e}")
    return tweets


# ───────────────────────────────────────────
# 戦略 2: Nitter スクレイピング
# ───────────────────────────────────────────

def _fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    try:
        with httpx.Client(headers=HEADERS_BROWSER, follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        logger.warning(f"Fetch failed [{url}]: {e}")
        return None


def _parse_nitter_tweets(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    tweets = []

    for item in soup.select(".timeline-item"):
        if item.select_one(".pinned"):
            continue
        try:
            content_el = item.select_one(".tweet-content")
            text = content_el.get_text(separator="\n", strip=True) if content_el else ""

            time_el = item.select_one("span.tweet-date a")
            published_at_raw = time_el["title"] if time_el and time_el.has_attr("title") else ""
            tweet_path = time_el["href"] if time_el and time_el.has_attr("href") else ""
            tweet_url = f"{base_url}{tweet_path}" if tweet_path else ""

            tweet_id_match = re.search(r"/status/(\d+)", tweet_path)
            tweet_id = tweet_id_match.group(1) if tweet_id_match else ""

            stats = {}
            for stat in item.select(".tweet-stat"):
                icon = stat.select_one(".icon")
                icon_class = " ".join(icon.get("class", [])) if icon else ""
                value_text = stat.get_text(strip=True).replace(",", "")
                value = int(value_text) if value_text.isdigit() else 0
                if "retweet" in icon_class:
                    stats["retweet_count"] = value
                elif "heart" in icon_class:
                    stats["like_count"] = value
                elif "comment" in icon_class:
                    stats["reply_count"] = value
                elif "quote" in icon_class:
                    stats["quote_count"] = value

            images = [
                img["src"] for img in item.select(".attachments img")
                if img.has_attr("src")
            ]

            tweets.append(
                {
                    "id": tweet_id,
                    "text": text,
                    "published_at": published_at_raw,
                    "url": tweet_url,
                    "stats": stats,
                    "images": images,
                    "source": "nitter",
                }
            )
        except Exception as e:
            logger.debug(f"Skipping item: {e}")
    return tweets


def _get_cursor(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.select_one(".show-more a")
    if next_link and next_link.has_attr("href"):
        m = re.search(r"cursor=([^&]+)", next_link["href"])
        if m:
            return m.group(1)
    return None


def _fetch_nitter(username: str, max_tweets: int = 20) -> list[dict]:
    all_tweets: list[dict] = []
    cursor: Optional[str] = None
    instances = NITTER_INSTANCES.copy()
    random.shuffle(instances)

    for instance in instances:
        if len(all_tweets) >= max_tweets:
            break
        url = f"{instance}/{username}"
        if cursor:
            url += f"?cursor={cursor}"

        logger.info(f"[nitter] Trying {url}")
        html = _fetch_html(url)
        if not html:
            continue

        tweets = _parse_nitter_tweets(html, instance)
        if not tweets:
            logger.warning(f"[nitter] No tweets from {instance}")
            continue

        all_tweets.extend(tweets)
        logger.info(f"[nitter] Got {len(tweets)} tweets (total: {len(all_tweets)})")

        cursor = _get_cursor(html)
        if not cursor:
            break
        time.sleep(random.uniform(1.5, 3.0))

    return all_tweets[:max_tweets]


# ───────────────────────────────────────────
# 公開 API（戦略を自動選択）
# ───────────────────────────────────────────

def fetch_tweets(
    username: str,
    max_tweets: int = 20,
    include_replies: bool = False,
    strategy: str = "auto",
) -> list[dict]:
    """
    指定 X アカウントのツイートを取得する。

    Parameters
    ----------
    username      : X のユーザー名（@ なし）
    max_tweets    : 最大取得件数
    include_replies: リプライを含めるか（Nitter のみ対応）
    strategy      : "auto" | "syndication" | "nitter"
                    auto = syndication を試して失敗なら nitter

    Returns
    -------
    list of tweet dicts
    """
    tweets: list[dict] = []

    if strategy in ("auto", "syndication"):
        logger.info(f"[strategy] Trying syndication for @{username}")
        tweets = _fetch_syndication(username, max_tweets)
        if tweets:
            logger.info(f"[strategy] syndication OK: {len(tweets)} tweets")
            return tweets

    if strategy in ("auto", "nitter"):
        logger.info(f"[strategy] Trying nitter for @{username}")
        tweets = _fetch_nitter(username, max_tweets)
        if tweets:
            logger.info(f"[strategy] nitter OK: {len(tweets)} tweets")
            return tweets

    logger.warning("All strategies failed.")
    return []


# ───────────────────────────────────────────
# 単体実行
# ───────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    # Windows CP932 対策
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp932", "mbcs"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Tweet scraper (no API key)")
    parser.add_argument("username", help="X username (without @)")
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--replies", action="store_true")
    parser.add_argument("--strategy", choices=["auto", "syndication", "nitter"], default="auto")
    parser.add_argument("--out", default="tweets.json")
    args = parser.parse_args()

    tweets = fetch_tweets(
        args.username,
        max_tweets=args.max,
        include_replies=args.replies,
        strategy=args.strategy,
    )

    result = {
        "username": args.username,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(tweets),
        "tweets": tweets,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] Saved {len(tweets)} tweets -> {args.out}")
