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

# ---------------------------------------------------------------------------
# POST FORMAT
# "single" = one post covers ONE story in depth: a cover + several point
#            slides (each a real key point pulled from the actual article)
#            + an outro. This is the current mode.
# "digest" = the older format (one slide per story across several stories).
# ---------------------------------------------------------------------------
POST_MODE = "single"

# For single-story mode: how many "key point" slides to build between the
# cover and the outro. Real points are extracted from the article text; if
# the article yields fewer than this, we build fewer (never invent filler).
MAX_POINT_SLIDES = 4

# For digest mode only (kept for backwards compatibility):
STORY_SLIDE_COUNT = 5

# Relevance filter: a story must match at least one of these in title+summary
# to be considered. Narrowed to AI / computer science / tech-industry topics
# specifically — this is what keeps things like space-agency news, movie
# reviews, or general science out, even though they show up in "tech" feeds.
# Case-insensitive substring match. Tune freely — this list is a starting
# point, not exhaustive.
KEYWORD_ALLOWLIST = [
    # AI / ML
    "AI", "artificial intelligence", "machine learning", "LLM", "chatbot",
    "generative", "neural network", "OpenAI", "Anthropic", "Claude", "Gemini",
    "ChatGPT", "Copilot", "agent",
    # software / CS
    "software", "app", "programming", "developer", "code", "coding", "API",
    "open source", "GitHub", "framework", "algorithm", "computer science",
    "cybersecurity", "hack", "breach", "vulnerability", "malware", "encryption",
    "leak", "privacy", "exploit", "phishing", "ransomware", "zero-day",
    # hardware / infra that's squarely tech-industry
    "chip", "semiconductor", "processor", "GPU", "CPU", "cloud", "data center",
    "server", "database",
    # tech industry / business
    "startup", "funding", "venture capital", "IPO", "acquisition", "big tech",
    "silicon valley", "tech industry",
    # the companies that anchor most real tech-industry stories
    "Google", "Microsoft", "Apple", "Meta", "Amazon", "Nvidia", "Tesla",
    "SpaceX", "Alibaba", "Samsung",
]

# ---------------------------------------------------------------------------
# GOOGLE GEMINI — used for two things:
#   1. summarizing the REAL article text into genuine key points (text model)
#   2. generating a background image per slide (image model)
# One free API key from https://aistudio.google.com/apikey covers both.
# Set as a GitHub Actions secret named GEMINI_API_KEY.
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_MODEL = "gemini-2.5-flash"          # summarize article -> key points
# Use the 2.5 image model: it's the one with a documented FREE API tier
# (~500 requests/day). The newer 3.x "-preview" image models often have no
# free API quota at all, which returns 429 on the very first call.
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

# If image generation fails or the key is missing, fall back to a solid
# dark background instead of breaking the run.
IMAGE_FALLBACK_ENABLED = True

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
DISPLAY_TIMEZONE_OFFSET_HOURS = 5.5

# File that remembers which article URLs we've already posted, so the bot
# never repeats a story. Committed back to the repo after every run.
HISTORY_FILE = "posted_history.json"
HISTORY_MAX_AGE_DAYS = 30  # prune entries older than this so the file doesn't grow forever

# ---------------------------------------------------------------------------
# VISUAL DESIGN — AI-generated background per slide, with a dark tint that
# gets DARKER toward the bottom so text stays readable. Theme: orange + white
# text only, over the tinted image. No other colors.
# ---------------------------------------------------------------------------
CANVAS_SIZE = (1080, 1350)  # 4:5 — the tallest ratio Instagram allows in-feed

COLORS = {
    "bg": "#0A0A0A",       # near-black fallback if an image can't be generated
    "text": "#FFFFFF",     # white — primary text
    "muted": "#EAEAEA",    # near-white — secondary text
    "accent": "#FF6B00",   # orange — headlines, tags, accents
    "scrim": (0, 0, 0),    # black tint, alpha varies (darker at bottom)
}

# Tint strength (0-255 alpha). Top of slide vs bottom of slide — the bottom
# is much darker so headline text at the lower third stays crisp.
SCRIM_ALPHA_TOP = 90
SCRIM_ALPHA_BOTTOM = 225

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
IG_HANDLE = "@midgeeks.studio"

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
