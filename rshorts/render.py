"""Compose the final 1080x1920 short: background + title card + karaoke captions + narration."""
from __future__ import annotations

import random
import re
import shutil
import subprocess
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .tts import Word

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
W, H, FPS = 1080, 1920, 30   # FPS is set to 60 by make_aita.py
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def _font(name: str, size: int):
    return ImageFont.truetype(str(FONTS / name), size)


def _fmt_count(n: int) -> str:
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


# ------------------------------------------------------------- title card
def title_card(title: str, subreddit: str, author: str, score: int, comments: int, out: Path,
               dark: bool = False, accent: str = "#ff4500", footer: str | None = None) -> Path:
    """Story card. With `footer`, that text replaces the vote/comment counts (used for original stories)."""
    cw, pad = 940, 44
    bg, fg, sub_fg = ("#1a1a1b", "#f0f0f0", "#9a9a9a") if dark else ("#ffffff", "#111111", "#7c7c7c")
    f_title, f_sub, f_meta = _font("Inter-Bold.otf", 54), _font("Inter-Bold.otf", 36), _font("Inter-SemiBold.otf", 30)

    # wrap title
    d0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines, cur = [], ""
    for word in title.split():
        test = f"{cur} {word}".strip()
        if d0.textlength(test, font=f_title) <= cw - 2 * pad:
            cur = test
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    lines = lines[:7]
    lh = 66
    ch = pad + 84 + 30 + len(lines) * lh + 30 + 50 + pad

    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=36, fill=bg)
    # avatar
    d.ellipse((pad, pad, pad + 84, pad + 84), fill=accent)
    initial = subreddit[:1].upper()
    d.text((pad + 42, pad + 42), initial, font=_font("Inter-Black.otf", 46), fill="white", anchor="mm")
    d.text((pad + 104, pad + 4), f"r/{subreddit}", font=f_sub, fill=fg)
    d.text((pad + 104, pad + 48), f"u/{author}", font=f_meta, fill=sub_fg)
    # title
    y = pad + 84 + 30
    for ln in lines:
        d.text((pad, y), ln, font=f_title, fill=fg)
        y += lh
    y += 30
    if footer:
        d.text((pad, y + 20), footer, font=f_meta, fill=sub_fg, anchor="lm")
        img.save(out)
        return out
    # footer: upvote arrow + count, comment bubble + count
    x = pad
    d.polygon([(x + 18, y), (x + 36, y + 22), (x + 26, y + 22), (x + 26, y + 40), (x + 10, y + 40), (x + 10, y + 22),
               (x, y + 22)], fill=accent)
    d.text((x + 50, y + 20), _fmt_count(score), font=f_meta, fill=sub_fg, anchor="lm")
    x += 50 + d.textlength(_fmt_count(score), font=f_meta) + 50
    d.rounded_rectangle((x, y + 2, x + 40, y + 32), radius=10, outline=sub_fg, width=4)
    d.polygon([(x + 8, y + 30), (x + 8, y + 42), (x + 20, y + 30)], fill=sub_fg)
    d.text((x + 54, y + 20), _fmt_count(comments), font=f_meta, fill=sub_fg, anchor="lm")
    img.save(out)
    return out


# ---------------------------------------------------------------- captions
def _ass_time(t: float) -> str:
    t = max(t, 0)
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean_cap(s: str) -> str:
    return re.sub(r"[{}\\]", "", s).strip().strip('"“”')


def group_words(words: list[Word], max_words=3, max_chars=16) -> list[list[Word]]:
    groups, cur = [], []
    for w in words:
        if not _clean_cap(w.text):
            continue
        n_chars = sum(len(x.text) + 1 for x in cur) + len(w.text)
        if cur and (len(cur) >= max_words or n_chars > max_chars or w.start - cur[-1].end > 0.35):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?,;:]$", w.text):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def captions_ass(words: list[Word], out: Path, *, start_after: float = 0.0, upper=True,
                 highlight="&H0000E5FF", size=100, y=1060) -> Path:
    """Big, bold, outlined captions; current spoken word is highlighted and each group pops in."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Black,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,9,4,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    words = [w for w in words if w.start >= start_after - 0.01]
    groups = group_words(words)
    for gi, g in enumerate(groups):
        g_end = groups[gi + 1][0].start if gi + 1 < len(groups) else g[-1].end + 0.5
        g_end = min(g_end, g[-1].end + 0.6)
        toks = [_clean_cap(w.text) for w in g]
        if upper:
            toks = [t.upper() for t in toks]
        for wi, w in enumerate(g):
            s = w.start
            e = g[wi + 1].start if wi + 1 < len(g) else g_end
            parts = [f"{{\\c{highlight}}}{t}{{\\c&H00FFFFFF&}}" if j == wi else t for j, t in enumerate(toks)]
            pop = "{\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Cap,,0,0,0,,{{\\pos({W // 2},{y})}}{pop}"
                         + " ".join(parts))
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return out


# -------------------------------------------------------------- background
def probe_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def pick_file(folder: Path, exts: set[str]) -> Path | None:
    files = [p for p in folder.glob("**/*") if p.suffix.lower() in exts] if folder.exists() else []
    return random.choice(files) if files else None


def _bg_input(bg: Path | None, duration: float) -> list[str]:
    if bg is None:  # procedural fallback
        return ["-f", "lavfi", "-i",
                f"gradients=s=540x960:r={FPS}:speed=0.012:n=5:type=spiral:"
                f"c0=0x12002b:c1=0x3a0ca3:c2=0x7209b7:c3=0x0d1b2a:c4=0x240046,format=yuv420p"]
    length = probe_duration(bg)
    if length > duration + 2:
        start = random.uniform(0, length - duration - 1)
        return ["-ss", f"{start:.2f}", "-i", str(bg)]
    return ["-stream_loop", "-1", "-i", str(bg)]


def montage(folder: Path, duration: float, out: Path, seg=(7.0, 14.0)) -> Path:
    """Stitch random segments of the short clips in `folder` into one 9:16 background >= duration."""
    files = [p for p in folder.glob("**/*") if p.suffix.lower() in VIDEO_EXT]
    lengths = {f: probe_duration(f) for f in files}
    segments, t, last = [], 0.0, None
    while t < duration + 1:
        choices = [f for f in files if f != last] or files
        f = random.choice(choices)
        n = min(random.uniform(*seg), lengths[f] - 0.2)
        if n < 2:
            files.remove(f)
            if not files:
                raise RuntimeError(f"no usable clips in {folder}")
            continue
        segments.append((f, random.uniform(0, max(lengths[f] - n - 0.1, 0)), n))
        t += n
        last = f
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    fc = []
    for i, (f, start, n) in enumerate(segments):
        cmd += ["-ss", f"{start:.2f}", "-t", f"{n:.2f}", "-i", str(f)]
        fc.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                  f"fps={FPS},format=yuv420p[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=1:a=0[v]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", str(out)]
    subprocess.run(cmd, check=True)
    return out


# ----------------------------------------------------------------- compose
def compose(*, narration_wav: Path, duration: float, ass: Path, card_png: Path, card_end: float,
            out: Path, background: Path | None, music: Path | None, music_volume=0.10, crf=20, preset="veryfast"):
    work = ass.parent
    total = duration + 0.8
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    cmd += _bg_input(background, total)
    cmd += ["-i", str(narration_wav), "-loop", "1", "-framerate", str(FPS), "-i", str(card_png)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    fade_out = max(card_end - 0.25, 0.1)
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},"
        f"eq=brightness=-0.04:saturation=1.1[bg];"
        f"[2:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1,fade=t=out:st={fade_out:.2f}:d=0.25:alpha=1[card];"
        f"[bg][card]overlay=(W-w)/2:(H-h)/2-60:enable='lte(t,{card_end:.2f})':shortest=0[v1];"
        f"[v1]ass={ass.name}:fontsdir={FONTS.as_posix().replace(':', chr(92) + ':')}[v]"
    )
    if music:
        fc += (f";[3:a]volume={music_volume},afade=t=out:st={total - 1.2:.2f}:d=1.2[m];"
               f"[1:a]apad[n];[n][m]amix=inputs=2:duration=shortest:normalize=0[a]")
    else:
        fc += ";[1:a]apad[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out.resolve())]
    # run from the work dir so the ass= path needs no escaping (Windows drive letters etc.)
    subprocess.run(cmd, check=True, cwd=work)
    return out


def check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg/ffprobe not found on PATH. Install it: https://ffmpeg.org/download.html")
