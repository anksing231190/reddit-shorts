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
    finish_day(day, out, done, failed, cfg)


def pending_days():
    return sorted(d for d in (ROOT / "scripts").glob("*/") if any(d.glob("[0-9]*.json"))
                  and not (ROOT / "daily" / d.name / "UPLOAD.md").exists())


# ---- parallel mode (GitHub Actions matrix): plan -> one job per video -> publish
def cmd_plan():
    files = [str(f.relative_to(ROOT)) for d in pending_days() for f in sorted(d.glob("[0-9]*.json"))]
    print(json.dumps(files))
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"files={json.dumps(files)}\n")


def cmd_one(rel: str):
    cfg = common.cfg()
    f = ROOT / rel
    out = ROOT / "out" / f.parent.name
    out.mkdir(parents=True, exist_ok=True)
    nn, path, err = render_one(str(f), str(out), cfg.get("voice_engine", "edge"), cfg.get("speed", 1.12))
    if err:
        (out / f"{nn}.failed").write_text(err)
        raise SystemExit(f"{nn} failed: {err}")
    print(f"   ✓ {nn}: {Path(path).name}")


def cmd_publish():
    cfg = common.cfg()
    for d in pending_days():
        day, src, out = d.name, ROOT / "out" / d.name, ROOT / "daily" / d.name
        out.mkdir(parents=True, exist_ok=True)
        done, failed = [], []
        for f in sorted(d.glob("[0-9]*.json")):
            nn = f.stem
            vids = sorted(src.glob(f"{nn}-*.mp4")) if src.exists() else []
            if vids:
                for p in (vids[0], vids[0].with_suffix(".json")):
                    if p.exists():
                        shutil.move(str(p), out / p.name)
                done.append((nn, str(out / vids[0].name), json.loads(f.read_text(encoding="utf-8"))))
            else:
                err = (src / f"{nn}.failed").read_text() if (src / f"{nn}.failed").exists() else "render job failed"
                failed.append((nn, err))
        finish_day(day, out, done, failed, cfg)
    catch_up_uploads()


def finish_day(day, out, done, failed, cfg):
    (out / "UPLOAD.md").write_text(upload_md(day, done))
    s, r = os.getenv("GITHUB_SERVER_URL"), os.getenv("GITHUB_REPOSITORY")
    link = f"{s}/{r}/tree/main/daily/{day}" if s and r else f"daily/{day}"
    body = (f"## {len(done)} AITA Shorts for {day}\n\n| # | Title | Card |\n|---|---|---|\n"
            + "\n".join(f"| {nn} | {st['youtube']['title']} | {st['post_title']} |" for nn, _, st in done)
            + (("\n\n**Failed:**\n" + "\n".join(f"- {nn}: {e}" for nn, e in failed)) if failed else "")
            + f"\n\nVideos and a copy-paste **UPLOAD.md** are in [`daily/{day}/`]({link}).")
    from . import upload
    try:
        ups = upload.upload_day(out)
    except Exception as e:  # never lose the rendered day because of an upload problem
        ups = [f"✗ upload failed: {str(e)[:300]}"]
    if ups:
        body += "\n\n**YouTube:**\n" + "\n".join(f"- {m}" for m in ups)
    elif upload.ready(cfg):
        body += f"\n\nNot uploaded to YouTube: {upload.ready(cfg)}."
    common.create_issue(f"AITA Shorts for {day}", body, ["daily-batch"])
    print(body)


def catch_up_uploads():
    """Days rendered before YouTube was connected (or whose upload hit the daily quota) get uploaded now."""
    from . import upload
    if not upload.ready(common.cfg()):
        for day in sorted((ROOT / "daily").glob("*/"))[-3:]:
            if (day / "UPLOAD.md").exists():
                upload.upload_day(day)


def main():
    if len(sys.argv) > 1:
        {"plan": lambda: cmd_plan(), "one": lambda: cmd_one(sys.argv[2]), "publish": lambda: cmd_publish()}[sys.argv[1]]()
        return
    pending = sorted(d for d in (ROOT / "scripts").glob("*/") if any(d.glob("[0-9]*.json"))
                     and not (ROOT / "daily" / d.name / "UPLOAD.md").exists())
    if not pending:
        print("nothing to render")
    for d in pending:
        render_day(d)
    catch_up_uploads()


if __name__ == "__main__":
    main()
