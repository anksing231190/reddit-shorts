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
import os
import random
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from rshorts import render, runner, text, tts

ROOT = Path(__file__).resolve().parent
VOICES = {"female": ["ava", "jenny", "emma", "aria"], "male": ["andrew", "brian", "guy", "christopher"]}
KOKORO = {"female": "af_heart", "male": "am_michael"}
render.FPS = 60
FPS = 60
MAX_BYTES = 95 * 1024 * 1024   # GitHub rejects files over 100 MB


def compose_live(seconds, seed, theme, wav, ass, card, card_end, out: Path, maxrate="4000k", crf=21):
    """Gameplay frames go straight from the renderer into this single encode (named pipe): one compression pass,
    about a third less time than encoding the gameplay first and the final video again."""
    work = ass.parent
    fifo = work / "game.raw"
    os.mkfifo(fifo)
    total = seconds
    fade_out = max(card_end - 0.25, 0.1)
    fc = (f"[0:v]format=yuv420p,eq=saturation=1.05[bg];"
          f"[2:v]format=rgba,fade=t=out:st={fade_out:.2f}:d=0.25:alpha=1[card];"   # card fully visible on frame 1
          f"[bg][card]overlay=(W-w)/2:(H-h)/2-60:enable='lte(t,{card_end:.2f})':shortest=0[v1];"
          f"[v1]ass={ass.name}:fontsdir={render.FONTS.as_posix()}[v];[1:a]apad[a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{runner.W}x{runner.H}", "-r", str(FPS), "-i", fifo.name,
           "-i", str(wav), "-loop", "1", "-framerate", str(FPS), "-i", str(card),
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", str(crf),
           "-maxrate", maxrate, "-bufsize", str(int(maxrate[:-1]) * 2) + "k", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out.resolve())]
    ff = subprocess.Popen(cmd, cwd=work)
    err = []

    def feed():
        try:
            with open(fifo, "wb") as sink:
                runner.render(None, total + 0.2, seed=seed, theme=theme, fps=FPS, sink=sink)
        except BrokenPipeError:
            pass   # ffmpeg stopped reading at -t
        except Exception as e:
            err.append(e)

    th = threading.Thread(target=feed)
    th.start()
    th.join()
    if ff.wait() or err:
        raise RuntimeError(f"encode failed {err[:1]}")
    if out.stat().st_size > MAX_BYTES:   # safety net: re-encode at a bitrate that fits
        kbps = int(MAX_BYTES * 8 / 1024 / total) - 200
        tmp = out.with_suffix(".tmp.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-c:v", "libx264", "-preset", "veryfast",
                        "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k", "-c:a", "copy",
                        "-movflags", "+faststart", str(tmp)], check=True)
        tmp.replace(out)
    return out


def slug(s: str, n=50) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n] or "story"


def make(story: dict, out_dir: Path, *, engine="edge", speed=1.25, seed=None, theme=None) -> Path:
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
    est = t_speech.duration + b_speech.duration + c_speech.duration + 2.0
    if est > 176:   # over 3:00 YouTube treats it as a normal video, not a Short: read a little faster to fit
        speed = round(speed * est / 172, 3)
        print(f"  ! {est:.0f}s is too long for a Short - re-reading at {speed}x", flush=True)
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
                                 td / "card.png", footer="Fictional story  ·  What's your verdict?")
        ass = render.captions_ass(speech.words, td / "captions.ass", start_after=body_start, y=700,
                                 label="Fictional story · not a real post")
        print(f"  🎮 gameplay + encode {speech.duration:.0f}s (seed {seed}, voice {voice}) ...", flush=True)
        compose_live(speech.duration + 0.8, seed, theme, wav, ass, card, card_end, out)
        # thumbnail = the opening frame (gameplay + the Reddit-style story card), set as the custom thumbnail on upload
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(1.0, card_end / 2):.2f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "3", str(out.with_suffix(".jpg"))], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story")
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--engine", default="edge", choices=["edge", "kokoro"])
    ap.add_argument("--speed", type=float, default=1.25)
    ap.add_argument("--theme", choices=list(runner.THEMES))
    a = ap.parse_args()
    story = json.loads(Path(a.story).read_text(encoding="utf-8"))
    print(make(story, Path(a.out), engine=a.engine, speed=a.speed, theme=a.theme))


if __name__ == "__main__":
    main()
