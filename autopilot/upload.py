"""Upload a rendered day to YouTube as scheduled Shorts (runs in GitHub Actions after rendering).

Each video goes up PRIVATE with a publishAt time, so YouTube makes it public by itself at its slot - one Short per
slot (config publish_slots_ist). Until then you can still edit or delete it in YouTube Studio.
Already-uploaded videos are recorded in state/uploads.json and never uploaded twice.

  python -m autopilot.upload daily/2026-11-23        # normally called by render_scripts
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from . import common, youtube

IST = ZoneInfo("Asia/Kolkata")


def ready(cfg) -> str | None:
    if not cfg.get("upload_to_youtube"):
        return "upload_to_youtube is false in autopilot/config.json"
    if not common.has_youtube_secrets():
        return "YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN secrets are not set"
    return None


def free_slots(cfg, k: int, taken: set[str]) -> list[dt.datetime]:
    """Next k publish times (from now + 20 min) that no earlier upload has booked."""
    now = dt.datetime.now(IST) + dt.timedelta(minutes=20)
    out, day = [], now.date()
    while len(out) < k:
        for s in cfg["publish_slots_ist"]:
            h, m = map(int, s.split(":"))
            t = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
            iso = t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            if t > now and iso not in taken and len(out) < k:
                out.append(t)
        day += dt.timedelta(days=1)
    return out


def upload_day(day_dir: Path) -> list[str]:
    cfg = common.cfg()
    why = ready(cfg)
    if why:
        print(f"YouTube upload skipped: {why}")
        return []
    log = common.load("uploads.json", [])
    done = {e["file"] for e in log}
    taken = {e["publish_at"] for e in log}
    todo = [p for p in sorted(day_dir.glob("[0-9][0-9]-*.mp4")) if str(p.relative_to(common.ROOT)) not in done]
    msgs = []
    for p, slot in zip(todo, free_slots(cfg, len(todo), taken)):
        s = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
        y = s["youtube"]
        at = slot.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        try:
            vid = youtube.upload(p, f"{y['title']} #shorts", y["description"], y["tags"], category="24",
                                 privacy="private", publish_at=at)
        except Exception as e:
            msgs.append(f"✗ {p.name}: {str(e)[:200]}")
            print(msgs[-1], flush=True)
            if "quota" in str(e).lower():
                break
            continue
        log.append({"file": str(p.relative_to(common.ROOT)), "video_id": vid, "title": y["title"], "publish_at": at})
        common.save("uploads.json", log)
        msgs.append(f"✔ {y['title']} - goes public {slot:%a %d %b %H:%M} IST - https://youtube.com/shorts/{vid}")
        print(msgs[-1], flush=True)
    return msgs


if __name__ == "__main__":
    for m in upload_day(Path(sys.argv[1]).resolve()):
        pass
