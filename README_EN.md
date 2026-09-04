# Tweet Scraper (No API Required)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇯🇵 [日本語版はこちら → README.md](README.md)

A tool that automatically fetches and saves tweets from specific X (Twitter) accounts **without using the official API**.  
**Just fork this repository to set up your own automated tweet collection pipeline on GitHub.**

---

## How to Use (Fork & Setup)

### Step 1 — Fork this Repository

1. Click the **Fork** button in the top-right corner of this page
2. Select your account as the fork destination and click **Create fork**

---

### Step 2 — Enable GitHub Actions

GitHub Actions is disabled by default in forked repositories.

1. Open the **Actions** tab in your forked repository
2. Click **"I understand my workflows, go ahead and enable them"**

---

### Step 3 — Set the Target Account

Open [`.github/workflows/fetch_tweets.yml`](.github/workflows/fetch_tweets.yml) and change the `USERNAME` value to the X account you want to track:

```yaml
# Before
USERNAME: ${{ github.event.inputs.username || 'elonmusk' }}

# After (e.g., to track @example)
USERNAME: ${{ github.event.inputs.username || 'example' }}
```

Click **Commit changes** to save.

---

### Step 4 — Run a Manual Test

1. Go to the **Actions** tab → click **Fetch Tweets & Save to GitHub** in the left sidebar
2. Click the **Run workflow** button on the right
3. Enter a username in the `username` field and click **Run workflow**

After a moment, `data/<username>/YYYY-MM-DD.json` will be created in your repository.

---

### Step 5 — Confirm Automatic Scheduling (Daily at UTC 0:00)

By default, the workflow runs automatically every day at **UTC 0:00 (9:00 AM JST)**.  
To change the schedule, edit the following line in `fetch_tweets.yml`:

```yaml
# Example: run daily at 9:00 AM UTC
- cron: "0 9 * * *"
```

---

## Understanding the Output Data

Fetched tweets are saved to `data/<username>/YYYY-MM-DD.json`.

```
data/
└── elonmusk/
    ├── 2026-09-03.json
    ├── 2026-09-04.json
    └── ...
```

JSON structure:

```json
{
  "username": "elonmusk",
  "fetched_at": "2026-09-03T00:00:00+00:00",
  "count": 20,
  "tweets": [
    {
      "id": "1234567890",
      "text": "Tweet content here",
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

## (Optional) Deploy as a REST API on Render

If you want to expose the scraper as a REST API:

### Deploy Steps

1. Create a free account at [render.com](https://render.com)
2. Click **New → Web Service**
3. Under **Connect a repository**, select your forked repository
4. `render.yaml` is detected automatically — click **Deploy**

Once deployed, access it like this:

```bash
# Fetch tweets (returns JSON)
curl https://your-app.onrender.com/tweets/elonmusk?max=20

# Health check
curl https://your-app.onrender.com/health
```

### Adding Authentication (Optional)

In your Render dashboard → **Environment**, add the following variable:

| Variable | Value |
|----------|-------|
| `API_TOKEN` | Any secret string you choose |

After setting this, include the token in every request:

```bash
curl -H "X-API-Token: YOUR_SECRET_TOKEN" \
     https://your-app.onrender.com/tweets/elonmusk
```

---

## (Optional) Run Locally

```bash
# 1. Clone your forked repository
git clone https://github.com/YOUR_NAME/REPO_NAME.git
cd REPO_NAME

# 2. Install dependencies
pip install -r requirements.txt

# 3. Fetch tweets and save to JSON
python -m scraper.tweet_scraper elonmusk --max 20 --out tweets.json

# 4. Start the Flask server
python app.py
# → http://localhost:5000/tweets/elonmusk
```

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| 0 tweets returned | The syndication endpoint may be blocked. Please open an [Issue](../../issues) |
| Actions not running | Make sure Actions is enabled in the **Actions** tab of your forked repo |
| `data/` folder not created | Verify that the workflow has `contents: write` permission |
| Nitter not responding | Check [nitter instance status](https://status.d420.de/) and update the `NITTER_INSTANCES` list in [`tweet_scraper.py`](scraper/tweet_scraper.py) |

---

## How It Works

```
Strategy 1: syndication.twitter.com
    ↓ X's official embed widget endpoint (no API key needed)
    ↓ Automatically obtains a guest token
    ↓ If this fails, fall back to...

Strategy 2: Nitter instances
    ↓ Open-source Twitter frontend
    ↓ Randomly tries multiple instances with automatic fallback
```

---

## ⚠️ Disclaimer

- This tool may violate X's Terms of Service. **Use at your own risk.**
- Changes on X's side may break this tool without notice.
- Excessive or high-frequency scraping may result in IP bans.

## Content Removal Requests

If X (Twitter) or any content rights holder requests the removal of data collected by this tool, **we will respond without delay.**  
To request deletion of data stored in a forked repository, please contact the repository owner via either of the following:

- Open an **Issue** in the forked repository
- Use GitHub's [Privacy Violation Report Form](https://support.github.com/contact/privacy)

Upon receiving a request, **the relevant data will be removed promptly.**
