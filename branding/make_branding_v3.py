#!/usr/bin/env python3
"""Channel branding v3 (photoreal character via --art): the shrugging woman ("did I do something wrong?"), an "AITA?" speech bubble and a
Reddit-style orange upvote arrow (a generic shape - not Reddit's logo).

  python branding/make_branding_v2.py "AITA Daily Shorts"

Character: Microsoft Fluent Emoji 3D "woman shrugging" (MIT licence, branding/assets/FLUENT-EMOJI-LICENSE.txt).
"""
import argparse
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
ART = Path(__file__).resolve().parent / "assets" / "woman_shrugging_3d_medium.png"   # replaced by --art
ORANGE, CREAM, NIGHT = (255, 87, 34), (255, 246, 236), (20, 10, 44)
SS = 2


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def vgrad(w, h, top, bottom):
    return Image.linear_gradient("L").resize((w, h)).point(lambda v: v).convert("L"), top, bottom


def gradient(w, h, top, bottom):
    m = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), m)


def woman(height):
    im = Image.open(ART).convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w = int(im.width * height / im.height)
    return im.resize((w, height), Image.LANCZOS)


def shadow(img, blur, opacity=120):
    a = img.split()[3].filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: v * opacity // 255))
    return sh


def upvote(d, cx, cy, s, fill):
    """Rounded upvote arrow (generic up-arrow shape)."""
    pts = [(cx, cy - s), (cx + s * 0.9, cy - s * 0.05), (cx + s * 0.42, cy - s * 0.05), (cx + s * 0.42, cy + s * 0.8),
           (cx - s * 0.42, cy + s * 0.8), (cx - s * 0.42, cy - s * 0.05), (cx - s * 0.9, cy - s * 0.05)]
    d.polygon(pts, fill=fill)


def bubble(d, box, text, f, fill=ORANGE, color=CREAM, tail="right"):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=(y1 - y0) * 0.35, fill=fill)
    w, h = x1 - x0, y1 - y0
    if tail == "right":
        d.polygon([(x0 + w * 0.62, y1 - 2), (x0 + w * 0.80, y1 + h * 0.42), (x0 + w * 0.84, y1 - 2)], fill=fill)
    else:
        d.polygon([(x0 + w * 0.16, y1 - 2), (x0 + w * 0.20, y1 + h * 0.42), (x0 + w * 0.38, y1 - 2)], fill=fill)
    tw = d.textlength(text, font=f)
    d.text((x0 + (w - tw) / 2, y0 + h * 0.13), text, font=f, fill=color)


def profile(name, out):
    S = 800 * SS
    im = gradient(S, S, (74, 28, 120), NIGHT).convert("RGBA")
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((S * 0.16, S * 0.3, S * 0.84, S * 0.98), fill=(255, 110, 60, 140))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S * 0.08)))
    wm = woman(int(S * 0.74))
    pos = (int((S - wm.width) / 2), int(S - wm.height))
    im.alpha_composite(shadow(wm, 18 * SS), (pos[0] + 6 * SS, pos[1] + 12 * SS))
    im.alpha_composite(wm, pos)
    d = ImageDraw.Draw(im)
    bubble(d, (S * 0.24, S * 0.10, S * 0.66, S * 0.30), "AITA?", font("Inter-Black.otf", int(S * 0.115)), tail="right")
    upvote(d, S * 0.76, S * 0.21, S * 0.075, ORANGE)
    im.convert("RGB").resize((800, 800), Image.LANCZOS).save(out, quality=95)


def skyline(d, W, base, rng, color, hmin, hmax, win):
    x = -20
    while x < W:
        w, h = rng.randint(60, 170), rng.randint(hmin, hmax)
        d.rectangle((x, base - h, x + w, base), fill=color)
        for wy in range(int(base - h + 18), int(base - 16), 34):
            for wx in range(int(x + 14), int(x + w - 18), 30):
                if rng.random() < 0.42:
                    d.rectangle((wx, wy, wx + 12, wy + 16), fill=win)
        x += w + rng.randint(-10, 14)


def banner(name, tagline, out):
    W, H = 2560 * SS, 1440 * SS
    im = gradient(W, H, (14, 6, 36), (126, 34, 98)).convert("RGBA")
    d = ImageDraw.Draw(im)
    rng = random.Random(11)
    for _ in range(380):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H * 0.5), rng.uniform(1, 3) * SS
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 255))
    skyline(d, W, H * 0.88, rng, (46, 20, 84), 150 * SS, 380 * SS, (255, 214, 120))
    skyline(d, W, H, rng, (24, 10, 50), 110 * SS, 260 * SS, (94, 242, 255))
    sw, sh = 1546 * SS, 423 * SS
    sx, sy = (W - sw) / 2, (H - sh) / 2
    plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle((sx - 30 * SS, sy - 20 * SS, sx + sw + 30 * SS, sy + sh + 20 * SS),
                                            radius=70 * SS, fill=(12, 6, 30, 185))
    im.alpha_composite(plate.filter(ImageFilter.GaussianBlur(30 * SS)))
    # the woman, left side of the safe area
    wm = woman(int(sh * 1.18))
    wx, wy = int(sx + 10 * SS), int(sy + sh + 20 * SS - wm.height)
    im.alpha_composite(shadow(wm, 14 * SS), (wx + 6 * SS, wy + 10 * SS))
    im.alpha_composite(wm, (wx, wy))
    d = ImageDraw.Draw(im)
    tx = max(wx + wm.width + 40 * SS, sx + sh * 1.05)
    avail = sx + sw - tx - 20 * SS
    # small "AITA?" bubble + upvote above the title
    fb = font("Inter-Black.otf", int(sh * 0.12))
    bubble(d, (tx, sy + sh * 0.02, tx + sh * 0.62, sy + sh * 0.2), "AITA?", fb, tail="left")
    upvote(d, tx + sh * 0.78, sy + sh * 0.11, sh * 0.075, ORANGE)
    size = int(sh * 0.27)
    while d.textlength(name.upper(), font=font("Inter-Black.otf", size)) > avail and size > 40:
        size -= 4
    d.text((tx, sy + sh * 0.27), name.upper(), font=font("Inter-Black.otf", size), fill=CREAM,
           stroke_width=4 * SS, stroke_fill=(40, 10, 50))
    d.text((tx + 4 * SS, sy + sh * 0.62), tagline, font=font("Inter-Bold.otf", int(sh * 0.11)), fill=(255, 176, 120))
    # NTA / YTA vote chips
    f3 = font("Inter-Black.otf", int(sh * 0.075))
    cx = tx + 4 * SS
    for label, col in (("NTA", (46, 196, 120)), ("YTA", (233, 54, 80)), ("Comment your verdict", None)):
        if col:
            w = d.textlength(label, font=f3) + 60 * SS
            d.rounded_rectangle((cx, sy + sh * 0.81, cx + w, sy + sh * 0.97), radius=30 * SS, fill=col)
            d.text((cx + 30 * SS, sy + sh * 0.825), label, font=f3, fill=CREAM)
            cx += w + 24 * SS
        else:
            d.text((cx + 8 * SS, sy + sh * 0.835), label, font=font("Inter-SemiBold.otf", int(sh * 0.07)),
                   fill=(225, 214, 255))
    im.convert("RGB").resize((2560, 1440), Image.LANCZOS).save(out, quality=93)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--art", help="cut-out PNG of the character (transparent background)")
    ap.add_argument("--suffix", default="v2")
    ap.add_argument("--tagline", default="Original stories. New Shorts every day.")
    a = ap.parse_args()
    if a.art:
        ART = Path(a.art)
    slug = re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-")
    out = Path(__file__).resolve().parent / ("v3" if a.suffix.startswith("v3") else "")
    out.mkdir(exist_ok=True)
    profile(a.name, out / f"{slug}_profile_{a.suffix}_800.jpg")
    banner(a.name, a.tagline, out / f"{slug}_banner_{a.suffix}_2560x1440.jpg")
    print("ok")
