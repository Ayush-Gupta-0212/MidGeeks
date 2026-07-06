"""
generate_slides.py
Single-story mode: builds one carousel about ONE news story:
  01_cover.jpg  -> a curiosity-driven cover (headline + "swipe to see why")
  NN_point.jpg  -> one slide per REAL key point (heading + detail)
  NN_outro.jpg  -> follow CTA + source credit

Design (per user spec):
  - Background: AI-generated image per slide (Gemini), dark & cinematic.
  - Dark tint over the image, DARKER toward the bottom, so text stays readable.
  - Text theme: orange + white only. Headlines/tags orange, body white.
  - Layout tuned to make people curious: the cover teases, points deliver.

Falls back to a solid dark background if image generation is unavailable, so
the pipeline never breaks on an image failure.
"""

import os
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config
import pexels_image

W, H = config.CANVAS_SIZE
MARGIN = 90


def _font(name, size):
    return ImageFont.truetype(config.FONTS[name], size)


def _text_width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap_to_width(draw, text, font, max_width):
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


def _autosize(draw, text, font_name, max_width, max_lines, start_size, min_size):
    size = start_size
    while size >= min_size:
        font = _font(font_name, size)
        lines = _wrap_to_width(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 3
    font = _font(font_name, min_size)
    lines = _wrap_to_width(draw, text, font, max_width)[:max_lines]
    return font, lines


# ---------------------------------------------------------------------------
# Background + tint
# ---------------------------------------------------------------------------

def _cover_fit(img, tw, th):
    sw, sh = img.size
    sr, tr = sw / sh, tw / th
    if sr > tr:
        nh = th
        nw = max(tw, int(round(nh * sr)))
    else:
        nw = tw
        nh = max(th, int(round(nw / sr)))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _background(concept):
    """AI image if available, else solid dark fallback."""
    img = pexels_image.generate_background(concept)
    if img is None:
        return Image.new("RGB", (W, H), config.COLORS["bg"])
    return _cover_fit(img, W, H)


def _apply_tint(img):
    """Black tint whose opacity ramps from SCRIM_ALPHA_TOP at the top to
    SCRIM_ALPHA_BOTTOM at the bottom — darker at the bottom, as specified,
    so lower-third text stays legible."""
    img = img.convert("RGBA")
    grad = Image.new("L", (1, H))
    top = config.SCRIM_ALPHA_TOP
    bot = config.SCRIM_ALPHA_BOTTOM
    for y in range(H):
        frac = y / H
        # ease-in so most of the darkening happens in the lower half
        eased = frac ** 1.4
        grad.putpixel((0, y), int(top + (bot - top) * eased))
    grad = grad.resize((W, H))
    tint = Image.new("RGBA", (W, H), config.COLORS["scrim"] + (0,))
    tint.putalpha(grad)
    return Image.alpha_composite(img, tint).convert("RGB")


def _canvas(concept):
    bg = _apply_tint(_background(concept))
    _current[0] = bg
    return bg, ImageDraw.Draw(bg)


# ---------------------------------------------------------------------------
# Shared drawing pieces
# ---------------------------------------------------------------------------

# Reference to the slide currently being drawn, so text helpers can composite
# a blurred drop shadow onto the actual image (a blur needs the pixels, not
# just a draw handle).
_current = [None]

# Softness of the drop shadow behind text. Larger = more diffuse/softer.
_SHADOW_BLUR = 7
_SHADOW_OFFSET = 5


def _soft_shadow(xy, text, font):
    """Composite a blurred dark shadow of `text` onto the current slide."""
    img = _current[0]
    if img is None:
        return
    x, y = xy
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((x + _SHADOW_OFFSET, y + _SHADOW_OFFSET), text, font=font, fill=(0, 0, 0, 235))
    layer = layer.filter(ImageFilter.GaussianBlur(_SHADOW_BLUR))
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), layer)


def _draw_text(draw, xy, text, font, fill, stroke=0):
    """All body/headline text: a soft blurred shadow underneath, then crisp
    text on top. `stroke` is ignored now (kept so existing calls still work)."""
    _soft_shadow(xy, text, font)
    draw.text(xy, text, font=font, fill=fill)


def _draw_text_soft(draw, xy, text, font, fill, shadow_offset=4):
    """Same soft-shadow treatment; kept as a separate name for the callers
    (headings, handle) that referenced it."""
    _soft_shadow(xy, text, font)
    draw.text(xy, text, font=font, fill=fill)


def _accent_bar(draw, x, y0, y1, w=9):
    draw.rectangle([x, y0, x + w, y1], fill=config.COLORS["accent"])


def _header(draw, label):
    y = 150
    draw.rectangle([MARGIN, y, MARGIN + 40, y + 7], fill=config.COLORS["accent"])
    f = _font("mono", 27)
    _draw_text(draw, (MARGIN + 56, y - 11), label, f, config.COLORS["accent"], stroke=2)


def _footer(draw, index, total, handle):
    y = H - 116
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill=(255, 255, 255), width=2)
    f = _font("mono", 24)
    tag = f"{index:02d} / {total:02d}"
    _draw_text(draw, (MARGIN, y + 24), tag, f, config.COLORS["accent"], stroke=2)
    hw = _text_width(draw, handle, f)
    _draw_text(draw, (W - MARGIN - hw, y + 24), handle, f, config.COLORS["text"], stroke=2)


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def render_cover(story, total, handle, concept):
    img, draw = _canvas(concept)
    _header(draw, "TECH SIGNAL")

    # Curiosity kicker in orange, then the headline big in white, anchored low.
    kicker_font = _font("mono", 30)
    headline_font, lines = _autosize(
        draw, story["title"], "headline", W - 2 * MARGIN - 28, 6, 82, 46
    )
    line_h = int(headline_font.size * 1.14)
    block_h = len(lines) * line_h
    bottom_y = H - 250
    top_y = bottom_y - block_h

    _draw_text(draw, (MARGIN + 28, top_y - 58), "HERE'S WHY IT MATTERS", kicker_font,
               config.COLORS["accent"], stroke=2)
    _accent_bar(draw, MARGIN, top_y - 8, bottom_y)

    y = top_y
    for line in lines:
        _draw_text(draw, (MARGIN + 28, y), line, headline_font, config.COLORS["text"], stroke=4)
        y += line_h

    swipe_font = _font("mono", 28)
    _draw_text(draw, (MARGIN + 28, H - 190), "SWIPE TO SEE →", swipe_font,
               config.COLORS["accent"], stroke=2)

    _footer(draw, 1, total, handle)
    return img


def render_point(point, index, total, handle, concept, number):
    img, draw = _canvas(concept)
    _header(draw, f"POINT {number}")

    heading_font, h_lines = _autosize(
        draw, point["heading"], "headline", W - 2 * MARGIN - 28, 3, 88, 50
    )
    detail_font = _font("body", 34)
    d_lines = _wrap_to_width(draw, point["detail"], detail_font, W - 2 * MARGIN - 28)

    h_lh = int(heading_font.size * 1.12)
    d_lh = int(detail_font.size * 1.34)
    gap = 28
    block_h = len(h_lines) * h_lh + gap + len(d_lines) * d_lh
    bottom_y = H - 200
    top_y = bottom_y - block_h

    _accent_bar(draw, MARGIN, top_y - 4, top_y + len(h_lines) * h_lh)

    y = top_y
    for line in h_lines:
        _draw_text_soft(draw, (MARGIN + 28, y), line, heading_font, config.COLORS["accent"])
        y += h_lh
    y += gap
    for line in d_lines:
        _draw_text(draw, (MARGIN + 28, y), line, detail_font, config.COLORS["text"], stroke=3)
        y += d_lh

    _footer(draw, index, total, handle)
    return img


def render_outro(story, total, handle, concept):
    img, draw = _canvas(concept)
    _header(draw, "THE TAKEAWAY")

    # A bolder, centered call-to-action. No source/photo credits — just the
    # follow prompt and the handle, sized to feel like the payoff slide.
    enjoyed_font = _font("body", 38)
    follow_font, follow_lines = _autosize(
        draw, "Follow for more tech stories", "headline",
        W - 2 * MARGIN - 28, 3, 88, 54
    )
    handle_font = _font("headline", 74)

    # Vertically center the block in the lower-middle of the slide.
    enjoyed_h = int(enjoyed_font.size * 1.3)
    follow_lh = int(follow_font.size * 1.14)
    handle_h = int(handle_font.size * 1.2)
    gap1, gap2 = 24, 40
    block_h = enjoyed_h + gap1 + len(follow_lines) * follow_lh + gap2 + handle_h
    top_y = (H - block_h) // 2 + 60

    y = top_y
    _draw_text(draw, (MARGIN + 28, y), "Enjoyed this breakdown?", enjoyed_font,
               config.COLORS["muted"], stroke=3)
    y += enjoyed_h + gap1

    _accent_bar(draw, MARGIN, y - 4, y + len(follow_lines) * follow_lh)
    for line in follow_lines:
        _draw_text(draw, (MARGIN + 28, y), line, follow_font, config.COLORS["text"], stroke=4)
        y += follow_lh
    y += gap2

    _draw_text_soft(draw, (MARGIN + 28, y), handle, handle_font, config.COLORS["accent"])

    _footer(draw, total, total, handle)
    return img


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _concept_for(story, point=None):
    """Text used to choose a slide's background photo. For a point slide we
    include the heading AND detail so the image reflects the point's full
    content; for the cover/outro we use the story title."""
    base = story.get("title", "technology")
    if point:
        return f"{base}. {point['heading']}. {point['detail']}"
    return base


def generate_single(story, points, handle=None, out_dir=None):
    """Build a one-story carousel. `points` is the list of real key points
    from article_points.build_points()."""
    handle = handle or config.IG_HANDLE
    out_dir = out_dir or config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.lower().endswith(".jpg"):
            os.remove(os.path.join(out_dir, f))

    # Fresh per-post state so no two slides repeat a photo and images vary
    # from day to day.
    pexels_image.reset_run()

    total = len(points) + 2  # cover + points + outro
    paths = []

    cover = render_cover(story, total, handle, _concept_for(story))
    p = os.path.join(out_dir, "01_cover.jpg")
    cover.save(p, "JPEG", quality=92)
    paths.append(p)

    for i, point in enumerate(points):
        slide_index = i + 2
        number = i + 1
        img = render_point(point, slide_index, total, handle,
                           _concept_for(story, point), number)
        p = os.path.join(out_dir, f"{slide_index:02d}_point.jpg")
        img.save(p, "JPEG", quality=92)
        paths.append(p)

    outro = render_outro(story, total, handle, _concept_for(story))
    p = os.path.join(out_dir, f"{total:02d}_outro.jpg")
    outro.save(p, "JPEG", quality=92)
    paths.append(p)

    return paths


if __name__ == "__main__":
    import json

    if os.path.exists("todays_story.json"):
        with open("todays_story.json", "r", encoding="utf-8") as f:
            payload = json.load(f)
        story, points = payload["story"], payload["points"]
    else:
        story = {
            "source": "TechCrunch",
            "title": "Nvidia unveils its next-gen AI chip with double the memory bandwidth",
            "link": "https://example.com/1",
        }
        points = [
            {"heading": "Double the bandwidth", "detail": "The new chip doubles memory bandwidth over the previous generation, per the announcement."},
            {"heading": "Ships in Q3", "detail": "Availability is slated for the third quarter, with pricing not yet disclosed."},
            {"heading": "Pressure on rivals", "detail": "Analysts say the launch raises the bar for competing accelerator makers."},
        ]

    out = generate_single(story, points, handle="@midgeeks.studio")
    print("Generated:")
    for p in out:
        print(" ", p)
