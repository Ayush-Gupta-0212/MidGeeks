"""
generate_slides.py
Turns a list of stories into a set of 1080x1350 JPEG carousel slides:
  01_cover.jpg -> one slide per story -> NN_outro.jpg

Design: deep-ink background, one amber accent, a monospace "readout" for
metadata (source, slide index) paired with a bold geometric headline face.
The mono treatment is intentional, not decorative — it's honest about this
being a machine-curated feed. All colors/fonts live in config.py.

Instagram's Graph API only accepts JPEG (no PNG), and crops every slide in
a carousel to match slide 1's aspect ratio — so every slide here is
rendered at the exact same CANVAS_SIZE.
"""

import os
from datetime import datetime, timedelta, timezone

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
    # Fall back to the smallest size, truncating extra lines with an ellipsis
    font = _font("headline", min_size)
    lines = _wrap_to_width(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "…"
    return font, lines


def _draw_corner_brackets(draw):
    c = config.COLORS["accent"]
    length, thickness, m = 46, 6, 52
    # top-left
    draw.line([(m, m), (m + length, m)], fill=c, width=thickness)
    draw.line([(m, m), (m, m + length)], fill=c, width=thickness)
    # bottom-right
    draw.line([(W - m, H - m), (W - m - length, H - m)], fill=c, width=thickness)
    draw.line([(W - m, H - m), (W - m, H - m - length)], fill=c, width=thickness)


def _draw_footer(draw, index, total, handle):
    mono = _font("mono", 24)
    tag = f"{index:02d} / {total:02d}"
    draw.text((MARGIN, H - 100), tag, font=mono, fill=config.COLORS["accent"])
    hw = _text_width(draw, handle, mono)
    draw.text((W - MARGIN - hw, H - 100), handle, font=mono, fill=config.COLORS["muted"])


def _new_canvas():
    img = Image.new("RGB", (W, H), config.COLORS["bg"])
    return img, ImageDraw.Draw(img)


def _ghost_numeral(draw, number):
    """Big, barely-there numeral in the background — the same slide index
    shown small in the footer, blown up as a quiet watermark. Structural,
    not decorative: it repeats real information (which slide this is)."""
    ghost_color = "#1A1D28"  # a hair lighter than bg — visible, not distracting
    font = _font("headline", 480)
    text = f"{number:02d}"
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text((W - tw - 60, H - th - 260), text, font=font, fill=ghost_color)


def _draw_content_block(draw, blocks, region_top, region_bottom):
    """Vertically centers a list of (lines, font, color, line_height, gap_after)
    blocks inside [region_top, region_bottom] instead of pinning text to the
    top and leaving the bottom half empty."""
    total_h = 0
    for lines, font, _color, line_h, gap_after in blocks:
        total_h += len(lines) * line_h + gap_after
    y = region_top + max(0, (region_bottom - region_top - total_h) // 2)
    for lines, font, color, line_h, gap_after in blocks:
        for line in lines:
            draw.text((MARGIN, y), line, font=font, fill=color)
            y += line_h
        y += gap_after


def render_cover(story_count, date_str, handle):
    img, draw = _new_canvas()
    _ghost_numeral(draw, 1)
    _draw_corner_brackets(draw)

    eyebrow_font = _font("mono", 30)
    draw.text((MARGIN, 150), "// TECH SIGNAL", font=eyebrow_font, fill=config.COLORS["accent"])

    noun = "headline" if story_count == 1 else "headlines"
    headline_font, lines = _autosize_headline(
        draw, f"{story_count} {noun} you missed today", W - 2 * MARGIN, 5, 96, 60
    )
    sub_font = _font("body", 34)

    _draw_content_block(
        draw,
        [
            (lines, headline_font, config.COLORS["text"], int(headline_font.size * 1.18), 26),
            ([date_str], sub_font, config.COLORS["muted"], int(sub_font.size * 1.3), 0),
        ],
        region_top=290,
        region_bottom=H - 260,
    )

    swipe_font = _font("mono", 28)
    draw.text((MARGIN, H - 180), "SWIPE →", font=swipe_font, fill=config.COLORS["accent"])

    _draw_footer(draw, 1, story_count + 2, handle)
    return img


def render_story(story, index, total, handle):
    img, draw = _new_canvas()
    _ghost_numeral(draw, index)
    _draw_corner_brackets(draw)

    mono = _font("mono", 26)
    draw.text(
        (MARGIN, 130),
        f"SOURCE: {story['source'].upper()}",
        font=mono,
        fill=config.COLORS["accent"],
    )

    headline_font, lines = _autosize_headline(
        draw, story["title"], W - 2 * MARGIN, 6, 72, 44
    )

    blocks = [(lines, headline_font, config.COLORS["text"], int(headline_font.size * 1.2), 30)]

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
                (wrapped, dek_font, config.COLORS["muted"], int(dek_font.size * 1.35), 0)
            )

    _draw_content_block(draw, blocks, region_top=230, region_bottom=H - 220)
    _draw_footer(draw, index, total, handle)
    return img


def render_outro(sources, handle, total):
    img, draw = _new_canvas()
    _ghost_numeral(draw, total)
    _draw_corner_brackets(draw)

    eyebrow_font = _font("mono", 30)
    draw.text((MARGIN, 150), "// END OF SIGNAL", font=eyebrow_font, fill=config.COLORS["accent"])

    headline_font, lines = _autosize_headline(
        draw, "Follow for tomorrow's headlines", W - 2 * MARGIN, 4, 84, 50
    )
    body_font = _font("body", 28)
    credit = "Sources: " + ", ".join(sorted(set(sources)))
    wrapped = _wrap_to_width(draw, credit, body_font, W - 2 * MARGIN)

    _draw_content_block(
        draw,
        [
            (lines, headline_font, config.COLORS["text"], int(headline_font.size * 1.2), 34),
            (wrapped, body_font, config.COLORS["muted"], int(body_font.size * 1.4), 0),
        ],
        region_top=290,
        region_bottom=H - 260,
    )

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

    cover = render_cover(len(stories), date_str, handle)
    p = os.path.join(out_dir, "01_cover.jpg")
    cover.save(p, "JPEG", quality=92)
    paths.append(p)

    for i, story in enumerate(stories, start=2):
        img = render_story(story, i, total, handle)
        p = os.path.join(out_dir, f"{i:02d}_story.jpg")
        img.save(p, "JPEG", quality=92)
        paths.append(p)

    outro = render_outro([s["source"] for s in stories], handle, total)
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
        # Sample data so this script is runnable/checkable on its own
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
