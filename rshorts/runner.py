"""Original endless-runner gameplay, rendered as background footage for story Shorts.

A pseudo-3D three-lane track seen from behind the runner: rails and sleepers, city blocks on both sides, trains to
dodge, barriers to jump, coin trails to collect, a HUD with score and coins. Everything is drawn with cairo (smooth
anti-aliased vector shapes) straight at 1080x1920 and piped to ffmpeg - no game assets, nothing copied, never the same
twice (every video gets its own seed, theme and level).

  python -m rshorts.runner out.mp4 --seconds 20 --seed 7 --theme neon
"""
from __future__ import annotations

import argparse
import math
import random
import subprocess
from dataclasses import dataclass

import cairocffi as cairo

W, H = 1080, 1920
HORIZON = 0.34 * H
CAM_H = 2.3                  # camera height above the track (world units) - behind-and-above view
F = (H - HORIZON) * 2.6 / CAM_H   # focal length: the ground at the bottom edge is z = 2.6
Z_NEAR, Z_FAR = 1.7, 75.0
LANE = 1.25                  # lane spacing
RUNNER_Z = 4.3               # runner depth

THEMES = {
    "neon": dict(sky=[(0, "#0b0624"), (0.55, "#3a0f5c"), (1, "#ff3d8b")], sun="#ffd166", fog="#ff5ea8",
                 ground="#16122b", ground2="#211a3d", rail="#c9d6ff", sleeper="#3b3260",
                 blocks=["#2a1f55", "#3a1f66", "#1f2e6b", "#4a1d5e"], window="#ffe27a", window2="#5ef2ff",
                 train=["#ff3d6e", "#21d4fd", "#ffb627", "#7cff6b"], hero="#ff7a1a", hero2="#1f2b55",
                 barrier=("#ffffff", "#ff2e63"), hud="#ffffff"),
    "sunset": dict(sky=[(0, "#1d2b64"), (0.5, "#f8657a"), (1, "#ffd27a")], sun="#fff2b0", fog="#ffb88a",
                   ground="#3d2a3f", ground2="#4b3350", rail="#fff1e0", sleeper="#6a4a4f",
                   blocks=["#6b3f69", "#874f6e", "#4f4a7a", "#a0566a"], window="#ffe6a8", window2="#ffd0e0",
                   train=["#2ec4b6", "#e71d36", "#3a86ff", "#ff9f1c"], hero="#00b4d8", hero2="#2b2d42",
                   barrier=("#ffffff", "#e63946"), hud="#ffffff"),
    "day": dict(sky=[(0, "#2f80ed"), (0.6, "#6fc3ff"), (1, "#d6f1ff")], sun="#fffbe0", fog="#cfefff",
                ground="#5b6b7a", ground2="#6b7d8c", rail="#f4f7fb", sleeper="#7a5c48",
                blocks=["#e07a5f", "#3d405b", "#81b29a", "#f2cc8f", "#6d6875"], window="#cfe8ff", window2="#ffffff",
                train=["#ef476f", "#118ab2", "#06d6a0", "#ffd166"], hero="#ef233c", hero2="#14213d",
                barrier=("#ffffff", "#f77f00"), hud="#ffffff"),
}


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


CAM = {"x": 0.0}   # the camera slides sideways with the runner's lane, like in runner games


def proj(x, y, z):
    """world (x right, y up, z forward) -> screen; camera at (CAM.x, CAM_H, 0)."""
    s = F / z
    return W / 2 + (x - CAM["x"]) * s, HORIZON + (CAM_H - y) * s, s


@dataclass
class Obj:
    z: float          # world z of the near face (in track distance)
    lane: int
    kind: str         # train | barrier | coin
    length: float = 0.0
    color: int = 0
    taken: bool = False


class Level:
    """Endless level generated in chunks; every chunk leaves at least one lane free and puts coins in it."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.objs: list[Obj] = []
        self.plan: list[tuple[float, int]] = [(0.0, 1)]   # (distance, lane the runner should be in from there)
        self.jumps: list[float] = []
        self.end = 20.0
        self.free = 1

    def extend(self, upto):
        r = self.rng
        while self.end < upto:
            z0 = self.end
            free = self.free if r.random() < 0.45 else r.choice([l for l in range(3) if abs(l - self.free) <= 1] or [1])
            if free != self.free:
                self.plan.append((z0 - 9.0, free))   # switch lanes a little before the obstacles arrive
                self.free = free
            blocked = [l for l in range(3) if l != free]
            for l in blocked:
                if r.random() < 0.75:
                    self.objs.append(Obj(z0 + r.uniform(0, 3), l, "train", r.uniform(7, 14), r.randrange(4)))
            if r.random() < 0.35:   # a barrier in the free lane -> the runner jumps it
                zb = z0 + r.uniform(5, 9)
                self.objs.append(Obj(zb, free, "barrier"))
                self.jumps.append(zb)
            else:
                for k in range(r.randint(5, 8)):
                    self.objs.append(Obj(z0 + 1.5 + k * 1.6, free, "coin"))
            self.end = z0 + r.uniform(17, 24)

    def lane_at(self, d):
        cur = self.plan[0][1]
        prev, t0 = cur, -99.0
        for pd, ln in self.plan:
            if pd <= d:
                prev, cur, t0 = cur, ln, pd
        return prev, cur, t0


def sky(cr, th):
    g = cairo.LinearGradient(0, 0, 0, HORIZON + 40)
    for off, c in th["sky"]:
        g.add_color_stop_rgba(off, *hexc(c))
    cr.set_source(g)
    cr.rectangle(0, 0, W, HORIZON + 40)
    cr.fill()
    # sun / moon glow
    sx, sy = W * 0.5, HORIZON - 150
    rg = cairo.RadialGradient(sx, sy, 10, sx, sy, 520)
    rg.add_color_stop_rgba(0, *hexc(th["sun"], 0.9))
    rg.add_color_stop_rgba(0.18, *hexc(th["sun"], 0.55))
    rg.add_color_stop_rgba(1, *hexc(th["sun"], 0))
    cr.set_source(rg)
    cr.arc(sx, sy, 520, 0, 2 * math.pi)
    cr.fill()
    cr.set_source_rgba(*hexc(th["sun"], 0.95))
    cr.arc(sx, sy, 95, 0, 2 * math.pi)
    cr.fill()


class Skyline:
    def __init__(self, rng, th):
        self.th = th
        self.layers = []
        for depth, (hmin, hmax, shade) in enumerate(((120, 330, 0.55), (180, 480, 0.8))):
            x, bs = -60, []
            while x < W + 60:
                w = rng.uniform(60, 150)
                h = rng.uniform(hmin, hmax)
                wins = [(rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9), rng.random()) for _ in range(int(w * h / 1800))]
                bs.append((x, w, h, wins))
                x += w + rng.uniform(-10, 20)
            self.layers.append((shade, bs))

    def draw(self, cr, t):
        for shade, bs in self.layers:
            base = HORIZON + 40
            col = hexc(self.th["blocks"][0])
            cr.set_source_rgba(col[0] * shade, col[1] * shade, col[2] * shade, 1)
            for x, w, h, _ in bs:
                cr.rectangle(x, base - h, w, h)
            cr.fill()
            for x, w, h, wins in bs:
                for wx, wy, ph in wins:
                    on = 0.5 + 0.5 * math.sin(t * 1.3 + ph * 40)
                    if on > 0.35:
                        cr.set_source_rgba(*hexc(self.th["window"], 0.35 + 0.4 * on * shade))
                        cr.rectangle(x + wx * (w - 8), base - h + wy * (h - 10), 6, 8)
                        cr.fill()


def quad(cr, pts, rgba):
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.close_path()
    cr.set_source_rgba(*rgba)
    cr.fill()


def box(cr, x0, x1, y0, y1, z0, z1, front, side_shade=0.72, top_shade=1.18, windows=None, show_front=True):
    """Axis-aligned box seen from the camera: front face at z0, side face toward the camera, top face."""
    a = [proj(x0, y0, z0), proj(x1, y0, z0), proj(x1, y1, z0), proj(x0, y1, z0)]
    b = [proj(x0, y0, z1), proj(x1, y0, z1), proj(x1, y1, z1), proj(x0, y1, z1)]
    f = hexc(front) if isinstance(front, str) else front
    shade = lambda k: (min(1, f[0] * k), min(1, f[1] * k), min(1, f[2] * k), f[3])
    # side face (the one facing the centre of the track)
    if x1 < CAM["x"]:
        quad(cr, [a[1][:2], b[1][:2], b[2][:2], a[2][:2]], shade(side_shade))
    elif x0 > CAM["x"]:
        quad(cr, [a[0][:2], b[0][:2], b[3][:2], a[3][:2]], shade(side_shade))
    if y1 < CAM_H:   # top visible
        quad(cr, [a[3][:2], a[2][:2], b[2][:2], b[3][:2]], shade(top_shade))
    if not show_front:
        return
    quad(cr, [p[:2] for p in a], f)
    if windows:
        cols, rows, col_a, col_b, seed = windows
        fx0, fy0 = a[0][:2]
        fx1, fy1 = a[2][:2]
        wdt, hgt = fx1 - fx0, fy0 - fy1
        if wdt > 6:
            rr = random.Random(seed)
            for c in range(cols):
                for r_ in range(rows):
                    v = rr.random()
                    if v < 0.55:
                        continue
                    cr.set_source_rgba(*hexc(col_a if v < 0.85 else col_b, 0.9))
                    cr.rectangle(fx0 + wdt * (c + 0.25) / cols, fy1 + hgt * (r_ + 0.25) / rows,
                                 wdt * 0.5 / cols, hgt * 0.5 / rows)
                    cr.fill()


def track(cr, th, dist):
    # ground plane
    g = cairo.LinearGradient(0, HORIZON, 0, H)
    g.add_color_stop_rgba(0, *hexc(th["fog"], 1))
    g.add_color_stop_rgba(0.08, *hexc(th["ground2"]))
    g.add_color_stop_rgba(1, *hexc(th["ground"]))
    cr.set_source(g)
    cr.rectangle(0, HORIZON, W, H - HORIZON)
    cr.fill()
    half = 1.5 * LANE + 0.35
    far, near = proj(0, 0, Z_FAR), proj(0, 0, Z_NEAR)
    # gravel bed
    quad(cr, [proj(-half, 0, Z_NEAR)[:2], proj(half, 0, Z_NEAR)[:2], proj(half, 0, Z_FAR)[:2], proj(-half, 0, Z_FAR)[:2]],
         hexc(th["ground2"]))
    # sleepers, far to near
    step = 0.9
    k0 = math.floor(dist / step)
    zs = [(k * step - dist) for k in range(k0 + 1, k0 + int(Z_FAR / step))]
    for z in reversed(zs):
        if z < Z_NEAR:
            continue
        for ln in (-1, 0, 1):
            cx = ln * LANE
            p = [proj(cx - 0.52, 0, z)[:2], proj(cx + 0.52, 0, z)[:2], proj(cx + 0.52, 0, z + 0.22)[:2],
                 proj(cx - 0.52, 0, z + 0.22)[:2]]
            quad(cr, p, hexc(th["sleeper"]))
    # rails
    for ln in (-1, 0, 1):
        for side in (-0.36, 0.36):
            x = ln * LANE + side
            a, b = proj(x, 0.04, Z_NEAR), proj(x, 0.04, Z_FAR)
            cr.move_to(a[0], a[1])
            cr.line_to(b[0], b[1])
            cr.set_source_rgba(*hexc(th["rail"], 0.95))
            cr.set_line_width(7)
            cr.stroke()
    # fog at the horizon
    fg = cairo.LinearGradient(0, HORIZON, 0, HORIZON + 160)
    fg.add_color_stop_rgba(0, *hexc(th["fog"], 0.85))
    fg.add_color_stop_rgba(1, *hexc(th["fog"], 0))
    cr.set_source(fg)
    cr.rectangle(0, HORIZON, W, 160)
    cr.fill()


class Sides:
    """City blocks along both sides of the track."""

    def __init__(self, rng, th):
        self.rng, self.th = rng, th
        self.blocks = {}

    def get(self, i, side):
        key = (i, side)
        if key not in self.blocks:
            r = random.Random(hash(key) ^ 0x5EED)
            self.blocks[key] = dict(h=r.uniform(2.5, 9), w=r.uniform(1.8, 3.2), depth=r.uniform(2.5, 4.2),
                                    color=r.choice(self.th["blocks"]), gap=r.random() < 0.15,
                                    cols=r.randint(2, 4), rows=r.randint(3, 8), seed=r.randrange(1 << 30))
        return self.blocks[key]

    def draw(self, cr, dist):
        spacing = 4.6
        k0 = math.floor(dist / spacing)
        items = []
        for k in range(k0, k0 + int(Z_FAR / spacing) + 1):
            z = k * spacing - dist
            for side in (-1, 1):
                b = self.get(k, side)
                if b["gap"] or z + b["depth"] < Z_NEAR:
                    continue
                items.append((z, side, b))
        for z, side, b in sorted(items, key=lambda it: -it[0]):
            z0 = max(z, Z_NEAR)
            inner = 1.5 * LANE + 1.1
            x0, x1 = (inner, inner + b["w"]) if side > 0 else (-inner - b["w"], -inner)
            box(cr, x0, x1, 0, b["h"], z0, z0 + b["depth"], b["color"],
                windows=(b["cols"], b["rows"], self.th["window"], self.th["window2"], b["seed"]))


def draw_train(cr, th, o, z):
    x = (o.lane - 1) * LANE
    z0 = max(z, Z_NEAR)
    col = th["train"][o.color]
    passed = z < Z_NEAR + 0.05   # its nose is already behind the camera: only the side and roof are visible
    box(cr, x - 0.58, x + 0.58, 0.05, 1.55, z0, z + o.length, col, side_shade=0.6, top_shade=1.25, show_front=not passed)
    if passed:
        return
    # front face details: windshield, stripe, headlights
    a, b = proj(x - 0.58, 1.55, z0), proj(x + 0.58, 0.05, z0)
    wdt, hgt = b[0] - a[0], b[1] - a[1]
    cr.set_source_rgba(0.08, 0.1, 0.16, 0.95)
    cr.rectangle(a[0] + wdt * 0.12, a[1] + hgt * 0.12, wdt * 0.76, hgt * 0.3)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.85)
    cr.rectangle(a[0], a[1] + hgt * 0.6, wdt, hgt * 0.07)
    cr.fill()
    for fx in (0.2, 0.8):
        cr.set_source_rgba(1, 0.95, 0.7, 1)
        cr.arc(a[0] + wdt * fx, a[1] + hgt * 0.8, max(2, wdt * 0.06), 0, 2 * math.pi)
        cr.fill()


def draw_barrier(cr, th, o, z):
    x = (o.lane - 1) * LANE
    c1, c2 = th["barrier"]
    for px in (-0.48, 0.42):
        box(cr, x + px, x + px + 0.06, 0, 0.55, z, z + 0.06, "#cccccc")
    a, b = proj(x - 0.55, 0.62, z), proj(x + 0.55, 0.36, z)
    wdt, hgt = b[0] - a[0], b[1] - a[1]
    cr.set_source_rgba(*hexc(c1))
    cr.rectangle(a[0], a[1], wdt, hgt)
    cr.fill()
    cr.set_source_rgba(*hexc(c2))
    n = 5
    for i in range(n):
        x0 = a[0] + wdt * i / n
        cr.move_to(x0, a[1] + hgt)
        cr.line_to(x0 + wdt / n * 0.5, a[1])
        cr.line_to(x0 + wdt / n, a[1])
        cr.line_to(x0 + wdt / n * 0.5, a[1] + hgt)
        cr.close_path()
        cr.fill()


def draw_coin(cr, o, z, t):
    x = (o.lane - 1) * LANE
    sx, sy, s = proj(x, 0.55, z)
    r = 0.22 * s
    spin = abs(math.cos(t * 5 + o.z))
    glow = cairo.RadialGradient(sx, sy, r * 0.2, sx, sy, r * 2.2)
    glow.add_color_stop_rgba(0, 1, 0.9, 0.3, 0.55)
    glow.add_color_stop_rgba(1, 1, 0.8, 0.2, 0)
    cr.set_source(glow)
    cr.arc(sx, sy, r * 2.2, 0, 2 * math.pi)
    cr.fill()
    cr.save()
    cr.translate(sx, sy)
    cr.scale(max(0.15, spin), 1)
    cr.set_source_rgba(1, 0.78, 0.1, 1)
    cr.arc(0, 0, r, 0, 2 * math.pi)
    cr.fill()
    cr.set_source_rgba(1, 0.93, 0.45, 1)
    cr.arc(0, 0, r * 0.68, 0, 2 * math.pi)
    cr.fill()
    cr.restore()


def draw_runner(cr, th, x_world, y_jump, t, roll):
    """Stylised runner seen from behind: sneakers, jeans, hoodie, cap, backpack."""
    sx, sy, s = proj(x_world, 0, RUNNER_Z)
    u = s * 1.15 / 125.0   # the figure is ~125 units tall = 1.15 world units
    # shadow
    cr.set_source_rgba(0, 0, 0, 0.35 * max(0.2, 1 - y_jump))
    cr.save()
    cr.translate(sx, sy)
    cr.scale(1, 0.28)
    cr.arc(0, 0, 38 * u * (1 - 0.3 * y_jump), 0, 2 * math.pi)
    cr.restore()
    cr.fill()
    base = sy - y_jump * s
    ph = t * 11.0
    swing = math.sin(ph) * (0.2 if y_jump > 0.05 else 1.0)
    hero, hero2 = hexc(th["hero"]), hexc(th["hero2"])
    lw = 13 * u

    def limb(x0, y0, ang, l1, l2, bend, col, width):
        cr.set_source_rgba(*col)
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        x1, y1 = x0 + math.sin(ang) * l1 * 0.35, y0 + math.cos(ang) * l1
        x2, y2 = x1 + math.sin(ang + bend) * l2 * 0.35, y1 + math.cos(ang + bend) * l2
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.line_to(x2, y2)
        cr.stroke()
        return x2, y2

    hip_y = base - 92 * u
    # legs (back view: the forward leg looks shorter as it lifts)
    for side, ph_ in ((-1, swing), (1, -swing)):
        lift = max(0, ph_) * 26 * u
        fx, fy = limb(sx + side * 11 * u, hip_y, 0, 46 * u - lift * 0.5, 44 * u - lift * 0.6, 0, (0.16, 0.22, 0.42, 1), lw * 1.25)
        cr.set_source_rgba(1, 1, 1, 1)                                  # sneaker
        cr.save()
        cr.translate(fx, fy + 4 * u)
        cr.scale(1.0, 0.6)
        cr.arc(0, 0, 13 * u, 0, 2 * math.pi)
        cr.restore()
        cr.fill()
        cr.set_source_rgba(*hero)
        cr.rectangle(fx - 12 * u, fy + 4 * u, 24 * u, 3 * u)
        cr.fill()
    # torso (hoodie) + backpack
    cr.set_source_rgba(*hero)
    cr.move_to(sx - 30 * u, hip_y + 4 * u)
    cr.curve_to(sx - 36 * u, hip_y - 40 * u, sx - 30 * u, hip_y - 66 * u, sx - 20 * u, hip_y - 72 * u)
    cr.line_to(sx + 20 * u, hip_y - 72 * u)
    cr.curve_to(sx + 30 * u, hip_y - 66 * u, sx + 36 * u, hip_y - 40 * u, sx + 30 * u, hip_y + 4 * u)
    cr.close_path()
    cr.fill()
    cr.set_source_rgba(*hero2)
    cr.rectangle(sx - 18 * u, hip_y - 58 * u, 36 * u, 44 * u)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.25)
    cr.rectangle(sx - 18 * u, hip_y - 58 * u, 36 * u, 6 * u)
    cr.fill()
    # arms swing opposite to legs
    for side, ph_ in ((-1, -swing), (1, swing)):
        limb(sx + side * 28 * u, hip_y - 64 * u, side * 0.35 + ph_ * 0.5, 30 * u, 28 * u, -side * 0.2, hero, lw * 1.05)
    # head, cap, headphones
    hy = hip_y - 92 * u
    cr.set_source_rgba(0.36, 0.22, 0.14, 1)
    cr.arc(sx, hy, 19 * u, 0, 2 * math.pi)
    cr.fill()
    cr.set_source_rgba(*hero2)
    cr.arc(sx, hy - 4 * u, 20 * u, math.pi, 2 * math.pi)
    cr.fill()
    cr.rectangle(sx - 20 * u, hy - 5 * u, 40 * u, 5 * u)
    cr.fill()
    cr.set_source_rgba(0.1, 0.1, 0.12, 1)
    cr.set_line_width(4 * u)
    cr.arc(sx, hy - 2 * u, 22 * u, math.pi * 1.05, math.pi * 1.95)
    cr.stroke()
    for side in (-1, 1):
        cr.arc(sx + side * 21 * u, hy + 2 * u, 6 * u, 0, 2 * math.pi)
        cr.fill()


def hud(cr, th, score, coins, pops):
    cr.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    # score (top right) and coin counter
    for i, (label, val) in enumerate((("", f"{score:07d}"), ("coin", f"{coins}"))):
        y = 150 + i * 86
        cr.set_font_size(58 if i == 0 else 50)
        ext = cr.text_extents(val)
        x = W - 60 - ext[2]
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.rectangle(x - (90 if label else 24), y - 62, ext[2] + (114 if label else 48), 78)
        cr.fill()
        if label:
            cr.set_source_rgba(1, 0.78, 0.1, 1)
            cr.arc(x - 44, y - 22, 22, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgba(1, 0.93, 0.45, 1)
            cr.arc(x - 44, y - 22, 14, 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgba(*hexc(th["hud"]))
        cr.move_to(x, y)
        cr.show_text(val)
    for (px, py, age) in pops:   # "+1" pops where coins were collected
        cr.set_font_size(54)
        cr.set_source_rgba(1, 0.9, 0.3, max(0, 1 - age / 0.6))
        cr.move_to(px, py - age * 160)
        cr.show_text("+1")


def speed_lines(cr, rng, t, strength):
    cr.set_line_width(3)
    for i in range(26):
        a = rng.uniform(0, 2 * math.pi)
        r0 = (rng.uniform(0.35, 0.9) + t * 2.5 * (1 + i % 3)) % 1.0
        r0 = 0.45 + r0 * 0.9
        cx, cy = W / 2, HORIZON + 60
        x0, y0 = cx + math.cos(a) * r0 * W, cy + math.sin(a) * r0 * H * 0.7
        x1, y1 = cx + math.cos(a) * (r0 + 0.12) * W, cy + math.sin(a) * (r0 + 0.12) * H * 0.7
        cr.set_source_rgba(1, 1, 1, 0.10 * strength)
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.stroke()


def vignette(cr):
    g = cairo.RadialGradient(W / 2, H * 0.55, H * 0.35, W / 2, H * 0.55, H * 0.85)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.45)
    cr.set_source(g)
    cr.rectangle(0, 0, W, H)
    cr.fill()


def render(out: str, seconds: float, seed: int = 1, theme: str | None = None, fps: int = 60, crf: int = 18,
           preset: str = "veryfast"):
    rng = random.Random(seed)
    th = THEMES[theme or rng.choice(list(THEMES))]
    level, skyline, sides = Level(seed), Skyline(rng, th), Sides(rng, th)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    dist, coins, score, pops = 0.0, 0, 0, []
    line_rng = random.Random(seed + 3)
    for f in range(int(seconds * fps)):
        t = f / fps
        speed = 13.0 + min(t, 90) * 0.06
        dist += speed / fps
        score += int(speed * 3)
        level.extend(dist + Z_FAR + 30)
        # runner lane (smooth switch) and jump arc
        prev, cur, t_sw = level.lane_at(dist + RUNNER_Z)
        k = min(1.0, max(0.0, (dist + RUNNER_Z - t_sw) / 4.0))
        k = k * k * (3 - 2 * k)
        x_r = ((prev + (cur - prev) * k) - 1) * LANE
        CAM["x"] = x_r * 0.8
        y_j = 0.0
        for zb in level.jumps:
            dj = (dist + RUNNER_Z) - (zb - 2.2)
            if 0 <= dj <= 5.0:
                y_j = max(y_j, math.sin(math.pi * dj / 5.0) * 1.1)
        # collect coins
        for o in level.objs:
            if o.kind == "coin" and not o.taken and abs((o.z - dist) - RUNNER_Z) < 0.5 and abs((o.lane - 1) * LANE - x_r) < 0.6:
                o.taken = True
                coins += 1
                px, py, _ = proj(x_r, 1.2, RUNNER_Z)
                pops.append([px + 30, py, 0.0])
        pops = [[x, y, a + 1 / fps] for x, y, a in pops if a < 0.6]
        level.objs = [o for o in level.objs if o.z - dist + (o.length or 1) > Z_NEAR - 1]

        sky(cr, th)
        skyline.draw(cr, t)
        track(cr, th, dist)
        sides.draw(cr, dist)
        vis = sorted([o for o in level.objs if Z_NEAR - (o.length or 0.5) < o.z - dist < Z_FAR and not o.taken],
                     key=lambda o: -(o.z - dist))
        behind = [o for o in vis if o.z - dist >= RUNNER_Z - 0.3]
        front = [o for o in vis if o.z - dist < RUNNER_Z - 0.3]
        for group, draw_r in ((behind, True), (front, False)):
            for o in group:
                z = o.z - dist
                if o.kind == "train":
                    draw_train(cr, th, o, z)
                elif o.kind == "barrier":
                    draw_barrier(cr, th, o, max(z, Z_NEAR))
                elif z > Z_NEAR:
                    draw_coin(cr, o, z, t)
            if draw_r:
                draw_runner(cr, th, x_r, y_j, t, False)
        speed_lines(cr, line_rng, t, min(1.0, (speed - 12) / 4))
        vignette(cr)
        hud(cr, th, score, coins, pops)
        surf.flush()
        ff.stdin.write(bytes(surf.get_data()))
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError("runner encode failed")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--theme", choices=list(THEMES))
    ap.add_argument("--fps", type=int, default=60)
    a = ap.parse_args()
    render(a.out, a.seconds, a.seed, a.theme, a.fps)
