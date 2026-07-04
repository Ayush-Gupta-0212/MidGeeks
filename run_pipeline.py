"""
run_pipeline.py
The single entry point: fetch stories -> render slides -> post to Instagram.
This is the one command the GitHub Actions workflow (and your local
terminal) actually calls.

Usage:
  python run_pipeline.py                 # official Graph API (recommended)
  python run_pipeline.py --unofficial    # instagrapi path instead
  python run_pipeline.py --dry-run       # fetch + render only, skip posting
"""

import argparse
import json

import config
import fetch_news
import generate_slides


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--unofficial",
        action="store_true",
        help="Post via instagrapi instead of the official Graph API",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and render slides but do not post anything",
    )
    parser.add_argument(
        "--handle",
        default=None,
        help="Shown in the slide footer, e.g. @your_account (defaults to config.IG_HANDLE)",
    )
    args = parser.parse_args()

    print("== 1/3  Fetching today's stories ==")
    stories = fetch_news.pick_todays_stories()
    if not stories:
        print("No new (unposted) stories found across any feed. Exiting without posting.")
        return
    for i, s in enumerate(stories, 1):
        print(f"  {i}. [{s['source']}] {s['title']}")
    with open("todays_stories.json", "w", encoding="utf-8") as f:
        json.dump(stories, f, indent=2)

    print("\n== 2/3  Generating slides ==")
    image_paths = generate_slides.generate(stories, handle=args.handle)
    for p in image_paths:
        print(" ", p)

    if args.dry_run:
        print("\n--dry-run set: stopping before posting. Check the output/ folder.")
        return

    print("\n== 3/3  Posting to Instagram ==")
    if args.unofficial:
        import post_instagram_unofficial as poster
    else:
        import post_instagram_official as poster
    poster.post_carousel(image_paths, stories)


if __name__ == "__main__":
    main()
