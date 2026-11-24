"""Posting plan: how many Shorts a day, at which times, changing on set dates (config "plan").

  "plan": [{"from": "2026-11-24", "slots": ["07:30", "08:30", "09:30", "10:30"]},
           {"from": "2026-12-07", "slots": ["07:30", "09:00", "10:30"]},
           {"from": "2026-12-21", "slots": ["08:00", "10:00"]}]

Each publish day uses the slots of the last entry whose "from" <= that day (falls back to "publish_slots").

  python -m autopilot.plan            # prints how many Shorts the next batch should have: the free slots of the
                                      # first publish day that still has room (the day the next batch will fill)
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from . import common


def slots_for(cfg: dict, day: dt.date) -> list[str]:
    best = None
    for p in cfg.get("plan") or []:
        if p["from"] <= day.isoformat():
            best = p["slots"]
    return best or cfg.get("publish_slots") or cfg.get("publish_slots_ist") or []


def taken_slots() -> set[str]:
    return {e["publish_at"] for e in common.load("uploads.json", []) if e.get("publish_at") and e.get("status") not in ("public", "private")}


def next_batch_size(cfg: dict | None = None, lead_minutes: int = 60) -> int:
    cfg = cfg or common.cfg()
    tz = ZoneInfo(cfg.get("publish_timezone") or "Asia/Kolkata")
    now = dt.datetime.now(tz) + dt.timedelta(minutes=lead_minutes)   # render + upload take ~40 min
    taken = taken_slots()
    day = now.date()
    for _ in range(60):
        free = 0
        for s in slots_for(cfg, day):
            h, m = map(int, s.split(":"))
            t = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            if t > now and t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") not in taken:
                free += 1
        if free:
            return free
        day += dt.timedelta(days=1)
    return len(slots_for(cfg, day)) or 2


if __name__ == "__main__":
    print(next_batch_size())
