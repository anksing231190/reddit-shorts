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
