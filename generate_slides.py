"""
generate_slides.py
Turns a list of stories into a set of 1080x1350 JPEG carousel slides:
  01_cover.jpg -> one slide per story -> NN_outro.jpg

Design: each slide's background is a real photo, thematically matched to
that slide's story via Pexels (see config.IMAGE_CONCEPT_MAP). A dark scrim
sits between the photo and the text so it stays legible regardless of what's
in the photo. Palette is deliberately just three colors: white text, one
orange accent, black scrim/stroke — nothing else.

Instagram's Graph API only accepts JPEG (no PNG), and crops every slide in
a carousel to match slide 1's aspect ratio — so every slide here is
rendered at the exact same CANVAS_SIZE.
"""

import os
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

import config

W, H = config.CANVAS_SIZE
MARGIN = 84

# Randomized once per run so the same concept ("AI") doesn't always return
# the same top photo day after day. Combined with a per-slide variant index,
# this gives every slide a distinct background.
_RUN_PHOTO_OFFSET = random.randint(0, 12)

# Tracks how many times each concept-query has been used so far this run, so
# the Nth slide sharing a concept asks for the Nth photo, not the same one.
_query_use_count = defaultdict(int)


def _font(name, size):
    return ImageFont.truetype(config.FONTS[name], size)


def _text_width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap_to_width(draw, text, font, max_width):
    """Greedy word-wrap using actual glyph widths (not character counts)."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _autosize_headline(draw, text, max_width, max_lines, start_size, min_size):
    """Shrinks the headline font until it wraps within max_lines at max_width."""
    size = start_size
    while size >= min_size:
        font = _font("headline", size)
        lines = _wrap_to_width(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 4
    font = _font("headline", min_size)
    lines = _wrap_to_width(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "…"
    return font, lines


# ---------------------------------------------------------------------------
# Background photo: pick a concept -> search Pexels -> download -> cover-fit
# ---------------------------------------------------------------------------

def _pick_image_query(story):
    haystack = f"{story.get('title', '')} {story.get('summary', '')}".lower()
    for keywords, query in config.IMAGE_CONCEPT_MAP:
        if any(k in haystack for k in keywords):
            return query
    return config.DEFAULT_IMAGE_QUERY


def _fetch_pexels_photo(query, variant=0):
    """Returns (image_url, photographer_credit) or (None, None) on any failure.
    `variant` picks a different photo from the result set so two slides that
    resolve to the same concept don't get the identical image. A per-run
    random offset also means the same concept looks different across days."""
    if not config.PEXELS_API_KEY:
        print("  [warn] PEXELS_API_KEY not set, using solid-color background")
        return None, None
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": "portrait", "size": "large", "per_page": 30},
            timeout=15,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"  [warn] no Pexels results for '{query}'")
            return None, None
        idx = (variant + _RUN_PHOTO_OFFSET) % len(photos)
        photo = photos[idx]
        url = photo["src"].get("large2x") or photo["src"].get("original")
        return url, photo.get("photographer", "")
    except Exception as e:
        print(f"  [warn] Pexels search failed for '{query}': {e}")
        return None, None


def _cover_fit(img, target_w, target_h):
    """Resize + center-crop so img fully covers target_w x target_h,
    like CSS object-fit: cover. Never distorts aspect ratio."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_h = target_h
        new_w = max(target_w, int(round(new_h * src_ratio)))
    else:
        new_w = target_w
        new_h = max(target_h, int(round(new_w / src_ratio)))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _background_image(query):
    """Returns (PIL Image sized exactly WxH, photographer_credit_or_None).
    Uses a per-concept counter so repeated concepts get different photos.
    Falls back to a solid color on any failure — a missing/failed photo
    should never break the pipeline."""
    variant = _query_use_count[query]
    _query_use_count[query] += 1
    url, credit = _fetch_pexels_photo(query, variant=variant)
    if not url:
        return Image.new("RGB", (W, H), config.COLORS["bg"]), None
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        photo = Image.open(BytesIO(resp.content)).convert("RGB")
        return _cover_fit(photo, W, H), credit
    except Exception as e:
        print(f"  [warn] couldn't download background photo: {e}")
        return Image.new("RGB", (W, H), config.COLORS["bg"]), None


def _apply_scrim(img):
    """Techy, sharp scrim built from three parts, composited over the photo:
      1. a left-to-right gradient (dark on the left where text lives, clear
         on the right so the photo still shows),
      2. a solid darker band anchored along the very bottom (footer zone),
      3. a lighter top band (eyebrow zone).
    This keeps left-aligned white/orange text crisp while letting the right
    side of every photo breathe — a more designed look than a flat overlay."""
    img = img.convert("RGBA")

    # 1. horizontal gradient: strong on the left, fading right
    h_grad = Image.new("L", (W, 1))
    for x in range(W):
        frac = x / W
        if frac < 0.62:
            alpha = 205 - int((frac / 0.62) * 70)   # 205 -> 135
        else:
            alpha = 135 - int(((frac - 0.62) / 0.38) * 95)  # 135 -> 40
        h_grad.putpixel((x, 0), max(0, alpha))
    h_grad = h_grad.resize((W, H))

    # 2 + 3. vertical emphasis: darker top & bottom anchor bands
    v_grad = Image.new("L", (1, H))
    for y in range(H):
        frac = y / H
        if frac < 0.16:
            a = 70 - int((frac / 0.16) * 70)         # 70 -> 0
        elif frac > 0.80:
            a = int(((frac - 0.80) / 0.20) * 90)     # 0 -> 90
        else:
            a = 0
        v_grad.putpixel((0, y), a)
    v_grad = v_grad.resize((W, H))

    from PIL import ImageChops
    combined = ImageChops.add(h_grad, v_grad)

    scrim = Image.new("RGBA", (W, H), config.COLORS["scrim"] + (0,))
    scrim.putalpha(combined)
    return Image.alpha_composite(img, scrim).convert("RGB")


def _new_canvas(query):
    bg, credit = _background_image(query)
    bg = _apply_scrim(bg)
    return bg, ImageDraw.Draw(bg), credit


# ---------------------------------------------------------------------------
# Drawing helpers — every piece of text gets a thin black stroke, on top of
# the scrim, as a second layer of legibility insurance over busy photos.
# ---------------------------------------------------------------------------

def _draw_text(draw, xy, text, font, fill, stroke_width=3):
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill="black")


def _draw_accent_bar(draw, x, y_top, y_bottom, width=8):
    """A solid orange vertical bar — the signature 'sharp' accent that sits
    just left of the headline block."""
    draw.rectangle([x, y_top, x + width, y_bottom], fill=config.COLORS["accent"])


def _draw_hairline(draw, y, x0=MARGIN, x1=W - MARGIN, color=None):
    draw.line([(x0, y), (x1, y)], fill=color or config.COLORS["accent"], width=2)


def _draw_header(draw, label):
    """Top-left eyebrow with a short orange tick before it and a hairline
    rule under it — clean, technical, consistent across every slide."""
    tick_y = 156
    draw.rectangle([MARGIN, tick_y, MARGIN + 34, tick_y + 6], fill=config.COLORS["accent"])
    mono = _font("mono", 27)
    _draw_text(draw, (MARGIN + 48, tick_y - 12), label, mono, config.COLORS["text"], stroke_width=2)


def _draw_footer(draw, index, total, handle):
    """Hairline rule, then index on the left and handle on the right below it."""
    rule_y = H - 118
    _draw_hairline(draw, rule_y, color=(255, 255, 255))
    mono = _font("mono", 24)
    tag = f"{index:02d} / {total:02d}"
    _draw_text(draw, (MARGIN, rule_y + 22), tag, mono, config.COLORS["accent"], stroke_width=2)
    hw = _text_width(draw, handle, mono)
    _draw_text(draw, (W - MARGIN - hw, rule_y + 22), handle, mono, config.COLORS["text"], stroke_width=2)


def _draw_content_block(draw, blocks, region_top, region_bottom):
    """Vertically centers a list of (lines, font, color, line_height, gap_after,
    stroke_width) blocks inside [region_top, region_bottom]."""
    total_h = 0
    for lines, _font_, _color, line_h, gap_after, _stroke in blocks:
        total_h += len(lines) * line_h + gap_after
    y = region_top + max(0, (region_bottom - region_top - total_h) // 2)
    for lines, font, color, line_h, gap_after, stroke in blocks:
        for line in lines:
            _draw_text(draw, (MARGIN, y), line, font, color, stroke_width=stroke)
            y += line_h
        y += gap_after


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Slide renderers — new "techy & sharp" layout:
#   header (tick + eyebrow)  ...  photo ...  orange accent bar + big headline
#   anchored toward the lower third, footer hairline + index/handle.
# ---------------------------------------------------------------------------

def _draw_headline_block(draw, lines, headline_font, bottom_y, tag=None):
    """Draws the headline bottom-anchored (last line sits at bottom_y),
    with an orange accent bar running the full height of the block on the
    left, and an optional small orange topic tag above it."""
    line_h = int(headline_font.size * 1.16)
    block_h = len(lines) * line_h
    top_y = bottom_y - block_h

    tag_h = 0
    if tag:
        tag_font = _font("mono", 26)
        tag_h = 48
        _draw_text(draw, (MARGIN + 26, top_y - tag_h), tag.upper(), tag_font,
                   config.COLORS["accent"], stroke_width=2)

    _draw_accent_bar(draw, MARGIN, top_y - (tag_h if tag else 0) + (6 if tag else 0), bottom_y, width=8)

    y = top_y
    for line in lines:
        _draw_text(draw, (MARGIN + 26, y), line, headline_font, config.COLORS["text"], stroke_width=4)
        y += line_h


def _topic_tag(query):
    """Turn the Pexels concept query into a short human tag for the slide."""
    mapping = {
        "artificial intelligence technology": "AI",
        "computer chip technology": "HARDWARE",
        "cybersecurity technology": "SECURITY",
        "data center server room": "INFRASTRUCTURE",
        "startup office team": "STARTUPS",
        "smartphone technology": "MOBILE",
        "programmer coding screen": "SOFTWARE",
        "technology abstract": "TECH",
    }
    return mapping.get(query, "TECH")


def render_cover(story_count, date_str, handle, query):
    img, draw, credit = _new_canvas(query)
    _draw_header(draw, "TECH SIGNAL")

    noun = "headline" if story_count == 1 else "headlines"
    headline_font, lines = _autosize_headline(
        draw, f"{story_count} {noun} you missed today", W - 2 * MARGIN - 26, 4, 100, 62
    )
    _draw_headline_block(draw, lines, headline_font, bottom_y=H - 320, tag=None)

    sub_font = _font("body", 34)
    _draw_text(draw, (MARGIN + 26, H - 300), date_str, sub_font, config.COLORS["muted"], stroke_width=3)

    swipe_font = _font("mono", 28)
    _draw_text(draw, (MARGIN + 26, H - 200), "SWIPE →", swipe_font, config.COLORS["accent"], stroke_width=2)

    _draw_footer(draw, 1, story_count + 2, handle)
    return img, credit


def render_story(story, index, total, handle):
    query = _pick_image_query(story)
    img, draw, credit = _new_canvas(query)
    _draw_header(draw, f"SOURCE: {story['source'].upper()}")

    headline_font, lines = _autosize_headline(
        draw, story["title"], W - 2 * MARGIN - 26, 6, 74, 46
    )
    _draw_headline_block(draw, lines, headline_font, bottom_y=H - 190, tag=_topic_tag(query))

    _draw_footer(draw, index, total, handle)
    return img, credit


def render_outro(sources, handle, total, photo_credits):
    img, draw, credit = _new_canvas(config.DEFAULT_IMAGE_QUERY)
    if credit:
        photo_credits.append(credit)
    _draw_header(draw, "END OF SIGNAL")

    headline_font, lines = _autosize_headline(
        draw, "Follow for tomorrow's headlines", W - 2 * MARGIN - 26, 4, 84, 52
    )
    _draw_headline_block(draw, lines, headline_font, bottom_y=H - 330, tag=None)

    body_font = _font("body", 26)
    y = H - 300
    credit_line = "Sources: " + ", ".join(sorted(set(sources)))
    for line in _wrap_to_width(draw, credit_line, body_font, W - 2 * MARGIN - 26):
        _draw_text(draw, (MARGIN + 26, y), line, body_font, config.COLORS["muted"], stroke_width=3)
        y += int(body_font.size * 1.4)
    if photo_credits:
        names = ", ".join(sorted(set(photo_credits)))
        y += 6
        for line in _wrap_to_width(draw, f"Photos: {names} via Pexels", body_font, W - 2 * MARGIN - 26):
            _draw_text(draw, (MARGIN + 26, y), line, body_font, config.COLORS["muted"], stroke_width=3)
            y += int(body_font.size * 1.4)

    _draw_footer(draw, total, total, handle)
    return img


def generate(stories, handle=None, out_dir=None):
    handle = handle or config.IG_HANDLE
    out_dir = out_dir or config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.lower().endswith(".jpg"):
            os.remove(os.path.join(out_dir, f))

    total = len(stories) + 2
    display_time = datetime.now(timezone.utc) + timedelta(hours=config.DISPLAY_TIMEZONE_OFFSET_HOURS)
    date_str = display_time.strftime("%B %-d, %Y") if os.name != "nt" else display_time.strftime("%B %d, %Y")
    paths = []
    photo_credits = []

    cover_query = _pick_image_query(stories[0]) if stories else config.DEFAULT_IMAGE_QUERY
    cover, credit = render_cover(len(stories), date_str, handle, cover_query)
    if credit:
        photo_credits.append(credit)
    p = os.path.join(out_dir, "01_cover.jpg")
    cover.save(p, "JPEG", quality=92)
    paths.append(p)

    for i, story in enumerate(stories, start=2):
        img, credit = render_story(story, i, total, handle)
        if credit:
            photo_credits.append(credit)
        p = os.path.join(out_dir, f"{i:02d}_story.jpg")
        img.save(p, "JPEG", quality=92)
        paths.append(p)

    outro = render_outro([s["source"] for s in stories], handle, total, photo_credits)
    p = os.path.join(out_dir, f"{total:02d}_outro.jpg")
    outro.save(p, "JPEG", quality=92)
    paths.append(p)

    return paths


if __name__ == "__main__":
    import json

    if os.path.exists("todays_stories.json"):
        with open("todays_stories.json", "r", encoding="utf-8") as f:
            stories = json.load(f)
    else:
        stories = [
            {
                "source": "TechCrunch",
                "title": "Startup raises $40M to build AI agents that actually finish tasks",
                "summary": "The round values the company at $300M as enterprise demand for autonomous agents accelerates.",
                "link": "https://example.com/1",
            },
            {
                "source": "The Verge",
                "title": "The next generation of foldable phones ditches the crease for good",
                "summary": "New hinge designs from three manufacturers promise a flat, seamless display.",
                "link": "https://example.com/2",
            },
            {
                "source": "Ars Technica",
                "title": "Researchers find a way to cut chip power use by 40 percent",
                "summary": "The technique works with existing manufacturing processes, no new fabs required.",
                "link": "https://example.com/3",
            },
        ]

    output_paths = generate(stories)
    print("Generated:")
    for p in output_paths:
        print(" ", p)
