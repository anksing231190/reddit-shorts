#!/usr/bin/env python3
"""AITA story (JSON) -> one 1080x1920 60 fps YouTube Short over original runner-game gameplay.

  python make_aita.py scripts/2026-11-23/01.json --out output/
  python make_aita.py story.json --engine kokoro          # offline voice

Story JSON (written by the daily Claude session, checked by autopilot/finalize.py):
  {"post_title": "AITA for ...", "username": "throwaway_...", "narrator": {"gender": "female", "age": 28},
   "body": "...", "closing": "So, am I the a-hole?", "youtube": {"title": ..., "description": ..., "tags": [...]}}
"""
from __future__ import annotations

import argparse
import json
import random
import re
import tempfile
from pathlib import Path

from rshorts import render, runner, text, tts

ROOT = Path(__file__).resolve().parent
VOICES = {"female": ["ava", "jenny", "emma", "aria"], "male": ["andrew", "brian", "guy", "christopher"]}
KOKORO = {"female": "af_heart", "male": "am_michael"}
render.FPS = 60


def slug(s: str, n=50) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n] or "story"


def make(story: dict, out_dir: Path, *, engine="edge", speed=1.12, seed=None, theme=None) -> Path:
    seed = seed if seed is not None else sum(map(ord, story["post_title"]))
    rng = random.Random(seed)
    gender = story.get("narrator", {}).get("gender", "female")
    gender = gender if gender in VOICES else "female"
    voice = rng.choice(VOICES[gender]) if engine == "edge" else KOKORO[gender]
    title_spoken = text.clean(story["post_title"], drop_edits=False)
    body = text.clean(story["body"])
    closing = story.get("closing") or "So, am I the a-hole? Tell me in the comments."

    def say(s):
        try:
            return tts.synthesize(s, engine, voice, speed)
        except Exception as e:  # Microsoft voice unreachable -> offline voice, never a failed day
            print(f"  ! {engine} voice failed ({str(e)[:80]}), using the offline voice")
            return tts.synthesize(s, "kokoro", KOKORO[gender], speed)

    t_speech, b_speech, c_speech = say(title_spoken), say(body), say(closing)
    voice = f"{voice} (or offline fallback)" if engine == "edge" else voice
    speech, offs = tts.concat([0.15, t_speech, 0.45, b_speech, 0.35, c_speech, 0.3])
    card_end, body_start = offs[2] + 0.2, offs[3]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slug(story['youtube']['title'] if story.get('youtube') else story['post_title'])}.mp4"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        wav = td / "narration.wav"
        tts.save_wav(speech, wav)
        card = render.title_card(story["post_title"], "AITA", story.get("username", "throwaway_account"), 0, 0,
                                 td / "card.png", footer="Original story  ·  What's your verdict?")
        ass = render.captions_ass(speech.words, td / "captions.ass", start_after=body_start, y=700)
        bg = td / "gameplay.mp4"
        print(f"  🎮 gameplay {speech.duration + 1.5:.0f}s (seed {seed}) ...", flush=True)
        runner.render(str(bg), speech.duration + 1.5, seed=seed, theme=theme, fps=60, crf=16, preset="veryfast")
        print(f"  🎞  compose {speech.duration:.1f}s  voice={voice}", flush=True)
        render.compose(narration_wav=wav, duration=speech.duration, ass=ass, card_png=card, card_end=card_end,
                       out=out, background=bg, music=None, crf=19, preset="fast")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story")
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--engine", default="edge", choices=["edge", "kokoro"])
    ap.add_argument("--speed", type=float, default=1.12)
    ap.add_argument("--theme", choices=list(runner.THEMES))
    a = ap.parse_args()
    story = json.loads(Path(a.story).read_text(encoding="utf-8"))
    print(make(story, Path(a.out), engine=a.engine, speed=a.speed, theme=a.theme))


if __name__ == "__main__":
    main()
