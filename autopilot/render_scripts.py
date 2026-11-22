"""Render every pushed scripts/<date>/ folder that has no daily/<date>/UPLOAD.md yet (GitHub Actions).

Each NN.json becomes daily/<date>/NN-<title>.mp4 (+ .json); UPLOAD.md collects titles, descriptions and tags, and a
GitHub issue links the batch. One failed video never stops the others.
"""
import json
import os
import shutil
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import common
from .common import ROOT

sys.path.insert(0, str(ROOT))


def render_one(path: str, out_dir: str, engine: str, speed: float):
    import make_aita
    story = json.loads(Path(path).read_text(encoding="utf-8"))
    nn = Path(path).stem
    try:
        tmp = make_aita.make(story, Path(out_dir) / f"_{nn}", engine=engine, speed=speed)
        final = Path(out_dir) / f"{nn}-{tmp.name}"
        shutil.move(str(tmp), final)
        shutil.rmtree(Path(out_dir) / f"_{nn}", ignore_errors=True)
        (final.with_suffix(".json")).write_text(json.dumps(story, indent=1, ensure_ascii=False))
        return nn, str(final), None
    except Exception as e:
        traceback.print_exc()
        return nn, None, str(e)[:300]


def upload_md(day, done):
    lines = [f"# AITA Shorts for {day}", "",
             "Upload each video as a Short. Post them in different slots across the day.", ""]
    for nn, path, story in done:
        y = story["youtube"]
        lines += [f"## {Path(path).name}", "", f"**Title:** {y['title']} #shorts", "", "**Description:**", "```",
                  y["description"], "```", "", f"**Tags:** {', '.join(y['tags'])}", ""]
    return "\n".join(lines)


def render_day(d: Path):
    cfg = common.cfg()
    day = d.name
    out = ROOT / "daily" / day
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(d.glob("[0-9]*.json"))
    print(f"== rendering {len(files)} AITA Shorts for {day}", flush=True)
    with ProcessPoolExecutor(int(os.getenv("RENDER_WORKERS", cfg.get("render_workers", 3)))) as ex:
        res = list(ex.map(render_one, [str(f) for f in files], [str(out)] * len(files),
                          [cfg.get("voice_engine", "edge")] * len(files), [cfg.get("speed", 1.12)] * len(files)))
    done, failed = [], []
    for (nn, path, err), f in zip(res, files):
        story = json.loads(f.read_text(encoding="utf-8"))
        if path:
            done.append((nn, path, story))
            print(f"   ✓ {nn}: {Path(path).name}", flush=True)
        else:
            failed.append((nn, err))
            print(f"   ✗ {nn}: {err}", flush=True)
    (out / "UPLOAD.md").write_text(upload_md(day, done))
    s, r = os.getenv("GITHUB_SERVER_URL"), os.getenv("GITHUB_REPOSITORY")
    link = f"{s}/{r}/tree/main/daily/{day}" if s and r else f"daily/{day}"
    body = (f"## {len(done)} AITA Shorts for {day}\n\n| # | Title | Card |\n|---|---|---|\n"
            + "\n".join(f"| {nn} | {st['youtube']['title']} | {st['post_title']} |" for nn, _, st in done)
            + (("\n\n**Failed:**\n" + "\n".join(f"- {nn}: {e}" for nn, e in failed)) if failed else "")
            + f"\n\nVideos and a copy-paste **UPLOAD.md** are in [`daily/{day}/`]({link}).")
    common.create_issue(f"AITA Shorts for {day}", body, ["daily-batch"])
    print(body)


def main():
    pending = sorted(d for d in (ROOT / "scripts").glob("*/") if any(d.glob("[0-9]*.json"))
                     and not (ROOT / "daily" / d.name / "UPLOAD.md").exists())
    if not pending:
        print("nothing to render")
    for d in pending:
        render_day(d)


if __name__ == "__main__":
    main()
