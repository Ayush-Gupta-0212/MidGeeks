"""
run_pipeline.py
Entry point. In single-story mode (the default), it:
  1. picks the single freshest unposted tech story
  2. fetches that article's REAL text and summarizes it into genuine points
     (skipping the story if it can't get real content — never invents any)
  3. generates the carousel (AI background per slide, orange/white design)
  4. posts it, and only THEN marks the story as posted

Usage:
  python run_pipeline.py                 # official Graph API (recommended)
  python run_pipeline.py --unofficial    # instagrapi path instead
  python run_pipeline.py --dry-run       # build slides only, skip posting
"""

import argparse
import json

import config
import fetch_news
import generate_slides
import article_points


def _run_single(args):
    print("== 1/4  Picking today's top story ==")
    # Try a few candidates in case the top one's article can't be summarized.
    candidates = fetch_news.fetch_candidates()
    if not candidates:
        print("No new (unposted) stories found. Exiting.")
        return

    story = None
    points = []
    for cand in candidates[:5]:
        print(f"  Trying: [{cand['source']}] {cand['title']}")
        pts, _ = article_points.build_points(cand)
        if pts:
            story, points = cand, pts
            break
        print("  -> couldn't get real article points, trying next story")

    if not story:
        print("Couldn't build real points for any candidate story. Exiting without posting.")
        return

    print(f"\nSelected: [{story['source']}] {story['title']}")
    print(f"Built {len(points)} real key points:")
    for i, p in enumerate(points, 1):
        print(f"  {i}. {p['heading']} — {p['detail']}")

    with open("todays_story.json", "w", encoding="utf-8") as f:
        json.dump({"story": story, "points": points}, f, indent=2)

    print("\n== 2/4  Generating slides (AI backgrounds) ==")
    image_paths = generate_slides.generate_single(story, points, handle=args.handle)
    for p in image_paths:
        print(" ", p)

    if args.dry_run:
        print("\n--dry-run set: stopping before posting. Check the output/ folder.")
        return

    print("\n== 3/4  Posting to Instagram ==")
    if args.unofficial:
        import post_instagram_unofficial as poster
    else:
        import post_instagram_official as poster
    poster.post_carousel(image_paths, [story])

    print("\n== 4/4  Marking story as posted ==")
    fetch_news.mark_posted(story)
    print("Done.")


def _run_digest(args):
    # Legacy multi-story mode.
    print("== 1/3  Fetching today's stories ==")
    stories = fetch_news.pick_todays_stories()
    if not stories:
        print("No new (unposted) stories found across any feed. Exiting.")
        return
    for i, s in enumerate(stories, 1):
        print(f"  {i}. [{s['source']}] {s['title']}")
    with open("todays_stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, indent=2)

    print("\n== 2/3  Generating slides ==")
    image_paths = generate_slides.generate_single  # not used in digest
    print("Digest mode is deprecated in this build; use POST_MODE='single'.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unofficial", action="store_true",
                        help="Post via instagrapi instead of the official Graph API")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build slides but do not post anything")
    parser.add_argument("--handle", default=None,
                        help="Shown in the slide footer (defaults to config.IG_HANDLE)")
    args = parser.parse_args()

    if config.POST_MODE == "single":
        _run_single(args)
    else:
        _run_digest(args)


if __name__ == "__main__":
    main()
