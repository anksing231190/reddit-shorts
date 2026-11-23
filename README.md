# Reddit-style AITA Shorts Autopilot

Every day a scheduled Claude session writes **5 original AITA-style stories** and pushes them to `scripts/<date>/`.
The push starts GitHub Actions, which renders each one into a **1080×1920, 60 fps YouTube Short** and commits it to
`daily/<date>/` with a copy-paste `UPLOAD.md`.

```
05:13 IST  Claude session ─► 5 new stories (never repeated, see state/aita_log.json) ─► title.py picks upload titles
           ─► push scripts/<date>/ ─► Actions: narration + card + captions + runner gameplay ─► daily/<date>/
```

## What each Short looks like
- **Story card** ("r/AITA", a throwaway username, the "AITA for…" title) while the title is read out.
- **Word-by-word captions**, big and outlined, current word highlighted.
- **Background: an original endless-runner game** (`rshorts/runner.py`): a three-lane railway through a city, trains
  to dodge, barriers to jump, coin trails, score and coin counter. The camera follows the runner. It's drawn with smooth
  vector graphics straight at 1080×1920, 60 fps, in a random theme (`neon`, `sunset`, `day`), and is different in
  every video. Nothing is taken from any real game, so there's no copyright risk.
- **Voice:** Microsoft neural voices (female or male to match the narrator), offline Kokoro voice as a fallback.

## Files per day
```
daily/2026-11-23/
  01-she-wanted-my-window-seat-for-free.mp4   (+ .json with the script)
  ...
  UPLOAD.md                                   titles, descriptions and tags to paste
```

## Try it locally
```bash
pip install -r requirements.txt
```
```bash
python make_aita.py story_samples/aita_sample.json --out output/
```
```bash
python -m rshorts.runner output/gameplay.mp4 --seconds 10 --theme neon
```

## Notes
- Stories are original fiction written in the AITA format. Each description says so.
- Each Short is about 30–60 MB. Expect about 7 GB of video a month; start a fresh repo every month or two, or move
  old videos to Releases.
- GitHub Actions: about 20 minutes a day, about 600 minutes a month (private repos get 2,000 free).

## Automatic YouTube upload (one-time setup)
Uploading is off until these are done (`upload_to_youtube` in `autopilot/config.json`).
1. **Google Cloud project:** at <https://console.cloud.google.com> create a project, then enable **YouTube Data API v3**
   and **YouTube Analytics API** (APIs & Services → Library).
2. **OAuth consent screen:** choose External, fill in the app name and your email, add the scopes `youtube.upload`,
   `youtube.force-ssl` and `yt-analytics.readonly`. Then click **Publish app** ("In production"). In Testing mode the
   login expires every 7 days and uploads stop.
3. **Credentials → Create OAuth client ID → Desktop app.** Copy the client ID and client secret.
4. **On your computer** (once): clone this repo, install Python packages, and sign in with the channel's Google account:
   `pip install requests` then `python -m autopilot.auth_setup --client-id <ID> --client-secret <SECRET>`.
   Your browser opens; Google warns the app is unverified (it's your own app): Advanced → Go to app → Allow.
   The terminal prints a refresh token.
5. **GitHub secrets** (Settings → Secrets and variables → Actions → New repository secret): `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. Set `"upload_to_youtube": true` in `autopilot/config.json` (or ask the daily Claude session to).

Each Short is uploaded **private with a scheduled publish time** (`publish_slots`: 06:30, 10:30, 17:30, 20:30, 23:30
US Pacific time), so YouTube makes one public per slot. Until then you can edit or delete it in YouTube Studio.

**Important: YouTube API audit.** Google keeps videos uploaded through the API **locked to private** for apps it hasn't
audited (all new projects). Apply at the "YouTube API Services - Audit and Quota Extension Form" (search that name).
It's free and usually takes a few weeks. Until it's approved, uploads arrive as private and you make them public in
Studio yourself.

**Quota:** the free 10,000 units a day allow 6 uploads per Google Cloud project, so 5 Shorts a day fits. Use a separate
project for each channel.
