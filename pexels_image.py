"""
pexels_image.py
Background images for slides, sourced from Pexels (free, effectively
unlimited: 200 requests/hour, and a post uses ~6).

This replaces the Gemini image path because Google grants ZERO free image
quota. Two guarantees, matching the brief:

  1. CONTEXT-RELEVANT: the Pexels search query for each slide is derived from
     that slide's OWN text — the story headline for the cover, and the point's
     heading + detail for each point slide — so the photo relates to what that
     specific slide is about, not just the story in general.

  2. UNIQUE: a per-run set of used photo IDs means no two slides in the same
     carousel ever get the same image, even when two slides map to the same
     visual concept. A per-run random offset also varies the images day to day.

Any failure (missing key, no results, network) returns None, and the caller
falls back to a solid dark background — a missing photo never breaks the run.
"""

import random
from io import BytesIO

import requests
from PIL import Image

import config

# --- per-run state (reset at the start of each carousel via reset_run) ------
_used_photo_ids = set()
_used_credits = []
_run_offset = [0]

# Keyword -> Pexels query. First group whose keyword appears in the slide's
# text wins, so order from most specific/distinctive signals to most general.
# "Event" signals (layoffs, breaches) sit above broad subject signals so a
# story's specific angle wins over its general topic. Tune freely.
_CONCEPT_QUERIES = [
    (("layoff", "job cut", "fired", "studio closure", "restructur",
      "shut down", "downsiz"), "empty office workspace"),
    (("cybersecurity", "hack", "breach", "vulnerability", "malware",
      "encryption", "ransomware", "phishing", "data leak", "exploit",
      "privacy"), "cybersecurity digital lock"),
    (("artificial intelligence", " ai ", " ai-", " ai.", "a.i.",
      "machine learning", "llm", "chatbot", "neural", "openai", "anthropic",
      "gemini", "claude", "chatgpt", "copilot", "generative"),
     "artificial intelligence technology"),
    (("chip", "semiconductor", "processor", " gpu", " cpu", "nvidia",
      "silicon"), "computer chip circuit board"),
    (("game pass", "gaming", "video game", "console", "xbox", "playstation",
      "nintendo", "steam deck"), "video game controller"),
    (("smartphone", "iphone", "android", "foldable", "mobile app"),
     "smartphone mobile technology"),
    (("cloud", "data center", "datacenter", "server", "database"),
     "data center server room"),
    (("electric car", "self-driving", "autonomous vehicle", "tesla", " ev ",
      "robotaxi"), "electric car technology"),
    (("crypto", "bitcoin", "blockchain", "web3", "ethereum"),
     "cryptocurrency blockchain"),
    (("robot", "robotic", "automation", "drone"), "robotics technology"),
    (("social media", "instagram", "tiktok", "twitter", "facebook", "youtube"),
     "social media smartphone"),
    (("satellite", "rocket", "space", "spacex", "orbit"), "space technology"),
    (("code", "coding", "software", "programming", "developer", "github",
      "open source", "framework", " api"), "software code screen"),
    (("revenue", "billion", "million", "profit", "funding", "investment",
      "valuation", "earnings", "financial", "acquisition"),
     "finance business chart"),
]
_FALLBACK_QUERY = "technology abstract dark"

# Hashtags matched to the same concepts used for image selection, so the tags
# fit the story's actual topic. A small base set is always included by the
# caption builder; these are added on top when the topic matches.
_CONCEPT_HASHTAGS = {
    "empty office workspace": ["#layoffs", "#techlayoffs", "#futureofwork"],
    "cybersecurity digital lock": ["#cybersecurity", "#infosec", "#databreach", "#privacy"],
    "artificial intelligence technology": ["#ai", "#artificialintelligence", "#machinelearning", "#genai"],
    "computer chip circuit board": ["#semiconductors", "#chips", "#hardware"],
    "video game controller": ["#gaming", "#videogames", "#gamedev"],
    "smartphone mobile technology": ["#smartphone", "#mobile", "#gadgets"],
    "data center server room": ["#cloud", "#datacenter", "#infrastructure"],
    "electric car technology": ["#ev", "#electricvehicles", "#autonomous"],
    "cryptocurrency blockchain": ["#crypto", "#blockchain", "#web3"],
    "robotics technology": ["#robotics", "#automation", "#robots"],
    "social media smartphone": ["#socialmedia", "#creators", "#apps"],
    "space technology": ["#space", "#spacetech", "#satellites"],
    "software code screen": ["#software", "#coding", "#developers", "#opensource"],
    "finance business chart": ["#techfunding", "#startups", "#venturecapital"],
    "technology abstract dark": ["#innovation", "#future"],
}


def hashtags_for_context(text, limit=None):
    """Topic-matched hashtags for a slide/story, chosen from the same concept
    the image was picked from (so tags fit the actual subject)."""
    query = query_from_context(text)
    tags = _CONCEPT_HASHTAGS.get(query, _CONCEPT_HASHTAGS[_FALLBACK_QUERY])
    return tags[:limit] if limit else list(tags)


def reset_run():
    """Call once at the start of each carousel so uniqueness + credits are
    tracked per-post, and images vary from one day to the next."""
    _used_photo_ids.clear()
    _used_credits.clear()
    _run_offset[0] = random.randint(0, 15)


def query_from_context(text):
    """Choose a Pexels search query from a slide's own text."""
    hay = f" {text.lower()} "
    for keywords, query in _CONCEPT_QUERIES:
        if any(k in hay for k in keywords):
            return query
    return _FALLBACK_QUERY


def last_run_credits():
    """Unique photographer names used this run (for the outro credit line)."""
    return sorted({c for c in _used_credits if c})


def _search(query, per_page=40):
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": config.PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait",
                "size": "large", "per_page": per_page},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("photos", [])


def generate_background(context_text):
    """Return a PIL Image for this slide's background (relevant to
    context_text, and not already used this run), or None on failure."""
    if not config.PEXELS_API_KEY:
        print("  [warn] PEXELS_API_KEY not set — using solid background")
        return None

    query = query_from_context(context_text)
    try:
        photos = _search(query)
    except Exception as e:
        print(f"  [warn] Pexels search failed for '{query}': {e}")
        return None
    if not photos:
        print(f"  [warn] no Pexels results for '{query}'")
        return None

    # Rotate the starting index per run, then pick the first photo not already
    # used this carousel -> guarantees a unique image per slide.
    n = len(photos)
    chosen = None
    for i in range(n):
        candidate = photos[(i + _run_offset[0]) % n]
        if candidate["id"] not in _used_photo_ids:
            chosen = candidate
            break
    if chosen is None:                      # every result already used (rare)
        chosen = photos[_run_offset[0] % n]

    _used_photo_ids.add(chosen["id"])
    _used_credits.append(chosen.get("photographer", ""))
    print(f"  picked Pexels photo for '{query}' (id {chosen['id']})")

    src = chosen.get("src", {})
    url = src.get("large2x") or src.get("original") or src.get("large")
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"  [warn] couldn't download Pexels photo: {e}")
        return None


if __name__ == "__main__":
    reset_run()
    for t in ["Xbox is a disaster",
              "Microsoft spent over $20 billion but revenue declined",
              "Reports indicate impending layoffs and studio closures",
              "Game Pass subscriber growth plateaued"]:
        print(f"{t!r} -> query {query_from_context(t)!r}")
