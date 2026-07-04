# Automated Tech-News Instagram Carousel Bot — Full Plan

A daily Instagram carousel post ("N headlines you missed today") built entirely
on free tools, triggered by one click or fully automatic on a schedule.
Everything below was checked against current (mid-2026) API docs, ToS pages,
and pricing pages — not just remembered from training — because this is
exactly the kind of stack where a tutorial that was right a year ago is now
wrong in a way that silently breaks your bot or violates a ToS.

**Total monthly cost: $0.** Confirmed feasible below.

---

## 1. How it fits together

```
 RSS feeds (TechCrunch, Verge, Wired,     ①  fetch_news.py
 Ars Technica, Hacker News)          ─────────────────────►  picks today's
                                                               top N unposted
                                                               stories
                                                                    │
                                                                    ▼
                                                          ②  generate_slides.py
                                                          renders JPEG slides
                                                          (cover + 1/story + outro)
                                                                    │
                                                                    ▼
                                                          ③  image goes public
                                                          (commit to repo → raw
                                                           GitHub URL, or Imgur)
                                                                    │
                                                                    ▼
                                                          ④  post_instagram_*.py
                                                          builds the carousel,
                                                          publishes it
                                                                    │
                                                                    ▼
                                                            Posted to Instagram

 Trigger layer: GitHub Actions
   • schedule: → runs every day automatically (fully automated)
   • workflow_dispatch: → a "Run workflow" button = your single click
     (also triggerable from the GitHub mobile app, or `gh workflow run`)
```

Every box above is a real file in this package, and every one of them has
been run in a sandbox to confirm it doesn't crash — the RSS parsing/dedup
logic was verified against a local sample feed, and the slide renderer
produced the actual JPEGs shown below. The one thing that could **not** be
tested from that sandbox is live calls to techcrunch.com or
graph.facebook.com (its network is locked to package registries only) —
those will run for real the first time inside GitHub Actions, which has
normal internet access. Do a `--dry-run` first (see §7) to see this live
before it ever touches your Instagram account.

### Sample output (real renders, mock headlines)

The `output/` folder ships with 5 pre-rendered JPEGs so you can see the look
before running anything: a cover slide, three story slides, and an outro.

---

## 2. Content sources — and a trap most tutorials walk you into

| Source | Cost | Catch |
|---|---|---|
| **RSS: TechCrunch, The Verge, Wired, Ars Technica** | Free, no key, no limit | The Verge/Ars only send excerpts in free RSS — fine here, we only need a headline + one-line dek |
| **Hacker News (via hnrss.org)** | Free, no key | Unofficial bridge, no SLA — fine for a hobby bot, don't depend on it for anything critical |
| ~~NewsAPI.org free tier~~ | Free | **Explicitly forbids anything outside local development** — their own ToS says a deployed/scheduled use requires a paid plan ($449/mo for the first tier up). A GitHub Actions run is not "local development." |
| ~~GNews free tier~~ | Free | Same shape of restriction: non-commercial/dev use only |

This is why the bot is built on RSS instead of the news APIs every tutorial
reaches for first: RSS is the publisher's own public broadcast feed, so there's
no ToS to violate by reading it on a schedule. `fetch_news.py` pulls all five
feeds, **strips any raw HTML the feed embeds in its summary** (hnrss.org wraps
its summary in `<p>`/`<a>` tags; Ars Technica uses inline `<em>` — both get
cleaned to plain text before rendering), drops anything already posted
(tracked in `posted_history.json`, pruned after 30 days), de-dupes
near-identical headlines across outlets, and keeps the freshest
`STORY_SLIDE_COUNT` (default 5).

**Content filtering**: `KEYWORD_BLOCKLIST` in `config.py` skips anything
matching a short default list (piracy-adjacent terms, "movie review", "box
office") since general-interest feeds like Ars Technica occasionally mix in
non-tech culture content, and Hacker News' front page occasionally surfaces
stories linking to shadow-library-type sites. It's a starting heuristic, not
a perfect filter — tune the list as you see what comes through. `KEYWORD_ALLOWLIST`
is the inverse (require a match) if you want to narrow to specific beats.

**Timezone**: the cover slide's date is computed in UTC by default, since
that's the GitHub Actions runner's clock. Set `DISPLAY_TIMEZONE_OFFSET_HOURS`
in `config.py` (e.g. `5.5` for India) if you want the printed date to match
your own local date instead of the runner's.

If you later want broader coverage, **Currents API** and **The Guardian Open
Platform** are two of the few news APIs whose free tiers explicitly permit
production/commercial use — worth a look, not required.

---

## 3. Visual design

Rendered with Pillow at 1080×1350 (4:5 — the tallest ratio Instagram allows
in-feed, so it takes more space while someone scrolls). Deliberately not the
generic "AI template" look (cream+serif, or dark+neon):

- **Ink-navy background**, warm off-white text, **one** signal-amber accent
- **Poppins Bold** headlines + a **monospace** eyebrow/index tag — the mono
  treatment is a nod to what this actually is (a machine reading a data feed),
  not decoration
- A large "ghost" numeral watermark repeats the slide index as a quiet
  background element instead of leaving dead space
- Small corner-bracket marks, like a viewfinder frame

All colors/fonts are constants at the top of `config.py` — reskin freely.
Fonts (Poppins Bold/Medium/SemiBold + DejaVu Sans Mono Bold) are bundled in
`assets/fonts/` under the OFL license, so the repo has zero runtime font
dependency and looks identical on any machine, including GitHub's runners.

---

## 4. The big decision: official API vs. unofficial tool

You asked to see both, so here's an honest comparison — but the short version
is: **because your account is already a Business/Creator account linked to a
Facebook Page, the official path costs you nothing extra and has no waiting
period.** There's little reason to take on ban risk for this project.

| | **Official — Instagram Graph API** (recommended) | **Unofficial — instagrapi** |
|---|---|---|
| What it is | Meta's own Content Publishing API | A reverse-engineered client that impersonates the mobile app |
| Setup | Meta Developer App + a token you generate from your own dashboard | `pip install instagrapi`, log in with username/password |
| **App Review wait?** | **No** — see box below | N/A |
| ToS risk | None — this is the sanctioned path | Real: Meta actively detects and challenges/bans automated logins; enforcement got stricter through 2025–2026 (2FA prompts, device-fingerprint checks) |
| Stability | Versioned API, ~2-year deprecation notice | Breaks whenever Instagram's private API changes, sometimes with no notice |
| What it needs | An access token (scoped, revocable) | Your actual Instagram password |
| Rate limit | 100 posts/24h (Meta's official number; one section of their own docs says 50 for carousels specifically — either way, nowhere near a concern for 1 post/day) | Instagram doesn't publish one; aggressive use is exactly what triggers bans |

> **Do you actually need Meta's App Review?** Almost every tutorial says
> "app review takes 2–4 weeks" — true only if your app will post on behalf of
> *other people's* accounts. Meta's own docs are explicit: *"If your app only
> serves your Instagram professional account or an account you manage,
> [the default] Standard Access is all your app needs."* Since this bot only
> ever touches your own account, you skip App Review entirely and can
> generate a working access token directly from your app's dashboard today.

**Recommendation: use `post_instagram_official.py`.** `post_instagram_unofficial.py`
is included and functional if you want it, with the risks commented directly
in the file — but there's no upside here given your account already qualifies
for the free, sanctioned route.

---

## 5. Setup checklist

### A. Meta Developer App (15 minutes, one time)

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** → type **Business**.
2. In your app's dashboard, **Add Product** → **Instagram** → set it up with
   **Instagram API with Instagram Login** (the simpler of the two paths —
   uses `graph.instagram.com` and doesn't route through a separate Facebook
   Page login flow).
3. Under **Generate access tokens**, click **Add account**, log into the
   Instagram account you already converted to Business/Creator, and approve.
   This immediately gives you a working, long-lived-refreshable
   **Instagram User access token** for *your own* account — no review queue.
4. Copy your **Instagram User ID** (shown next to the connected account) and
   the **access token**.

Token lifespan is ~60 days. Set a recurring reminder to regenerate it (or
automate the refresh call — `GET /refresh_access_token`, one line, worth
adding once this is running smoothly).

### B. Repo setup

1. Open `config.py` and set `IG_HANDLE` to your real `@username` (it's public
   info, not a secret — this is just what prints in the corner of every slide).
2. Create a **public** GitHub repo (public is what makes the free
   raw-URL image hosting work — your code has no secrets in it; those live in
   step C below). Push all the files in this package to it.
3. If you'd rather keep the repo private, set `IMAGE_HOST_MODE=imgur`
   instead (register a free app at [api.imgur.com](https://api.imgur.com/oauth2/addclient)
   for a `Client-ID`, no OAuth login needed for anonymous uploads).

### C. Secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret.**

| Secret | Value |
|---|---|
| `IG_USER_ID` | from step A.4 |
| `IG_ACCESS_TOKEN` | from step A.4 |
| `IMGUR_CLIENT_ID` | only if using Imgur mode |

### D. First run

- **Actions tab → "Post Tech News Carousel" → Run workflow → tick "Generate
  slides only, don't post" → Run.** Check the workflow's artifact download
  for the rendered slides before ever posting live.
- Happy with them? Run it again unticked. That's your real post — and also
  your "single click" trigger from now on, from a laptop or the GitHub
  mobile app.

---

## 6. The "single click" / full-automation trigger

`.github/workflows/post_tech_news.yml` (included) gives you **both**:

- `schedule:` → runs on its own every day at the UTC time you set — true
  "fully automated, no click needed."
- `workflow_dispatch:` → adds a **Run workflow** button on the Actions tab.
  This is a real single-click trigger from a browser (desktop or mobile
  browser both work reliably). The GitHub *mobile app's* support for
  starting a brand-new run with the dry-run toggle has been inconsistently
  reported (works for some, silently fails for others) — the app is solid
  for re-running a past run or checking status, but for the dropdown with
  inputs, use a browser. `gh workflow run post_tech_news.yml` from a
  terminal, or the REST API, are the other reliable single-command options.

The workflow: checks out the repo → fetches stories → renders slides →
**commits the images back to the repo** (this is the step that makes the
raw.githubusercontent.com URLs real before the posting step tries to use
them) → publishes the carousel → uploads the slides as a downloadable
workflow artifact either way.

**Cost:** GitHub Actions is free and unlimited on public repos for standard
runners. A private repo's free tier (2,000 min/month) would also cover this
easily — one run takes roughly 2–3 minutes, so even daily runs use ~90
minutes a month.

---

## 7. Running it locally first (optional but recommended)

```bash
git clone <your-repo-url> && cd <your-repo>
pip install -r requirements.txt

# See the slides without posting anything:
python run_pipeline.py --dry-run --handle "@your_real_handle"
open output/01_cover.jpg   # (or just look in the output/ folder)

# The real thing, official API:
export IG_USER_ID=...
export IG_ACCESS_TOKEN=...
python run_pipeline.py --handle "@your_real_handle"
```

---

## 8. Cost summary

| Piece | Tool | Cost |
|---|---|---|
| Content | RSS (TechCrunch, Verge, Wired, Ars Technica, HN) | $0 |
| Image rendering | Pillow, self-hosted in the workflow | $0 |
| Image hosting | GitHub raw (or Imgur) | $0 |
| Posting | Instagram Graph API, Standard Access | $0 |
| Automation/trigger | GitHub Actions | $0 (public repo = unlimited) |
| **Total** | | **$0/month** |

---

## 9. Known limits & maintenance

- **Token expiry**: ~60 days for the long-lived Instagram token. Calendar
  reminder, or automate `GET /refresh_access_token` before it lapses.
- **JPEG only**: Graph API rejects PNG outright — `generate_slides.py`
  already saves JPEG, just don't change that.
- **Aspect ratio**: the *first* slide sets the crop for the whole carousel,
  so every slide must share the same ratio — already enforced by using one
  `CANVAS_SIZE` constant everywhere.
- **API versioning**: Meta deprecates Graph API versions roughly every 2
  years; `config.GRAPH_API_VERSION` is the one place to bump when that happens.
- **RSS feed changes**: publishers occasionally change feed URLs/formats
  without notice — `fetch_news.py`'s per-feed try/except means one broken
  feed just gets skipped with a warning instead of crashing the whole run.
- **Rate limits**: nowhere close to a concern at 1 post/day (limit is
  50–100/day depending on which part of Meta's own docs you read).

---

## 10. Files in this package

```
config.py                       - all settings: colors, fonts, feeds, slide count
fetch_news.py                   - pulls + dedupes today's stories from RSS
generate_slides.py              - renders the JPEG carousel slides
post_instagram_official.py      - recommended: posts via the Graph API
post_instagram_unofficial.py    - alternative: posts via instagrapi (risk-flagged)
run_pipeline.py                 - runs all three steps end to end, for local use
requirements.txt                - pip dependencies
assets/fonts/                   - bundled OFL fonts (Poppins, DejaVu Sans Mono)
output/                         - sample pre-rendered slides + where new ones land
.github/workflows/post_tech_news.yml  - the schedule + one-click trigger
.gitignore                      - keeps ig_session.json (unofficial path) out of git
```

## 11. Natural next steps

- Swap `KEYWORD_ALLOWLIST` in `config.py` to narrow feeds to specific beats
  (e.g. only AI, or only hardware).
- Add a second daily run at a different hour for a different beat.
- Automate the 60-day token refresh as its own scheduled workflow.
- A/B test the caption format or slide count against saves/shares once you
  have a few weeks of Instagram Insights data (the Graph API also exposes
  those metrics if you want to close the loop automatically).
