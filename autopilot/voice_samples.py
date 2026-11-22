"""Render the same AITA excerpt in every free Microsoft voice so you can pick one by ear (runs in GitHub Actions,
where the voice service is reachable). Output: samples/voices/<voice>_<speed>.mp3 + samples/voices/README.md

  python -m autopilot.voice_samples
"""
import subprocess
import tempfile
from pathlib import Path

from rshorts import tts

from .common import ROOT

TEXT = ("Am I the a-hole for refusing to give up my window seat to a mom who booked the middle seat on purpose? "
        "I paid extra for the window because I get motion sick. Before the doors even closed, she tapped my shoulder "
        "and said her son really wanted the window, so I should swap. I said no, politely. She rolled her eyes and "
        "said, it's a kid, have some compassion. Then the flight attendant checked the seat map and said, ma'am, you "
        "chose these seats yourself yesterday.")
SPEEDS = [1.12, 1.25]
LABEL = {"christopher": "deep, serious male", "guy": "friendly male", "andrew": "warm, natural male",
         "brian": "casual young male", "eric": "clear male", "aria": "expressive female", "jenny": "friendly female",
         "ava": "bright, natural female", "emma": "calm female", "ryan": "British male", "sonia": "British female"}


def main():
    out = ROOT / "samples" / "voices"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in tts.EDGE_VOICES:
        for sp in SPEEDS:
            f = out / f"{name}_{sp:.2f}.mp3"
            try:
                s = tts.synthesize(TEXT, "edge", name, sp)
                with tempfile.TemporaryDirectory() as td:
                    wav = Path(td) / "v.wav"
                    tts.save_wav(s, wav)
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(f)],
                                   check=True)
                rows.append(f"| {name} | {LABEL.get(name, '')} | {sp:.2f}x | [{f.name}]({f.name}) | {s.duration:.0f}s |")
                print("ok", f.name, flush=True)
            except Exception as e:
                rows.append(f"| {name} | {LABEL.get(name, '')} | {sp:.2f}x | failed: {str(e)[:80]} | |")
                print("failed", name, sp, e, flush=True)
    (out / "README.md").write_text(
        "# Voice samples\n\nThe same AITA excerpt in every free Microsoft voice. 1.12x is the current Shorts speed; "
        "1.25x is faster, like many viral Reddit channels.\nOpen a file and press the download/play button to listen. "
        "Tell Claude which one you want (name and speed).\n\n| Voice | Sound | Speed | File | Length |\n|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
