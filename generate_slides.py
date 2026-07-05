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
from datetime import datetime, timedelta, timezone
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

import config

W, H = config.CANVAS_SIZE
MARGIN = 84


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


def _fetch_pexels_photo(query):
    """Returns (image_url, photographer_credit) or (None, None) on any failure —
    callers must handle None and fall back to a solid color, never crash."""
    if not config.PEXELS_API_KEY:
        print("  [warn] PEXELS_API_KEY not set, using solid-color background")
        return None, None
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "orientation": "portrait", "size": "large", "per_page": 5},
            timeout=15,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"  [warn] no Pexels results for '{query}'")
            return None, None
        photo = photos[0]
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
    Falls back to a solid color on any failure — a missing/failed photo
    should never break the pipeline."""
    url, credit = _fetch_pexels_photo(query)
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
    """Dark vertical-gradient overlay: heaviest at top (eyebrow) and bottom
    (footer/brackets), lighter through the middle third. Keeps white/orange
    text legible over literally any photo without hiding it completely."""
    img = img.convert("RGBA")
    gradient = Image.new("L", (1, H))
    for y in range(H):
        frac = y / H
        if frac < 0.30:
            alpha = 195 - int((frac / 0.30) * 55)        # 195 -> 140
        elif frac > 0.66:
            alpha = 140 + int(((frac - 0.66) / 0.34) * 60)  # 140 -> 200
        else:
            alpha = 140
        gradient.putpixel((0, y), alpha)
    gradient = gradient.resize((W, H))
    scrim = Image.new("RGBA", (W, H), config.COLORS["scrim"] + (0,))
    scrim.putalpha(gradient)
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


def _draw_corner_brackets(draw):
    c = config.COLORS["accent"]
    length, thickness, m = 46, 6, 52
    draw.line([(m, m), (m + length, m)], fill=c, width=thickness)
    draw.line([(m, m), (m, m + length)], fill=c, width=thickness)
    draw.line([(W - m, H - m), (W - m - length, H - m)], fill=c, width=thickness)
    draw.line([(W - m, H - m), (W - m, H - m - length)], fill=c, width=thickness)


def _draw_footer(draw, index, total, handle):
    mono = _font("mono", 24)
    tag = f"{index:02d} / {total:02d}"
    _draw_text(draw, (MARGIN, H - 100), tag, mono, config.COLORS["accent"], stroke_width=2)
    hw = _text_width(draw, handle, mono)
    _draw_text(draw, (W - MARGIN - hw, H - 100), handle, mono, config.COLORS["text"], stroke_width=2)


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

def render_cover(story_count, date_str, handle, query):
    img, draw, credit = _new_canvas(query)
    _draw_corner_brackets(draw)

    eyebrow_font = _font("mono", 30)
    _draw_text(draw, (MARGIN, 150), "// TECH SIGNAL", eyebrow_font, config.COLORS["accent"])

    noun = "headline" if story_count == 1 else "headlines"
    headline_font, lines = _autosize_headline(
        draw, f"{story_count} {noun} you missed today", W - 2 * MARGIN, 5, 96, 60
    )
    sub_font = _font("body", 34)

    _draw_content_block(
        draw,
        [
            (lines, headline_font, config.COLORS["text"], int(headline_font.size * 1.18), 26, 4),
            ([date_str], sub_font, config.COLORS["text"], int(sub_font.size * 1.3), 0, 3),
        ],
        region_top=290,
        region_bottom=H - 260,
    )

    swipe_font = _font("mono", 28)
    _draw_text(draw, (MARGIN, H - 180), "SWIPE →", swipe_font, config.COLORS["accent"])

    _draw_footer(draw, 1, story_count + 2, handle)
    return img, credit


def render_story(story, index, total, handle):
    query = _pick_image_query(story)
    img, draw, credit = _new_canvas(query)
    _draw_corner_brackets(draw)

    mono = _font("mono", 26)
    _draw_text(
        draw, (MARGIN, 130), f"SOURCE: {story['source'].upper()}", mono, config.COLORS["accent"], stroke_width=2
    )

    headline_font, lines = _autosize_headline(
        draw, story["title"], W - 2 * MARGIN, 6, 72, 44
    )

    blocks = [(lines, headline_font, config.COLORS["text"], int(headline_font.size * 1.2), 30, 4)]

    dek_font = _font("body", 30)
    summary = " ".join(story.get("summary", "").split())
    if summary:
        all_lines = _wrap_to_width(draw, summary, dek_font, W - 2 * MARGIN)
        wrapped = all_lines[:2]
        if len(all_lines) > 2:
            last = wrapped[-1].rstrip(".,;:")
            while _text_width(draw, last + "…", dek_font) > W - 2 * MARGIN and " " in last:
                last = last.rsplit(" ", 1)[0]
            wrapped[-1] = last + "…"
        if wrapped:
            blocks.append(
                (wrapped, dek_font, config.COLORS["muted"], int(dek_font.size * 1.35), 0, 3)
            )

    _draw_content_block(draw, blocks, region_top=230, region_bottom=H - 220)
    _draw_footer(draw, index, total, handle)
    return img, credit


def render_outro(sources, handle, total, photo_credits):
    img, draw, credit = _new_canvas(config.DEFAULT_IMAGE_QUERY)
    if credit:
        photo_credits.append(credit)
    _draw_corner_brackets(draw)

    eyebrow_font = _font("mono", 30)
    _draw_text(draw, (MARGIN, 150), "// END OF SIGNAL", eyebrow_font, config.COLORS["accent"])

    headline_font, lines = _autosize_headline(
        draw, "Follow for tomorrow's headlines", W - 2 * MARGIN, 4, 84, 50
    )
    body_font = _font("body", 28)
    credit_line = "Sources: " + ", ".join(sorted(set(sources)))
    wrapped = _wrap_to_width(draw, credit_line, body_font, W - 2 * MARGIN)

    photo_line = []
    if photo_credits:
        names = ", ".join(sorted(set(photo_credits)))
        photo_line = _wrap_to_width(draw, f"Photos: {names} via Pexels", body_font, W - 2 * MARGIN)

    blocks = [
        (lines, headline_font, config.COLORS["text"], int(headline_font.size * 1.2), 34, 4),
        (wrapped, body_font, config.COLORS["muted"], int(body_font.size * 1.4), 10 if photo_line else 0, 3),
    ]
    if photo_line:
        blocks.append((photo_line, body_font, config.COLORS["muted"], int(body_font.size * 1.4), 0, 3))

    _draw_content_block(draw, blocks, region_top=290, region_bottom=H - 260)
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
