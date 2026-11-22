"""Check an AITA draft written by the daily Claude session and turn it into a render-ready script (no API key).

  python -m autopilot.finalize drafts/01.json --out scripts/2026-11-23/01.json

Draft fields:
  post_title_candidates  3 different "AITA for ..." / "WIBTA if ..." lines, best first - the winner is read aloud
                    first and shown on the card (max 140 chars). yt-script hookscore.py ranks them (blended with
                    your order), because this line is the hook of the Short.
  username          a made-up throwaway handle (no real people)
  narrator          {"gender": "female" | "male", "age": 27}
  body              the story, first person, 380-500 words (about 2:10-2:55)
  closing           optional last line (default "So, am I the a-hole? Tell me in the comments.")
  premise           one line, logged so later stories never repeat it
  title_candidates  10 YouTube titles, best first (not starting with AITA)
  thumb_text        2-4 words the title is checked against (title.py)
  description_first_lines, tags
  search_queries    3 searches this Short should win (yt-seo query test: their words should appear in the title
                    or the first description lines - a warning is printed if they don't)
The youtube-agent-skill title.py lint picks the upload title (lint score first, then your order).
"""
import argparse
import json
import re
from pathlib import Path

from . import common

REQUIRED = ["post_title_candidates", "username", "narrator", "body", "premise", "title_candidates", "thumb_text",
            "description_first_lines", "tags"]


def check(d, cfg) -> list[str]:
    errs = [f"missing field: {k}" for k in REQUIRED if k not in d]
    if errs:
        return errs
    for pt in d["post_title_candidates"]:
        if not re.match(r"^(AITA|WIBTA)\b", pt):
            errs.append(f"post title must start with AITA or WIBTA: {pt[:60]}")
        if len(pt) > 140:
            errs.append(f"post title over 140 characters: {pt[:60]}")
    n = len(d["body"].split())
    if not cfg["body_words_min"] <= n <= cfg["body_words_max"]:
        errs.append(f"body is {n} words; needs {cfg['body_words_min']}-{cfg['body_words_max']}")
    if d["narrator"].get("gender") not in ("female", "male"):
        errs.append("narrator.gender must be female or male")
    if len(d["title_candidates"]) < 5:
        errs.append("need 10 title_candidates")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = common.cfg()
    d = json.loads(Path(a.draft).read_text(encoding="utf-8"))
    errs = check(d, cfg)
    if errs:
        raise SystemExit("draft problems:\n  " + "\n  ".join(errs))
    # yt-script: rank the spoken opening line (the post title) with hookscore.py, blended with the writer's order
    hooks = []
    for rank, h in enumerate(d["post_title_candidates"][:3]):
        r = common.skill_tool("yt-script/hookscore.py", "--hook", h)[0]
        r["blend"] = r["verdict"] + (len(d["post_title_candidates"][:3]) - rank) * 5
        hooks.append(r)
    hooks.sort(key=lambda r: -r["blend"])
    d["post_title"] = hooks[0]["hook"]
    rows = []
    for rank, t in enumerate(d["title_candidates"][:10]):
        r = common.skill_tool("yt-package/title.py", "--title", t, "--thumb", d["thumb_text"])[0]
        r["writer_rank"] = rank
        rows.append(r)
    rows.sort(key=lambda r: (-r["score"], r["writer_rank"]))
    title = rows[0]["title"]
    tags = list(dict.fromkeys([t.lower() for t in d["tags"][:8]] + cfg["default_tags"]))[:15]
    s = {k: d[k] for k in ("post_title", "username", "narrator", "body", "premise")}
    s["closing"] = d.get("closing") or "So, am I the a-hole? Tell me in the comments."
    s["youtube"] = {
        "title": title,
        "description": (f"{d['description_first_lines']}\n\nWhat's your verdict: NTA or YTA? Comment below.\n\n"
                        "Original fiction written for this channel in the style of AITA posts. Gameplay footage is "
                        "from an original runner game made for this channel.\n\n#aita #redditstories #storytime #shorts"),
        "tags": tags,
    }
    s["review"] = {"words": len(d["body"].split()), "title_panel": rows[:3],
                   "hook_panel": [{"hook": r["hook"], "verdict": r["verdict"]} for r in hooks]}
    # yt-seo query test
    visible = (title + " " + d["description_first_lines"]).lower()
    misses = [q for q in d.get("search_queries", [])
              if not all(w in visible for w in re.findall(r"[a-z0-9']+", q.lower()) if len(w) > 3)]
    s["review"]["search_queries"] = d.get("search_queries", [])
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(s, indent=1, ensure_ascii=False))
    print(f"OK {out}  words={s['review']['words']}\n   card : {s['post_title']}  (hook score {hooks[0]['verdict']})"
          f"\n   title: {title}")
    for q in misses:
        print(f"   ! yt-seo: the words of '{q}' are not all in the title or first description lines")


if __name__ == "__main__":
    main()
