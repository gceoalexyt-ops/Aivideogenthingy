#!/usr/bin/env python3
"""Render "10 foxes vs 100 rabbits: who survives?": an ecosystem-simulation Short.

The island is a real agent simulation (../sim.py): nothing is keyframed. The run's own events place the
narration: the foxes' boom, the last rabbit, the last fox. Narrator: Kokoro "am_onyx".

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
W, H, SR = V.W, V.H, V.SR
FPS = 30
SEED = int(os.environ.get("SEED", "0"))
PARAMS = sim.Params(fox_gain=1.2, fox_burn=0.006, fox_speed=3.8, rabbit_flee=60, fox_sense=170)
VOICE = "am_onyx"
CX, CY = W / 2, 1010  # island centre on screen
SCALE = 0.98  # px on screen per sim unit
WHITE, RED, YELLOW = (255, 255, 255), (235, 60, 60), (255, 220, 60)
RAB_COL, FOX_COL = (245, 245, 245), (240, 130, 40)
N.KEYWORDS = {
    "foxes": FOX_COL, "fox": FOX_COL, "rabbits": (210, 210, 255), "island": (110, 220, 140),
    "all": RED, "starve": RED, "pick": YELLOW, "take": YELLOW, "over": YELLOW,
}  # fmt: skip
HOOK = "Ten foxes. A hundred rabbits. One island."
LINES = {  # name: text (placed on the run's own events below)
    "boom": "The rabbits take over...",
    "catch": "until the foxes catch up.",
    "eat": "Then the foxes eat them all...",
    "starve": "and starve.",
    "pick": "Who did you pick?",
}


# ---------------------------------------------------------------- voice / audio
def synth(texts):
    from kokoro_onnx import Kokoro

    d = V.kokoro_dir()
    k = Kokoro(str(d / V.KOKORO_FILES[0]), str(d / V.KOKORO_FILES[1]))
    out = []
    for text in texts:
        s, sr = k.create(text, voice=VOICE, speed=1.08, lang="en-us")
        s = np.asarray(s, np.float32)
        loud = np.nonzero(np.abs(s) > 0.02)[0]
        s = s[max(0, loud[0] - int(0.02 * sr)) : loud[-1] + int(0.06 * sr)]
        n = int(len(s) * SR / sr)
        out.append(np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32))
    return out


def env(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def chomp():
    n = int(0.12 * SR)
    g = np.random.default_rng(3)
    t = np.arange(n) / SR
    return 0.45 * np.sin(2 * np.pi * np.cumsum(np.linspace(220, 70, n)) / SR) * env(n, 0.03) + 0.2 * g.normal(0, 1, n) * env(n, 0.012) * (t < 0.03)


def pip(k):
    n = int(0.06 * SR)
    f = 1400 + 80 * (k % 5)
    return 0.06 * np.sin(2 * np.pi * f * np.arange(n) / SR) * env(n, 0.015)


def drum():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(8)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(np.linspace(90, 38, n)) / SR) * env(n, 0.35) + 0.25 * g.normal(0, 1, n) * env(n, 0.05)


def pad(n, t_end):
    """Low, tense pad: Am - F - C - G, one chord per 1.6 s, with a soft heartbeat pulse that speeds up."""
    out = np.zeros(n)
    chords = [(45, 57, 60, 64), (41, 53, 57, 60), (48, 55, 60, 64), (43, 55, 59, 62)]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    seg = int(1.6 * SR)
    for c in range(n // seg + 1):
        i0 = c * seg
        ln = min(seg + int(0.4 * SR), n - i0)
        if ln <= 0:
            break
        t = np.arange(ln) / SR
        e = np.minimum(1, t / 0.3) * np.minimum(1, (ln / SR - t) / 0.4)
        for m in chords[c % 4]:
            out[i0 : i0 + ln] += 0.05 * np.sin(2 * np.pi * hz(m) * t) * e
    t, beat = 0.0, 0.62
    while t < t_end:
        i0 = int(t * SR)
        ln = min(int(0.15 * SR), n - i0)
        out[i0 : i0 + ln] += 0.25 * np.sin(2 * np.pi * np.cumsum(np.linspace(80, 45, ln)) / SR) * env(ln, 0.04)
        beat = max(0.33, beat * 0.985)
        t += beat
    return out


# ---------------------------------------------------------------- drawing
def sprite(kind, s=2):
    """Rabbit or fox seen from above, drawn at 2x and scaled down for smooth edges."""
    sz = 30 * s
    im = Image.new("RGBA", (sz, sz))
    d = ImageDraw.Draw(im)
    c = sz / 2
    if kind == "rabbit":
        for dx in (-5, 5):
            d.ellipse([c + dx * s - 3 * s, c - 13 * s, c + dx * s + 3 * s, c - 1 * s], fill=RAB_COL, outline=(90, 90, 90), width=s)
        d.ellipse([c - 8 * s, c - 6 * s, c + 8 * s, c + 9 * s], fill=RAB_COL, outline=(90, 90, 90), width=s)
        d.ellipse([c - 4 * s, c - 2 * s, c - 2 * s, c], fill=(20, 20, 20))
        d.ellipse([c + 2 * s, c - 2 * s, c + 4 * s, c], fill=(20, 20, 20))
    else:
        for dx in (-6, 6):
            d.polygon([(c + dx * s - 4 * s, c - 4 * s), (c + dx * s, c - 13 * s), (c + dx * s + 4 * s, c - 4 * s)], fill=FOX_COL, outline=(80, 30, 0))
        d.ellipse([c - 10 * s, c - 7 * s, c + 10 * s, c + 10 * s], fill=FOX_COL, outline=(80, 30, 0), width=s)
        d.polygon([(c - 5 * s, c + 3 * s), (c, c + 10 * s), (c + 5 * s, c + 3 * s)], fill=(255, 245, 235))
        d.ellipse([c - 5 * s, c - 1 * s, c - 2 * s, c + 2 * s], fill=(20, 20, 20))
        d.ellipse([c + 2 * s, c - 1 * s, c + 5 * s, c + 2 * s], fill=(20, 20, 20))
    return im.resize((38, 38), Image.LANCZOS)


def island_base():
    y, x = np.mgrid[0:H, 0:W]
    r = np.hypot(x - CX, y - CY) / SCALE
    sea = np.stack([20 + 0 * x, 70 + 20 * (y / H), 130 + 40 * (y / H)], -1)
    img = sea.copy()
    sand = (r < sim.ISLAND_R + 22)
    img[sand] = (225, 200, 140)
    foam = (r >= sim.ISLAND_R + 22) & (r < sim.ISLAND_R + 30)
    img[foam] = (200, 230, 240)
    return Image.fromarray(img.astype(np.uint8)), r < sim.ISLAND_R


def grass_layer(grass, mask_img):
    g = grass[..., None]
    rgb = (1 - g) * np.array([150, 120, 70]) + g * np.array([70, 160, 70])
    im = Image.fromarray(rgb.astype(np.uint8)).resize((int(2 * sim.ISLAND_R * SCALE),) * 2, Image.BILINEAR)
    return im


def to_screen(pos):
    return CX + pos[:, 0] * SCALE, CY + pos[:, 1] * SCALE


def draw_graph(d, hist, n_ticks, x0=90, y0=330, w=900, h=170):
    d.rounded_rectangle([x0 - 16, y0 - 16, x0 + w + 16, y0 + h + 16], 18, fill=(0, 0, 0, 120))
    if len(hist) < 2:
        return
    hist = np.asarray(hist, float)
    top = max(50.0, hist.max())
    xs = x0 + np.arange(len(hist)) / max(1, n_ticks - 1) * w
    for col, k in ((RAB_COL, 0), (FOX_COL, 1)):
        ys = y0 + h - hist[:, k] / top * h
        d.line(list(zip(xs, ys)), fill=col, width=6)


# ---------------------------------------------------------------- main
def main():
    # run the simulation once, recording everything per tick
    w = sim.new_world(SEED, p=PARAMS)
    states, hist, catches, births = [], [], [], []
    ext_r = ext_f = None
    states.append((w.rab["pos"].copy(), w.fox["pos"].copy(), w.grass.copy()))  # the untouched start: 100 vs 10
    hist.append((len(w.rab["pos"]), len(w.fox["pos"])))
    catches.append([])
    births.append(0)
    while True:
        br, bf, ca = sim.step(w)
        nr, nf = len(w.rab["pos"]), len(w.fox["pos"])
        states.append((w.rab["pos"].copy(), w.fox["pos"].copy(), w.grass.copy()))
        hist.append((nr, nf))
        catches.append(ca)
        births.append(br + bf)
        if ext_r is None and nr == 0:
            ext_r = w.tick
        if ext_f is None and nf == 0:
            ext_f = w.tick
        if (nr == 0 and nf == 0) or w.tick >= 100 * sim.TICKS_PER_YEAR:
            break
    T = len(states)
    yr = lambda tick: tick / sim.TICKS_PER_YEAR  # noqa: E731
    print(f"seed {SEED}: rabbits extinct year {ext_r and yr(ext_r):.1f}, foxes extinct year {ext_f and yr(ext_f):.1f}")
    h = np.array(hist)
    fox_rise = int(np.argmax(h[:, 1] >= 40))  # foxes take off

    names = ["hook"] + list(LINES)
    voices = dict(zip(names, synth([HOOK] + list(LINES.values()))))
    dur = {k: len(v) / SR for k, v in voices.items()}

    # timeline: hook (world frozen), then the sim plays at a constant rate
    t_sim0 = dur["hook"] + 0.25
    t_sim1 = t_sim0 + 10.8  # the whole run in 10.8 s
    rate = T / (t_sim1 - t_sim0)  # ticks per second
    ttime = lambda tick: t_sim0 + tick / rate  # noqa: E731
    total = t_sim1 + dur["pick"] + 1.4

    # place narration on the run's events, never overlapping
    want = {
        "hook": 0.0,
        "boom": t_sim0 + 0.1,
        "catch": ttime(fox_rise) - 0.3,
        "eat": ttime(ext_r) - dur["eat"] - 0.1,
        "starve": ttime(ext_f) - dur["starve"] * 0.6,
        "pick": ttime(ext_f) + 0.9,
    }
    starts, cur = {}, 0.0
    for k in names:
        starts[k] = max(want[k], cur)
        cur = starts[k] + dur[k] + 0.08
    scenes = []
    for k in names:
        text = HOOK if k == "hook" else LINES[k]
        _, ws = V.word_times(text, dur[k])
        scenes.append(N.Scene(k, text, starts[k], dur[k] + 0.25, ws))
    total = max(total, starts["pick"] + dur["pick"] + 1.0)
    print(f"duration {total:.1f}s; lines at " + ", ".join(f"{k} {v:.1f}" for k, v in starts.items()))

    # ---- audio
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for k in names:
        i0 = int(starts[k] * SR)
        v = voices[k]
        voice[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.95
    fx = np.zeros(n)

    def add(t0, snd, g=1.0):
        i0 = int(max(0, t0) * SR)
        if i0 < n:
            fx[i0 : i0 + len(snd)] += g * snd[: n - i0]

    last_c = last_b = -1.0
    for tick in range(T):
        tt = ttime(tick)
        if catches[tick] and tt - last_c > 0.07:
            add(tt, chomp(), 0.7)
            last_c = tt
        if births[tick] and tt - last_b > 0.11:
            add(tt, pip(tick), 1.0)
            last_b = tt
    for e in (ext_r, ext_f):
        if e:
            add(ttime(e), drum(), 1.0 if e == ext_f else 0.6)
    mix = voice + 0.8 * fx + pad(n, ttime(ext_f or T))
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    wav = HERE / "audio.tmp.wav"
    V.write_wav(wav, mix[: int(total * SR)])

    # ---- video
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    base, _ = island_base()
    isz = int(2 * sim.ISLAND_R * SCALE)
    imask = Image.new("L", (isz, isz))
    ImageDraw.Draw(imask).ellipse([0, 0, isz - 1, isz - 1], fill=255)
    rab_s, fox_s = sprite("rabbit"), sprite("fox")
    rab_icon, fox_icon = rab_s.resize((80, 80), Image.LANCZOS), fox_s.resize((80, 80), Image.LANCZOS)
    puffs = []  # [x, y, age]
    frames = int(total * FPS)
    first_frame = None
    for f in range(frames):
        t = f / FPS
        tick = int(np.clip((t - t_sim0) * rate, 0, T - 1))
        playing = t >= t_sim0
        R, F, grass = states[tick] if playing else states[0]
        if not playing:
            R, F = states[0][0], states[0][1]
        img = base.copy()
        img.paste(grass_layer(grass, imask), (int(CX - isz / 2), int(CY - isz / 2)), imask)
        if playing:
            t_prev = int(np.clip((t - 1 / FPS - t_sim0) * rate, 0, T - 1))
            for k in range(t_prev + 1, tick + 1):
                for c in catches[k]:
                    puffs.append([CX + c[0] * SCALE, CY + c[1] * SCALE, 0.0])
        rx, ry = to_screen(R)
        for x, y in zip(rx, ry):
            img.paste(rab_s, (int(x - 19), int(y - 19)), rab_s)
        fx_, fy_ = to_screen(F)
        for x, y in zip(fx_, fy_):
            img.paste(fox_s, (int(x - 19), int(y - 19)), fox_s)
        ov = Image.new("RGBA", (W, H))
        od = ImageDraw.Draw(ov)
        alive = []
        for p in puffs:
            p[2] += 1 / FPS
            if p[2] < 0.35:
                r = 10 + 40 * p[2]
                a = int(200 * (1 - p[2] / 0.35))
                od.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], outline=(255, 70, 70, a), width=5)
                alive.append(p)
        puffs = alive
        # HUD
        nr, nf = (hist[tick] if playing else (len(R), len(F)))
        draw_graph(od, hist[: tick + 1] if playing else [], T)
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(img)
        img.paste(rab_icon, (70, 160), rab_icon)
        img.paste(fox_icon, (W - 150, 160), fox_icon)
        V.paste_center(img, V.text_img(str(nr), 92, RAB_COL, 10), 250, 200)
        V.paste_center(img, V.text_img(str(nf), 92, FOX_COL, 10), W - 260, 200)
        year = yr(tick) if playing else 0
        V.paste_center(img, V.text_img(f"YEAR {int(year)}", 54, WHITE, 8), W / 2, 200)

        if not playing or t < t_sim0 + 0.4:
            k = 1.0 if not playing else 1 - (t - t_sim0) / 0.4
            V.paste_center(img, V.text_img("10 FOXES vs 100 RABBITS", 64, YELLOW, 12), W / 2, 930, V.pop_scale(t - 0.05), alpha=k)
            V.paste_center(img, V.text_img("WHO SURVIVES?", 110, WHITE, 14), W / 2, 1060, V.pop_scale(t - 0.6), alpha=k)
        if ext_r and t >= ttime(ext_r) and (not ext_f or t < ttime(ext_f)):
            V.paste_center(img, V.pill("RABBITS EXTINCT", 64, (170, 30, 30)), W / 2, 1010, V.pop_scale(t - ttime(ext_r)))
        if ext_f and t >= ttime(ext_f):
            lt = t - ttime(ext_f)
            V.paste_center(img, V.text_img("NOBODY", 150, RED, 16), W / 2, 880, V.pop_scale(lt, 0.18) * (1 + 0.3 * math.exp(-lt / 0.1)))
            V.paste_center(img, V.text_img("SURVIVED", 150, RED, 16), W / 2, 1030, V.pop_scale(lt - 0.15, 0.18))
            V.paste_center(img, V.text_img(f"YEAR {int(yr(ext_f))}", 64, WHITE, 10), W / 2, 1160, V.pop_scale(lt - 0.35))
            if lt > 0.9:
                V.paste_center(img, V.pill("SUB GOAL", 50, (30, 120, 200)), W / 2, 1275, V.pop_scale(lt - 0.9))
                V.paste_center(img, V.pill("EVERY 10 SUBS = A NEW SPECIES", 40, (20, 20, 30)), W / 2, 1360, V.pop_scale(lt - 1.05))
        sc = max((s for s in scenes if s.start <= t), key=lambda s: s.start)
        if t - sc.start < sc.D:
            N.draw_caption(img, sc.words, sc.starts, t - sc.start, y=1580)
        if f == 0:
            first_frame = img.copy()
        if t > total - 0.3 and first_frame is not None:  # loop: fade back into the opening frame
            img = Image.blend(img, first_frame, min(1, (t - (total - 0.3)) / 0.3))
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
