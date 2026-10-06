#!/usr/bin/env python3
"""Render "Never Dig Straight Down": a cutaway Short, plus the subscriber-goal ending.

A side cutaway of the ground: grass, dirt, stone, ores and two hidden lava caves. You dig straight down,
fall into lava, then learn the staircase method and the water-bucket backup. Reuses the renderer from
../enderman, helpers from ../name_tags and the ending from ../sub_goal.py.

    SUBS=19 python shorts/dig_down/make_short.py   # -> shorts/dig_down/dig_down_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NT = _load("name_tags", HERE.parent / "name_tags" / "make_short.py")
SG = _load("sub_goal", HERE.parent / "sub_goal.py")
E, N, V = NT.E, NT.N, NT.V
SG.register(E)
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
ease, clamp01, lerp, bump = V.ease, V.clamp01, V.lerp, V.bump
OUT = HERE / "dig_down_short.mp4"

LINES = [
    ("never", "Never dig straight down."),
    ("why", "This is why."),
    ("unknown", "You can't see what's under the block you're mining. It could be a cave, or lava."),
    ("stairs", "Dig a staircase instead."),
    ("see", "That way, you always see what's in front of you, and you can't fall."),
    ("bucket", "And carry a water bucket. It turns lava into obsidian."),
    ("subs", SG.line()),
]
HOLD = {"never": 0.1, "why": 0.6, "unknown": 0.3, "stairs": 0.2, "see": 0.3, "bucket": 0.4, "subs": 0.8}
E.LINES = LINES

RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
CYAN, BLUE, PURPLE = (110, 230, 230), (110, 180, 255), (190, 130, 255)
N.KEYWORDS = {
    "never": RED, "straight": RED, "down": RED, "why": RED, "can't": RED, "under": YELLOW, "cave": YELLOW,
    "lava": ORANGE, "staircase": GREEN, "instead": GREEN, "always": GREEN, "see": GREEN, "fall": RED,
    "water": BLUE, "bucket": BLUE, "obsidian": PURPLE, "goal": CYAN, "diamond": CYAN, "subscriber": RED,
    "subscribe": RED, "yours": CYAN,
}  # fmt: skip

# ----------------------------------------------------------------------------------------- textures
E.TEX["grass_top"] = V.TEX["grass_top"][0]
E.TEX["grass_side"] = V.TEX["grass_side"][0]
E.TEX["dirt"] = V.TEX["dirt"][0]
E.TEX["stone"] = E.rgba(E.noise((126, 126, 128), 12))
E.TEX["stone_dark"] = E.rgba(E.noise((70, 70, 74), 9))
E.TEX["dirt_dark"] = E.rgba(V.TEX["dirt"][0][..., :3].astype(float) * 0.55)
rng = np.random.default_rng(51)


def ore(spot):
    a = E.noise((126, 126, 128), 12)
    for _ in range(5):
        y, x = rng.integers(2, 13, 2)
        a[y : y + 2, x : x + 3] = spot
    return E.rgba(a)


E.TEX["diamond_ore"] = ore((90, 230, 226))
E.TEX["iron_ore"] = ore((214, 170, 130))
E.TEX["coal_ore"] = ore((34, 34, 36))
ob = E.noise((30, 18, 44), 6)
ob[rng.random((16, 16)) < 0.15] = (70, 46, 100)
E.TEX["obsidian"] = E.rgba(ob)
for i, fr in enumerate(V.TEX["lava"]):
    E.TEX[f"lava{i}"] = fr.copy()

# ----------------------------------------------------------------------------------------- world
X0, X1, Y_BOTTOM = -6, 9, -13
CAVE_A = {(x, y) for x in range(-3, 3) for y in range(-9, -6)}
LAVA_A = [(x, -10) for x in range(-3, 3)]
CAVE_B = {(x, y) for x in range(5, 9) for y in range(-7, -4)}
LAVA_B = [(x, -8) for x in range(5, 9)]
ORES = {(3, -11): "diamond_ore", (4, -11): "diamond_ore", (-4, -6): "iron_ore", (-2, -4): "coal_ore",
        (3, -3): "coal_ore", (7, -10): "iron_ore", (-5, -10): "diamond_ore"}  # fmt: skip


def tex_at(x, y):
    if y == -1:
        return {"*": "grass_side", "+y": "grass_top"}
    if y >= -3:
        return {"*": "dirt"}
    return {"*": ORES.get((x, y), "stone")}


def world(removed=frozenset()):
    """Front cutaway layer (z=0) plus a darker back wall (z=1)."""
    b = {}
    lava_cells = set(LAVA_A) | set(LAVA_B)
    for x in range(X0, X1):
        for y in range(Y_BOTTOM, 0):
            back = "dirt_dark" if y >= -3 else "stone_dark"
            b[(x, y, 1)] = {"*": back}
            if (x, y) in CAVE_A or (x, y) in CAVE_B or (x, y) in removed or (x, y) in lava_cells:
                continue
            b[(x, y, 0)] = tex_at(x, y)
    return b


_wcache = {}


def world_faces(removed):
    key = frozenset(removed)
    if key not in _wcache:
        _wcache[key] = E.blocks_faces({**world(key), **E.tree(-4, 0), **E.tree(7, 0)})
    return _wcache[key]


def lava_faces(t, obsidian_b=False):
    f = []
    tex = f"lava{int(t * 6) % 8}"
    for x, y in LAVA_A:
        f += E.box((0, 0, 0), (1, 0.875, 1), {"*": tex}, origin=(x, y, 0))
    for x, y in LAVA_B:
        if obsidian_b:
            f += E.box((0, 0, 0), (1, 1, 1), {"*": "obsidian"}, origin=(x, y, 0), outline=True)
        else:
            f += E.box((0, 0, 0), (1, 0.875, 1), {"*": tex}, origin=(x, y, 0))
    return f


SHIRT, PANTS, SKIN, HAIR = (64, 150, 104), (58, 66, 128), (214, 162, 122), (78, 52, 34)


def miner(pos, yaw, t, swing=0.0, clip_y=None):
    M = E.Ry(yaw)
    f = []
    for lo, hi, col in (
        ((-0.25, 0, -0.125), (0, 0.75, 0.125), PANTS),
        ((0, 0, -0.125), (0.25, 0.75, 0.125), PANTS),
        ((-0.25, 0.75, -0.125), (0.25, 1.5, 0.125), SHIRT),
        ((-0.5, 0.75, -0.125), (-0.25, 1.5, 0.125), SKIN),
    ):
        f += E.box(lo, hi, {"*": col}, M, pos, clip_y=clip_y)
    a = -0.3 - 1.1 * swing
    R = E.Rx(a)
    piv = (0, 1.4, 0)
    f += E.box((0.25, 0.75, -0.125), (0.5, 1.5, 0.125), {"*": SKIN}, M, pos, piv, R)
    f += E.box((0.34, 0.72, -0.03), (0.41, 0.79, 0.6), {"*": (120, 85, 50)}, M, pos, piv, R)
    f += E.box((0.33, 0.52, 0.5), (0.42, 1.0, 0.6), {"*": (90, 220, 220)}, M, pos, piv, R)
    f += E.box((-0.25, 1.5, -0.25), (0.25, 2.0, 0.25), {"*": SKIN, "+y": HAIR, "+z": "player_face"}, M, pos)
    return f


def sky():
    k = np.linspace(0, 1, H)[:, None, None]
    arr = np.array((84, 146, 250.0)) * (1 - k) + np.array((198, 224, 255.0)) * k
    return Image.fromarray(np.broadcast_to(arr, (H, W, 3)).astype(np.uint8), "RGB")


SKY = sky()


def draw_death(img, lt):
    k = ease(lt / 0.25)
    img.paste(Image.blend(img, Image.new("RGB", (W, H), (150, 0, 0)), 0.55 * k))
    V.paste_center(img, V.text_img("You Died!", 128, WHITE, 0), W / 2, 560, V.pop_scale(lt, 0.25))
    V.paste_center(img, V.text_img("Player tried to swim in lava", 50, (235, 235, 235), 0), W / 2, 690, 1, k)
    d = ImageDraw.Draw(img)
    for i, label in enumerate(("Respawn", "Title Screen")):
        y = 800 + i * 120
        d.rectangle((240, y, 840, y + 90), fill=(110, 110, 110), outline=(30, 30, 30), width=5)
        V.paste_center(img, V.text_img(label, 44, WHITE, 0), W / 2, y + 47)


def outline_cells(img, cam, cells, col, width=7):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    pts = [(min(xs), max(ys) + 1), (max(xs) + 1, max(ys) + 1), (max(xs) + 1, min(ys)), (min(xs), min(ys))]
    proj = [cam.project((x, y, -0.02)) for x, y in pts]
    if all(proj):
        p = [q[0] for q in proj]
        d = ImageDraw.Draw(img)
        d.line(p + [p[0]], fill=(0, 0, 0), width=width + 6)
        d.line(p + [p[0]], fill=col, width=width)


def draw_fire(img, cam, center, t, s=1.0):
    pr = cam.project(center)
    if not pr:
        return
    (x, y), z = pr
    size = max(8, int(cam.f * 0.6 * s / z))
    for i, ox in enumerate((-0.4, 0.0, 0.4)):
        spr = N.fire_sprite(int(t * 12) + i * 3, size)
        img.paste(spr, (round(x + ox * size - size / 2), round(y - size * 0.9)), spr)


# ----------------------------------------------------------------------------------------- audio
def mine_tick():
    n = int(0.08 * SR)
    g = np.random.default_rng(14)
    return 0.3 * np.convolve(g.normal(0, 1, n), np.ones(5) / 5, "same") * np.exp(-np.arange(n) / (0.015 * SR))


def fall_whistle(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 900 - 500 * t / dur
    return 0.12 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.05)


def sizzle(dur):
    n = int(dur * SR)
    g = np.random.default_rng(3)
    return 0.12 * np.diff(g.normal(0, 1, n + 1)) * np.exp(-np.arange(n) / (0.5 * SR))


# ----------------------------------------------------------------------------------------- main
STEPS = [(1, [(1, -1)]), (2, [(2, -1), (2, -2)]), (3, [(3, -2), (3, -3)]), (4, [(4, -3), (4, -4)])]


def stair_removed(k):
    out = set()
    for i in range(k):
        out.update(STEPS[i][1])
    return out


def main():
    voices = E.synth()
    scenes, t = [], 0.0
    for (name, text), v in zip(LINES, voices):
        vd = len(v) / SR
        _, starts = V.word_times(text, vd)
        scenes.append(N.Scene(name, text, t, vd + 0.05 + HOLD[name], starts))
        t += scenes[-1].D
    total = t
    S = {s.name: s for s in scenes}
    print(f"duration {total:.1f}s")

    dig_times = [0.12 + 0.24 * i for i in range(6)]
    t_fall = dig_times[-1] + 0.2
    t_land = t_fall + 0.5
    st = S["stairs"]
    see = S["see"]
    stair_times = [st.start + 0.15 + i * (st.D + see.w["front"] - 0.3) / 4 for i in range(4)]
    t_reveal = stair_times[-1] + 0.2
    bk = S["bucket"]
    t_pour = bk.start + bk.w["bucket"]
    t_obs = bk.start + bk.w["turns"]

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

    for td in dig_times:
        add(td, mine_tick())
        add(td + 0.1, mine_tick(), 0.7)
    add(t_fall, fall_whistle(t_land - t_fall))
    add(t_land, V.sfx("splash"), 0.6)
    add(t_land, sizzle(1.2))
    add(S["why"].start + 0.25, N.wah_sfx())
    add(S["unknown"].start + S["unknown"].w["cave"], V.sfx("pop"))
    add(S["unknown"].start + S["unknown"].w["lava"], V.sfx("buzz"))
    for ts in stair_times:
        add(ts, mine_tick())
        add(ts + 0.12, mine_tick(), 0.7)
    add(t_reveal, V.sfx("ding"))
    add(t_pour, V.sfx("splash"), 0.7)
    add(t_obs, sizzle(0.6))
    add(t_obs + 0.1, V.sfx("chime"))
    sub = S["subs"]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(SG.SUBS):
        add(t0d + (t1d - t0d) * i / SG.SUBS, V.sfx("pop"), 0.6)
    add(t1d, V.sfx("chime"))
    for name in ("unknown", "stairs", "subs"):
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
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(total * FPS)
    for f in range(frames):
        t = f / FPS
        sc = max((s for s in scenes if s.start <= t), key=lambda s: s.start)
        lt, name = t - sc.start, sc.name
        pills, extra = [], []

        if name == "subs":
            img, _ = SG.render(E, V, N, lt, sc)
        else:
            removed, player, swing, death, fire = set(), None, 0.0, None, None
            obsidian = False
            if name in ("never", "why"):
                cam = E.Cam.look((0.5, -4.6, -9.2), (0.5, -4.6, 0.5))
                k = sum(1 for td in dig_times if t >= td + 0.1)
                removed = {(0, -1 - i) for i in range(k)}
                if t < t_fall:
                    feet = -float(k)
                    swing = abs(math.sin(t * 13))
                else:
                    q = clamp01((t - t_fall) / (t_land - t_fall))
                    feet = -6.0 - 3.15 * q * q
                    if t >= t_land:
                        feet = -9.15 - 0.9 * ease((t - t_land) / 0.8)
                        fire = (0.5, feet + 1.6, 0.0)
                player = ((0.5, feet, 0.5), math.pi)
                if name == "why":
                    death = lt
            elif name == "unknown":
                cam = E.Cam.look((0.5, -4.6, -9.2), (0.5, -4.6, 0.5))
                player = ((0.5, 0.0, 0.5), math.pi)
                pr = cam.project((0.5, -0.5, -0.05))
                pills.append(("?", (40, 40, 50), pr[0] if pr else (W / 2, 900), lt - 0.2, 70))
                if lt >= sc.w["cave"]:
                    extra.append(("outline", CAVE_A, YELLOW))
                    pr = cam.project((-0.5, -6.6, -0.05))
                    pills.append(("CAVE", (170, 140, 20), pr[0], lt - sc.w["cave"], 54))
                if lt >= sc.w["lava"]:
                    pr = cam.project((-0.5, -9.4, -0.05))
                    pills.append(("LAVA", (200, 70, 20), pr[0], lt - sc.w["lava"], 54))
            else:
                cam = E.Cam.look((3.6, -3.6, -9.6), (3.6, -3.6, 0.5))
                k = sum(1 for ts in stair_times if t >= ts + 0.12)
                removed = stair_removed(k)
                if name == "stairs" and k < 4:
                    swing = abs(math.sin(t * 13))
                x, feet = 0.5 + k, -float(k)
                if k == 4:
                    removed.add((5, -4))
                player = ((x, feet, 0.5), math.pi / 2 + 0.6)
                if name == "see" and t >= t_reveal:
                    extra.append(("outline", CAVE_B, GREEN))
                    pills.append(("SEE IT FIRST ✓", (30, 140, 60), (W / 2, 470), t - t_reveal, 60))
                if name == "bucket":
                    obsidian = t >= t_obs
                    if t_pour <= t < t_obs + 0.3:
                        extra.append(("water", t))
                    pills.append(("LAVA ➜ OBSIDIAN", (110, 50, 170), (W / 2, 470), t - t_obs, 60))
            faces = world_faces(removed) + lava_faces(t, obsidian)
            if player:
                faces += miner(player[0], player[1], t, swing)
            img = SKY.copy()
            E.draw_faces(img, cam, faces)
            for e in extra:
                if e[0] == "outline":
                    outline_cells(img, cam, e[1], e[2])
                elif e[0] == "water":
                    d = ImageDraw.Draw(img)
                    a = cam.project((5.0, -4.0, 0.2))
                    b = cam.project((6.5, -7.2, 0.2))
                    if a and b:
                        (ax, ay), _ = a
                        (bx, by), _ = b
                        k = clamp01((e[1] - t_pour) / 0.3)
                        d.polygon([(ax, ay), (ax + 50, ay), (lerp(ax + 50, bx + 120, k), lerp(ay, by, k)), (lerp(ax, bx - 120, k), lerp(ay, by, k))],
                                  fill=(70, 130, 240))  # fmt: skip
            if fire:
                draw_fire(img, cam, fire, t)
            if name == "never" and t >= t_land:
                img = Image.blend(img, Image.new("RGB", (W, H), (255, 120, 20)), 0.45 * math.exp(-(t - t_land) / 0.25))
            if death is not None:
                draw_death(img, death)
            if name == "bucket" and t >= t_obs:
                NT.draw_sparkles(img, cam, (6.5, -7.5, -0.2), t_obs, t, [(190, 130, 255), (255, 255, 255)], seed=9)
        for text, col, (x, y), age, size in pills:
            V.paste_center(img, V.pill(text, size, col), x, y, V.pop_scale(age))
        N.draw_caption(img, sc.words, sc.starts, lt, y=1330 if name != "why" else 1420)
        if name in ("unknown", "stairs", "subs") and lt < 0.1:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.25 * (1 - lt / 0.1))
        ffp.stdin.write(img.tobytes())
        if f % 90 == 0:
            print(f"frame {f}/{frames}", flush=True)
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
