"""
post_instagram_official.py
Publishes the generated slides as ONE carousel post using Meta's official
Instagram Graph API (Content Publishing).

Flow (per Meta's docs, developers.facebook.com/docs/instagram-platform/content-publishing):
  1. Make every JPEG reachable at a public URL (Instagram's servers fetch it).
  2. POST /{IG_USER_ID}/media once per image, with is_carousel_item=true
     -> get back a container id for each.
  3. Poll each container's status_code until FINISHED (images are usually
     instant, but we check anyway — Meta recommends up to ~5 checks).
  4. POST /{IG_USER_ID}/media with media_type=CAROUSEL and children=<ids>
     -> get back one carousel container id.
  5. POST /{IG_USER_ID}/media_publish with that creation_id -> published.

Needs IG_USER_ID + IG_ACCESS_TOKEN as environment variables (GitHub Secrets).
Both come from your own Meta Developer App's dashboard — since this only
ever posts to your own account, Standard Access is enough and there is
NO app-review wait (see README, "Do you need Meta's App Review?").
"""

import sys
import time

import requests

import config

GRAPH_URL = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}"


def _require_credentials():
    missing = [
        name
        for name, val in [("IG_USER_ID", config.IG_USER_ID), ("IG_ACCESS_TOKEN", config.IG_ACCESS_TOKEN)]
        if not val
    ]
    if missing:
        sys.exit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them as GitHub Actions secrets (see README setup checklist)."
        )


def _check(response):
    data = response.json()
    if response.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Graph API error: {data}")
    return data


def upload_image_urls(image_paths):
    """Turn local JPEGs into public URLs Instagram can fetch.
    Default: commit them to this (public) GitHub repo and use the raw URL.
    Set IMAGE_HOST_MODE=imgur to use anonymous Imgur uploads instead
    (works even if your repo is private)."""
    if config.IMAGE_HOST_MODE == "imgur":
        return _upload_via_imgur(image_paths)
    return _urls_via_github_raw(image_paths)


def _urls_via_github_raw(image_paths):
    if not config.GITHUB_REPO:
        sys.exit(
            "IMAGE_HOST_MODE=github but GITHUB_REPOSITORY isn't set. "
            "This mode is meant to run inside GitHub Actions, which sets it "
            "automatically. Locally, export GITHUB_REPOSITORY='you/your-repo' "
            "and make sure you've committed+pushed the images first, or use "
            "IMAGE_HOST_MODE=imgur instead."
        )
    base = f"https://raw.githubusercontent.com/{config.GITHUB_REPO}/{config.GITHUB_BRANCH}"
    urls = [f"{base}/{path}" for path in image_paths]
    print("Using GitHub raw URLs (repo must be PUBLIC for Instagram to fetch these):")
    for u in urls:
        print(" ", u)
    return urls


def _upload_via_imgur(image_paths):
    if not config.IMGUR_CLIENT_ID:
        sys.exit("IMAGE_HOST_MODE=imgur but IMGUR_CLIENT_ID isn't set.")
    urls = []
    for path in image_paths:
        with open(path, "rb") as f:
            resp = requests.post(
                "https://api.imgur.com/3/image",
                headers={"Authorization": f"Client-ID {config.IMGUR_CLIENT_ID}"},
                files={"image": f},
                timeout=30,
            )
        data = _check(resp)
        urls.append(data["data"]["link"])
    return urls


def create_item_container(image_url):
    resp = requests.post(
        f"{GRAPH_URL}/{config.IG_USER_ID}/media",
        data={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": config.IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    return _check(resp)["id"]


def wait_until_ready(container_id, max_checks=5, delay_seconds=15):
    for attempt in range(max_checks):
        resp = requests.get(
            f"{GRAPH_URL}/{container_id}",
            params={"fields": "status_code", "access_token": config.IG_ACCESS_TOKEN},
            timeout=30,
        )
        status = _check(resp).get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} failed to process")
        time.sleep(delay_seconds)
    print(f"  [warn] container {container_id} still not FINISHED after {max_checks} checks; trying publish anyway")


def create_carousel_container(item_ids, caption):
    resp = requests.post(
        f"{GRAPH_URL}/{config.IG_USER_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": config.IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    return _check(resp)["id"]


def publish(creation_id):
    resp = requests.post(
        f"{GRAPH_URL}/{config.IG_USER_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": config.IG_ACCESS_TOKEN},
        timeout=30,
    )
    return _check(resp)["id"]


def build_caption(stories):
    lines = ["Today's tech signal:\n"]
    for s in stories:
        lines.append(f"→ {s['title']} ({s['source']})")
    lines.append("\nFull links in bio.\n")
    lines.append(config.CAPTION_HASHTAGS)
    return "\n".join(lines)


def post_carousel(image_paths, stories):
    _require_credentials()

    print("1/4  Uploading images to a public URL...")
    image_urls = upload_image_urls(image_paths)

    print("2/4  Creating a container per slide...")
    item_ids = []
    for url in image_urls:
        item_id = create_item_container(url)
        wait_until_ready(item_id)
        item_ids.append(item_id)
        print(f"    container ready: {item_id}")

    print("3/4  Creating the carousel container...")
    caption = build_caption(stories)
    carousel_id = create_carousel_container(item_ids, caption)
    wait_until_ready(carousel_id)

    print("4/4  Publishing...")
    media_id = publish(carousel_id)
    print(f"\nPublished! media id: {media_id}")
    return media_id


if __name__ == "__main__":
    import json
    import os

    with open("todays_stories.json", "r", encoding="utf-8") as f:
        stories = json.load(f)

    image_paths = sorted(
        os.path.join(config.OUTPUT_DIR, f)
        for f in os.listdir(config.OUTPUT_DIR)
        if f.lower().endswith(".jpg")
    )
    post_carousel(image_paths, stories)
