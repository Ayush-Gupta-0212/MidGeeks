"""
gemini_image.py
Generates a background image for a slide using Gemini's image model
(Nano Banana / gemini-3.1-flash-image) via the REST API.

Key design decisions:
  - We ask for NO text in the image. Our headline/points are drawn on top as
    real, crisp text — letting the model bake in text would collide with ours
    and AI text is often garbled anyway.
  - We ask for a dark, moody, high-contrast composition with room at the
    bottom, because the design puts white/orange text over a bottom-heavy
    dark tint.
  - Any failure (missing key, quota, network) returns None, and the caller
    falls back to a solid dark background. A missing image must never break
    the run.
"""

import base64
import time
from io import BytesIO

import requests
from PIL import Image

import config

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Free-tier image generation is capped at roughly 10 images/minute. We space
# requests out and retry on 429 (rate limit) with growing backoff so a normal
# 6-slide post stays comfortably under the limit instead of firing all at once.
_MIN_SECONDS_BETWEEN_CALLS = 7
_last_call_time = [0.0]


def _throttle():
    """Ensure at least _MIN_SECONDS_BETWEEN_CALLS since the previous call."""
    elapsed = time.time() - _last_call_time[0]
    if elapsed < _MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(_MIN_SECONDS_BETWEEN_CALLS - elapsed)
    _last_call_time[0] = time.time()


def _build_prompt(concept):
    return (
        "Generate a moody, cinematic, high-quality background image for a tech "
        "news social media post. "
        f"Theme/subject: {concept}. "
        "Style: dark and atmospheric, deep shadows, subtle orange rim lighting "
        "and accents, modern and premium, slightly abstract. "
        "The lower third must be dark and relatively empty so white text can be "
        "overlaid. Absolutely NO text, letters, words, numbers, logos, or "
        "watermarks anywhere in the image. Portrait orientation, 4:5."
    )


def generate_background(concept):
    """Returns a PIL Image (RGB) or None on any failure."""
    if not config.GEMINI_API_KEY:
        print("  [warn] GEMINI_API_KEY not set — using solid background")
        return None

    url = _ENDPOINT.format(model=config.GEMINI_IMAGE_MODEL)
    payload = {
        "contents": [{"parts": [{"text": _build_prompt(concept)}]}],
        "generationConfig": {
            # Must include TEXT — requesting IMAGE alone makes the whole
            # response fail rather than returning image-only output.
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "4:5"},
        },
    }

    max_attempts = 4
    data = None
    for attempt in range(max_attempts):
        _throttle()
        try:
            resp = requests.post(
                url,
                headers={
                    "x-goog-api-key": config.GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=90,
            )
            if resp.status_code == 429:
                # Rate limited: wait longer each time before retrying.
                wait = 20 * (attempt + 1)
                print(f"  [warn] rate limited (429) on '{concept}', "
                      f"waiting {wait}s then retrying ({attempt + 1}/{max_attempts})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            print(f"  [warn] Gemini image request failed for '{concept}': {e}")
            return None

    if data is None:
        print(f"  [warn] still rate limited after {max_attempts} attempts for '{concept}'; "
              "falling back to solid background")
        return None

    # Walk the response parts for inline image data.
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        print(f"  [warn] unexpected Gemini image response shape for '{concept}'")
        return None

    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            try:
                raw = base64.b64decode(inline["data"])
                return Image.open(BytesIO(raw)).convert("RGB")
            except Exception as e:
                print(f"  [warn] couldn't decode Gemini image: {e}")
                return None

    print(f"  [warn] no image in Gemini response for '{concept}'")
    return None


if __name__ == "__main__":
    img = generate_background("artificial intelligence and neural networks")
    if img:
        img.save("test_gemini_bg.png")
        print("saved test_gemini_bg.png", img.size)
    else:
        print("no image returned (check GEMINI_API_KEY / quota)")
