#!/usr/bin/env python3
"""Render "I put 100 rabbits on an island. Then I added 10 foxes.": an ecosystem-simulation Short.

Everything on the island is a real agent simulation (../sim.py); nothing is keyframed. The edit is built
on the run's own events: the foxes are dropped in after two years, the camera follows a real chase in
slow motion, then the actual last rabbit until it's caught, then the foxes starve. Narrator: Kokoro
"am_onyx".

    python ecosim/foxes_rabbits/make_short.py   # -> ecosim/foxes_rabbits/foxes_rabbits_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from ecosim import sim  # noqa: E402

OUT = HERE / "foxes_rabbits_short.mp4"
_spec = importlib.util.spec_from_file_location("water_elevator", HERE.parent.parent / "shorts" / "water_elevator" / "make_short.py")
WE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WE)
N, V = WE.N, WE.V
W, H, SR, FPS = V.W, V.H, V.SR, 30
SEED = int(os.environ.get("SEED", "18"))
PARAMS = sim.Params(fox_gain=1.2, fox_burn=0.006, fox_speed=3.8, rabbit_flee=60, fox_sense=170)
T_ADD = 60  # foxes arrive after two years
VOICE = "am_onyx"
BASE = 1080 / 1100  # screen px per world unit at zoom 1 (whole island in frame)
ISLAND_Y = 1010  # where the island centre sits on screen in the wide shot
TEX_EXT, TEX_PPU = 1100.0, 2.0  # world textures cover [-1100, 1100]^2 at 2 px per unit
WHITE, RED, YELLOW = (255, 255, 255), (235, 55, 55), (255, 220, 60)
RAB_COL, FOX_COL = (238, 234, 226), (228, 112, 34)
N.KEYWORDS = {
    "rabbits": (225, 225, 255), "rabbit": (225, 225, 255), "island": (120, 220, 140), "foxes": FOX_COL,
    "ten": FOX_COL, "hundred": (225, 225, 255), "last": RED, "won": FOX_COL, "starved": RED, "next": YELLOW,
}  # fmt: skip
LINES = [
    ("hook", "I put a hundred rabbits on an island."),
    ("foxes", "Then I added ten foxes."),
    ("eat", "Every rabbit they ate made more foxes."),
    ("last", "This is the last rabbit."),
    ("starve", "The foxes won. Then they starved."),
    ("next", "Who should I add next?"),
]


# ================================================================ simulation record
def record():
    w = sim.new_world(SEED, foxes=0, p=PARAMS)

    def snap():
        return {
            "r_pos": w.rab["pos"].copy(), "r_head": w.rab["head"].copy(), "r_id": w.rab["id"].copy(),
            "f_pos": w.fox["pos"].copy(), "f_head": w.fox["head"].copy(), "f_id": w.fox["id"].copy(),
            "f_en": w.fox["energy"].copy(), "grass": w.grass.copy(), "catch": list(w.catch_log), "death": list(w.death_log),
        }  # fmt: skip

    S = [snap()]
    ext_r = ext_f = None
    while w.tick < 100 * sim.TICKS_PER_YEAR:
        if w.tick == T_ADD:
            sim.add_foxes(w, 10)
        sim.step(w)
        S.append(snap())
        nr, nf = len(w.rab["pos"]), len(w.fox["pos"])
        if ext_r is None and nr == 0:
            ext_r = len(S) - 1
        if ext_r and nf == 0:
            ext_f = len(S) - 1
            break
    return S, ext_r, ext_f


def state_at(S, ft):
    """Animals at a fractional tick, interpolated by id so slow motion stays smooth."""
    k = int(np.clip(math.floor(ft), 0, len(S) - 1))
    k1 = min(k + 1, len(S) - 1)
    a = float(np.clip(ft - k, 0, 1))
    out = {}
    for p in ("r", "f"):
        A, B = S[k], S[k1]
        ids0, ids1 = A[p + "_id"], B[p + "_id"]
        pos = A[p + "_pos"].copy()
        j = np.searchsorted(ids1, ids0)
        j = np.clip(j, 0, max(0, len(ids1) - 1))
        match = (len(ids1) > 0) & (ids1[j] == ids0) if len(ids1) else np.zeros(len(ids0), bool)
        pos[match] = pos[match] * (1 - a) + B[p + "_pos"][j[match]] * a
        keep = match | (a < 0.5)
        res = {"pos": pos[keep], "head": A[p + "_head"][keep], "id": ids0[keep]}
        if p == "f":
            res["en"] = A["f_en"][keep]
        if a >= 0.5:  # newborns appear half way
            new = ~np.isin(ids1, ids0)
            for key, src in (("pos", "_pos"), ("head", "_head"), ("id", "_id")):
                res[key] = np.concatenate([res[key], B[p + src][new]])
            if p == "f":
                res["en"] = np.concatenate([res["en"], B["f_en"][new]])
        out[p] = res
    out["grass"] = S[k]["grass"] * (1 - a) + S[k1]["grass"] * a
    return out


# ================================================================ world textures
def value_noise(size, cells, rng):
    small = rng.uniform(0, 1, (cells, cells)).astype(np.float32)
    return np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC), np.float32) / 255


def build_world(rng):
    n = int(2 * TEX_EXT * TEX_PPU)
    c = (np.arange(n) + 0.5) / TEX_PPU - TEX_EXT
    X, Y = np.meshgrid(c, c)
    rr, th = np.hypot(X, Y), np.arctan2(Y, X)
    coast = 492 + 16 * np.sin(3 * th + 1.0) + 10 * np.sin(7 * th + 2.0) + 6 * np.sin(13 * th)
    n1, n2, n3 = value_noise(n, 24, rng), value_noise(n, 90, rng), value_noise(n, 300, rng)
    # grass and dirt
    g = 0.55 * n1 + 0.3 * n2 + 0.15 * n3
    grass = np.stack([60 + 40 * g, 135 + 50 * g, 50 + 25 * g], -1)
    blades = rng.uniform(0, 1, (n, n)) > 0.985
    grass[blades] *= 0.72
    d = 0.5 * n1 + 0.5 * n2
    dirt = np.stack([125 + 40 * d, 98 + 32 * d, 62 + 22 * d], -1)
    # beach and sea (identical in both textures)
    depth = np.clip((rr - coast) / 160, 0, 1)
    wave = 0.5 + 0.5 * np.sin(rr / 9.0 + 2 * n1 * 6.28)
    sea = np.stack([25 + 40 * (1 - depth), 95 + 90 * (1 - depth) + 10 * wave, 150 + 60 * (1 - depth) + 8 * wave], -1)
    sand = np.stack([226 + 14 * n2, 204 + 12 * n2, 150 + 10 * n2], -1)
    foam = (rr >= coast) & (rr < coast + 6)
    outside = rr >= sim.ISLAND_R + 4
    for tex in (grass, dirt):
        tex[outside & (rr < coast)] = sand[outside & (rr < coast)]
        tex[rr >= coast] = sea[rr >= coast]
        tex[foam] = (235, 245, 245)
    gimg, dimg = Image.fromarray(grass.astype(np.uint8)), Image.fromarray(dirt.astype(np.uint8))
    # trees and rocks along the edge of the island (drawn into both textures, under the animals)
    for img in (gimg, dimg):
        dr = ImageDraw.Draw(img)
        trng = np.random.default_rng(7)
        for _ in range(26):
            a = trng.uniform(0, 2 * math.pi)
            r = trng.uniform(440, 478)
            x, y = (r * math.cos(a) + TEX_EXT) * TEX_PPU, (r * math.sin(a) + TEX_EXT) * TEX_PPU
            s = trng.uniform(14, 24) * TEX_PPU
            dr.ellipse([x - s + 8, y - s + 12, x + s + 8, y + s + 12], fill=(40, 60, 35))
            dr.ellipse([x - s, y - s, x + s, y + s], fill=(34, 98, 44))
            dr.ellipse([x - s * 0.6, y - s * 0.7, x + s * 0.3, y + s * 0.1], fill=(52, 128, 58))
        for _ in range(10):
            a = trng.uniform(0, 2 * math.pi)
            r = trng.uniform(470, 490)
            x, y = (r * math.cos(a) + TEX_EXT) * TEX_PPU, (r * math.sin(a) + TEX_EXT) * TEX_PPU
            s = trng.uniform(6, 11) * TEX_PPU
            dr.ellipse([x - s, y - s * 0.7, x + s, y + s * 0.7], fill=(128, 126, 120), outline=(90, 88, 84), width=3)
    return gimg, dimg


# ================================================================ drawing
class Cam:
    def __init__(self, cx, cy, z):
        self.cx, self.cy, self.z = cx, cy, z
        self.s = BASE * z

    def to_screen(self, p):
        return W / 2 + (p[..., 0] - self.cx) * self.s, H / 2 + (p[..., 1] - self.cy) * self.s

    def world_box(self):
        hw, hh = W / 2 / self.s, H / 2 / self.s
        return self.cx - hw, self.cy - hh, self.cx + hw, self.cy + hh


WIDE = Cam(0.0, (H / 2 - ISLAND_Y) / BASE, 1.0)


def lerp_cam(a, b, k):
    k = k * k * (3 - 2 * k)
    # interpolate zoom in log space so it feels even
    z = math.exp(math.log(a.z) * (1 - k) + math.log(b.z) * k)
    return Cam(a.cx + (b.cx - a.cx) * k, a.cy + (b.cy - a.cy) * k, z)


def draw_ground(cam, grass, gtex, dtex):
    x0, y0, x1, y1 = cam.world_box()
    box = tuple((v + TEX_EXT) * TEX_PPU for v in (x0, y0, x1, y1))
    g_img = gtex.resize((W, H), Image.BILINEAR, box=box)
    d_img = dtex.resize((W, H), Image.BILINEAR, box=box)
    # grass level grid (covers the sim island) padded so any camera box stays inside it
    pad = 30
    cell = 2 * sim.ISLAND_R / sim.GRID
    gg = np.pad(grass, pad, constant_values=1.0)
    m = Image.fromarray((np.clip(gg, 0, 1) * 255).astype(np.uint8))
    gb = tuple(((v + sim.ISLAND_R) / cell + pad) for v in (x0, y0, x1, y1))
    mask = m.resize((W, H), Image.BILINEAR, box=gb)
    return Image.composite(g_img, d_img, mask)


def ell(cx, cy, a, b, ang, n=16):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x, y = a * np.cos(t), b * np.sin(t)
    c, s = math.cos(ang), math.sin(ang)
    return list(zip(cx + x * c - y * s, cy + x * s + y * c))


def local(cx, cy, ang, lx, ly, s):
    c, sn = math.cos(ang), math.sin(ang)
    return cx + (lx * c - ly * sn) * s, cy + (lx * sn + ly * c) * s


def draw_rabbit(d, sh, x, y, ang, s, col=RAB_COL, eyes=False):
    k = s * 1.25
    sh.polygon(ell(x + 3 * k, y + 4 * k, 12 * k, 8 * k, ang), fill=(0, 0, 0, 70))
    out = (120, 108, 96)
    tx, ty = local(x, y, ang, -11, 0, k)
    d.ellipse([tx - 3.4 * k, ty - 3.4 * k, tx + 3.4 * k, ty + 3.4 * k], fill=(255, 255, 255), outline=out)
    d.polygon(ell(*local(x, y, ang, -2, 0, k), 9.5 * k, 6.8 * k, ang), fill=col, outline=out)
    hx, hy = local(x, y, ang, 7, 0, k)
    d.polygon(ell(hx, hy, 5.6 * k, 4.6 * k, ang), fill=col, outline=out)
    for side in (-1, 1):  # long ears lying back over the shoulders, on top so they always read
        ex, ey = local(x, y, ang, 1.5, side * 2.6, k)
        a = ang + side * 0.28
        d.polygon(ell(ex, ey, 7.5 * k, 2.2 * k, a), fill=col, outline=out)
        if k > 1.4:
            d.polygon(ell(ex, ey, 5.5 * k, 0.9 * k, a), fill=(240, 170, 180))
    nx, ny = local(x, y, ang, 12.2, 0, k)
    d.ellipse([nx - 1.1 * k, ny - 1.1 * k, nx + 1.1 * k, ny + 1.1 * k], fill=(230, 130, 150))
    if eyes:
        for side in (-1, 1):
            ex, ey = local(x, y, ang, 8.5, side * 3.4, k)
            d.ellipse([ex - 0.9 * k, ey - 0.9 * k, ex + 0.9 * k, ey + 0.9 * k], fill=(25, 15, 15))


def draw_fox(d, sh, x, y, ang, s, starve=0.0, eyes=False):
    k = s * 1.25
    grey = lambda c: tuple(int(v * (1 - starve) + 120 * starve) for v in c)  # noqa: E731
    body, cream, dark = grey(FOX_COL), grey((250, 238, 220)), grey((70, 35, 20))
    sh.polygon(ell(x - 2 * k, y + 5 * k, 20 * k, 8 * k, ang), fill=(0, 0, 0, 70))
    d.polygon(ell(*local(x, y, ang, -16, 0, k), 9 * k, 4.2 * k, ang), fill=body, outline=dark)
    tx, ty = local(x, y, ang, -24, 0, k)
    d.ellipse([tx - 3.2 * k, ty - 3.2 * k, tx + 3.2 * k, ty + 3.2 * k], fill=cream)
    thin = 1 - 0.35 * starve
    d.polygon(ell(*local(x, y, ang, -2, 0, k), 12 * k, 6.5 * k * thin, ang), fill=body, outline=dark)
    for side in (-1, 1):
        pts = [local(x, y, ang, 8, side * 3, k), local(x, y, ang, 6, side * 9, k), local(x, y, ang, 12, side * 5, k)]
        d.polygon(pts, fill=dark)
    hx, hy = local(x, y, ang, 11, 0, k)
    d.ellipse([hx - 5.5 * k, hy - 5.5 * k, hx + 5.5 * k, hy + 5.5 * k], fill=body, outline=dark)
    d.polygon([local(x, y, ang, 14, -3.2, k), local(x, y, ang, 21, 0, k), local(x, y, ang, 14, 3.2, k)], fill=cream)
    nx, ny = local(x, y, ang, 21, 0, k)
    d.ellipse([nx - 1.3 * k, ny - 1.3 * k, nx + 1.3 * k, ny + 1.3 * k], fill=(15, 10, 10))
    if eyes:
        for side in (-1, 1):
            ex, ey = local(x, y, ang, 13, side * 2.4, k)
            d.ellipse([ex - 1.1 * k, ey - 1.1 * k, ex + 1.1 * k, ey + 1.1 * k], fill=(20, 15, 10))


def icon(kind, size):
    im = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(im)
    sh = ImageDraw.Draw(Image.new("RGBA", (size, size)))
    if kind == "r":
        draw_rabbit(d, sh, size * 0.52, size * 0.52, -math.pi / 2, size / 34, eyes=True)
    else:
        draw_fox(d, sh, size * 0.5, size * 0.62, -math.pi / 2, size / 52, eyes=True)
    return im


# ================================================================ audio
def env(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def chomp(g=1.0):
    n = int(0.16 * SR)
    rng = np.random.default_rng(3)
    t = np.arange(n) / SR
    return g * (0.5 * np.sin(2 * np.pi * np.cumsum(np.linspace(240, 60, n)) / SR) * env(n, 0.04) + 0.3 * rng.normal(0, 1, n) * env(n, 0.012) * (t < 0.04))


def thud():
    n = int(0.3 * SR)
    rng = np.random.default_rng(4)
    return 0.7 * np.sin(2 * np.pi * np.cumsum(np.linspace(110, 40, n)) / SR) * env(n, 0.07) + 0.15 * rng.normal(0, 1, n) * env(n, 0.02)


def heartbeat():
    n = int(0.35 * SR)
    one = 0.8 * np.sin(2 * np.pi * np.cumsum(np.linspace(70, 40, int(0.12 * SR))) / SR) * env(int(0.12 * SR), 0.03)
    out = np.zeros(n)
    out[: len(one)] += one
    out[int(0.16 * SR) : int(0.16 * SR) + len(one)] += 0.7 * one
    return out


def swell(dur, up=True):
    n = int(dur * SR)
    rng = np.random.default_rng(5)
    x = np.convolve(rng.normal(0, 1, n), np.ones(30) / 30, "same") * 4
    e = np.linspace(0, 1, n) ** 2 if up else np.linspace(1, 0, n) ** 2
    return 0.35 * x * e


def boom():
    n = int(2.0 * SR)
    rng = np.random.default_rng(8)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(np.linspace(80, 32, n)) / SR) * env(n, 0.45) + 0.3 * rng.normal(0, 1, n) * env(n, 0.06)


def music(n, segs):
    """Pulse that tightens through the hunt, drops out for the last rabbit, then a low drone."""
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    out = np.zeros(n)
    t0, t1 = segs["foxes"][0], segs["last"][0]
    t, beat, i = t0, 0.36, 0
    bass = [45, 45, 48, 43]
    while t < t1:
        i0 = int(t * SR)
        ln = min(int(beat * SR * 0.9), n - i0)
        tt = np.arange(ln) / SR
        f = hz(bass[(i // 4) % 4])
        out[i0 : i0 + ln] += 0.22 * np.sign(np.sin(2 * np.pi * f * tt)) * env(ln, 0.06) * 0.6
        kl = min(int(0.1 * SR), n - i0)
        out[i0 : i0 + kl] += 0.35 * np.sin(2 * np.pi * np.cumsum(np.linspace(120, 45, kl)) / SR) * env(kl, 0.03)
        if i % 2:
            hl = min(int(0.04 * SR), n - i0)
            out[i0 : i0 + hl] += 0.06 * np.random.default_rng(i).normal(0, 1, hl) * env(hl, 0.01)
        beat = max(0.2, beat * 0.985)
        t += beat
        i += 1
    out = np.convolve(out, np.ones(4) / 4, "same")
    a, b = int(segs["starve"][0] * SR), n
    tt = np.arange(b - a) / SR
    out[a:b] += 0.12 * (np.sin(2 * np.pi * hz(33) * tt) + 0.5 * np.sin(2 * np.pi * hz(40) * tt)) * np.minimum(1, tt / 0.5)
    return out


def synth(texts):
    from kokoro_onnx import Kokoro

    d = V.kokoro_dir()
    k = Kokoro(str(d / V.KOKORO_FILES[0]), str(d / V.KOKORO_FILES[1]))
    out = []
    for text in texts:
        s, sr = k.create(text, voice=VOICE, speed=1.06, lang="en-us")
        s = np.asarray(s, np.float32)
        loud = np.nonzero(np.abs(s) > 0.02)[0]
        s = s[max(0, loud[0] - int(0.02 * sr)) : loud[-1] + int(0.06 * sr)]
        n = int(len(s) * SR / sr)
        out.append(np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32))
    return out


# ================================================================ edit
def ease_io(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def main():
    S, ext_r, ext_f = record()
    yr = lambda tick: tick / sim.TICKS_PER_YEAR  # noqa: E731
    nr = np.array([len(s["r_id"]) for s in S])
    nf = np.array([len(s["f_id"]) for s in S])
    print(f"seed {SEED}: rabbits peak {nr.max()}, foxes peak {nf.max()}, last rabbit caught year {yr(ext_r):.1f}, last fox year {yr(ext_f):.1f}")
    last_fid, last_rid, _ = S[ext_r]["catch"][-1]

    # a real chase for the slow-motion cut: a catch while the foxes are booming, with the fox in view for 1 s before
    chase, best = None, 0.0
    for k in range(T_ADD + 90, ext_r - 60):
        if not (40 <= nf[k] <= 220):
            continue
        for fid, rid, pos in S[k]["catch"]:
            k0 = k - 30
            if np.hypot(*pos) > 330 or fid not in S[k0]["f_id"] or rid not in S[k0]["r_id"]:
                continue
            fp = S[k0]["f_pos"][np.searchsorted(S[k0]["f_id"], fid)]
            rp = S[k0]["r_pos"][np.searchsorted(S[k0]["r_id"], rid)]
            dist = float(np.hypot(*(fp - rp)))
            if dist > best:  # the longest real chase that ends in a catch
                chase, best = (k, fid, rid), dist
    print("chase", chase)
    k_few = max(ext_r - 40, int(np.argmax((nr <= 3) & (np.arange(len(S)) > T_ADD))))

    names = [n for n, _ in LINES]
    voice = dict(zip(names, synth([t for _, t in LINES])))
    vd = {k: len(v) / SR for k, v in voice.items()}

    # segments: name, duration, tick0, tick1, timing, camera
    hook_rabbit = S[0]["r_id"][int(np.argmin(np.hypot(*S[0]["r_pos"].T)))]
    ck, cfid, crid = chase
    segs_def = [
        ("hook", max(2.2, vd["hook"] + 0.2), 0, T_ADD, "lin", ("reveal", hook_rabbit)),
        ("foxes", max(1.7, vd["foxes"] + 0.25), T_ADD + 1, T_ADD + 18, "lin", ("wide",)),
        ("eat", 1.6, T_ADD + 18, ck - 30, "accel", ("wide",)),
        ("chase", 1.9, ck - 30, ck + 4, "lin", ("track", cfid, 3.0)),
        ("ff", 1.3, ck + 4, k_few, "io", ("wide",)),
        ("last", max(2.6, vd["last"] + 1.0), k_few, ext_r, "lin", ("track_r", last_rid, 3.2)),
        ("caught", 0.45, ext_r, ext_r, "lin", ("track_r", last_rid, 3.2)),
        ("starve", max(2.4, vd["starve"] + 0.35), ext_r, ext_f, "io", ("out", last_rid)),
        ("next", vd["next"] + 1.5, ext_f, ext_f, "lin", ("wide",)),
    ]
    segs, t = {}, 0.0
    for name, dur, k0, k1, mode, cam in segs_def:
        segs[name] = (t, dur, k0, k1, mode, cam)
        t += dur
    total = t
    starts = {"hook": 0.0, "foxes": segs["foxes"][0] + 0.05, "eat": segs["eat"][0] + 0.05, "last": segs["last"][0] + 0.15,
              "starve": segs["starve"][0] + 0.25, "next": segs["next"][0] + 0.35}  # fmt: skip
    print(f"duration {total:.1f}s: " + ", ".join(f"{k} {v[0]:.1f}" for k, v in segs.items()))

    def tick_at(tv):
        for name, (t0, dur, k0, k1, mode, _) in segs.items():
            if t0 <= tv < t0 + dur or name == "next":
                u = min(1.0, (tv - t0) / dur)
                if mode == "accel":
                    u = u * u
                elif mode == "io":
                    u = ease_io(u)
                return name, k0 + (k1 - k0) * u, u

    # ---------------- audio
    n = int(total * SR) + SR
    vo = np.zeros(n)
    for k in names:
        i0 = int(starts[k] * SR)
        v = voice[k]
        vo[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.95
    fx = np.zeros(n)

    def add(t0, snd, g=1.0):
        i0 = int(max(0, t0) * SR)
        if i0 < n:
            fx[i0 : i0 + len(snd)] += g * snd[: n - i0]

    # catches -> chomps (throttled); find the video time of each tick by sampling the edit
    times = np.arange(0, total, 1 / 120)
    ticks = np.array([tick_at(tv)[1] for tv in times])
    last_c = -1
    for k in range(1, len(S)):
        if not S[k]["catch"]:
            continue
        hit = np.nonzero((ticks >= k) & (ticks < k + 1))[0]
        if not len(hit):
            continue
        tv = times[hit[0]]
        if tv - last_c > 0.07:
            big = any(c[1] in (crid, last_rid) for c in S[k]["catch"])
            add(tv, chomp(1.4 if big else 0.6))
            last_c = tv
    t_drop = segs["foxes"][0]
    for i in range(10):
        add(t_drop + 0.25 + 0.06 * i, thud(), 0.5)
    add(segs["chase"][0] - 0.25, swell(0.3), 1.0)
    add(segs["ff"][0], swell(segs["ff"][1], up=False), 0.8)
    t_hb = segs["last"][0] + 0.2
    gap = 0.75
    while t_hb < segs["caught"][0]:
        add(t_hb, heartbeat(), 1.0)
        gap = max(0.42, gap * 0.9)
        t_hb += gap
    add(segs["caught"][0], boom(), 0.9)
    add(segs["next"][0], boom(), 0.7)
    mus = music(n, segs)
    mix = vo + 0.85 * fx + 0.5 * mus
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    wav = HERE / "audio.tmp.wav"
    V.write_wav(wav, mix[: int(total * SR)])

    # ---------------- video
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    gtex, dtex = build_world(np.random.default_rng(11))
    r_icon, f_icon = icon("r", 96), icon("f", 96)
    bursts = []  # [x_world, y_world, t0, big]
    seen_catch = set()
    frames = int(total * FPS)
    first = None
    vign = None
    yy, xx = np.mgrid[0:H, 0:W]
    vign = np.clip((np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) - 0.55) / 0.6, 0, 1)[..., None].astype(np.float32)
    for f in range(frames):
        tv = f / FPS
        seg, ft, u = tick_at(tv)
        t0, dur, k0, k1, mode, camspec = segs[seg]
        st = state_at(S, ft)
        lt = tv - t0

        def pos_of(kind, aid):
            ids = st[kind]["id"]
            m = np.nonzero(ids == aid)[0]
            return st[kind]["pos"][m[0]] if len(m) else None

        # camera
        kind = camspec[0]
        if kind == "wide":
            cam = WIDE
        elif kind == "reveal":
            p = S[0]["r_pos"][np.searchsorted(S[0]["r_id"], camspec[1])]
            close = Cam(p[0], p[1] - 40, 4.5)
            cam = lerp_cam(close, WIDE, min(1, max(0, (lt - 0.35) / (dur * 0.75))))
        elif kind in ("track", "track_r"):
            p = pos_of("f" if kind == "track" else "r", camspec[1])
            if p is None:
                p = track_last
            track_last = p
            target = Cam(p[0], p[1] + 110 / (BASE * camspec[2]), camspec[2])
            cam = lerp_cam(WIDE, target, min(1, lt / 0.45)) if seg == "last" else target
        else:  # "out": pull back from where the last rabbit died
            cam = lerp_cam(Cam(track_last[0], track_last[1] + 110 / (BASE * 3.2), 3.2), WIDE, min(1, lt / 0.9))

        img = draw_ground(cam, st["grass"], gtex, dtex)
        shadow = Image.new("RGBA", (W, H))
        sd = ImageDraw.Draw(shadow)
        layer = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(layer)
        eyes = cam.z > 1.8
        rx, ry = cam.to_screen(st["r"]["pos"])
        on = (rx > -40) & (rx < W + 40) & (ry > -40) & (ry < H + 40)
        for x, y, a in zip(rx[on], ry[on], st["r"]["head"][on]):
            draw_rabbit(d, sd, x, y, a, cam.s, eyes=eyes)
        fx_, fy_ = cam.to_screen(st["f"]["pos"])
        on = (fx_ > -60) & (fx_ < W + 60) & (fy_ > -60) & (fy_ < H + 60)
        drop_t = tv - segs["foxes"][0] - 0.25
        for i, (x, y, a, en) in enumerate(zip(fx_[on], fy_[on], st["f"]["head"][on], st["f"]["en"][on])):
            starve = float(np.clip((0.6 - en) / 0.6, 0, 1)) if seg in ("starve", "next") else 0.0
            if seg == "foxes":
                h = 1 - min(1, max(0, (drop_t - 0.06 * i) / 0.3))
                if drop_t - 0.06 * i < 0:
                    continue
                sd.ellipse([x - 16 * cam.s, y - 8 * cam.s, x + 16 * cam.s, y + 8 * cam.s], fill=(0, 0, 0, int(90 * (1 - h))))
                draw_fox(d, sd, x, y - 260 * h * h, a, cam.s * (1 + 1.4 * h), eyes=eyes)
            else:
                draw_fox(d, sd, x, y, a, cam.s, starve=starve, eyes=eyes)
        # catch bursts
        for k in range(int(ft) - 1, int(ft) + 1):
            if 0 <= k < len(S):
                for c in S[k]["catch"]:
                    if (k, c[1]) not in seen_catch and k <= ft:
                        seen_catch.add((k, c[1]))
                        bursts.append([c[2][0], c[2][1], tv, 1 if c[1] in (crid, last_rid) else 0.5])
        alive = []
        for b in bursts:
            age = tv - b[2]
            if age < 0.45:
                bx, by = cam.to_screen(np.array([b[0], b[1]]))
                r = (8 + 40 * age / 0.45) * cam.s * (1 + b[3])
                a = int(220 * (1 - age / 0.45))
                d.ellipse([bx - r, by - r, bx + r, by + r], outline=(255, 60, 60, a), width=max(2, int(3 * cam.s)))
                rng = np.random.default_rng(int(b[2] * 1000))
                for _ in range(8 if b[3] else 4):
                    ang = rng.uniform(0, 2 * np.pi)
                    dd = r * rng.uniform(0.6, 1.3)
                    pr = 2.2 * cam.s
                    d.ellipse([bx + dd * math.cos(ang) - pr, by + dd * math.sin(ang) - pr, bx + dd * math.cos(ang) + pr, by + dd * math.sin(ang) + pr], fill=(255, 255, 255, a))
                alive.append(b)
        bursts = alive
        img = Image.alpha_composite(Image.alpha_composite(img.convert("RGBA"), shadow), layer).convert("RGB")

        # grading: dark vignette for the last rabbit, red flash when it's caught, grey for the starving
        arr = np.asarray(img, np.float32)
        if seg in ("last", "caught"):
            pulse = 0.55 + 0.1 * math.sin(tv * 9)
            arr = arr * (1 - pulse * vign * min(1, lt / 0.4) if seg == "last" else 1 - 0.65 * vign)
        if seg == "caught":
            fl = math.exp(-lt / 0.15)
            arr = arr * (1 - 0.5 * fl) + np.array([255, 30, 30]) * 0.5 * fl
        if seg in ("starve", "next"):
            g = arr.mean(-1, keepdims=True)
            k = min(1, (tv - segs["starve"][0]) / 2.0) * 0.55
            arr = arr * (1 - k) + g * k
        if seg == "ff":
            arr = arr * 0.85 + 30
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        if seg == "caught":
            sh = 18 * math.exp(-lt / 0.12)
            img = img.transform(img.size, Image.AFFINE, (1, 0, sh * math.sin(tv * 80), 0, 1, sh * math.cos(tv * 60)))

        # HUD
        tick_i = int(min(len(S) - 1, max(0, ft)))
        img.paste(r_icon, (60, 150), r_icon)
        img.paste(f_icon, (W - 156, 150), f_icon)
        V.paste_center(img, V.text_img(str(nr[tick_i]), 92, WHITE, 11), 240, 200)
        V.paste_center(img, V.text_img(str(nf[tick_i]) if tick_i > T_ADD else "0", 92, FOX_COL, 11), W - 250, 200)
        V.paste_center(img, V.text_img(f"YEAR {int(yr(tick_i))}", 52, YELLOW if seg == "ff" else WHITE, 9), W / 2, 200, 1.0 + (0.15 if seg == "ff" else 0))
        if seg == "ff":
            V.paste_center(img, V.pill(">>  FAST FORWARD", 46, (20, 20, 30)), W / 2, 330)
        if seg == "chase":
            V.paste_center(img, V.pill("SLOW MOTION", 42, (20, 20, 30)), W / 2, 330, V.pop_scale(lt))
        if seg == "next":
            V.paste_center(img, V.text_img("NOBODY", 150, RED, 16), W / 2, 820, V.pop_scale(lt, 0.18) * (1 + 0.3 * math.exp(-lt / 0.1)))
            V.paste_center(img, V.text_img("SURVIVED", 150, RED, 16), W / 2, 970, V.pop_scale(lt - 0.15, 0.18))
            V.paste_center(img, V.text_img(f"YEAR {int(yr(ext_f))}", 64, WHITE, 10), W / 2, 1100, V.pop_scale(lt - 0.3))
            V.paste_center(img, V.pill("SUB GOAL", 50, (30, 120, 200)), W / 2, 1230, V.pop_scale(lt - 0.6))
            V.paste_center(img, V.pill("EVERY 10 SUBS = A NEW SPECIES", 40, (20, 20, 30)), W / 2, 1315, V.pop_scale(lt - 0.75))

        # captions
        for k in reversed(names):
            if tv >= starts[k]:
                text = dict(LINES)[k]
                if tv - starts[k] < vd[k] + 0.35:
                    _, ws = V.word_times(text, vd[k])
                    N.draw_caption(img, text.split(), ws, tv - starts[k], y=1560)
                break
        if f == 0:
            first = img.copy()
        if tv > total - 0.35:  # loop back into the opening close-up
            img = Image.blend(img, first, min(1, (tv - (total - 0.35)) / 0.35))
        ffp.stdin.write(img.tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{frames}", flush=True)
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
