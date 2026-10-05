#!/usr/bin/env python3
"""Render "Never sleep in the Nether": a fast, loopable YouTube Short about bed explosions and bed mining.

Built for retention: an explosion inside the first second, 1-2 word captions, a cut or punch every beat,
an open loop ("pros do this on purpose") paid off at the end, and a last frame that matches the first so
the Short replays seamlessly ("Just remember..." -> "Never sleep in the Nether.").

Reuses the voxel renderer, text helpers and Kokoro narration from ../infinite_water/make_short.py.

    python shorts/nether_bed/make_short.py      # -> shorts/nether_bed/nether_bed_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("voxel", HERE.parent / "infinite_water" / "make_short.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
OUT = HERE / "nether_bed_short.mp4"
VOICE, SPEED = "af_heart", 1.15
ease, ramp, clamp01, lerp = V.ease, V.ramp, V.clamp01, V.lerp

LINES = [
    ("never", "Never sleep in the Nether."),
    ("explode", "Beds explode here, and the blast is bigger than TNT."),
    ("killer", "The game even names your killer:"),
    ("igd", "Intentional Game Design."),
    ("purpose", "But pros do this on purpose."),
    ("debris", "Ancient debris is blast proof. So you blow up a bed,"),
    ("boom", "and only the netherite ore survives."),
    ("cheap", "Way cheaper than TNT. Just remember,"),
]
GAP = 0.06

RED, ORANGE, YELLOW, GREEN, WHITE = (255, 70, 60), (255, 150, 40), (255, 222, 60), (110, 240, 120), (255, 255, 255)
PURPLE = (200, 140, 255)
KEYWORDS = {
    "never": RED, "sleep": RED, "explode": ORANGE, "bigger": YELLOW, "tnt": RED, "killer": RED,
    "intentional": YELLOW, "game": YELLOW, "design": YELLOW, "purpose": YELLOW, "ancient": PURPLE,
    "debris": PURPLE, "proof": GREEN, "bed": RED, "netherite": PURPLE, "survives": GREEN,
    "cheaper": GREEN, "remember": YELLOW,
}  # fmt: skip


# ----------------------------------------------------------------------------------------- textures
def _noise(rng, base, var):
    return np.array(base, float)[None, None, :] + rng.integers(-var, var + 1, (16, 16, 1))


def make_textures():
    rng = np.random.default_rng(11)
    r, c = np.mgrid[0:16, 0:16]
    T = V.TEX

    nr = _noise(rng, (138, 52, 48), 14)
    nr[rng.random((16, 16)) < 0.18] = (100, 32, 32)
    nr[rng.random((16, 16)) < 0.10] = (172, 80, 72)
    T["netherrack"] = [V._rgba(nr)]

    top = _noise(rng, (92, 64, 58), 8)
    d = np.hypot(r - 7.5, c - 7.5)
    for k in (2.2, 5.0):
        top[np.abs(d - k) < 0.75] = (134, 102, 90)
    top[d < 1.0] = (66, 44, 42)
    T["debris_top"] = [V._rgba(top)]
    side = _noise(rng, (88, 60, 56), 8)
    side[(c + 2.2 * np.sin(r * 0.7)) % 5 < 1.1] = (138, 106, 94)
    side[r < 2] = (70, 48, 46)
    T["debris_side"] = [V._rgba(side)]

    wool = _noise(rng, (164, 34, 38), 9)
    foot = wool.copy()
    foot[(r == 0) | (r == 15) | (c == 0)] = (118, 20, 24)
    T["bed_foot"] = [V._rgba(foot)]
    head = wool.copy()
    pillow = (c >= 9) & (c <= 14) & (r >= 2) & (r <= 13)
    head[pillow] = _noise(rng, (236, 236, 236), 6)[pillow]
    head[(r == 0) | (r == 15) | (c == 15)] = (118, 20, 24)
    T["bed_head"] = [V._rgba(head)]
    bside = V._rgba(wool)
    bside[11] = (110, 18, 22, 255)
    wood = V._rgba(_noise(rng, (150, 104, 60), 8))
    bside[12:] = 0
    for cols in (slice(0, 3), slice(13, 16)):
        bside[12:, cols] = wood[12:, cols]
    T["bed_side"] = [bside]

    tnt = _noise(rng, (206, 46, 36), 10)
    tnt[:, ::4] *= 0.8
    tnt[4:12] = _noise(rng, (236, 234, 228), 5)[4:12]
    letters = ["###.#..#.###", ".#..##.#..#.", ".#..#.##..#.", ".#..#..#..#."]
    for i, row in enumerate(letters):
        for j, ch in enumerate(row):
            if ch == "#":
                tnt[6 + i, 2 + j] = (30, 30, 30)
    T["tnt_side"] = [V._rgba(tnt)]
    ttop = _noise(rng, (196, 58, 48), 8)
    ttop[np.hypot(r - 7.5, c - 7.5) < 5] = (220, 214, 206)
    ttop[np.hypot(r - 7.5, c - 7.5) < 1.6] = (50, 50, 50)
    T["tnt_top"] = [V._rgba(ttop)]

    T["wool"] = [V._rgba(wool)]
    planks = _noise(rng, (176, 138, 84), 8)
    planks[r % 4 == 3] = (118, 88, 50)
    planks[(r // 4 % 2 == 0) & (c == 5)] = (118, 88, 50)
    planks[(r // 4 % 2 == 1) & (c == 12)] = (118, 88, 50)
    T["planks"] = [V._rgba(planks)]
    T["sand"] = [V._rgba(_noise(rng, (220, 206, 160), 10))]


make_textures()

# name -> (top texture, side texture, height in 32nds)
BLOCKS = {
    "netherrack": ("netherrack", "netherrack", 32),
    "debris": ("debris_top", "debris_side", 32),
    "bed_foot": ("bed_foot", "bed_side", 18),
    "bed_head": ("bed_head", "bed_side", 18),
    "tnt": ("tnt_top", "tnt_side", 32),
    "lava": ("lava", "lava", 28),
    "wool": ("wool", "wool", 32),
    "planks": ("planks", "planks", 32),
    "sand": ("sand", "sand", 32),
}


def fire_frames():
    rng = np.random.default_rng(5)
    frames = []
    for k in range(8):
        arr = np.zeros((16, 16, 4), np.uint8)
        for col in range(1, 15):
            h = int(5 + 9 * abs(math.sin(col * 1.7 + k * 0.9)) * (1 - abs(col - 7.5) / 9) + rng.integers(0, 3))
            for row in range(16 - h, 16):
                f = (16 - row) / max(h, 1)
                col_rgb = (255, 240, 120) if f < 0.35 else (255, 160, 40) if f < 0.7 else (220, 70, 20)
                arr[row, col] = col_rgb + (235,)
        frames.append(Image.fromarray(arr, "RGBA"))
    return frames


FIRE = fire_frames()


@lru_cache(maxsize=64)
def fire_sprite(k, size):
    return FIRE[k % 8].resize((size, size), Image.NEAREST)


GUNPOWDER = [
    "................",
    "................",
    "................",
    "......##........",
    ".....#gg#.##....",
    "....#ggggggg#...",
    "...#gGgggGggg#..",
    "..#ggggGggggGg#.",
    "..#gGggggggGgg#.",
    ".#ggggGgggggggg#",
    ".#gGgggggGggGgg#",
    "..#############.",
    "................",
    "................",
    "................",
    "................",
]


@lru_cache(maxsize=8)
def gunpowder_icon(size):
    cols = {"#": (40, 40, 40, 255), "g": (110, 110, 110, 255), "G": (160, 160, 160, 255)}
    arr = np.zeros((16, 16, 4), np.uint8)
    for y, row in enumerate(GUNPOWDER):
        for x, ch in enumerate(row):
            if ch in cols:
                arr[y, x] = cols[ch]
    return Image.fromarray(arr, "RGBA").resize((size, size), Image.NEAREST)


@lru_cache(maxsize=16)
def cube_icon(name, a):
    img = Image.new("RGBA", (2 * a + 4, 2 * a + 4), (0, 0, 0, 0))
    top, side, hq = BLOCKS[name]
    ox, oy = a + 2, a // 2 + 2
    for tex, face in ((top, "top"), (side, "left"), (side, "right")):
        spr, dx, dy = V.face_sprite(tex, face, a, hq, 0, 10)
        img.alpha_composite(spr, (ox + dx, oy + dy))
    return img


# ----------------------------------------------------------------------------------------- worlds
def world_a():
    """The hook: a netherrack island with a bed, over a lava sea."""
    b = {}
    for x in range(7):
        for y in range(7):
            for z in (-2, -1, 0):
                b[(x, y, z)] = "netherrack"
    for p in ((5, 0, 0), (6, 0, 0), (6, 1, 0)):
        b[p] = "lava"
    for p in ((1, 5, 1), (5, 5, 1), (5, 5, 2), (0, 2, 1)):
        b[p] = "netherrack"
    b[(2, 3, 1)], b[(3, 3, 1)] = "bed_foot", "bed_head"
    return b


def world_b():
    """Side-by-side TNT and bed."""
    b = {(x, y, z): "netherrack" for x in range(10) for y in range(3) for z in (-1, 0)}
    b[(2, 1, 1)] = "tnt"
    b[(6, 1, 1)], b[(7, 1, 1)] = "bed_foot", "bed_head"
    return b


DEBRIS = [(2, 2, 1), (3, 3, 1), (1, 2, 2)]


def world_c(bed=True):
    """A chunk of netherrack hiding ancient debris, with a bed on top."""
    b = {(x, y, z): "netherrack" for x in range(6) for y in range(6) for z in range(-2, 3)}
    for p in DEBRIS:
        b[p] = "debris"
    if bed:
        b[(2, 2, 3)], b[(3, 2, 3)] = "bed_foot", "bed_head"
    return b


def blast(blocks, center, radius, seed):
    rng = np.random.default_rng(seed)
    out = dict(blocks)
    for p, n in sorted(blocks.items()):
        if n == "debris":
            continue
        d = math.dist((p[0] + 0.5, p[1] + 0.5, p[2] + 0.5), center)
        if d < radius + rng.uniform(-0.4, 0.4):
            del out[p]
    return out


def fire_spots(blocks, center, radius, seed):
    rng = np.random.default_rng(seed)
    spots = []
    for (x, y, z), n in sorted(blocks.items()):
        if n == "netherrack" and (x, y, z + 1) not in blocks:
            if math.dist((x + 0.5, y + 0.5, z + 1), center) < radius and rng.random() < 0.45:
                spots.append(((x, y, z + 1), rng.uniform(0.05, 0.45), int(rng.integers(8))))
    return spots


A_BED = (3.0, 3.5, 1.3)
WA = world_a()
WA_CRATER = blast(WA, A_BED, 2.5, 1)
WA_FIRE = fire_spots(WA_CRATER, A_BED, 3.6, 2)
C_BED = (3.0, 2.5, 3.3)
WC = world_c()
WC_BARE = world_c(bed=False)
WC_CRATER = blast(WC, C_BED, 2.7, 3)
WC_FIRE = fire_spots(WC_CRATER, C_BED, 3.4, 4)


# ----------------------------------------------------------------------------------------- drawing
def draw_blocks(img, P, blocks, anim, xray=0.0, offsets=None):
    offsets = offsets or {}
    nr_alpha = round(10 - 7 * xray)

    def solid(pos):
        n = blocks.get(pos)
        if n is None or pos in offsets or BLOCKS[n][2] != 32 or n == "lava":
            return False
        return not (n == "netherrack" and nr_alpha < 10)

    for x, y, z in sorted(blocks, key=lambda p: (p[0] + p[1], p[2])):
        name = blocks[(x, y, z)]
        top, side, hq = BLOCKS[name]
        dz = offsets.get((x, y, z), 0.0)
        al = nr_alpha if name == "netherrack" else 10
        ox, oy = P(x, y, z + dz)
        faces = []
        if not solid((x, y, z + 1)) or dz:
            faces.append((top, "top"))
        if not solid((x, y + 1, z)) or dz:
            faces.append((side, "left"))
        if not solid((x + 1, y, z)) or dz:
            faces.append((side, "right"))
        for tex, face in faces:
            spr, dx, dy = V.face_sprite(tex, face, P.a, hq, anim, al)
            img.paste(spr, (round(ox + dx), round(oy + dy)), spr)


def draw_fires(img, P, spots, t_since, t):
    size = max(8, round(P.a * 0.95))
    for (x, y, z), delay, k in spots:
        if t_since < delay:
            continue
        spr = fire_sprite(int(t * 12) + k, size)
        sx, sy = P(x + 0.5, y + 0.5, z)
        img.paste(spr, (round(sx - size / 2), round(sy - size + size * 0.12)), spr)


def draw_wire(d, P, pos, col, width):
    x, y, z = pos
    c = {(i, j, k): P(x + i, y + j, z + k) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    for (i, j, k), p in c.items():
        for nb in ((1 - i, j, k), (i, 1 - j, k), (i, j, 1 - k)):
            if nb > (i, j, k):
                d.line([p, c[nb]], fill=col, width=width)


def make_background():
    k = np.linspace(0, 1, H)[:, None, None]
    sky = np.array((14, 4, 10)) * (1 - k) + np.array((96, 26, 14)) * k
    img = Image.fromarray(np.broadcast_to(sky, (H, W, 3)).astype(np.uint8), "RGB")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(12):
        r = 900 - i * 60
        gd.ellipse((W / 2 - r, H + 200 - r * 0.6, W / 2 + r, H + 200 + r * 0.6), fill=(255, 90, 20, 10))
    img.paste(glow, (0, 0), glow)
    return img


BG = make_background()
ASH = np.random.default_rng(9).random((70, 4))


def draw_ash(img, t):
    d = ImageDraw.Draw(img)
    for i, (x0, y0, sp, kind) in enumerate(ASH):
        x = (x0 * W + 30 * math.sin(t * 0.8 + i)) % W
        y = (y0 * H - t * (40 + 90 * sp)) % H
        col = (255, 140, 50) if kind < 0.3 else (90, 70, 70)
        s = 3 if kind < 0.3 else 4
        d.rectangle((x, y, x + s, y + s), fill=col)


class Boom:
    """Explosion effects at time t0 (global) around a world point."""

    def __init__(self, t0, center, size, seed):
        self.t0, self.center, self.size = t0, center, size
        rng = np.random.default_rng(seed)
        self.chunks = [
            (
                (rng.uniform(-1, 1) * 4 * size, rng.uniform(-1, 1) * 4 * size, rng.uniform(3, 8) * size),
                [(112, 42, 40), (82, 26, 26), (164, 34, 38), (146, 64, 60)][rng.integers(4)],
                rng.uniform(0.12, 0.26),
            )
            for _ in range(46)
        ]
        self.smoke = [
            ((rng.uniform(-1, 1) * 1.2, rng.uniform(-1, 1) * 1.2, rng.uniform(0, 1.0)), rng.uniform(0.5, 1.0))
            for _ in range(14)
        ]

    def flash(self, t):
        dt = t - self.t0
        return 0.0 if dt < 0 else 0.95 * math.exp(-dt / 0.07)

    def shake(self, t, f):
        dt = t - self.t0
        if dt < 0:
            return 0, 0
        amp = 34 * self.size * math.exp(-dt / 0.22)
        return amp * math.sin(f * 2.1), amp * math.cos(f * 3.7)

    def draw(self, img, P, t):
        dt = t - self.t0
        if not 0 <= dt < 1.8:
            return
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        cx, cy, cz = self.center
        sx, sy = P(cx, cy, cz)
        a = P.a
        # shock ring on the ground
        if dt < 0.45:
            R = (0.5 + 9 * dt) * self.size * a
            al = int(200 * (1 - dt / 0.45))
            d.ellipse((sx - R * 1.41, sy - R * 0.7, sx + R * 1.41, sy + R * 0.7), outline=(255, 220, 160, al), width=10)
        # smoke
        for (ox, oy, oz), s in self.smoke:
            if dt > 0.08:
                k = dt - 0.08
                px, py = P(cx + ox * (1 + k), cy + oy * (1 + k), cz + oz + 1.6 * k)
                r = (0.5 + 1.1 * k) * s * a * self.size
                al = int(170 * max(0, 1 - k / 1.6))
                g = int(60 + 40 * s)
                d.ellipse((px - r, py - r, px + r, py + r), fill=(g, g - 8, g - 12, al))
        # fireball
        if dt < 0.5:
            R = (0.4 + 2.6 * min(dt, 0.15) / 0.15) * a * self.size
            al = int(255 * (1 - dt / 0.5))
            for rr, col in ((1.0, (255, 120, 30)), (0.72, (255, 190, 60)), (0.42, (255, 250, 200))):
                d.ellipse((sx - R * rr, sy - R * rr, sx + R * rr, sy + R * rr), fill=col + (al,))
        # flying chunks
        for (vx, vy, vz), col, s in self.chunks:
            if dt < 1.3:
                px, py = P(cx + vx * dt, cy + vy * dt, cz + vz * dt - 9 * dt * dt)
                r = s * a
                d.rectangle((px - r, py - r, px + r, py + r), fill=col + (255,), outline=(20, 5, 5, 255))
        img.paste(ov, (0, 0), ov)


# ----------------------------------------------------------------------------------------- UI
def caption_groups(words):
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        if len(cur) >= 2 or w[-1] in ",.:?!":
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def clean(w):
    return re.sub(r"[^\w']", "", w).lower()


def draw_caption(img, words, starts, t, y=1380):
    groups = caption_groups(words)
    gi = 0
    for i, g in enumerate(groups):
        if t >= starts[g[0]] - 0.04:
            gi = i
    g = groups[gi]
    cur = max([i for i in g if t >= starts[i] - 0.03] or [g[0]])
    ims = []
    for i in g:
        key = clean(words[i])
        col = KEYWORDS.get(key, YELLOW if i == cur else WHITE)
        if i != cur and key not in KEYWORDS:
            col = WHITE
        ims.append((V.text_img(words[i].upper().strip(",.:"), 118, col, 14), i == cur))
    age = t - starts[g[0]]
    pop = 1.0 + 0.18 * (1 - clamp01(age / 0.1)) if age >= 0 else 1.0
    scales = [pop * (1.08 if is_cur else 1.0) for _, is_cur in ims]
    space = 34
    total = sum(im.width * k for (im, _), k in zip(ims, scales)) + space * (len(ims) - 1)
    fit = min(1.0, 980 / total)
    x = W / 2 - total * fit / 2
    for (im, _), k in zip(ims, scales):
        w = im.width * k * fit
        V.paste_center(img, im, x + w / 2, y, k * fit)
        x += w + space * fit


def draw_death(img, lt_killer, lt_igd, words_t):
    """Death screen: red tint, 'You Died!', killer message."""
    k = ease(lt_killer / 0.3)
    tint = Image.new("RGB", (W, H), (150, 0, 0))
    img.paste(Image.blend(img, tint, 0.55 * k))
    if k <= 0:
        return
    V.paste_center(img, V.text_img("You Died!", 128, WHITE, 0), W / 2 + 6, 566, 1, k * 0.5)
    V.paste_center(img, V.text_img("You Died!", 128, WHITE, 0), W / 2, 560, V.pop_scale(lt_killer, 0.25))
    msg = "Player was killed by"
    n = int(len(msg) * clamp01((lt_killer - 0.25) / 0.6))
    if n:
        im = V.text_img(msg[:n], 54, (235, 235, 235), 0)
        img.paste(im, (round(W / 2 - V.text_img(msg, 54, WHITE, 0).width / 2), 680), im)
    if lt_igd is not None and lt_igd >= 0:
        im = V.text_img("[Intentional Game Design]", 64, YELLOW, 6, (60, 0, 0))
        V.paste_center(img, im, W / 2, 790, V.pop_scale(lt_igd, 0.18))
    d = ImageDraw.Draw(img)
    for i, label in enumerate(("Respawn", "Title Screen")):
        y = 930 + i * 120
        d.rectangle((240, y, 840, y + 90), fill=(110, 110, 110), outline=(30, 30, 30), width=5)
        d.line((246, y + 6, 834, y + 6), fill=(170, 170, 170), width=4)
        V.paste_center(img, V.text_img(label, 44, WHITE, 0), W / 2, y + 47)


def draw_cost(img, t_bed, t_tnt, lt):
    dim = Image.new("RGB", (W, H), (0, 0, 0))
    img.paste(Image.blend(img, dim, 0.45 * ease((lt - t_bed + 0.1) / 0.2)))
    cards = [
        ("BED", [("wool", 3), ("planks", 3)], GREEN, "✓", t_bed),
        ("TNT", [("gunpowder", 5), ("sand", 4)], RED, "✗", t_tnt),
    ]
    for i, (title, items, col, mark, t0) in enumerate(cards):
        sc = V.pop_scale(lt - t0, 0.2)
        if sc <= 0:
            continue
        card = Image.new("RGBA", (860, 300), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, 859, 299), 40, fill=(20, 16, 22, 240), outline=col + (255,), width=8)
        tim = V.text_img(title, 76, col, 0)
        card.alpha_composite(tim, (44, 30))
        mim = V.text_img(mark, 110, col, 0)
        card.alpha_composite(mim, (860 - mim.width - 44, 22))
        x = 44
        for name, n in items:
            icon = gunpowder_icon(120) if name == "gunpowder" else cube_icon(name, 56)
            card.alpha_composite(icon, (x, 140 + (120 - icon.height) // 2))
            nim = V.text_img(f"×{n}", 64, WHITE, 0)
            card.alpha_composite(nim, (x + 130, 165))
            x += 380
        V.paste_center(img, card, W / 2, 520 + i * 340, sc)


# ----------------------------------------------------------------------------------------- audio
def boom_sfx():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(1)
    f = 95 * np.exp(-t / 0.5) + 28
    low = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45)
    noise = np.convolve(rng.normal(0, 1, n), np.ones(6) / 6, "same") * np.exp(-t / 0.22)
    crack = rng.normal(0, 1, n) * np.exp(-t / 0.015)
    return 0.9 * low + 0.7 * noise + 0.5 * crack


def riser_sfx(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(2)
    env = (t / dur) ** 2
    f = 180 + 700 * (t / dur) ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    noise = np.convolve(rng.normal(0, 1, n), np.ones(4) / 4, "same")
    return 0.25 * env * (tone + 0.8 * noise)


def wah_sfx():
    """Sad descending trombone for the death message."""
    out = []
    for i, (f, d) in enumerate(((392, 0.2), (370, 0.2), (349, 0.2), (330, 0.55))):
        n = int(d * SR)
        t = np.arange(n) / SR
        vib = 1 + 0.012 * np.sin(2 * np.pi * 6 * t) * (i == 3)
        ph = 2 * np.pi * np.cumsum(f * vib) / SR
        s = np.sign(np.sin(ph)) * 0.5 + np.sin(ph) * 0.5
        s = np.convolve(s, np.ones(10) / 10, "same")
        env = np.minimum(1, t / 0.02) * np.minimum(1, (d - t) / 0.05)
        out.append(s * env)
    return 0.16 * np.concatenate(out)


def tick_sfx():
    n = int(0.012 * SR)
    return 0.15 * np.random.default_rng(3).normal(0, 1, n) * np.linspace(1, 0, n)


def music(n, ducks):
    """Driving minor-key chiptune at 140 bpm with kick and hats; ducked around big moments."""
    out = np.zeros(n)
    eighth = 60 / 140 / 2
    chords = [(57, 60, 64, 69), (53, 57, 60, 65), (50, 53, 57, 62), (52, 56, 59, 64)]
    pattern = (0, 2, 1, 3, 2, 1, 3, 2)
    rng = np.random.default_rng(4)

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    step = 0
    while step * eighth * SR < n:
        i0 = int(step * eighth * SR)
        chord = chords[(step // 8) % 4]
        ln = min(int(eighth * SR * 0.9), n - i0)
        tt = np.arange(ln) / SR
        f = hz(chord[pattern[step % 8]] + 12)
        pulse = np.sign(np.sin(2 * np.pi * f * tt)) * 0.6 + np.sin(2 * np.pi * f * tt) * 0.4
        out[i0 : i0 + ln] += 0.14 * pulse * np.exp(-tt / 0.08)
        if step % 2 == 0:
            bl = min(int(2 * eighth * SR), n - i0)
            bt = np.arange(bl) / SR
            out[i0 : i0 + bl] += 0.32 * np.sin(2 * np.pi * hz(chord[0] - 24) * bt) * np.exp(-bt / 0.3)
            kl = min(int(0.14 * SR), n - i0)
            kf = np.linspace(140, 42, kl)
            out[i0 : i0 + kl] += 0.55 * np.sin(2 * np.pi * np.cumsum(kf) / SR) * np.exp(-np.arange(kl) / (0.04 * SR))
        else:
            hl = min(int(0.03 * SR), n - i0)
            out[i0 : i0 + hl] += 0.06 * rng.normal(0, 1, hl) * np.linspace(1, 0, hl)
        step += 1
    gain = np.ones(n)
    for t0, dur in ducks:
        i0, i1 = int(t0 * SR), min(n, int((t0 + dur) * SR))
        if i0 < n:
            gain[i0:i1] = np.minimum(gain[i0:i1], 0.12)
            rel = min(n - i1, int(0.4 * SR))
            gain[i1 : i1 + rel] = np.minimum(gain[i1 : i1 + rel], np.linspace(0.12, 1, rel))
    return out * gain


# ----------------------------------------------------------------------------------------- timeline
class Scene:
    def __init__(self, name, text, start, dur, starts):
        self.name, self.text, self.start, self.D = name, text, start, dur
        self.words, self.starts = text.split(), starts
        self.w = {}
        for word, s in zip(self.words, starts):
            self.w.setdefault(clean(word), s)


def synth():
    from kokoro_onnx import Kokoro

    d = V.kokoro_dir()
    k = Kokoro(str(d / V.KOKORO_FILES[0]), str(d / V.KOKORO_FILES[1]))
    out = []
    for _, text in LINES:
        s, sr = k.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        s = np.asarray(s, np.float32)
        loud = np.nonzero(np.abs(s) > 0.02)[0]
        s = s[max(0, loud[0] - int(0.02 * sr)) : loud[-1] + int(0.06 * sr)]
        n = int(len(s) * SR / sr)
        out.append(np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32))
    return out


# Frame-0 camera; the last frame returns here so the Short loops cleanly.
CAM0 = (1.9, A_BED, 1000)


def main():
    voices = synth()
    scenes, t = [], 0.0
    for (name, text), v in zip(LINES, voices):
        vd = len(v) / SR
        _, starts = V.word_times(text, vd)
        dur = vd + GAP
        scenes.append(Scene(name, text, t, dur, starts))
        t += dur
    total = t
    S = {s.name: s for s in scenes}
    print(f"duration {total:.1f}s")

    t_boom1 = S["never"].start + S["never"].w["nether"] - 0.05
    t_boom2 = S["boom"].start
    boom1 = Boom(t_boom1, A_BED, 1.0, 1)
    boom2 = Boom(t_boom2, C_BED, 1.0, 2)
    t_loop = S["cheap"].start + S["cheap"].w["just"] - 0.05
    t_bed_card = S["cheap"].w["cheaper"] - 0.1
    t_tnt_card = S["cheap"].w["tnt"] - 0.05

    # ---- audio
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for s, v in zip(scenes, voices):
        i0 = int(s.start * SR)
        voice[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.92
    fx = np.zeros(n)

    def add(t0, s, g=1.0):
        i0 = int(max(0, t0) * SR)
        if i0 < n:
            fx[i0 : i0 + len(s)] += g * s[: n - i0]

    add(t_boom1, boom_sfx())
    add(t_boom2, boom_sfx())
    for name in ("explode", "killer", "purpose", "boom"):
        add(S[name].start - 0.12, V.sfx("whoosh"), 0.8)
    add(S["igd"].start, wah_sfx())
    msg_t = S["killer"].start + 0.25
    for i in range(0, 20, 2):
        add(msg_t + i * 0.03, tick_sfx())
    add(S["purpose"].start + 0.1, riser_sfx(S["purpose"].D + S["debris"].w["ancient"] - 0.1))
    add(S["debris"].start + S["debris"].w["proof"], V.sfx("ding"))
    for i in range(3):
        add(t_boom2 + 0.75 + 0.3 * i, V.sfx("ding"))
    add(t_boom2 + 1.7, V.sfx("chime"))
    add(S["cheap"].start + t_bed_card, V.sfx("pop"))
    add(S["cheap"].start + t_tnt_card, V.sfx("buzz"))
    add(t_loop, V.sfx("whoosh"), 0.8)
    ducks = [(t_boom1, 0.45), (t_boom2, 0.45), (S["igd"].start, S["igd"].D)]
    mix = voice + 0.7 * fx + 0.11 * music(n, ducks)
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    wav = HERE / "audio.tmp.wav"
    V.write_wav(wav, mix[: int(total * SR)])

    # ---- video
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(total * FPS)
    for f in range(frames):
        t = f / FPS
        sc = max((s for s in scenes if s.start <= t), key=lambda s: s.start)
        lt = t - sc.start
        name = sc.name
        punch = 1 + 0.07 * math.exp(-lt / 0.12)
        anim = int(t * 6) % 8
        blocks, xray, offsets, fires, fire_t, booms, highlight = WA, 0.0, None, [], 0.0, [], []

        if name == "never":
            booms = [boom1]
            if t < t_boom1:
                zoom = lerp(1.9, 2.05, ease(t / max(t_boom1, 0.01)))
            else:
                blocks, fires, fire_t = WA_CRATER, WA_FIRE, t - t_boom1
                zoom = lerp(2.05, 1.45, ease((t - t_boom1) / 0.5))
            cam = (zoom, A_BED, 1000)
            punch = 1.0
        elif name == "explode":
            blocks = world_b()
            cam = (0.95, (5, 1.5, 0.5), 980)
        elif name in ("killer", "igd"):
            blocks, fires, fire_t = WA_CRATER, WA_FIRE, t - t_boom1
            cam = (lerp(1.45, 1.6, ease((t - S["killer"].start) / 2.5)), (3, 3.5, 0.5), 1000)
            booms = [boom1]
        elif name == "purpose":
            blocks = WC_BARE
            cam = (lerp(1.0, 1.15, ease(lt / sc.D)), (3, 3, 0.5), 1010)
        elif name == "debris":
            tso = sc.w["so"]
            blocks = WC_BARE if lt < tso + 0.15 else WC
            xray = clamp01(lt / 0.2) * (1 - clamp01((lt - tso) / 0.25))
            if lt >= tso + 0.15:
                drop = 1 - ease((lt - tso - 0.15) / 0.25)
                offsets = {(2, 2, 3): 1.5 * drop, (3, 2, 3): 1.5 * drop}
            cam = (lerp(1.15, 1.25, ease(lt / sc.D)), (3, 3, 0.5), 1010)
            punch = 1 + 0.07 * math.exp(-lt / 0.12) + 0.05 * math.exp(-max(0, lt - tso) / 0.12) * (lt >= tso)
        elif name == "boom":
            blocks, fires, fire_t, booms = WC_CRATER, WC_FIRE, t - t_boom2, [boom2]
            cam = (1.25, (3, 3, 0.5), 1010)
            highlight = [(p, t - t_boom2 - 0.75 - 0.3 * i) for i, p in enumerate(DEBRIS)]
            punch = 1.0
        else:  # cheap
            if t < t_loop:
                blocks, fires, fire_t, booms = WC_CRATER, WC_FIRE, t - t_boom2, [boom2]
                cam = (1.25, (3, 3, 0.5), 1010)
                highlight = [(p, 9) for p in DEBRIS]
            else:
                k = ease((t - t_loop) / max(0.01, total - 1 / FPS - t_loop))
                cam = (lerp(1.75, CAM0[0], k), CAM0[1], CAM0[2])
                punch = 1.0

        zoom, focus, sy = cam
        P = V.Proj(zoom * punch, focus, sy)
        sxk = syk = 0
        for b in booms:
            dx, dy = b.shake(t, f)
            sxk += dx
            syk += dy
        P.cx += round(sxk)
        P.cy += round(syk)

        img = BG.copy()
        draw_ash(img, t)
        draw_blocks(img, P, blocks, anim, xray, offsets)
        draw_fires(img, P, fires, fire_t, t)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for p, age in highlight:
            if age >= 0:
                pulse = 0.6 + 0.4 * math.sin(t * 8)
                draw_wire(od, P, p, (255, 215, 60, int(255 * pulse)), max(4, P.a // 16))
        if name == "explode":
            for c0, r, col, label, tw in (
                ((2.5, 1.5, 1.5), 4, (255, 140, 40), "TNT  POWER 4", sc.w["blast"]),
                ((7.0, 1.5, 1.3), 5, (255, 60, 50), "BED  POWER 5", sc.w["bigger"]),
            ):
                k = ease((lt - tw) / 0.3)
                if k > 0:
                    cx, cy = P(*c0)
                    R = r * 0.55 * P.a * 1.12 * k
                    od.ellipse((cx - R, cy - R, cx + R, cy + R), fill=col + (60,), outline=col + (230,), width=7)
        img.paste(ov, (0, 0), ov)
        for b in booms:
            b.draw(img, P, t)

        # labels and overlays
        if name == "explode":
            for c0, r, label, tw, col in (
                ((2.5, 1.5, 1.5), 4, "TNT: 4", sc.w["blast"], (210, 110, 20)),
                ((7.0, 1.5, 1.3), 5, "BED: 5", sc.w["bigger"], (200, 30, 30)),
            ):
                cx, cy = P(*c0)
                V.paste_center(img, V.pill(label, 52, col), cx, cy - r * 0.55 * P.a * 1.12 - 50, V.pop_scale(lt - tw - 0.15))
        if name == "purpose":
            cx, cy = P(3, 3, 3.6)
            V.paste_center(img, V.pill("?", 110, (120, 40, 160)), cx, cy - 40 + 12 * math.sin(lt * 6), V.pop_scale(lt - 0.2))
        if name == "debris":
            cx, cy = P(2.5, 2.5, 3.2)
            V.paste_center(img, V.pill("X-RAY", 44, (60, 60, 70)), W / 2, 330, V.pop_scale(lt) * (1 - clamp01((lt - sc.w["so"]) / 0.2)))
            V.paste_center(img, V.pill("BLAST PROOF", 54, (30, 140, 60)), W / 2, 450, V.pop_scale(lt - sc.w["blast"]) * (1 - clamp01((lt - sc.w["so"]) / 0.2)))
        if name == "boom" or (name == "cheap" and lt < t_bed_card):
            got = sum(1 for _, age in highlight if age >= 0)
            if got:
                V.paste_center(img, V.pill(f"ANCIENT DEBRIS ×{got}", 60, (110, 50, 170)), W / 2, 380, 1 + 0.15 * V.bump(highlight[got - 1][1], 0, 0.25))
        if name in ("killer", "igd"):
            draw_death(img, t - S["killer"].start, (t - S["igd"].start) if name == "igd" else None, None)
        if name == "cheap" and t < t_loop:
            draw_cost(img, t_bed_card, t_tnt_card, lt)

        draw_caption(img, sc.words, sc.starts, lt)

        fl = sum(b.flash(t) for b in booms)
        if name == "cheap" and t >= t_loop:
            fl = max(fl, 0.8 * (1 - clamp01((t - t_loop) / 0.15)))
        if fl > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 236, 200)), min(0.95, fl))
        ff.stdin.write(img.tobytes())
        if f % 150 == 0:
            print(f"frame {f}/{frames}")
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
