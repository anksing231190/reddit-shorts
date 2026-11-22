#!/usr/bin/env python3
"""Channel profile picture (800x800) and banner (2560x1440, text inside the 1546x423 safe area).

  python branding/make_branding.py "NTA or YTA" --tagline "Original stories. You be the judge."
"""
import argparse
import math
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
ORANGE, PINK, NIGHT, NIGHT2, CREAM = (255, 106, 26), (255, 61, 139), (16, 10, 40), (52, 18, 84), (255, 244, 230)
SS = 2   # supersample for smooth edges


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def gradient(w, h, top, bottom):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        k = y / (h - 1)
        c = tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3))
        for x in range(w):
            px[x, y] = c
    return im


def fast_gradient(w, h, top, bottom):
    col = gradient(1, h, top, bottom)
    return col.resize((w, h))


def gavel(d, cx, cy, s, color):
    """Judge's gavel, tilted, drawn from rounded shapes. s = overall size."""
    ang = math.radians(-35)
    def rot(x, y):
        return (cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang))
    def poly(pts):
        d.polygon([rot(x, y) for x, y in pts], fill=color)
    # head
    poly([(-0.42 * s, -0.36 * s), (0.18 * s, -0.36 * s), (0.18 * s, -0.04 * s), (-0.42 * s, -0.04 * s)])
    for x0 in (-0.48 * s, 0.12 * s):  # rims
        poly([(x0, -0.42 * s), (x0 + 0.12 * s, -0.42 * s), (x0 + 0.12 * s, 0.02 * s), (x0, 0.02 * s)])
    # handle
    poly([(-0.17 * s, -0.04 * s), (-0.07 * s, -0.04 * s), (-0.07 * s, 0.55 * s), (-0.17 * s, 0.55 * s)])
    # sound block
    bx, by = cx + 0.18 * s, cy + 0.42 * s
    d.rounded_rectangle((bx - 0.28 * s, by, bx + 0.28 * s, by + 0.12 * s), radius=0.04 * s, fill=color)


def bubble(d, box, fill, tail="left"):
    x0, y0, x1, y1 = box
    r = (y1 - y0) * 0.28
    d.rounded_rectangle(box, radius=r, fill=fill)
    w = x1 - x0
    if tail == "left":
        d.polygon([(x0 + w * 0.18, y1 - 2), (x0 + w * 0.12, y1 + (y1 - y0) * 0.28), (x0 + w * 0.34, y1 - 2)], fill=fill)


def profile(name, out):
    S = 800 * SS
    im = fast_gradient(S, S, (40, 14, 70), NIGHT)
    d = ImageDraw.Draw(im)
    # glow
    glow = Image.new("RGB", (S, S), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((S * 0.15, S * 0.12, S * 0.85, S * 0.82), fill=(150, 40, 90))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(S * 0.12)), 0.35)
    d = ImageDraw.Draw(im)
    bubble(d, (S * 0.14, S * 0.2, S * 0.86, S * 0.68), ORANGE)
    gavel(d, S * 0.5, S * 0.42, S * 0.36, CREAM)
    # label under the bubble, kept inside the circle crop: shrink to fit, or two lines for long names
    label = re.sub(r"\s+", " ", name).upper()
    lines, size = [label], int(S * 0.12)
    while size > S * 0.075 and d.textlength(label, font=font("Inter-Black.otf", size)) > S * 0.56:
        size -= 4
    if d.textlength(label, font=font("Inter-Black.otf", size)) > S * 0.56:
        words = label.split()
        half = (len(words) + 1) // 2
        lines, size = [" ".join(words[:half]), " ".join(words[half:])], int(S * 0.08)
        while size > 20 and max(d.textlength(l, font=font("Inter-Black.otf", size)) for l in lines) > S * 0.5:
            size -= 4
    f = font("Inter-Black.otf", size)
    y = S * (0.71 if len(lines) == 1 else 0.70)
    for l in lines:
        tw = d.textlength(l, font=f)
        d.text(((S - tw) / 2, y), l, font=f, fill=CREAM, stroke_width=int(S * 0.008), stroke_fill=NIGHT)
        y += size * 1.05
    im.resize((800, 800), Image.LANCZOS).save(out, quality=95)


def skyline(d, W, base, rng, color, hmin, hmax, win=None):
    x = -20
    while x < W:
        w = rng.randint(60, 170)
        h = rng.randint(hmin, hmax)
        d.rectangle((x, base - h, x + w, base), fill=color)
        if win:
            for wy in range(int(base - h + 18), int(base - 16), 34):
                for wx in range(int(x + 14), int(x + w - 18), 30):
                    if rng.random() < 0.45:
                        d.rectangle((wx, wy, wx + 12, wy + 16), fill=win)
        x += w + rng.randint(-10, 14)


def banner(name, tagline, out):
    W, H = 2560 * SS, 1440 * SS
    im = fast_gradient(W, H, (12, 6, 34), (120, 30, 96))
    d = ImageDraw.Draw(im)
    rng = random.Random(7)
    # stars
    for _ in range(420):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H * 0.55), rng.uniform(1, 3.2) * SS
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255))
    # sun glow behind the centre
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W * 0.36, H * 0.42, W * 0.64, H * 0.9), fill=(255, 90, 120))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(W * 0.05)), 0.45)
    d = ImageDraw.Draw(im)
    skyline(d, W, H * 0.86, rng, (44, 20, 82), 160 * SS, 420 * SS, win=(255, 214, 120))
    skyline(d, W, H, rng, (22, 10, 48), 120 * SS, 300 * SS, win=(94, 242, 255))
    # rails converging to the centre (runner-game nod)
    for side in (-1, 1):
        for off in (0.03, 0.09):
            d.line((W / 2 + side * W * off, H, W / 2 + side * W * 0.008, H * 0.78), fill=(200, 214, 255), width=5 * SS)
    # safe area: 1546x423 centred
    sw, sh = 1546 * SS, 423 * SS
    sx, sy = (W - sw) / 2, (H - sh) / 2
    # dark plate for legibility
    plate = Image.new("L", (W, H), 0)
    ImageDraw.Draw(plate).rounded_rectangle((sx - 20 * SS, sy - 10 * SS, sx + sw + 20 * SS, sy + sh + 10 * SS),
                                            radius=60 * SS, fill=150)
    im = Image.composite(Image.new("RGB", (W, H), (10, 6, 26)), im, plate.filter(ImageFilter.GaussianBlur(40 * SS)))
    d = ImageDraw.Draw(im)
    # icon bubble on the left of the title
    ib = sh * 0.62
    bx0, by0 = sx + 40 * SS, sy + (sh - ib) / 2 - 20 * SS
    bubble(d, (bx0, by0, bx0 + ib * 1.15, by0 + ib * 0.85), ORANGE)
    gavel(d, bx0 + ib * 0.575, by0 + ib * 0.4, ib * 0.62, CREAM)
    tx = bx0 + ib * 1.15 + 60 * SS
    avail = sx + sw - tx - 30 * SS
    size = int(sh * 0.36)
    while True:
        f = font("Inter-Black.otf", size)
        if d.textlength(name.upper(), font=f) <= avail or size < 40:
            break
        size -= 4
    d.text((tx, sy + sh * 0.14), name.upper(), font=f, fill=CREAM, stroke_width=4 * SS, stroke_fill=(40, 10, 50))
    f2 = font("Inter-Bold.otf", int(sh * 0.12))
    d.text((tx + 6 * SS, sy + sh * 0.62), tagline, font=f2, fill=(255, 190, 140))
    f3 = font("Inter-SemiBold.otf", int(sh * 0.085))
    d.text((tx + 6 * SS, sy + sh * 0.8), "New Shorts every day  ·  NTA or YTA? Comment your verdict", font=f3,
           fill=(220, 210, 255))
    im.resize((2560, 1440), Image.LANCZOS).save(out, quality=93)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--tagline", default="Original stories. You be the judge.")
    ap.add_argument("--out", default=str(ROOT / "branding"))
    a = ap.parse_args()
    slug = re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    profile(a.name, out / f"{slug}_profile_800.jpg")
    banner(a.name, a.tagline, out / f"{slug}_banner_2560x1440.jpg")
    print("ok", slug)
