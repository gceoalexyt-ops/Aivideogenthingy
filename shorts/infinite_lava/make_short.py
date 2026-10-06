#!/usr/bin/env python3
"""Render "Infinite Lava": the sequel to the infinite-water Short, plus the subscriber-goal ending.

A lava source on top of a block, pointed dripstone hanging under it, and a cauldron below: lava drips
through the dripstone and slowly fills the cauldron, forever. Reuses the first-person renderer from
../enderman and the mob/HUD helpers from ../name_tags; the ending comes from ../sub_goal.py.

    SUBS=19 python shorts/infinite_lava/make_short.py   # -> shorts/infinite_lava/infinite_lava_short.mp4
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
OUT = HERE / "infinite_lava_short.mp4"

LINES = [
    ("hook", "You know infinite water. But infinite lava?"),
    ("block", "Put lava on top of any block,"),
    ("drip", "hang pointed dripstone under it,"),
    ("cauldron", "and put a cauldron below."),
    ("fill", "The lava drips through the stone, and fills the cauldron. Forever."),
    ("slow", "It's slow, so build a few side by side."),
    ("fuel", "Every bucket smelts a hundred items in a furnace."),
    ("subs", SG.line()),
]
HOLD = {"hook": 0.25, "block": 0.15, "drip": 0.15, "cauldron": 0.3, "fill": 0.35, "slow": 0.3, "fuel": 0.35, "subs": 0.8}
E.LINES = LINES

RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
CYAN, BLUE = (110, 230, 230), (110, 180, 255)
N.KEYWORDS = {
    "infinite": YELLOW, "water": BLUE, "lava": ORANGE, "block": YELLOW, "pointed": YELLOW, "dripstone": YELLOW,
    "cauldron": YELLOW, "drips": ORANGE, "fills": ORANGE, "forever": GREEN, "slow": RED, "few": GREEN,
    "hundred": GREEN, "furnace": ORANGE, "goal": CYAN, "diamond": CYAN, "subscriber": RED, "subscribe": RED,
    "yours": CYAN, "nineteen": CYAN,
}  # fmt: skip

# ----------------------------------------------------------------------------------------- textures
r16, c16 = np.mgrid[0:16, 0:16]
E.TEX["stone"] = E.rgba(E.noise((126, 126, 128), 12))
ds = E.noise((150, 114, 92), 10)
ds[:, c16[0] % 5 == 0] *= 0.82
E.TEX["dripstone"] = E.rgba(ds)
cd = E.noise((70, 70, 76), 8)
cd[(r16 == 0) | (r16 == 15) | (c16 == 0) | (c16 == 15)] = (44, 44, 48)
E.TEX["cauldron"] = E.rgba(cd)
for i, fr in enumerate(V.TEX["lava"]):
    E.TEX[f"lava{i}"] = fr.copy()
fs = E.noise((116, 116, 118), 10)
E.TEX["furnace"] = E.rgba(fs)
ff = fs.copy()
ff[7:13, 3:13] = (40, 40, 42)
ff[2:4, 2:14] = (80, 80, 84)
E.TEX["furnace_front"] = E.rgba(ff)
fl = ff.copy()
fl[9:13, 4:12] = (255, 150, 40)
fl[11:13, 5:11] = (255, 230, 120)
E.TEX["furnace_lit"] = E.rgba(fl)


def lava_tex(t):
    return f"lava{int(t * 6) % 8}"


# ----------------------------------------------------------------------------------------- models
def farm(x0, z0, t, level, pop=None, lava_top=True, y0=3):
    """One lava farm at (x0, z0): cauldron on the ground, dripstone under a block with lava on top.
    pop: dict part -> scale (0..1) for build-in animation."""
    pop = pop or {}
    f = []

    def s(name):
        return pop.get(name, 1.0)

    k = s("block")
    if k > 0:
        c = 0.5 * (1 - k)
        f += E.box((c, c, c), (1 - c, 1 - c, 1 - c), {"*": "stone"}, origin=(x0, y0, z0), outline=True)
    k = s("lava")
    if k > 0 and lava_top:
        f += E.box((0, 0, 0), (1, 0.875 * k, 1), {"*": lava_tex(t)}, origin=(x0, y0 + 1, z0))
    k = s("drip")
    if k > 0:
        y = y0
        for w, h in ((0.5, 0.35), (0.36, 0.3), (0.24, 0.25), (0.12, 0.22)):
            h *= k
            f += E.box((0.5 - w / 2, y - h, 0.5 - w / 2), (0.5 + w / 2, y, 0.5 + w / 2), {"*": "dripstone"}, origin=(x0, 0, z0))
            y -= h
    k = s("cauldron")
    if k > 0:
        hgt = 0.95 * k
        look = {"*": "cauldron"}
        f += E.box((0, 0.2 * k, 0), (1, 0.32 * k, 1), look, origin=(x0, 0, z0))
        f += E.box((0, 0, 0), (0.125, hgt, 1), look, origin=(x0, 0, z0))
        f += E.box((0.875, 0, 0), (1, hgt, 1), look, origin=(x0, 0, z0))
        f += E.box((0.125, 0, 0), (0.875, hgt, 0.125), look, origin=(x0, 0, z0))
        f += E.box((0.125, 0, 0.875), (0.875, hgt, 1), look, origin=(x0, 0, z0))
        if level > 0.01 and k >= 1:
            f += E.box((0.125, 0.32, 0.125), (0.875, 0.32 + 0.56 * level, 0.875), {"*": lava_tex(t)}, origin=(x0, 0, z0))
    return f


def furnace(pos, lit):
    return E.box((0, 0, 0), (1, 1, 1), {"*": "furnace", "-z": "furnace_lit" if lit else "furnace_front"}, origin=pos, outline=True)


def draw_drips(img, cam, x0, z0, t, period, phase, level, y0=3):
    """Lava drops falling from the dripstone tip into the cauldron."""
    d = ImageDraw.Draw(img)
    tip, bottom = y0 - 1.12, 0.32 + 0.56 * level
    k = ((t + phase) % period) / period
    if k < 0.35:
        y = tip - 0.03 * (k / 0.35)
        rr = 0.045 * (k / 0.35) + 0.02
    else:
        q = (k - 0.35) / 0.65
        y = tip - (tip - bottom) * q * q
        rr = 0.06
        if q > 0.95:
            return True
    pr = cam.project((x0 + 0.5, y, z0 + 0.5))
    if pr:
        (sx, sy), z = pr
        r = max(3, cam.f * rr / z)
        d.ellipse((sx - r * 1.6, sy - r * 1.6, sx + r * 1.6, sy + r * 1.6), fill=(255, 120, 30))
        d.ellipse((sx - r, sy - r * 1.2, sx + r, sy + r * 1.2), fill=(255, 220, 90))
    return False


def drip_sfx():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 900 + 900 * t / 0.12
    return 0.18 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.03)


def sizzle(dur):
    n = int(dur * SR)
    g = np.random.default_rng(3)
    hp = np.diff(g.normal(0, 1, n + 1))
    return 0.05 * hp * (0.6 + 0.4 * np.sin(np.arange(n) / SR * 13))


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

    def at(scene, word, off=0.0):
        return S[scene].start + S[scene].w[word] + off

    T = {
        "lava_whip": at("hook", "lava", -0.15),
        "block": S["block"].start + 0.05,
        "lava": at("block", "block"),
        "drip": at("drip", "dripstone", -0.1),
        "cauldron": at("cauldron", "cauldron", -0.1),
        "fill0": S["fill"].start,
        "full": at("fill", "forever", -0.1),
        "slow": S["slow"].start,
        "fuel": at("fuel", "bucket"),
        "lit": at("fuel", "smelts"),
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

    add(0.05, V.sfx("splash"), 0.5)
    add(T["lava_whip"], V.sfx("whoosh"), 0.7)
    for k in ("block", "drip", "cauldron"):
        add(T[k], V.sfx("pop"))
    add(T["lava"], V.sfx("splash"), 0.4)
    add(T["lava"], sizzle(T["slow"] - T["lava"]), 0.8)
    t_d = T["fill0"]
    while t_d < T["full"]:
        add(t_d, drip_sfx())
        t_d += 0.55
    add(T["full"], V.sfx("chime"))
    add(T["lit"], NT.sparkle(), 0.8)
    add(T["fuel"], V.sfx("splash"), 0.4)
    sub = S["subs"]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(SG.SUBS):
        add(t0d + (t1d - t0d) * i / SG.SUBS, V.sfx("pop"), 0.6)
    add(t1d, V.sfx("chime"))
    for name in ("slow", "fuel", "subs"):
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
    E.WMAP[:] = False
    for x, z in ((-6, 3), (-5, 3), (-6, 4), (-5, 4)):
        E.WMAP[x + E.WMAP_OFF, z + E.WMAP_OFF] = True

    for f in range(frames):
        t = f / FPS
        sc = max((s for s in scenes if s.start <= t), key=lambda s: s.start)
        lt, name = t - sc.start, sc.name
        pills = []

        if name == "subs":
            img, _ = SG.render(E, V, N, lt, sc)
        else:
            faces = list(E.TREE_FACES)
            pop = {
                "block": ease((t - T["block"]) / 0.2),
                "lava": ease((t - T["lava"]) / 0.3),
                "drip": ease((t - T["drip"]) / 0.25),
                "cauldron": ease((t - T["cauldron"]) / 0.2),
            }
            level = clamp01((t - T["fill0"]) / max(0.1, T["full"] - T["fill0"]))
            drips = []
            if name == "hook":
                if t < T["lava_whip"]:
                    cam = E.Cam.look((-5.0, 2.4, 0.4), (-5.0, 0.0, 4.0))
                    pills.append(("INFINITE WATER ✓", (40, 110, 210), (W / 2, 470), lt - 0.2, 60))
                else:
                    k = ease((t - T["lava_whip"]) / 0.3)
                    cam = E.Cam.look((lerp(-5.0, 2.2, k), 2.4, lerp(0.4, -2.2, k)), (lerp(-5.0, 0.5, k), lerp(0.0, 2.2, k), lerp(4.0, 0.5, k)))
                    faces += farm(0, 0, t, 0.6)
                    drips.append((0, 0, 0.9, 0.0, 0.6))
                    pills.append(("INFINITE LAVA?", (210, 90, 20), (W / 2, 470), t - T["lava_whip"] - 0.15, 60))
            elif name in ("block", "drip", "cauldron", "fill"):
                a = 0.9 * (t - S["block"].start) / max(1.0, S["fill"].start + S["fill"].D - S["block"].start) - 0.45
                cam = E.Cam.look((0.5 + 6.3 * math.sin(a), 3.0, 0.5 - 6.3 * math.cos(a)), (0.5, 2.3, 0.5))
                faces += farm(0, 0, t, level, pop)
                if name == "fill":
                    drips.append((0, 0, 0.55, 0.0, level))
                    if t >= T["full"]:
                        pills.append(("FULL. FOREVER. ∞", (30, 140, 60), (W / 2, 470), t - T["full"], 60))
            elif name == "slow":
                k = ease(lt / 0.6)
                cam = E.Cam.look((0.5, lerp(2.6, 4.2, k), lerp(-3.7, -7.5, k)), (0.5, 1.6, 0.5))
                for i, x0 in enumerate((-4, -2, 0, 2, 4)):
                    lv = (0.35 + 0.6 * ((lt * 0.3 + i * 0.37) % 1)) if x0 != 0 else 1.0
                    faces += farm(x0, 0, t, lv)
                    drips.append((x0, 0, 0.8 + 0.13 * i, i * 0.3, lv))
                pills.append(("SLOW? BUILD MORE", (180, 60, 40), (W / 2, 470), lt - 0.3, 60))
            else:  # fuel
                cam = E.Cam.look((-0.2, 2.2, -3.2), (1.0, 0.8, 0.5))
                faces += farm(-1.2, 0.0, t, 1.0)
                faces += furnace((1.4, 0, 0), t >= T["lit"])
                drips.append((-1.2, 0.0, 0.8, 0.0, 1.0))
                pills.append(("1 BUCKET = 100 ITEMS", (200, 90, 20), (W / 2, 470), t - T["lit"], 60))
            img = E.render_env(cam, t)
            E.draw_faces(img, cam, faces)
            for x0, z0, period, phase, lv in drips:
                draw_drips(img, cam, x0, z0, t, period, phase, lv)
            for k, part in (("block", "block"), ("lava", "lava"), ("drip", "drip"), ("cauldron", "cauldron")):
                if name in ("block", "drip", "cauldron"):
                    NT.draw_sparkles(img, cam, (0.5, {"block": 3.5, "lava": 4.5, "drip": 2.5, "cauldron": 0.5}[part], 0.5),
                                     T[k], t, [(255, 255, 255), (255, 220, 120)], n=14, seed=len(part))  # fmt: skip
            if name == "fill" and t >= T["full"]:
                NT.draw_sparkles(img, cam, (0.5, 0.9, 0.5), T["full"], t, [(255, 200, 60), (255, 255, 255)], seed=7)
            if name == "fuel" and t >= T["lit"]:
                NT.draw_sparkles(img, cam, (1.9, 0.6, 0.0), T["lit"], t, [(255, 160, 40), (255, 240, 140)], seed=8)
        for text, col, (x, y), age, size in pills:
            V.paste_center(img, V.pill(text, size, col), x, y, V.pop_scale(age))
        N.draw_caption(img, sc.words, sc.starts, lt, y=1330)
        if name in ("slow", "fuel", "subs") and lt < 0.1:
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
