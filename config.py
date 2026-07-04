"""
Central configuration for the tech-news Instagram bot.
Edit this file to reskin the design, change sources, or tune slide count.
Nothing in here is a secret — tokens/passwords live in environment variables
(set as GitHub Actions Secrets), never in this file.
"""

import os

# ---------------------------------------------------------------------------
# CONTENT SOURCES
# All RSS/Atom feeds. feedparser handles every one of these the same way,
# including the Hacker News front page (via the hnrss.org bridge) so we don't
# need a second client just for HN.
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage?points=100"},
]

# How many story slides to build (plus 1 cover + 1 outro = TOTAL_SLIDES + 2).
# Instagram carousels max out at 10 items total, so keep this <= 8.
STORY_SLIDE_COUNT = 5

# Simple relevance filter: if a feed mixes non-tech content (e.g. The Verge's
# culture desk), require at least one of these words in title+summary.
# Set to None to disable filtering for a given feed.
KEYWORD_ALLOWLIST = None  # e.g. ["AI", "chip", "app", "startup", "software"]

# Stories are skipped if title+summary+link contains any of these — a light
# default net against off-brand content (piracy-adjacent sites, movie/TV
# reviews that general-interest feeds like Ars Technica sometimes include).
# Tune freely; matching is case-insensitive substring, so keep terms specific.
KEYWORD_BLOCKLIST = [
    "archive.gl",
    "torrent",
    "piracy",
    "box office",
    "movie review",
    "film review",
]

# Hours to add to UTC for the date printed on the cover slide (does NOT
# affect the cron schedule in the workflow, which is always UTC).
# 0 = UTC, 5.5 = India (IST), -5 = US Eastern, etc.
DISPLAY_TIMEZONE_OFFSET_HOURS = 0

# File that remembers which article URLs we've already posted, so the bot
# never repeats a story. Committed back to the repo after every run.
HISTORY_FILE = "posted_history.json"
HISTORY_MAX_AGE_DAYS = 30  # prune entries older than this so the file doesn't grow forever

# ---------------------------------------------------------------------------
# VISUAL DESIGN — deliberately not the generic "AI template" look.
# Signal-wire theme: deep ink background, one amber accent, monospace
# "readout" tags for metadata (source/index) since this literally is a
# machine reading a data feed — the mono type is honest about what it is.
# ---------------------------------------------------------------------------
CANVAS_SIZE = (1080, 1350)  # 4:5 — the tallest ratio Instagram allows in-feed

COLORS = {
    "bg": "#12141C",       # deep ink navy, not pure black
    "text": "#F5F3EE",     # warm off-white
    "muted": "#8B90A0",    # cool grey-blue for secondary text
    "accent": "#FFB238",   # signal amber — the one accent color, used sparingly
}

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
FONTS = {
    "headline": os.path.join(FONT_DIR, "Poppins-Bold.ttf"),
    "body": os.path.join(FONT_DIR, "Poppins-Medium.ttf"),
    "mono": os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf"),
}

OUTPUT_DIR = "output"

# The @handle shown in the small corner tag on every slide. Not a secret —
# just edit this one line before you push. (CLI --handle, if passed to
# run_pipeline.py, overrides this for a one-off local run.)
IG_HANDLE = "@yourhandle"

# ---------------------------------------------------------------------------
# INSTAGRAM — OFFICIAL GRAPH API (recommended path)
# Set these as GitHub Actions Secrets, never hardcode them.
# ---------------------------------------------------------------------------
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
GRAPH_API_VERSION = "v25.0"

# How the generated slide JPEGs become public URLs Instagram can fetch.
# "github" = commit to this repo and use raw.githubusercontent.com (repo MUST be public).
# "imgur"  = anonymous upload to Imgur (works with a private repo too).
IMAGE_HOST_MODE = os.environ.get("IMAGE_HOST_MODE", "github")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "")  # auto-set by GitHub Actions, "user/repo"
GITHUB_BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID", "")

# ---------------------------------------------------------------------------
# INSTAGRAM — UNOFFICIAL / instagrapi path (alternative, see README for risks)
# ---------------------------------------------------------------------------
IG_USERNAME = os.environ.get("IG_USERNAME", "")
IG_PASSWORD = os.environ.get("IG_PASSWORD", "")
IG_SESSION_FILE = "ig_session.json"

CAPTION_HASHTAGS = (
    "#technews #tech #technology #ai #startup #gadgets #innovation "
    "#dailytech #techupdates"
)
