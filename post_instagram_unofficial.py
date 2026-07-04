"""
post_instagram_unofficial.py
Alternative posting path using instagrapi, which talks to Instagram's
undocumented private mobile API instead of the official Graph API.

READ THIS BEFORE USING:
  - This is against Instagram's Terms of Service. Meta actively detects and
    challenges/bans accounts it flags as automated, and enforcement has
    gotten stricter (2FA challenges, device-fingerprint checks).
  - It requires your actual Instagram username/password, not a scoped token.
  - Since your account already qualifies for the official API with ZERO
    app-review wait (see README), this file exists only because you asked
    to see both options for comparison — the official script is the one
    actually recommended for this project.
  - If you use this anyway: never commit ig_session.json to git (it holds
    your live login session — .gitignore it), keep posting frequency low,
    and expect to occasionally have to solve a login challenge by hand.

Install with: pip install instagrapi
"""

import json
import os
import sys

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, LoginRequired, TwoFactorRequired

import config


def _login():
    if not config.IG_USERNAME or not config.IG_PASSWORD:
        sys.exit("Set IG_USERNAME and IG_PASSWORD environment variables first.")

    cl = Client()
    cl.delay_range = [1, 3]  # small human-like delay between internal requests

    if os.path.exists(config.IG_SESSION_FILE):
        cl.load_settings(config.IG_SESSION_FILE)
        try:
            cl.login(config.IG_USERNAME, config.IG_PASSWORD)
            cl.get_timeline_feed()  # cheap call to confirm the session is still valid
            return cl
        except LoginRequired:
            print("Saved session expired, logging in fresh...")

    try:
        cl.login(config.IG_USERNAME, config.IG_PASSWORD)
    except TwoFactorRequired:
        code = input("Enter the 2FA code Instagram just sent you: ").strip()
        cl.login(config.IG_USERNAME, config.IG_PASSWORD, verification_code=code)
    except ChallengeRequired:
        sys.exit(
            "Instagram is asking for a login challenge (SMS/email/in-app "
            "approval). Log in manually from the same IP once, approve it, "
            "then re-run this script."
        )

    cl.dump_settings(config.IG_SESSION_FILE)
    return cl


def build_caption(stories):
    lines = ["Today's tech signal:\n"]
    for s in stories:
        lines.append(f"→ {s['title']} ({s['source']})")
    lines.append("\nFull links in bio.\n")
    lines.append(config.CAPTION_HASHTAGS)
    return "\n".join(lines)


def post_carousel(image_paths, stories):
    cl = _login()
    caption = build_caption(stories)
    media = cl.album_upload(image_paths, caption)
    print(f"Published! code: {media.code}  url: https://www.instagram.com/p/{media.code}/")
    return media


if __name__ == "__main__":
    with open("todays_stories.json", "r", encoding="utf-8") as f:
        stories = json.load(f)

    image_paths = sorted(
        os.path.join(config.OUTPUT_DIR, f)
        for f in os.listdir(config.OUTPUT_DIR)
        if f.lower().endswith(".jpg")
    )
    post_carousel(image_paths, stories)
