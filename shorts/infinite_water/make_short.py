#!/usr/bin/env python3
"""Render a vertical YouTube Short that explains Minecraft's infinite water source.

Everything is generated here, with no game assets: isometric voxel scenes drawn with Pillow, narration
from the open Kokoro TTS model, and synthesized music and sound effects, muxed with ffmpeg.

    pip install pillow numpy kokoro-onnx soundfile      # plus ffmpeg on PATH
    python shorts/infinite_water/make_short.py         # -> shorts/infinite_water/infinite_water_short.mp4

Scenes listed in BROLL cut to real gameplay from broll/luanti_broll.mp4, recorded in Luanti (an open-source
Minecraft-like game) by broll/record.py; set NO_BROLL=1 for the fully animated version.

The Kokoro model (~120 MB) downloads to ~/.cache/kokoro-onnx on first run (override with KOKORO_DIR).
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import urllib.request
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "infinite_water_short.mp4"
W, H, FPS, SR = 1080, 1920, 30, 48000
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOICE, SPEED = "af_heart", 1.08
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")

# One narration line per scene.
LINES = [
    ("hook", "This tiny hole gives you infinite water. Here's exactly why it works."),
    ("dig", "Dig a two by two hole, just one block deep."),
    ("pour", "Pour a bucket of water into two opposite corners."),
    ("flow", "Now watch the other two corners. They touch two sources, so they become source blocks too."),
    (
        "rule",
        "Here's the rule. Flowing water becomes a new source when it touches at least two source blocks "
        "on its sides, and sits on a solid block, or more water.",
    ),
    ("scoop", "So every time you scoop out a bucket, its neighbors refill it instantly. It never runs dry."),
    ("lava", "One catch: lava won't do this by default. Only water."),
    ("outro", "Follow for more Minecraft mechanics, explained in under a minute."),
]
GAP, TAIL = 0.3, 1.4  # silence after each line; extra hold on the last scene

# The world: a 6x6 grass island, three blocks thick, with a 2x2 hole in the middle.
N = 6
HOLE = [(2, 2), (3, 2), (2, 3), (3, 3)]
A, B = (2, 2), (3, 3)  # where the buckets go (opposite corners)
S1, S2 = (3, 2), (2, 3)  # the corners that become sources
FULL, FLOW_H = 0.875, 0.4

BLUE, GREEN, RED, YELLOW = (40, 110, 235), (40, 170, 70), (220, 50, 45), (255, 222, 60)


# ----------------------------------------------------------------------------------------- helpers
def clamp01(x):
    return max(0.0, min(1.0, x))


def ease(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ramp(t, t0, t1):
    return ease((t - t0) / (t1 - t0))


def lerp(a, b, k):
    return a + (b - a) * k


def lerp2(p, q, k):
    return (lerp(p[0], q[0], k), lerp(p[1], q[1], k))


def bump(t, t0, t1):
    """0 -> 1 -> 0 over [t0, t1]."""
    if t <= t0 or t >= t1:
        return 0.0
    return math.sin(math.pi * (t - t0) / (t1 - t0))


@lru_cache(None)
def font(size):
    return ImageFont.truetype(FONT, size)


# ----------------------------------------------------------------------------------------- textures
def _rgba(arr, alpha=255):
    out = np.zeros((16, 16, 4), np.uint8)
    out[..., :3] = np.clip(arr, 0, 255)
    out[..., 3] = alpha
    return out


def make_textures():
    rng = np.random.default_rng(7)

    def noise(base, var):
        return np.array(base, float)[None, None, :] + rng.integers(-var, var + 1, (16, 16, 1))

    tex = {}
    grass = noise((96, 162, 56), 16)
    grass[rng.random((16, 16)) < 0.14] *= 0.82
    tex["grass_top"] = [_rgba(grass)]
    dirt = noise((134, 96, 67), 12)
    dirt[rng.random((16, 16)) < 0.16] = (104, 74, 50)
    dirt[rng.random((16, 16)) < 0.08] = (162, 121, 87)
    tex["dirt"] = [_rgba(dirt)]
    side = dirt.copy()
    depth = 3 + (rng.random(16) < 0.5) + (rng.random(16) < 0.25)
    for c in range(16):
        side[: depth[c], c] = grass[: depth[c], c] * 0.92
    tex["grass_side"] = [_rgba(side)]

    r, c = np.mgrid[0:16, 0:16]
    for name, base, hi, alpha in (
        ("water", (44, 98, 222), 50, 205),
        ("flow", (78, 140, 240), 55, 185),
    ):
        frames = []
        for k in range(8):
            ph = k / 8 * 2 * math.pi
            v = np.sin(2 * math.pi * (c / 16 + r / 32) * 2 + ph) + 0.35 * np.sin(r * 0.9 - ph)
            arr = noise(base, 5)
            arr[v > 0.9] += hi
            arr[v < -1.0] -= 14
            frames.append(_rgba(arr, alpha))
        tex[name] = frames
    for name, base in (("lava", (214, 84, 14)), ("lavaflow", (232, 112, 26))):
        frames = []
        for k in range(8):
            ph = k / 8 * 2 * math.pi
            v = np.sin(c * 0.8 + ph) + np.sin(r * 0.7 - ph * 0.7) + rng.normal(0, 0.25, (16, 16))
            arr = noise(base, 8)
            arr[v > 0.9] = (255, 196, 54)
            arr[v < -1.1] = (160, 42, 8)
            frames.append(_rgba(arr))
        tex[name] = frames
    return tex


TEX = make_textures()
SHADE = {"top": 1.0, "left": 0.84, "right": 0.68}
BLOCK_FACES = {"grass": ("grass_top", "grass_side"), "dirt": ("dirt", "dirt")}


@lru_cache(maxsize=8192)
def face_sprite(tex, face, a, hq, frame, alq):
    """One textured face of a unit cube of height hq/32, as (RGBA image, dx, dy) from the cube's origin."""
    h = hq / 32

    def p(x, y, z):
        return ((x - y) * a, (x + y) * a / 2 - z * a)

    if face == "top":
        O, U, V = p(0, 0, h), p(1, 0, h), p(0, 1, h)
        poly = [O, U, p(1, 1, h), V]
        v0, v1 = 0.0, 16.0
    elif face == "left":  # the +y face
        O, U, V = p(0, 1, h), p(1, 1, h), p(0, 1, 0)
        poly = [O, U, p(1, 1, 0), V]
        v0, v1 = (1 - h) * 16, 16.0
    else:  # the +x face
        O, U, V = p(1, 0, h), p(1, 1, h), p(1, 0, 0)
        poly = [O, U, p(1, 1, 0), V]
        v0, v1 = (1 - h) * 16, 16.0
    ux, uy = U[0] - O[0], U[1] - O[1]
    vx, vy = V[0] - O[0], V[1] - O[1]
    det = ux * vy - uy * vx
    minx = math.floor(min(q[0] for q in poly))
    miny = math.floor(min(q[1] for q in poly))
    bw = math.ceil(max(q[0] for q in poly)) - minx + 1
    bh = math.ceil(max(q[1] for q in poly)) - miny + 1
    ox, oy = minx - O[0], miny - O[1]
    dv = v1 - v0
    coeffs = (
        16 * vy / det,
        -16 * vx / det,
        16 + 16 * (ox * vy - oy * vx) / det,
        -dv * uy / det,
        dv * ux / det,
        16 + v0 + dv * (ux * oy - uy * ox) / det,
    )
    src = TEX[tex][frame % len(TEX[tex])].astype(float)
    src[..., :3] *= SHADE[face]
    tiled = Image.fromarray(np.tile(src.astype(np.uint8), (3, 3, 1)), "RGBA")
    img = tiled.transform((bw, bh), Image.AFFINE, coeffs, resample=Image.NEAREST)
    local = [(q[0] - minx, q[1] - miny) for q in poly]
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).polygon(local, fill=255, outline=255)
    if tex in ("grass_top", "grass_side", "dirt"):
        edge = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        ImageDraw.Draw(edge).line(local + [local[0]], fill=(0, 0, 0, 55), width=max(1, a // 40))
        img = Image.alpha_composite(img, edge)
    alpha = np.minimum(np.asarray(img.getchannel("A")), np.asarray(mask)).astype(float) * (alq / 10)
    img.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    return img, minx, miny


# ----------------------------------------------------------------------------------------- camera
class Proj:
    def __init__(self, zoom, focus, sy):
        self.a = a = max(8, 2 * round(40 * zoom))
        fx, fy, fz = focus
        self.cx = round(540 - (fx - fy) * a)
        self.cy = round(sy - (fx + fy) * a / 2 + fz * a)

    def __call__(self, x, y, z):
        return (self.cx + (x - y) * self.a, self.cy + (x + y) * self.a / 2 - z * self.a)


# ----------------------------------------------------------------------------------------- UI pieces
@lru_cache(maxsize=512)
def text_img(text, size, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0)):
    f = font(size)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text(
        (2 - l, 2 - t), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill
    )
    return im


@lru_cache(maxsize=256)
def pill(text, size, bg, fg=(255, 255, 255)):
    t = text_img(text, size, fg)
    px, py = int(size * 0.5), int(size * 0.32)
    w, h = t.width + 2 * px, t.height + 2 * py
    im = Image.new("RGBA", (w + 10, h + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rad = h // 2
    d.rounded_rectangle((5, 9, w + 5, h + 9), rad, fill=(0, 0, 0, 110))
    d.rounded_rectangle((5, 3, w + 5, h + 3), rad, fill=bg + (255,), outline=(255, 255, 255, 255), width=4)
    im.alpha_composite(t, (5 + px, 3 + py))
    return im


def paste_center(img, im, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.02 or alpha <= 0.02:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BICUBIC)
    if alpha < 0.99:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    img.paste(im, (round(cx - im.width / 2), round(cy - im.height / 2)), im)


def pop_scale(age, dur=0.22):
    """Pop-in with a small overshoot."""
    if age < 0:
        return 0.0
    k = clamp01(age / dur)
    return k * (1 + 0.25 * math.sin(math.pi * k))


BUCKET_ART = [
    "................",
    ".....######.....",
    "....#......#....",
    "...#........#...",
    "..#..........#..",
    ".OOOOOOOOOOOOOO.",
    ".OIIIIIIIIIIIIO.",
    ".OLLLLLLLLLLLSO.",
    ".OLLLLLLLLLLLSO.",
    "..OLLLLLLLLLSO..",
    "..OLLLLLLLLLSO..",
    "..OLLLLLLLLLSO..",
    "...OLLLLLLLSO...",
    "...OLLLLLLLSO...",
    "....OOOOOOOO....",
    "................",
]


@lru_cache(maxsize=64)
def bucket_img(ps, full, tilt_q):
    colors = {
        "#": (70, 70, 76),
        "O": (52, 52, 58),
        "L": (206, 208, 214),
        "S": (150, 152, 160),
        "I": (64, 120, 235) if full else (36, 36, 42),
    }
    arr = np.zeros((16, 16, 4), np.uint8)
    for y, row in enumerate(BUCKET_ART):
        for x, ch in enumerate(row):
            if ch in colors:
                arr[y, x] = colors[ch] + (255,)
    im = Image.fromarray(arr, "RGBA").resize((16 * ps, 16 * ps), Image.NEAREST)
    return im.rotate(tilt_q, resample=Image.BICUBIC, expand=True) if tilt_q else im


def make_background():
    top, bot = np.array((88, 156, 250)), np.array((196, 228, 255))
    k = np.linspace(0, 1, H)[:, None, None]
    sky = top * (1 - k) + bot * k
    return Image.fromarray(np.broadcast_to(sky, (H, W, 3)).astype(np.uint8), "RGB")


BG = make_background()
CLOUDS = [(80, 520, 260, 60), (620, 430, 320, 70), (300, 740, 200, 50), (860, 690, 240, 56)]


def draw_clouds(img, t):
    d = ImageDraw.Draw(img)
    for i, (x, y, w, h) in enumerate(CLOUDS):
        x = (x + t * (14 + 5 * i)) % (W + w + 200) - w - 100
        d.rectangle((x, y, x + w, y + h), fill=(246, 249, 255))
        d.rectangle((x + w * 0.2, y - h * 0.6, x + w * 0.65, y), fill=(246, 249, 255))


# ----------------------------------------------------------------------------------------- narration
def kokoro_dir():
    d = Path(os.environ.get("KOKORO_DIR", Path.home() / ".cache" / "kokoro-onnx"))
    d.mkdir(parents=True, exist_ok=True)
    for name in KOKORO_FILES:
        if not (d / name).exists():
            print(f"downloading {name} ...")
            urllib.request.urlretrieve(KOKORO_URL + name, d / name)
    return d


def synth_lines():
    from kokoro_onnx import Kokoro

    d = kokoro_dir()
    k = Kokoro(str(d / KOKORO_FILES[0]), str(d / KOKORO_FILES[1]))
    out = []
    for _, text in LINES:
        samples, sr = k.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        s = np.asarray(samples, np.float32)
        loud = np.nonzero(np.abs(s) > 0.02)[0]
        s = s[max(0, loud[0] - int(0.03 * sr)) : loud[-1] + int(0.08 * sr)]
        # resample to the mix rate
        n = int(len(s) * SR / sr)
        out.append(np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32))
    return out


def word_times(text, dur):
    """Estimated start time of each word, spreading the line by word length and punctuation pauses."""
    words = text.split()
    weights = []
    for w in words:
        wt = len(re.sub(r"\W", "", w)) + 1.6
        if w[-1] in ",:;":
            wt += 3.0
        elif w[-1] in ".!?":
            wt += 4.5
        weights.append(wt)
    total = sum(weights)
    starts, acc = [], 0.0
    for wt in weights:
        starts.append(acc / total * dur)
        acc += wt
    return words, starts


class Ctx:
    """Timing for one scene: its length, its nominal-time scale, and when each narrated word starts."""

    def __init__(self, name, start, dur, words, starts, nominal):
        self.name, self.start, self.D = name, start, dur
        self.s = dur / nominal
        self.words, self.starts = words, starts
        self.w = {}
        for w, t in zip(words, starts):
            self.w.setdefault(re.sub(r"[^\w']", "", w).lower(), t + VOICE_LEAD)

    def T(self, x):
        return x * self.s


VOICE_LEAD = 0.05
NOMINAL = {"hook": 4.0, "dig": 3.0, "pour": 3.6, "flow": 5.0, "rule": 9.0, "scoop": 6.0, "lava": 4.0, "outro": 4.0}


# ----------------------------------------------------------------------------------------- scenes
def base_state():
    return dict(
        water={},
        removed={c: 1.0 for c in HOLE},
        badges=[],
        outlines=[],
        arrows=[],
        wires=[],
        bucket=None,
        stream=None,
        panel=None,
        counter=None,
        follow=None,
        flash=0.0,
    )


def all_water(st):
    for c in HOLE:
        st["water"][c] = ("water", FULL)


def top_pt(c, h=FULL):
    return (c[0] + 0.5, c[1] + 0.5, h)


def src_badge(c, t0, t, text="SOURCE", bg=BLUE, size=30):
    return (top_pt(c), text, size, bg, t - t0)


def scene_hook(t, c):
    st = base_state()
    all_water(st)
    st["badges"].append(((3, 3, FULL), "∞", 104, BLUE, t - 0.35))
    return st


def scene_dig(t, c):
    st = base_state()
    st["removed"] = {cell: ramp(t, c.T(0.3 + 0.45 * i), c.T(0.3 + 0.45 * i) + 0.3) for i, cell in enumerate(HOLE)}
    st["flash"] = 1 - clamp01(t / 0.25)
    return st


def bucket_path(t, keys):
    """keys: [(time, (x, y))]; piecewise eased positions between cells."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t <= t1:
            return lerp2(p0, p1, ramp(t, t0, t1)) if t1 > t0 else p1
    return keys[-1][1]


OFF = (6.8, 0.6)


def scene_pour(t, c):
    T = c.T
    st = base_state()
    lv_a = FULL * ramp(t, T(0.65), T(1.05))
    lv_s = FLOW_H * ramp(t, T(1.0), T(1.35))
    lv_b = FULL * ramp(t, T(1.9), T(2.3))
    for cell, kind, h in ((A, "water", lv_a), (B, "water", lv_b), (S1, "flow", lv_s), (S2, "flow", lv_s)):
        if h > 0.01:
            st["water"][cell] = (kind, h)
    pos = bucket_path(
        t, [(0, OFF), (T(0.45), A), (T(1.25), A), (T(1.7), B), (T(2.5), B), (T(3.0), OFF)]
    )
    tilt = 70 * (
        ramp(t, T(0.45), T(0.65)) - ramp(t, T(1.1), T(1.25)) + ramp(t, T(1.7), T(1.85)) - ramp(t, T(2.35), T(2.5))
    )
    full = not (T(1.1) < t < T(1.25)) and t < T(2.35)
    st["bucket"] = (pos, tilt, full, 0.0)
    if T(0.6) < t < T(1.1):
        st["stream"] = (A, lv_a)
    elif T(1.85) < t < T(2.35):
        st["stream"] = (B, lv_b)
    st["badges"] += [src_badge(A, T(1.05), t), src_badge(B, T(2.3), t)]
    return st


def scene_flow(t, c):
    st = base_state()
    tc, ta = c.w["become"], c.w["touch"]
    h = FLOW_H + (FULL - FLOW_H) * ramp(t, tc, tc + 0.3)
    st["water"] = {A: ("water", FULL), B: ("water", FULL)}
    for s in (S1, S2):
        st["water"][s] = ("flow" if t < tc + 0.15 else "water", h)
        if t < tc + 0.3:
            st["outlines"].append((s, h, YELLOW))
        if ta <= t < tc + 0.5:
            for src in (A, B):
                st["arrows"].append((top_pt(src), top_pt(s, h), ramp(t, ta, ta + 0.4), (90, 235, 110)))
        st["badges"].append(src_badge(s, tc + 0.3, t))
    st["badges"] += [src_badge(A, -9, t), src_badge(B, -9, t)]
    return st


def scene_rule(t, c):
    st = base_state()
    t1, t2, tconv = c.w["least"], c.w["solid"], c.D - 0.85
    h = FLOW_H + (FULL - FLOW_H) * ramp(t, tconv, tconv + 0.3)
    st["water"] = {A: ("water", FULL), B: ("water", FULL), S2: ("water", FULL)}
    st["water"][S1] = ("flow" if t < tconv + 0.15 else "water", h)
    if 0.2 < t < tconv + 0.3:
        st["outlines"].append((S1, h, YELLOW))
    if t1 <= t < tconv + 0.4:
        for src in (A, B):
            st["arrows"].append((top_pt(src), top_pt(S1, h), ramp(t, t1, t1 + 0.4), (90, 235, 110)))
    if t2 <= t < tconv + 0.4:
        st["wires"].append(((S1[0], S1[1], -1), (255, 150, 30)))
    st["badges"] += [src_badge(x, -9, t, size=26) for x in (A, B, S2)]
    st["badges"].append(src_badge(S1, tconv + 0.3, t, "NEW SOURCE!", GREEN, 32))
    st["panel"] = (
        "THE SOURCE RULE",
        [("✓ Next to 2+ source blocks", t1, (130, 255, 150)), ("✓ On a solid block or water", t2, (130, 255, 150))],
        t,
    )
    return st


SCOOP_CELLS, SCOOP_DIPS = (S1, S2, A), (0.9, 2.4, 3.9)


def scene_scoop(t, c):
    T = c.T
    st = base_state()
    all_water(st)
    refills = 0
    for cell, dip in zip(SCOOP_CELLS, SCOOP_DIPS):
        d = T(dip)
        if d <= t < d + 0.15:
            st["water"][cell] = ("water", FULL * (1 - ramp(t, d, d + 0.15)))
        elif d + 0.15 <= t < d + 0.35:
            st["water"].pop(cell)
        elif d + 0.35 <= t < d + 0.65:
            st["water"][cell] = ("flow", FULL * ramp(t, d + 0.35, d + 0.65))
        if t >= d + 0.6:
            refills += 1
            st["badges"].append(((cell[0] + 0.5, cell[1] + 0.5, FULL), "REFILLED", 26, GREEN, t - d - 0.6))
    st["badges"] = [b for b in st["badges"] if b[4] < 1.2]
    pos = bucket_path(
        t,
        [(0, OFF), (T(0.5), S1), (T(1.6), S1), (T(2.1), S2), (T(3.1), S2), (T(3.6), A), (T(5.2), A), (T(5.8), OFF)],
    )
    dip = sum(bump(t, T(x) - 0.2, T(x) + 0.25) for x in SCOOP_DIPS)
    st["bucket"] = (pos, 0.0, t >= T(SCOOP_DIPS[0]) + 0.05, dip)
    st["counter"] = ("BUCKETS: ∞" if t >= T(4.9) else f"BUCKETS: {refills}", t - T(4.9))
    return st


def scene_lava(t, c):
    st = base_state()
    tx, to = c.w["lava"] + 0.3, c.w["only"]
    st["water"] = {A: ("lava", FULL), B: ("lava", FULL), S1: ("lavaflow", 0.3), S2: ("lavaflow", 0.3)}
    st["badges"] = [((s[0] + 0.5, s[1] + 0.5, 0.3), "✗", 56, RED, t - tx) for s in (S1, S2)]
    st["panel"] = (
        "INFINITE SOURCE?",
        [("✓ Water", to, (130, 255, 150)), ("✗ Lava (by default)", to + 0.35, (255, 130, 120))],
        t,
    )
    st["flash"] = 1 - clamp01(t / 0.25)
    return st


def scene_outro(t, c):
    st = base_state()
    all_water(st)
    st["follow"] = t
    st["flash"] = 1 - clamp01(t / 0.25)
    return st


SCENES = {
    "hook": scene_hook,
    "dig": scene_dig,
    "pour": scene_pour,
    "flow": scene_flow,
    "rule": scene_rule,
    "scoop": scene_scoop,
    "lava": scene_lava,
    "outro": scene_outro,
}

# (zoom, focus point, screen y of focus); "hook" and "outro" also drift.
CAMS = {
    "hook": (1.75, (3, 3, 0.5), 1040),
    "dig": (1.3, (3, 3, 0.2), 1040),
    "pour": (1.4, (3, 3, 0.6), 1080),
    "flow": (1.55, (3, 3, 0.5), 1060),
    "rule": (1.8, (3, 3, 0.5), 1130),
    "scoop": (1.5, (3, 3, 0.6), 1090),
    "lava": (1.55, (3, 3, 0.5), 1070),
    "outro": (1.1, (3, 3, 0.0), 1140),
}


def cam_at(name, t, D):
    zoom, focus, sy = CAMS[name]
    if name == "hook":
        zoom = lerp(1.75, 1.45, ease(t / D))
    if name == "outro":
        zoom = lerp(1.1, 1.0, ease(t / D))
    return zoom, focus, sy


# Real gameplay b-roll recorded in Luanti (see broll/). scene -> (in-point in the clip, playback speed).
BROLL_FILE = HERE / "broll" / "luanti_broll.mp4"
BROLL = {"dig": (1.0, 1.0), "pour": (5.8, 1.0), "scoop": (13.3, 1.0), "lava": (22.0, 1.5), "outro": (31.2, 1.0)}
# Clip times of the on-screen actions (from broll/director.lua), for sound effects.
BROLL_SFX = {
    "dig": [(1.6 + 0.6 * i, "pop") for i in range(4)],
    "pour": [(6.5, "splash"), (9.0, "splash")],
    "scoop": [(x, k) for t in (14.0, 16.0, 18.0) for x, k in ((t, "scoop"), (t + 0.4, "ding"))],
    "lava": [(22.0, "splash"), (23.5, "splash")],
}
USE_BROLL = BROLL_FILE.exists() and not os.environ.get("NO_BROLL")


def has_broll(name):
    return USE_BROLL and name in BROLL


class Clip:
    """Streams b-roll frames for one scene, starting at its in-point."""

    def __init__(self, start, speed):
        cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(start), "-i", str(BROLL_FILE),
               "-vf", f"setpts=PTS/{speed},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]  # fmt: skip
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.last = None

    def frame(self):
        buf = self.p.stdout.read(W * H * 3)
        if len(buf) == W * H * 3:
            self.last = Image.frombytes("RGB", (W, H), buf)
        return self.last.copy()

    def close(self):
        self.p.kill()
        self.p.wait()


def draw_broll_label(img):
    paste_center(img, pill("REAL GAMEPLAY · LUANTI (MINECRAFT-LIKE)", 26, (25, 25, 30)), W / 2, 1330)


def scene_events(c):
    """Sound effects (and particle bursts) per scene, in local time."""
    T, ev = c.T, []
    if has_broll(c.name):
        start, speed = BROLL[c.name]
        ev += [((ft - start) / speed, kind, None) for ft, kind in BROLL_SFX.get(c.name, [])]
        if c.name in ("dig", "lava", "outro"):
            ev.append((0.0, "whoosh", None))
        if c.name == "lava":
            ev.append((c.w["lava"] + 0.3, "buzz", None))
        if c.name == "outro":
            ev.append((0.25, "chime", None))
        return ev
    if c.name == "hook":
        ev.append((0.35, "ding", (3, 3, FULL)))
    elif c.name == "dig":
        ev.append((0.0, "whoosh", None))
        ev += [(T(0.3 + 0.45 * i), "pop", (x + 0.5, y + 0.5, 1.0)) for i, (x, y) in enumerate(HOLE)]
    elif c.name == "pour":
        ev += [(T(0.7), "splash", top_pt(A, 0.4)), (T(1.95), "splash", top_pt(B, 0.4))]
    elif c.name == "flow":
        ev.append((c.w["become"] + 0.25, "ding", None))
    elif c.name == "rule":
        ev.append((c.D - 0.6, "ding", None))
    elif c.name == "scoop":
        for cell, dip in zip(SCOOP_CELLS, SCOOP_DIPS):
            ev += [(T(dip), "scoop", top_pt(cell, 0.6)), (T(dip) + 0.6, "ding", None)]
        ev.append((T(4.9), "chime", None))
    elif c.name == "lava":
        ev += [(0.0, "whoosh", None), (c.w["lava"] + 0.3, "buzz", None)]
    elif c.name == "outro":
        ev += [(0.0, "whoosh", None), (0.25, "chime", None)]
    return ev


# ----------------------------------------------------------------------------------------- drawing
def draw_world(img, P, st, anim):
    removed = st["removed"]
    occ, items = set(), []
    for x in range(N):
        for y in range(N):
            for z in (-2, -1, 0):
                dz, al = 0.0, 1.0
                if z == 0 and (x, y) in removed:
                    p = removed[(x, y)]
                    if p >= 1:
                        continue
                    dz, al = 0.8 * p, 1 - p
                if dz == 0:
                    occ.add((x, y, z))
                items.append(((x + y, z, 0), ("block", x, y, z, dz, al)))
    for (x, y), (kind, h) in st["water"].items():
        items.append(((x + y, 0, 1), ("fluid", x, y, kind, h)))
    items.sort(key=lambda it: it[0])
    a = P.a
    for _, it in items:
        if it[0] == "block":
            _, x, y, z, dz, al = it
            top, side = BLOCK_FACES["grass" if z == 0 else "dirt"]
            ox, oy = P(x, y, z + dz)
            faces = []
            if (x, y, z + 1) not in occ or dz:
                faces.append((top, "top"))
            if (x, y + 1, z) not in occ or dz:
                faces.append((side, "left"))
            if (x + 1, y, z) not in occ or dz:
                faces.append((side, "right"))
            for tex, face in faces:
                spr, dx, dy = face_sprite(tex, face, a, 32, 0, round(al * 10))
                img.paste(spr, (round(ox + dx), round(oy + dy)), spr)
        else:
            _, x, y, kind, h = it
            hq = max(1, round(h * 32))
            ox, oy = P(x, y, 0)
            faces = [("top", None)]
            for face, nb in (("left", (x, y + 1)), ("right", (x + 1, y))):
                other = st["water"].get(nb)
                if (nb[0], nb[1], 0) not in occ and (other is None or other[1] < h - 0.02):
                    faces.append((face, nb))
            for face, _ in faces:
                spr, dx, dy = face_sprite(kind, face, a, hq, anim, 10)
                img.paste(spr, (round(ox + dx), round(oy + dy)), spr)


PARTICLE_COLORS = {
    "pop": [(96, 162, 56), (134, 96, 67), (104, 74, 50), (80, 140, 45)],
    "splash": [(70, 130, 240), (120, 170, 255), (200, 225, 255)],
    "scoop": [(70, 130, 240), (120, 170, 255)],
}


def make_particles(events):
    rng = np.random.default_rng(3)
    parts = []
    for t0, kind, pos in events:
        if kind not in PARTICLE_COLORS or pos is None:
            continue
        cols = PARTICLE_COLORS[kind]
        for _ in range(14):
            v = (rng.uniform(-1.6, 1.6), rng.uniform(-1.6, 1.6), rng.uniform(2.5, 4.5))
            parts.append((t0, pos, v, cols[rng.integers(len(cols))], rng.uniform(0.09, 0.16)))
    return parts


def draw_particles(img, P, parts, t):
    d = ImageDraw.Draw(img)
    for t0, (x, y, z), (vx, vy, vz), col, size in parts:
        dt = t - t0
        if not 0 <= dt < 0.6:
            continue
        sx, sy = P(x + vx * dt, y + vy * dt, z + vz * dt - 6 * dt * dt)
        r = size * P.a / 2
        d.rectangle((sx - r, sy - r, sx + r, sy + r), fill=col, outline=(0, 0, 0))


def draw_arrow(d, p0, p1, prog, color, width):
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1 or prog <= 0:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    s = (x0 + ux * L * 0.2, y0 + uy * L * 0.2)
    e = (x1 - ux * L * 0.22, y1 - uy * L * 0.22)
    tip = lerp2(s, e, prog)
    hs = width * 2.2
    head = [
        (tip[0] + ux * hs, tip[1] + uy * hs),
        (tip[0] - uy * hs * 0.8, tip[1] + ux * hs * 0.8),
        (tip[0] + uy * hs * 0.8, tip[1] - ux * hs * 0.8),
    ]
    d.line([s, tip], fill=(0, 0, 0, 255), width=width + 8)
    d.polygon(head, fill=(0, 0, 0, 255), outline=(0, 0, 0, 255), width=5)
    d.line([s, tip], fill=color + (255,), width=width)
    d.polygon(head, fill=color + (255,))


def draw_bucket(img, P, bucket, stream):
    (bx, by), tilt, full, dip = bucket
    ps = max(5, round(P.a / 11))
    size = 16 * ps
    tx, ty = P(bx + 0.5, by + 0.5, 1.0)
    hover = ty - 1.55 * P.a + dip * 0.55 * P.a
    th = math.radians(tilt)
    cx, cy = tx + 0.5 * size * math.sin(th), hover
    if stream is not None:
        cell, h = stream
        sx, sy = P(cell[0] + 0.5, cell[1] + 0.5, h)
        mouth_y = cy - 0.5 * size * math.cos(th) + size * 0.1
        w = ps * 2.2
        ov = Image.new("RGBA", (round(2 * w) + 2, max(2, round(sy - mouth_y))), (60, 120, 240, 215))
        ImageDraw.Draw(ov).rectangle((round(w * 0.5), 0, round(w * 0.9), ov.height), fill=(150, 195, 255, 230))
        img.paste(ov, (round(sx - w), round(mouth_y)), ov)
    spr = bucket_img(ps, full, round(tilt))
    img.paste(spr, (round(cx - spr.width / 2), round(cy - spr.height / 2)), spr)


def draw_scene_overlays(img, P, st):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    width = max(4, P.a // 20)
    for cell, h, col in st["outlines"]:
        x, y = cell
        pts = [P(x, y, h), P(x + 1, y, h), P(x + 1, y + 1, h), P(x, y + 1, h)]
        d.line(pts + [pts[0], pts[1]], fill=col + (255,), width=width, joint="curve")
    for (x, y, z), col in st["wires"]:
        c = {(i, j, k): P(x + i, y + j, z + k) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
        for (i, j, k), p in c.items():
            for nb in ((1 - i, j, k), (i, 1 - j, k), (i, j, 1 - k)):
                if nb > (i, j, k):
                    d.line([p, c[nb]], fill=col + (255,), width=width)
    for p0, p1, prog, col in st["arrows"]:
        draw_arrow(d, P(*p0), P(*p1), prog, col, max(8, P.a // 14))
    img.paste(ov, (0, 0), ov)
    if st["bucket"]:
        draw_bucket(img, P, st["bucket"], st["stream"])
    for pt, text, size, bg, age in st["badges"]:
        sc = pop_scale(age)
        if sc <= 0:
            continue
        sx, sy = P(*pt)
        im = pill(text, size, bg)
        paste_center(img, im, sx, sy - im.height * 0.75 - 6, sc)


def draw_header(img):
    paste_center(img, text_img("MINECRAFT MECHANICS", 42, YELLOW, 7), W / 2, 128)
    paste_center(img, text_img("INFINITE WATER", 104, (255, 255, 255), 12, (16, 36, 86)), W / 2, 214)


def draw_panel(img, panel):
    title, rows, t = panel
    shown = [r for r in rows if t >= r[1]]
    h = 108 + 78 * len(rows)
    top = 312
    box = Image.new("RGBA", (920, h), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle(
        (0, 0, 919, h - 1), 34, fill=(18, 24, 44, 255), outline=(255, 255, 255, 230), width=4
    )
    img.paste(box, (80, top), box)
    paste_center(img, text_img(title, 52, YELLOW), W / 2, top + 58)
    for i, (text, t0, col) in enumerate(shown):
        k = ease((t - t0) / 0.25)
        im = text_img(text, 46, col)
        x = 130 + (1 - k) * 60
        img.paste(im, (round(x), round(top + 108 + 78 * i)), im) if k > 0.99 else paste_center(
            img, im, x + im.width / 2, top + 108 + 78 * i + im.height / 2, 1.0, k
        )


def draw_counter(img, counter):
    text, age_inf = counter
    sc = 1.0 + (0.25 * bump(age_inf, 0, 0.35) if age_inf >= 0 else 0)
    paste_center(img, pill(text, 64, BLUE), W / 2, 400, sc)


def draw_follow(img, t):
    sc = pop_scale(t - 0.2, 0.3) * (1 + 0.04 * math.sin(t * 6))
    paste_center(img, pill("FOLLOW  +", 92, RED), W / 2, 470, sc)
    paste_center(img, text_img("for more mechanics", 58, (255, 255, 255), 8), W / 2, 610, 1.0, ease((t - 0.5) / 0.3))


def caption_chunks(words):
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        if len(cur) >= 3 or w[-1] in ",.:?!":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def draw_caption(img, words, starts, t):
    """Show the chunk being spoken, current word highlighted."""
    chunks = caption_chunks(words)
    ci = 0
    for i, ch in enumerate(chunks):
        if t >= starts[ch[0]] - 0.05:
            ci = i
    chunk = chunks[ci]
    cur = max([i for i in chunk if t >= starts[i] - 0.03] or [chunk[0]])
    size = 84
    imgs = [
        text_img(words[i].upper(), size, YELLOW if i == cur else (255, 255, 255), 11) for i in chunk
    ]
    space = 22
    lines, line, lw = [], [], 0
    for im in imgs:
        if line and lw + space + im.width > 980:
            lines.append(line)
            line, lw = [], 0
        lw += (space if line else 0) + im.width
        line.append(im)
    lines.append(line)
    age = t - starts[chunk[0]]
    sc = 1.0 + 0.08 * (1 - clamp01(age / 0.12)) if age >= 0 else 1.0
    y = 1480 - (len(lines) - 1) * 52
    for line in lines:
        total = sum(im.width for im in line) + space * (len(line) - 1)
        x = W / 2 - total / 2
        for im in line:
            paste_center(img, im, x + im.width / 2, y, sc)
            x += im.width + space
        y += 104


# ----------------------------------------------------------------------------------------- audio
def env_decay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def sfx(kind):
    rng = np.random.default_rng(hash(kind) % 2**32)
    if kind == "pop":
        n = int(0.14 * SR)
        f = np.linspace(420, 110, n)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_decay(n, 0.04)
        s[: int(0.015 * SR)] += rng.normal(0, 0.5, int(0.015 * SR))
        return 0.55 * s
    if kind in ("splash", "whoosh"):
        n = int((0.5 if kind == "splash" else 0.35) * SR)
        noise = rng.normal(0, 1, n)
        k = 10 if kind == "splash" else 30
        noise = np.convolve(noise, np.ones(k) / k, "same")
        env = np.minimum(1, np.arange(n) / (0.01 * SR)) * env_decay(n, 0.13)
        if kind == "whoosh":
            env = np.sin(np.linspace(0, np.pi, n)) ** 2
        return (1.6 if kind == "splash" else 0.9) * noise * env
    if kind == "scoop":
        n = int(0.16 * SR)
        f = np.linspace(260, 760, n)
        return 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.linspace(0, np.pi, n))
    if kind in ("ding", "chime"):
        n = int(0.7 * SR)
        tt = np.arange(n) / SR
        notes = (1046.5, 1568.0) if kind == "ding" else (1046.5, 1318.5, 1568.0, 2093.0)
        s = np.zeros(n)
        for i, fr in enumerate(notes):
            off = int(i * 0.06 * SR) if kind == "chime" else 0
            s[off:] += np.sin(2 * np.pi * fr * tt[: n - off]) * env_decay(n - off, 0.18)
        return (0.16 if kind == "ding" else 0.12) * s
    if kind == "buzz":
        n = int(0.4 * SR)
        tt = np.arange(n) / SR
        s = np.sign(np.sin(2 * np.pi * 98 * tt)) + 0.5 * np.sign(np.sin(2 * np.pi * 104 * tt))
        s = np.convolve(s, np.ones(12) / 12, "same")
        return 0.18 * s * np.minimum(1, (n - np.arange(n)) / (0.08 * SR))
    raise ValueError(kind)


def music(n):
    """A soft chiptune loop: arpeggiated C - Am - F - G with a sine bass and a light kick."""
    total = n / SR
    out = np.zeros(n)
    bpm = 120
    eighth = 60 / bpm / 2
    chords = [(60, 64, 67, 72), (57, 60, 64, 69), (53, 57, 60, 65), (55, 59, 62, 67)]
    pattern = (0, 1, 2, 3, 2, 1, 2, 1)

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    step = 0
    while step * eighth < total:
        t0 = step * eighth
        chord = chords[(step // 8) % 4]
        i0 = int(t0 * SR)
        ln = min(int(eighth * SR * 0.95), n - i0)
        tt = np.arange(ln) / SR
        f = hz(chord[pattern[step % 8]] + 12)
        tri = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * tt))
        out[i0 : i0 + ln] += 0.22 * tri * env_decay(ln, 0.09)
        if step % 2 == 0:
            bl = min(int(2 * eighth * SR), n - i0)
            bt = np.arange(bl) / SR
            out[i0 : i0 + bl] += 0.35 * np.sin(2 * np.pi * hz(chord[0] - 24) * bt) * env_decay(bl, 0.25)
            kl = min(int(0.12 * SR), n - i0)
            kf = np.linspace(120, 45, kl)
            out[i0 : i0 + kl] += 0.4 * np.sin(2 * np.pi * np.cumsum(kf) / SR) * env_decay(kl, 0.03)
        step += 1
    fade = int(1.2 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())


# ----------------------------------------------------------------------------------------- main
def main():
    voices = synth_lines()
    ctxs, start = [], 0.0
    for i, ((name, text), v) in enumerate(zip(LINES, voices)):
        vd = len(v) / SR
        dur = VOICE_LEAD + vd + GAP + (TAIL if i == len(LINES) - 1 else 0)
        words, starts = word_times(text, vd)
        ctxs.append(Ctx(name, start, dur, words, starts, NOMINAL[name]))
        start += dur
    total = start
    print(f"duration {total:.1f}s")

    events = []
    for c in ctxs:
        events += [(c.start + lt, kind, pos) for lt, kind, pos in scene_events(c)]
    parts = make_particles(events)

    # audio
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for c, v in zip(ctxs, voices):
        i0 = int((c.start + VOICE_LEAD) * SR)
        voice[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.9
    fx = np.zeros(n)
    for t0, kind, _ in events:
        s = sfx(kind)
        i0 = int(t0 * SR)
        fx[i0 : i0 + len(s)] += s[: n - i0]
    mix = voice + 0.6 * fx + 0.09 * music(n)
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    wav = HERE / "audio.tmp.wav"
    write_wav(wav, mix[: int(total * SR)])

    # video
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(total * FPS)
    clip, clip_scene = None, None
    for f in range(frames):
        t = f / FPS
        si = max(i for i, c in enumerate(ctxs) if c.start <= t)
        c = ctxs[si]
        lt = t - c.start
        st = SCENES[c.name](lt, c)
        zoom, focus, sy = cam_at(c.name, lt, c.D)
        if si > 0:
            p = ctxs[si - 1]
            pz, pf, psy = cam_at(p.name, p.D, p.D)
            k = ease(lt / 0.6)
            zoom = lerp(pz, zoom, k)
            focus = tuple(lerp(u, v, k) for u, v in zip(pf, focus))
            sy = lerp(psy, sy, k)
        P = Proj(zoom, focus, sy)
        broll = has_broll(c.name)
        if broll:
            if clip_scene != si:
                if clip:
                    clip.close()
                clip, clip_scene = Clip(*BROLL[c.name]), si
            img = clip.frame()
        else:
            img = BG.copy()
            draw_clouds(img, t)
            draw_world(img, P, st, int(t * 6) % 8)
            draw_particles(img, P, parts, t)
            draw_scene_overlays(img, P, st)
        if si > 0 and broll != has_broll(ctxs[si - 1].name):
            st["flash"] = max(st["flash"], 1 - clamp01(lt / 0.2))
        if c.name != "outro":
            draw_header(img)
        if broll:
            draw_broll_label(img)
        if st["panel"]:
            draw_panel(img, st["panel"])
        if st["counter"] and not broll:
            draw_counter(img, st["counter"])
        if st["follow"] is not None:
            draw_follow(img, st["follow"])
        if lt >= VOICE_LEAD - 0.05:
            draw_caption(img, c.words, [s + VOICE_LEAD for s in c.starts], lt)
        if st["flash"] > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), st["flash"] * 0.85)
        ff.stdin.write(img.tobytes())
        if f % 150 == 0:
            print(f"frame {f}/{frames}")
    if clip:
        clip.close()
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
