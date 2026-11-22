#!/usr/bin/env python3
"""Channel branding v4: Reddit-post look without Reddit's logo - orange-red, an "r/AITA" badge, a post card with
upvote/downvote arrows and a comment bubble. (Reddit's alien "Snoo" logo is a trademark and is not used.)

  python branding/make_branding_v4.py "AITA Daily Shorts"
"""
import argparse
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OR, OR2, WHITE, INK, GREY, DARK = (255, 69, 0), (255, 120, 60), (255, 255, 255), (26, 26, 27), (120, 124, 126), (14, 14, 16)
SS = 2


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), int(size))


def arrow(d, cx, cy, s, fill, up=True, outline=None, width=0):
    k = 1 if up else -1
    pts = [(cx, cy - k * s), (cx + s * 0.95, cy - k * s * 0.02), (cx + s * 0.42, cy - k * s * 0.02),
           (cx + s * 0.42, cy + k * s * 0.85), (cx - s * 0.42, cy + k * s * 0.85), (cx - s * 0.42, cy - k * s * 0.02),
           (cx - s * 0.95, cy - k * s * 0.02)]
    d.polygon(pts, fill=fill, outline=outline, width=width)


def comment_icon(d, x, y, s, color, w):
    d.rounded_rectangle((x, y, x + s * 1.3, y + s), radius=s * 0.3, outline=color, width=w)
    d.polygon([(x + s * 0.25, y + s - w), (x + s * 0.2, y + s * 1.35), (x + s * 0.6, y + s - w)], fill=color)


def r_badge(d, cx, cy, r, bg=OR, fg=WHITE):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
    f = font("Inter-Black.otf", r * 1.05)
    t = "r/"
    tw = d.textlength(t, font=f)
    d.text((cx - tw / 2 + r * 0.04, cy - r * 0.68), t, font=f, fill=fg)


def profile(out):
    S = 800 * SS
    im = Image.new("RGB", (S, S), OR)
    g = Image.linear_gradient("L").resize((S, S))
    im = Image.composite(Image.new("RGB", (S, S), (220, 50, 0)), im, g)
    d = ImageDraw.Draw(im)
    # white speech bubble with AITA?
    x0, y0, x1, y1 = S * 0.13, S * 0.27, S * 0.87, S * 0.66
    d.rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) * 0.3, fill=WHITE)
    d.polygon([(S * 0.28, y1 - 4), (S * 0.24, S * 0.80), (S * 0.43, y1 - 4)], fill=WHITE)
    f = font("Inter-Black.otf", S * 0.2)
    t = "AITA?"
    tw = d.textlength(t, font=f)
    d.text(((S - tw) / 2, y0 + (y1 - y0) * 0.12), t, font=f, fill=OR)
    # small upvote arrow, top right
    arrow(d, S * 0.73, S * 0.2, S * 0.085, WHITE)
    im.resize((800, 800), Image.LANCZOS).save(out, quality=95)


def banner(name, out):
    W, H = 2560 * SS, 1440 * SS
    im = Image.new("RGB", (W, H), DARK)
    # orange glow + scattered faint arrows
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W * 0.2, H * 0.15, W * 0.8, H * 0.85), fill=(255, 69, 0))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(W * 0.08)), 0.38)
    d = ImageDraw.Draw(im)
    rng = random.Random(4)
    for _ in range(90):
        x, y, s = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(26, 60) * SS
        up = rng.random() < 0.75
        c = (70, 34, 20) if up else (34, 34, 60)
        arrow(d, x, y, s, c, up=up)
    # post card in the 1546x423 safe area
    sw, sh = 1546 * SS, 423 * SS
    sx, sy = (W - sw) / 2, (H - sh) / 2
    card = (sx - 10 * SS, sy - 30 * SS, sx + sw + 10 * SS, sy + sh + 30 * SS)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle(card, radius=40 * SS, fill=170)
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, shadow.filter(ImageFilter.GaussianBlur(40 * SS)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(card, radius=40 * SS, fill=WHITE)
    # vote column
    vx = sx + 70 * SS
    arrow(d, vx, sy + sh * 0.2, 38 * SS, OR)
    fv = font("Inter-Black.otf", sh * 0.09)
    t = "NTA"
    d.text((vx - d.textlength(t, font=fv) / 2, sy + sh * 0.34), t, font=fv, fill=OR)
    t = "YTA"
    d.text((vx - d.textlength(t, font=fv) / 2, sy + sh * 0.5), t, font=fv, fill=(113, 147, 255))
    arrow(d, vx, sy + sh * 0.78, 38 * SS, (113, 147, 255), up=False)
    # header: r/ badge, r/AITA, posted by
    hx = sx + 170 * SS
    r_badge(d, hx + 36 * SS, sy + 36 * SS, 36 * SS)
    d.text((hx + 92 * SS, sy + 10 * SS), "r/AITA", font=font("Inter-Black.otf", 40 * SS), fill=INK)
    d.text((hx + 92 * SS + d.textlength("r/AITA ", font=font("Inter-Black.otf", 40 * SS)), sy + 18 * SS),
           "·  Posted daily  ·  Original stories", font=font("Inter-SemiBold.otf", 30 * SS), fill=GREY)
    # title
    title = name.upper()
    size = sh * 0.3
    avail = sx + sw - hx - 40 * SS
    while d.textlength(title, font=font("Inter-Black.otf", size)) > avail:
        size -= 4
    d.text((hx, sy + sh * 0.25), title, font=font("Inter-Black.otf", size), fill=INK)
    d.text((hx + 4 * SS, sy + sh * 0.58), "Am I the A-hole? You be the judge.", font=font("Inter-Bold.otf", sh * 0.1),
           fill=(60, 60, 64))
    # footer: comments / verdict / share
    fy = sy + sh * 0.83
    ff = font("Inter-Bold.otf", sh * 0.072)
    comment_icon(d, hx, fy, 34 * SS, GREY, 5 * SS)
    d.text((hx + 60 * SS, fy - 6 * SS), "Comment your verdict", font=ff, fill=GREY)
    x2 = hx + 60 * SS + d.textlength("Comment your verdict", font=ff) + 60 * SS
    pill = "New Shorts every day"
    pw = d.textlength(pill, font=ff) + 60 * SS
    d.rounded_rectangle((x2, fy - 14 * SS, x2 + pw, fy + 48 * SS), radius=30 * SS, fill=OR)
    d.text((x2 + 30 * SS, fy - 6 * SS), pill, font=ff, fill=WHITE)
    im.resize((2560, 1440), Image.LANCZOS).save(out, quality=93)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    a = ap.parse_args()
    slug = re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-")
    out = Path(__file__).resolve().parent
    profile(out / f"{slug}_profile_v4_800.jpg")
    banner(a.name, out / f"{slug}_banner_v4_2560x1440.jpg")
    print("ok")
