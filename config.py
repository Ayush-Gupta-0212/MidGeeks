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

# Relevance filter: a story must match at least one of these to be considered
# at all. Scoped tightly to AI tools, software, CS, and core tech-industry
# topics — not general technology. Hardware/robotics are excluded here unless
# they're part of a broader AI or chip story.
KEYWORD_ALLOWLIST = [
    # AI tools and models — the primary focus
    "AI", "artificial intelligence", "machine learning", "LLM", "chatbot",
    "generative AI", "neural network", "OpenAI", "Anthropic", "Claude",
    "Gemini", "ChatGPT", "Copilot", "GPT", "agent", "AI model", "AI tool",
    "large language model", "diffusion model", "AI assistant", "AI startup",
    "AI company", "foundation model",
    # software / computer science
    "software", "app", "programming", "developer", "code", "coding", "API",
    "open source", "GitHub", "framework", "algorithm", "computer science",
    "cybersecurity", "hack", "breach", "vulnerability", "malware", "encryption",
    "leak", "privacy", "exploit", "phishing", "ransomware", "zero-day",
    # cloud and infra
    "cloud", "data center", "server", "database", "SaaS", "platform",
    # core chip/semiconductor only when tied to AI workloads
    "AI chip", "GPU", "Nvidia", "TPU",
    # tech industry news
    "startup", "funding", "venture capital", "IPO", "acquisition", "layoff",
    "big tech", "tech company",
    # the specific companies whose stories are almost always relevant
    "Google", "Microsoft", "Apple", "Meta", "Amazon", "Nvidia", "OpenAI",
    "Anthropic", "Mistral", "xAI", "Perplexity", "Cohere",
]

# Stories matching these HIGH-PRIORITY terms get ranked above all others —
# even if a lower-priority story is newer. This is how we ensure AI tools
# and software stories beat hardware/robotics ones when both are available.
KEYWORD_PRIORITY = [
    "AI tool", "AI model", "AI assistant", "ChatGPT", "Claude", "Gemini",
    "GPT", "LLM", "large language model", "generative AI", "OpenAI",
    "Anthropic", "Mistral", "Perplexity", "Cohere", "xAI",
    "machine learning", "foundation model", "AI agent", "AI startup",
    "software", "developer", "programming", "open source", "cybersecurity",
    "hack", "breach", "vulnerability",
]

# ---------------------------------------------------------------------------
# GOOGLE GEMINI — now used ONLY for summarizing real article text into key
# points (the text model). Image generation moved to Pexels below, because
# Google grants zero free image quota. One free key still needed for text.
# Set as a GitHub Actions secret named GEMINI_API_KEY.
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_MODEL = "gemini-2.5-flash"          # summarize article -> key points

# ---------------------------------------------------------------------------
# PEXELS — background photos (free, ~200 requests/hour; a post uses ~6).
# Each slide's photo is chosen to match that slide's content, and no two
# slides in a post repeat a photo. Get a free key at
# https://www.pexels.com/api/ and set it as a secret named PEXELS_API_KEY.
# ---------------------------------------------------------------------------
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

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

# Base hashtags added to EVERY post (broad reach). Topic-specific tags that
# match each story are added on top automatically (see pexels_image
# .hashtags_for_context), so you don't need many here.
CAPTION_BASE_HASHTAGS = ["#technews", "#tech", "#technology", "#dailytech"]

# A short call-to-action line near the end of every caption.
CAPTION_CTA = "Follow @midgeeks.studio for more tech stories 👀"
