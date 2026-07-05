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

# Used to pick a Pexels search term for each slide's background photo (see
# generate_slides.py). Order matters — first matching concept wins. Keep this
# in sync with what you actually cover; add rows as your beat expands.
IMAGE_CONCEPT_MAP = [
    (["ai", "artificial intelligence", "machine learning", "llm", "chatbot",
      "generative", "neural network", "openai", "anthropic", "claude",
      "gemini", "chatgpt", "copilot"], "artificial intelligence technology"),
    (["chip", "semiconductor", "processor", "gpu", "cpu"], "computer chip technology"),
    (["cybersecurity", "hack", "breach", "vulnerability", "malware", "encryption"],
     "cybersecurity technology"),
    (["cloud", "data center", "server", "database"], "data center server room"),
    (["startup", "funding", "venture capital", "ipo", "acquisition"],
     "startup office team"),
    (["app", "smartphone", "phone"], "smartphone technology"),
    (["code", "coding", "programming", "developer", "software", "github",
      "open source"], "programmer coding screen"),
]
DEFAULT_IMAGE_QUERY = "technology abstract"

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
# VISUAL DESIGN — each slide's background is a real photo (via Pexels, see
# below), related to that slide's story. A dark scrim sits between the photo
# and the text so it stays readable regardless of what's in the photo.
# Palette: white text, one orange accent, black scrim — no other colors.
# ---------------------------------------------------------------------------
CANVAS_SIZE = (1080, 1350)  # 4:5 — the tallest ratio Instagram allows in-feed

COLORS = {
    "bg": "#000000",       # fallback fill if a photo can't be fetched
    "text": "#FFFFFF",     # white — primary text, on top of the scrim
    "muted": "#D8D8D8",    # light grey — secondary text (deks, credits)
    "accent": "#FF7A1A",   # orange — the one accent color, used sparingly
    "scrim": (0, 0, 0),    # black — alpha varies by position, see _apply_scrim
}

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
FONTS = {
    "headline": os.path.join(FONT_DIR, "Poppins-Bold.ttf"),
    "body": os.path.join(FONT_DIR, "Poppins-Medium.ttf"),
    "mono": os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf"),
}

OUTPUT_DIR = "output"

# ---------------------------------------------------------------------------
# BACKGROUND PHOTOS — Pexels (free, instant API key, no article-photo
# copyright concerns since Pexels' library is licensed for exactly this).
# Get a key at https://www.pexels.com/api/ (sign up, key appears instantly).
# ---------------------------------------------------------------------------
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

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
