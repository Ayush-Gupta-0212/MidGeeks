"""
fetch_news.py
Pulls recent stories from free, key-less RSS feeds, drops anything we've
already posted, and picks the freshest N stories for today's carousel.

Deliberately NOT using NewsAPI.org / GNews free tiers here: both explicitly
restrict their free tier to local development and forbid the kind of
scheduled, always-on use this bot needs (see README "Content sources" section
for sources). RSS has no such restriction — it's the public feed the
publisher already broadcasts to every reader.
"""

import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser

import config

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(text):
    """RSS summaries sometimes carry raw HTML (hnrss.org wraps its summary
    in <p>/<a> tags; Ars Technica uses inline <em> etc.). Strip tags and
    unescape entities so slides show plain text, not markup."""
    if not text:
        return ""
    no_tags = _TAG_RE.sub(" ", text)
    return html.unescape(" ".join(no_tags.split()))


def _entry_timestamp(entry):
    """Best-effort published time as a UTC epoch, falling back to 'now'."""
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return time.mktime(value)
    return time.time()


def _passes_keyword_filter(entry, allowlist):
    if not allowlist:
        return True
    haystack = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    return any(word.lower() in haystack for word in allowlist)


def _passes_blocklist(candidate_text, blocklist):
    if not blocklist:
        return True
    haystack = candidate_text.lower()
    return not any(word.lower() in haystack for word in blocklist)


def load_history():
    if not os.path.exists(config.HISTORY_FILE):
        return {}
    try:
        with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_history(history):
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.HISTORY_MAX_AGE_DAYS)
    pruned = {
        url: posted_at
        for url, posted_at in history.items()
        if datetime.fromisoformat(posted_at) > cutoff
    }
    with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(pruned, f, indent=2)


def fetch_candidates():
    """Return every not-yet-posted entry across all feeds, newest first."""
    history = load_history()
    candidates = []

    for feed in config.RSS_FEEDS:
        parsed = feedparser.parse(feed["url"])
        if parsed.bozo and not parsed.entries:
            print(f"  [warn] couldn't read {feed['name']} ({feed['url']}): {parsed.bozo_exception}")
            continue

        for entry in parsed.entries:
            link = entry.get("link", "").strip()
            if not link or link in history:
                continue
            if not _passes_keyword_filter(entry, config.KEYWORD_ALLOWLIST):
                continue

            title = (entry.get("title") or "").strip()
            summary = _clean_html(entry.get("summary"))
            if not _passes_blocklist(f"{title} {summary} {link}", config.KEYWORD_BLOCKLIST):
                continue

            candidates.append(
                {
                    "source": feed["name"],
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "timestamp": _entry_timestamp(entry),
                }
            )

    candidates.sort(key=lambda c: c["timestamp"], reverse=True)
    return candidates


def pick_todays_stories(count=None):
    count = count or config.STORY_SLIDE_COUNT
    candidates = fetch_candidates()

    # De-dupe near-identical headlines across outlets covering the same story
    seen_titles = set()
    picked = []
    for c in candidates:
        key = c["title"].lower()[:60]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        picked.append(c)
        if len(picked) == count:
            break

    if not picked:
        return picked

    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()
    for story in picked:
        history[story["link"]] = now_iso
    save_history(history)

    return picked


if __name__ == "__main__":
    stories = pick_todays_stories()
    print(f"Selected {len(stories)} stories:\n")
    for i, s in enumerate(stories, 1):
        print(f"{i}. [{s['source']}] {s['title']}")
        print(f"   {s['link']}\n")

    with open("todays_stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, indent=2)
