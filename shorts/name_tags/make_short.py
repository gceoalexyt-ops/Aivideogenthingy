#!/usr/bin/env python3
"""Render "Name Tag Secrets": a first-person, loopable YouTube Short about secret mob names.

Dinnerbone/Grumm flip a mob upside down, jeb_ makes a sheep rainbow (shearing still drops its real color),
Toast gives a rabbit a memorial skin, Johnny turns a vindicator on almost every mob, and named mobs never
despawn. Reuses the first-person renderer in ../enderman/make_short.py with new mob models.

    python shorts/name_tags/make_short.py       # -> shorts/name_tags/name_tags_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("enderman", HERE.parent / "enderman" / "make_short.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
N, V = E.N, E.V
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
ease, clamp01, lerp, bump = V.ease, V.clamp01, V.lerp, V.bump
OUT = HERE / "name_tags_short.mp4"

LINES = [
    ("dinner", "Name any mob Dinnerbone, and this happens."),
    ("grumm", "Grumm works too."),
    ("jeb", "Name a sheep jeb, with an underscore, and it turns rainbow."),
    ("shear", "But shear it, and you still get its real color."),
    ("toast", "Name a rabbit Toast, and it gets a special skin, made in memory of a player's lost bunny."),
    ("johnny", "Name a vindicator Johnny, and it attacks almost every mob it sees."),
    ("bonus", "Bonus: named mobs never despawn."),
    ("loop", "So grab a name tag, and"),
]
HOLD = {"dinner": 0.45, "grumm": 0.3, "jeb": 0.35, "shear": 0.35, "toast": 0.3, "johnny": 0.35, "bonus": 0.35, "loop": 0.0}
E.LINES = LINES

RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
PINK, BLUE = (255, 140, 200), (120, 190, 255)
N.KEYWORDS = {
    "dinnerbone": YELLOW, "happens": RED, "grumm": YELLOW, "jeb": PINK, "underscore": PINK, "rainbow": PINK,
    "shear": BLUE, "real": GREEN, "color": GREEN, "toast": ORANGE, "special": ORANGE, "memory": ORANGE,
    "bunny": ORANGE, "johnny": RED, "attacks": RED, "every": RED, "bonus": YELLOW, "never": GREEN,
    "despawn": GREEN, "name": YELLOW, "tag": YELLOW,
}  # fmt: skip

# ----------------------------------------------------------------------------------------- palette
E.SKY_TOP, E.SKY_HOR, E.CLOUD = np.array((84, 146, 250.0)), np.array((198, 224, 255.0)), np.array((255, 255, 255.0))
E.GRASS = V.TEX["grass_top"][0][..., :3].astype(float)
E.GRASS_AVG = E.GRASS.reshape(-1, 3).mean(0)
E.tex_tile.cache_clear()

# ----------------------------------------------------------------------------------------- textures
rng = np.random.default_rng(41)
r16, c16 = np.mgrid[0:16, 0:16]


def blobs(base, spot, n, seed, size=2.6):
    g = np.random.default_rng(seed)
    arr = E.noise(base, 6)
    for _ in range(n):
        cy, cx, rr = g.uniform(0, 16), g.uniform(0, 16), g.uniform(1.5, size)
        arr[np.hypot(r16 - cy, c16 - cx) < rr] = spot
    return arr


hide = blobs((236, 234, 228), (44, 34, 32), 5, 1, 3.2)
E.TEX["cow_hide"] = E.rgba(hide)
E.TEX["cow_hide_hurt"] = E.rgba(hide * np.array((1.0, 0.45, 0.45)) + np.array((90, 0, 0)))
cface = E.noise((44, 34, 32), 4)
cface[2:6, 4:12] = (236, 234, 228)
cface[6:8, 3:5] = (250, 250, 250)
cface[6:8, 11:13] = (250, 250, 250)
cface[7, 4] = cface[7, 11] = (20, 20, 20)
cface[10:15, 4:12] = (226, 160, 160)
cface[12, 5:7] = cface[12, 9:11] = (120, 70, 70)
E.TEX["cow_face"] = E.rgba(cface)
E.TEX["cow_face_hurt"] = E.rgba(cface * np.array((1.0, 0.45, 0.45)) + np.array((90, 0, 0)))
sface = E.noise((206, 176, 146), 6)
sface[6:8, 3:6] = (250, 250, 250)
sface[6:8, 10:13] = (250, 250, 250)
sface[6:8, 4] = sface[6:8, 11] = (30, 30, 30)
sface[11:13, 6:10] = (226, 160, 160)
E.TEX["sheep_face"] = E.rgba(sface)
E.TEX["rabbit_fur"] = E.rgba(E.noise((150, 112, 74), 10))
E.TEX["toast_fur"] = E.rgba(blobs((240, 240, 238), (30, 28, 28), 6, 3, 3.0))
for name, base in (("rabbit_face", (150, 112, 74)), ("toast_face", (240, 240, 238))):
    fc = E.noise(base, 6)
    if name == "toast_face":
        fc[:7, :8] = (30, 28, 28)
    fc[6:9, 2:5] = (30, 20, 20)
    fc[6:9, 11:14] = (30, 20, 20)
    fc[10:12, 7:9] = (240, 150, 170)
    E.TEX[name] = E.rgba(fc)
vf = E.noise((146, 156, 148), 6)
vf[4, 2:14] = (40, 40, 40)
vf[5:7, 3:6] = (250, 250, 250)
vf[5:7, 10:13] = (250, 250, 250)
vf[5:7, 4] = vf[5:7, 11] = (40, 110, 60)
vf[12, 5:11] = (90, 70, 70)
E.TEX["vind_face"] = E.rgba(vf)

DYES = [
    (240, 240, 240), (250, 150, 40), (200, 80, 200), (110, 170, 230), (250, 215, 50), (120, 200, 40),
    (240, 140, 170), (70, 70, 75), (150, 150, 145), (40, 140, 150), (130, 50, 180), (50, 70, 170),
    (120, 80, 50), (90, 120, 30), (180, 40, 40), (25, 25, 30),
]  # fmt: skip


def rainbow(t):
    x = (t * 1.4) % 16
    i = int(x)
    a, b = DYES[i], DYES[(i + 1) % 16]
    return tuple(int(lerp(a[k], b[k], x - i)) for k in range(3))


# ----------------------------------------------------------------------------------------- models
def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def place(faces, pos, yaw, flip=0.0, h=1.0, hop=0.0):
    """Model space -> world: optional upside-down flip about mid-height, yaw, then translate."""
    R = E.Ry(yaw) @ Rz(flip)
    c = np.array([0, h / 2, 0])
    t = np.array(pos, float) + np.array([0, hop, 0])
    out = []
    for v, n, look, outline in faces:
        out.append((((v - c) @ R.T) + c + t, R @ n, look, outline))
    return out


def legs4(lo_x, hi_x, lo_z, hi_z, height, w, col, t, walk):
    sw = 0.5 * walk * math.sin(t * 8)
    f = []
    for i, (x, z) in enumerate(((lo_x, lo_z), (hi_x - w, lo_z), (lo_x, hi_z - w), (hi_x - w, hi_z - w))):
        a = sw if i in (0, 3) else -sw
        f += E.box((x, 0, z), (x + w, height, z + w), {"*": col}, pivot=(0, height, z + w / 2), R=E.Rx(a))
    return f


def cow(t, walk=0.0, hurt=False):
    hide, face = ("cow_hide_hurt", "cow_face_hurt") if hurt else ("cow_hide", "cow_face")
    f = legs4(-0.4, 0.4, -0.55, 0.55, 0.72, 0.25, hide, t, walk)
    f += E.box((-0.45, 0.72, -0.6), (0.45, 1.45, 0.6), {"*": hide})
    f += E.box((-0.25, 0.95, 0.6), (0.25, 1.45, 0.95), {"*": hide, "+z": face})
    for x in (-0.33, 0.25):
        f += E.box((x, 1.38, 0.68), (x + 0.08, 1.55, 0.76), {"*": (220, 210, 190)})
    return f


def sheep(t, wool=(240, 240, 240), sheared=False, walk=0.0):
    skin = (206, 176, 146)
    f = legs4(-0.35, 0.35, -0.45, 0.45, 0.7, 0.2, skin, t, walk)
    if sheared:
        f += E.box((-0.3, 0.7, -0.45), (0.3, 1.2, 0.45), {"*": tuple(int(c * 0.55 + s * 0.45) for c, s in zip(wool, skin))})
    else:
        f += E.box((-0.42, 0.62, -0.55), (0.42, 1.38, 0.55), {"*": wool})
    f += E.box((-0.2, 0.95, 0.5), (0.2, 1.35, 0.85), {"*": skin, "+z": "sheep_face", "+y": wool if not sheared else skin})
    return f


def rabbit(t, toast=False):
    fur, face = ("toast_fur", "toast_face") if toast else ("rabbit_fur", "rabbit_face")
    f = E.box((-0.15, 0, -0.25), (0.15, 0.3, 0.15), {"*": fur})
    f += E.box((-0.13, 0.18, 0.1), (0.13, 0.42, 0.34), {"*": fur, "+z": face})
    for x in (-0.11, 0.04):
        f += E.box((x, 0.42, 0.18), (x + 0.07, 0.68, 0.24), {"*": fur})
    return f


ROBE, PANTS, VSKIN = (66, 74, 96), (44, 48, 66), (146, 156, 148)


def vindicator(t, walk=0.0, swing=0.0):
    sw = 0.6 * walk * math.sin(t * 10)
    f = E.box((-0.25, 0, -0.12), (0.0, 0.75, 0.12), {"*": PANTS}, pivot=(0, 0.75, 0), R=E.Rx(sw))
    f += E.box((0.0, 0, -0.12), (0.25, 0.75, 0.12), {"*": PANTS}, pivot=(0, 0.75, 0), R=E.Rx(-sw))
    f += E.box((-0.25, 0.75, -0.15), (0.25, 1.5, 0.15), {"*": ROBE})
    f += E.box((-0.25, 1.5, -0.25), (0.25, 2.0, 0.25), {"*": VSKIN, "+z": "vind_face", "+y": (40, 40, 44)})
    f += E.box((-0.05, 1.5, 0.25), (0.05, 1.72, 0.35), {"*": VSKIN})
    f += E.box((-0.38, 0.8, -0.1), (-0.25, 1.48, 0.1), {"*": ROBE}, pivot=(0, 1.45, 0), R=E.Rx(-sw))
    arm = E.Rx(-1.2 - 1.4 * swing)
    f += E.box((0.25, 0.8, -0.1), (0.38, 1.48, 0.1), {"*": ROBE}, pivot=(0, 1.45, 0), R=arm)
    f += E.box((0.28, 0.45, -0.04), (0.35, 0.85, 0.04), {"*": (112, 80, 48)}, pivot=(0, 1.45, 0), R=arm)
    f += E.box((0.26, 0.45, 0.02), (0.37, 0.62, 0.24), {"*": (206, 208, 214)}, pivot=(0, 1.45, 0), R=arm)
    return f


def wool_cube(pos, t0, t):
    dt = max(0.0, t - t0)
    y = max(0.0, 1.0 + 3.2 * dt - 9 * dt * dt)
    s = 0.13
    return E.box((-s, 0, -s), (s, 2 * s, s), {"*": (242, 242, 242)}, E.Ry(dt * 3), (pos[0], y, pos[2]))


# ----------------------------------------------------------------------------------------- HUD
NAME_TAG = [
    "................",
    "...ooo..........",
    "..o...o.........",
    "..o...o.........",
    "...ooo#####.....",
    "......#BBBB#....",
    ".....#BBBBBB#...",
    "....#BBBBBBBB#..",
    "....#BB....BB#..",
    "....#BBBBBBBB#..",
    "....#BbbbbbbB#..",
    "....#BBBBBBBB#..",
    "....##########..",
    "................",
    "................",
    "................",
]
SHEARS = [
    "................",
    "..........##....",
    ".........#ww#...",
    "........#ww#....",
    ".......#ww#.....",
    "..##..#ww#......",
    ".#ww##ww#.......",
    "..##ww#.........",
    "...#ww#.........",
    "..#rr##ww#......",
    ".#r..r#.##......",
    ".#r..r#.........",
    "..#rr#..........",
    "................",
    "................",
    "................",
]


@lru_cache(maxsize=8)
def item_sprite(kind, size):
    art = NAME_TAG if kind == "tag" else SHEARS
    cols = {"#": (60, 44, 30), "B": (226, 204, 150), "b": (170, 150, 104), "o": (150, 150, 150),
            "w": (220, 220, 226), "r": (200, 50, 40)}  # fmt: skip
    arr = np.zeros((16, 16, 4), np.uint8)
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch in cols:
                arr[y, x] = cols[ch] + (255,)
    return Image.fromarray(arr, "RGBA").resize((size, size), Image.NEAREST).rotate(-25, expand=True)


def draw_hand_item(img, t, item, jab):
    dx, dy = -90 * jab, -120 * jab
    by = 6 * math.sin(t * 3.2) + dy
    d = ImageDraw.Draw(img)
    for poly, col in (
        ([(700, 1920), (900, 1920), (1010, 1585), (850, 1535)], (214, 162, 122)),
        ([(900, 1920), (1080, 1920), (1080, 1640), (1010, 1585)], (176, 128, 94)),
        ([(850, 1535), (1010, 1585), (1080, 1555), (930, 1505)], (232, 184, 146)),
    ):
        d.polygon([(x + dx, y + by) for x, y in poly], fill=col)
    if item:
        spr = item_sprite(item, 300)
        img.paste(spr, (round(760 + dx), round(1270 + by)), spr)


@lru_cache(maxsize=256)
def label_img(text, size):
    t = V.text_img(text, size, WHITE, 0)
    im = Image.new("RGBA", (t.width + size // 2, t.height + size // 3), (0, 0, 0, 110))
    im.alpha_composite(t, (size // 4, size // 6))
    return im


def draw_label(img, cam, pt, text, age):
    if age < 0:
        return
    pr = cam.project(pt)
    if not pr:
        return
    (x, y), z = pr
    size = int(max(20, min(96, cam.f * 0.2 / z)))
    V.paste_center(img, label_img(text, size), x, y, V.pop_scale(age, 0.2))


def draw_sparkles(img, cam, center, t0, t, cols, n=26, seed=0, dur=0.7):
    dt = t - t0
    if not 0 <= dt < dur:
        return
    g = np.random.default_rng(seed)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        p = np.array(center, float) + g.uniform(-0.6, 0.6, 3) + g.uniform(-1, 1, 3) * 1.4 * dt + np.array([0, 0.8 * dt, 0])
        pr = cam.project(p)
        if not pr:
            continue
        (x, y), z = pr
        s = max(3, cam.f * 0.05 / z) * (1 - dt / dur)
        d.rectangle((x - s, y - s, x + s, y + s), fill=cols[g.integers(len(cols))])


# ----------------------------------------------------------------------------------------- audio
def boing():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 220 + 380 * np.abs(np.sin(2 * np.pi * 2.0 * t)) * np.exp(-t / 0.3) + 25 * np.sin(2 * np.pi * 14 * t)
    return 0.3 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.25)


def snip():
    n = int(0.25 * SR)
    g = np.random.default_rng(12)
    out = np.zeros(n)
    for start in (0, int(0.11 * SR)):
        ln = int(0.03 * SR)
        out[start : start + ln] += np.diff(g.normal(0, 1, ln + 1)) * np.exp(-np.arange(ln) / (0.006 * SR))
    return 0.35 * out


def thud():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(13)
    f = np.linspace(150, 50, n)
    return 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.06) + 0.25 * g.normal(0, 1, n) * np.exp(-t / 0.02)


def sparkle():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for i, fr in enumerate((1318.5, 1568, 2093, 2637, 3136)):
        o = int(i * 0.07 * SR)
        out[o:] += np.sin(2 * np.pi * fr * t[: n - o]) * np.exp(-t[: n - o] / 0.15)
    return 0.09 * out


# ----------------------------------------------------------------------------------------- main
COW = (0.0, 0.0, 3.9)
SHEEP1 = (2.9, 0.0, 5.6)
SHEEP2 = (-2.5, 0.0, 5.0)
RABBIT = (-1.1, 0.0, 2.9)
CAM0 = ((0.0, 1.62, 0.0), (0.0, 0.95, 3.9))


def main():
    voices = E.synth()
    scenes, t = [], 0.0
    for (name, text), v in zip(LINES, voices):
        vd = len(v) / SR
        _, starts = V.word_times(text, vd)
        dur = vd + 0.05 + HOLD[name]
        scenes.append(N.Scene(name, text, t, dur, starts))
        t += dur
    total = t
    S = {s.name: s for s in scenes}
    print(f"duration {total:.1f}s")

    def at(scene, word, off=0.0):
        return S[scene].start + S[scene].w[word] + off

    T = {
        "cow_name": at("dinner", "dinnerbone", -0.1),
        "cow_flip": at("dinner", "happens"),
        "s1_name": S["grumm"].start + 0.05,
        "s1_flip": S["grumm"].start + 0.45,
        "s2_name": at("jeb", "jeb", -0.1),
        "s2_rain": at("jeb", "rainbow"),
        "shear": at("shear", "shear"),
        "real": at("shear", "real"),
        "rab_name": at("toast", "toast", -0.1),
        "rab_skin": at("toast", "special"),
        "memory": at("toast", "memory"),
        "hit1": at("johnny", "attacks"),
        "hit2": at("johnny", "sees", -0.1),
    }

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

    for k in ("cow_name", "s1_name", "s2_name", "rab_name"):
        add(T[k] + 0.12, V.sfx("ding"))
    add(T["cow_flip"], boing())
    add(T["s1_flip"], boing(), 0.8)
    add(T["s2_rain"], sparkle())
    add(T["shear"], snip())
    add(T["shear"] + 0.05, V.sfx("pop"))
    add(T["shear"] + 0.2, V.sfx("pop"))
    add(T["rab_skin"], V.sfx("whoosh"), 0.6)
    add(T["rab_skin"], sparkle(), 0.7)
    add(T["hit1"], thud())
    add(T["hit2"], thud())
    add(S["bonus"].start + S["bonus"].w["never"], V.sfx("chime"))
    for name in ("johnny", "bonus", "loop"):
        add(S[name].start - 0.1, V.sfx("whoosh"), 0.5)
    mix = voice + 0.7 * fx + 0.1 * V.music(n)
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

    def flip_amt(t, t0):
        return math.pi * ease((t - t0) / 0.3)

    for f in range(frames):
        t = f / FPS
        sc = max((s for s in scenes if s.start <= t), key=lambda s: s.start)
        lt, name = t - sc.start, sc.name
        fresh = name == "loop"  # the loop scene resets the world to frame 0
        faces = list(E.TREE_FACES)
        labels, after, pills = [], [], []
        item, jab, fp = "tag", 0.0, True

        # --- world state
        cow_flip = 0.0 if fresh else flip_amt(t, T["cow_flip"])
        s1_flip = 0.0 if fresh else flip_amt(t, T["s1_flip"])
        s2_wool = (240, 240, 240) if fresh or t < T["s2_rain"] else rainbow(t - T["s2_rain"])
        s2_sheared = not fresh and t >= T["shear"]
        toast = not fresh and t >= T["rab_skin"]
        hurt = (not fresh) and (0 <= t - T["hit1"] < 0.3)
        cow_yaw = math.pi
        faces += place(cow(t, walk=0.0 if cow_flip == 0 else 0.7, hurt=hurt), COW, cow_yaw, cow_flip, 1.5)
        faces += place(sheep(t, walk=0.0 if s1_flip == 0 else 0.7), SHEEP1, math.pi - 0.6, s1_flip, 1.4)
        faces += place(sheep(t, s2_wool, s2_sheared), SHEEP2, math.pi + 0.5, 0.0, 1.4)
        hop = 0.0 if fresh else 0.25 * abs(math.sin(t * 5))
        faces += place(rabbit(t, toast), RABBIT, math.pi - 0.3, 0.0, 0.7, hop)
        if not fresh:
            if t >= T["cow_name"]:
                labels.append(((COW[0], 2.0, COW[2]) if cow_flip < 1.5 else (COW[0], 2.0, COW[2]), "Dinnerbone", t - T["cow_name"]))
            if t >= T["s1_name"]:
                labels.append(((SHEEP1[0], 1.9, SHEEP1[2]), "Grumm", t - T["s1_name"]))
            if t >= T["s2_name"]:
                labels.append(((SHEEP2[0], 1.9, SHEEP2[2]), "jeb_", t - T["s2_name"]))
            if t >= T["rab_name"]:
                labels.append(((RABBIT[0], 1.05, RABBIT[2]), "Toast", t - T["rab_name"]))
            for k, pos, cols in (
                ("cow_flip", (COW[0], 0.8, COW[2]), [(255, 255, 255), (255, 230, 120)]),
                ("s1_flip", (SHEEP1[0], 0.8, SHEEP1[2]), [(255, 255, 255), (255, 230, 120)]),
                ("s2_rain", (SHEEP2[0], 0.9, SHEEP2[2]), DYES[1:7]),
                ("rab_skin", (RABBIT[0], 0.3, RABBIT[2]), [(255, 255, 255), (30, 30, 30), (255, 200, 120)]),
            ):
                after.append(("sparkle", pos, T[k], cols))
            if t >= T["shear"]:
                for i, off in enumerate(((0.5, 0, -0.4), (-0.3, 0, -0.6))):
                    p = np.array(SHEEP2) + np.array(off)
                    faces += wool_cube(p, T["shear"] + 0.12 * i, t)

        # --- camera and per-scene extras
        cam = E.Cam.look(*CAM0)
        if name == "dinner":
            jab = bump(t, T["cow_name"] - 0.05, T["cow_name"] + 0.25)
            if t >= T["cow_flip"]:
                pills.append(("UPSIDE DOWN!", (200, 60, 60), (W / 2, 470), t - T["cow_flip"] - 0.15, 66))
        elif name == "grumm":
            k = ease(lt / 0.35)
            target = np.array(CAM0[1]) * (1 - k) + np.array([SHEEP1[0], 0.9, SHEEP1[2]]) * k
            cam = E.Cam.look(CAM0[0], target)
            jab = bump(t, T["s1_name"] - 0.05, T["s1_name"] + 0.25)
        elif name == "jeb":
            k = ease(lt / 0.35)
            target = np.array([SHEEP1[0], 0.9, SHEEP1[2]]) * (1 - k) + np.array([SHEEP2[0], 0.9, SHEEP2[2]]) * k
            cam = E.Cam.look((0, 1.62, 0.8 * k), target)
            jab = bump(t, T["s2_name"] - 0.05, T["s2_name"] + 0.25)
            pills.append(("TYPE IT: jeb_", (170, 60, 150), (W / 2, 470), t - T["s2_name"] - 0.2, 60))
        elif name == "shear":
            cam = E.Cam.look((-1.1, 1.62, 2.4), (SHEEP2[0], 0.7, SHEEP2[2] - 0.4))
            item = "shears"
            jab = bump(t, T["shear"] - 0.05, T["shear"] + 0.25)
            pills.append(("DROPS WHITE WOOL", (60, 110, 190), (W / 2, 470), t - T["real"], 60))
        elif name == "toast":
            cam = E.Cam.look((0, 1.62, 0.2), (RABBIT[0], 0.3, RABBIT[2]))
            jab = bump(t, T["rab_name"] - 0.05, T["rab_name"] + 0.25)
            pills.append(("IN MEMORY OF TOAST ♥", (200, 110, 40), (W / 2, 470), t - T["memory"], 56))
        elif name in ("johnny", "bonus"):
            fp = False
            if name == "johnny":
                cam = E.Cam.look((-5.5, 2.6, 0.2), (-0.6, 1.0, 5.2))
                k1 = ease((t - sc.start) / max(0.1, T["hit1"] - sc.start - 0.15))
                p0, p1 = np.array([-6.0, 0, 8.0]), np.array([-0.9, 0, 4.2])
                p2 = np.array([-1.7, 0, 5.2])
                if t < T["hit1"]:
                    vp, walk = p0 + (p1 - p0) * k1, 1.0
                    d = p1 - p0
                else:
                    k2 = ease((t - T["hit1"] - 0.25) / max(0.1, T["hit2"] - T["hit1"] - 0.5))
                    vp, walk = p1 + (p2 - p1) * k2, (1.0 if 0 < k2 < 1 else 0.0)
                    d = (np.array(SHEEP2) - vp) if t > T["hit1"] + 0.25 else np.array(COW) - vp
                yaw = math.atan2(d[0], d[2])
                swing = bump(t, T["hit1"] - 0.15, T["hit1"] + 0.2) + bump(t, T["hit2"] - 0.15, T["hit2"] + 0.2)
                faces += place(vindicator(t, walk, swing), vp, yaw, 0.0, 2.0)
                labels.append(((vp[0], 2.45, vp[2]), "Johnny", lt - 0.1))
                pills.append(("ATTACKS ALMOST EVERYTHING", (180, 40, 40), (W / 2, 470), t - T["hit1"], 52))
            else:
                cam = E.Cam.look((0.2, 2.5, -2.4), (0.0, 0.8, 4.4))
                faces += place(vindicator(t), (-1.7, 0, 5.2), math.pi - 0.4, 0.0, 2.0)
                labels.append(((-1.7, 2.45, 5.2), "Johnny", 9))
                pills.append(("✓ NEVER DESPAWN", (30, 140, 60), (W / 2, 470), lt - sc.w["never"], 66))
        elif name == "loop":
            cam = E.Cam.look(*CAM0)

        img = E.render_env(cam, t)
        E.draw_faces(img, cam, faces)
        for a in after:
            draw_sparkles(img, cam, a[1], a[2], t, a[3], seed=int(a[2] * 100))
        for pt, text, age in labels:
            draw_label(img, cam, pt, text, age)
        for text, col, (x, y), age, size in pills:
            V.paste_center(img, V.pill(text, size, col), x, y, V.pop_scale(age))
        if fp:
            E.draw_crosshair(img)
            draw_hand_item(img, t, item, jab)
        N.draw_caption(img, sc.words, sc.starts, lt, y=1330)
        if name in ("johnny", "bonus", "loop") and lt < 0.1:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.25 * (1 - lt / 0.1))
        ff.stdin.write(img.tobytes())
        if f % 90 == 0:
            print(f"frame {f}/{frames}", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
