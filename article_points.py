"""
article_points.py
For single-story mode: take ONE story, fetch the REAL article text from its
URL, and ask Gemini to distill that text into a handful of genuine key points.

The whole point of this module is honesty: the slides make specific claims
about a news story, so those claims must come from the actual article, not
from the model's imagination. Every safeguard here exists to avoid putting
fabricated statements under a real outlet's name:

  - We fetch and extract the real article body first.
  - We hand that text to Gemini and instruct it to summarize ONLY what the
    text says, and to return fewer points rather than invent any.
  - If the article can't be fetched or is too short to summarize, we DO NOT
    fall back to making things up — we return an empty list and the caller
    skips the single-story post for that story.
"""

import json
import re

import requests

import config

_TAG_RE = re.compile(r"<[^>]+>")


def fetch_article_text(url, max_chars=8000):
    """Download the article page and pull out its readable body text.
    Best-effort and dependency-light: strips scripts/styles/tags. Returns
    plain text (truncated) or '' on failure."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TechNewsBot/1.0)"},
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  [warn] couldn't fetch article {url}: {e}")
        return ""

    html = resp.text

    # Drop script/style/noscript blocks entirely before stripping tags.
    html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html,
                  flags=re.DOTALL | re.IGNORECASE)

    # Prefer the <article> region if present — it's usually the story body.
    article_match = re.search(r"<article[^>]*>(.*?)</article>", html,
                              flags=re.DOTALL | re.IGNORECASE)
    body = article_match.group(1) if article_match else html

    # Collect paragraph text specifically — filters out most nav/boilerplate.
    paras = re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.DOTALL | re.IGNORECASE)
    if paras:
        text = " ".join(_TAG_RE.sub(" ", p) for p in paras)
    else:
        text = _TAG_RE.sub(" ", body)

    # Unescape a few common entities and collapse whitespace.
    for a, b in [("&amp;", "&"), ("&#39;", "'"), ("&rsquo;", "'"),
                 ("&ldquo;", '"'), ("&rdquo;", '"'), ("&quot;", '"'),
                 ("&nbsp;", " "), ("&mdash;", "—"), ("&ndash;", "–")]:
        text = text.replace(a, b)
    text = " ".join(text.split())
    return text[:max_chars]


def _gemini_summarize(title, source, article_text, max_points):
    """Ask Gemini's text model to distil real article text into key points.
    Returns a list of {'heading', 'detail'} dicts, or [] on any failure."""
    if not config.GEMINI_API_KEY:
        print("  [warn] GEMINI_API_KEY not set — cannot summarize article")
        return []

    prompt = (
        "You are helping build an Instagram carousel about ONE news story. "
        "Below is the real text of the article. Extract up to "
        f"{max_points} key points a reader would care about.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY facts stated in the article text below. Do NOT add outside "
        "knowledge, speculation, or invented figures.\n"
        "- If the article only supports fewer points, return fewer. Never pad.\n"
        "- Each point: a short punchy heading (max 6 words) and a one-sentence "
        "detail (max 24 words), both drawn strictly from the text.\n"
        "- Return ONLY valid JSON: a list of objects with keys 'heading' and "
        "'detail'. No markdown, no commentary.\n\n"
        f"ARTICLE TITLE: {title}\n"
        f"SOURCE: {source}\n\n"
        f"ARTICLE TEXT:\n{article_text}"
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_TEXT_MODEL}:generateContent"
    )
    try:
        resp = requests.post(
            url,
            headers={
                "x-goog-api-key": config.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"  [warn] Gemini summarization failed: {e}")
        return []

    # Model sometimes wraps JSON in ```json fences — strip them.
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        points = json.loads(text)
    except json.JSONDecodeError:
        print(f"  [warn] couldn't parse Gemini JSON: {text[:200]}")
        return []

    cleaned = []
    for p in points:
        if isinstance(p, dict) and p.get("heading") and p.get("detail"):
            cleaned.append({
                "heading": str(p["heading"]).strip(),
                "detail": str(p["detail"]).strip(),
            })
    return cleaned[:max_points]


def build_points(story, max_points=None):
    """Top-level: given a story dict, return (points, article_text).
    points is a list of {'heading','detail'} — empty if we couldn't get
    real content (caller should then skip single-story mode for this story)."""
    max_points = max_points or config.MAX_POINT_SLIDES

    article_text = fetch_article_text(story["link"])
    # Require a meaningful amount of real text before summarizing.
    if len(article_text) < 400:
        print(f"  [warn] article too short to summarize ({len(article_text)} chars); "
              "skipping single-story mode for this story")
        return [], article_text

    points = _gemini_summarize(
        story.get("title", ""), story.get("source", ""), article_text, max_points
    )
    return points, article_text


if __name__ == "__main__":
    import sys
    sample = {
        "title": "Sample headline about an AI chip",
        "source": "TechCrunch",
        "link": sys.argv[1] if len(sys.argv) > 1 else "https://example.com",
    }
    pts, text = build_points(sample)
    print(f"Fetched {len(text)} chars of article text")
    print(json.dumps(pts, indent=2))
