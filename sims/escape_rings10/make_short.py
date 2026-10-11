#!/usr/bin/env python3
"""Render "Can it escape 10 rings?": a physics-simulation Short.

One ball starts inside ten nested rings, each spinning at its own speed and direction with its own gap.
The ball only touches the innermost ring that's still standing; when it gets through that ring's gap,
the ring shatters and the next one out takes over. Bounces play "Für Elise" (Beethoven, public domain).
Plain 2D physics, nothing keyframed. Reuses the drawing and audio helpers from ../escape_ring.

    python sims/escape_rings10/make_short.py --search    # list good seeds
    SUBS=0 SEED=212 python sims/escape_rings10/make_short.py      # -> sims/escape_rings10/escape_rings10_short.mp4
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
OUT = HERE / "escape_rings10_short.mp4"
_spec = importlib.util.spec_from_file_location("escape_ring", HERE.parent / "escape_ring" / "make_short.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
W, H, FPS, SR, CX, CY = E.W, E.H, E.FPS, E.SR, E.CX, E.CY
SUB = 12
N_RINGS = 10
RADII = [110 + 38 * k for k in range(N_RINGS)]  # 110 .. 452 px
TH = 10.0
GAP = math.radians(40)
G = 2600.0
BR = 13.0
VMIN = 1250.0
TAIL = 3.4
SUBS = int(os.environ.get("SUBS", "0"))  # channel subscribers when rendered: +1 ring each next video
# Für Elise, opening
THEME = [76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 68, 71, 72,
         64, 76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 72, 71, 69]  # fmt: skip


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def rings_for(rng):
    """(start angle, spin) for each ring; alternating directions so the gaps rarely line up."""
    return [(rng.uniform(0, 2 * math.pi), (1 if k % 2 else -1) * rng.uniform(1.2, 2.6)) for k in range(N_RINGS)]


def simulate(seed, max_t=30.0):
    rng = np.random.default_rng(seed)
    rings = rings_for(rng)
    p = np.array([0.0, -20.0])
    a = rng.uniform(0, 2 * math.pi)
    v = np.array([math.cos(a), math.sin(a)]) * 1100
    dt = 1 / (FPS * SUB)
    t, active = 0.0, 0
    frames, bounces, breaks = [], [], []
    for f in range(int(max_t * FPS)):
        for _ in range(SUB):
            t += dt
            v[1] += G * dt
            p += v * dt
            if active >= N_RINGS:
                continue
            R = RADII[active]
            phi0, om = rings[active]
            phi = phi0 + om * t
            inner = R - TH / 2
            d = math.hypot(*p)
            hit = False
            if abs(wrap(math.atan2(p[1], p[0]) - phi)) > GAP / 2:
                if d < R and d + BR > inner:
                    n = p / d
                    if v @ n > 0:
                        v -= 2 * (v @ n) * n
                        hit = True
                    p[:] = n * (inner - BR)
            else:
                for s in (-1, 1):
                    e = R * np.array([math.cos(phi + s * GAP / 2), math.sin(phi + s * GAP / 2)])
                    dv = p - e
                    dd = math.hypot(*dv)
                    if dd < BR + TH / 2:
                        n = dv / max(dd, 1e-6)
                        if v @ n < 0:
                            v -= 2 * (v @ n) * n
                            hit = True
                        p[:] = e + n * (BR + TH / 2)
                if d - BR > R + TH / 2:
                    breaks.append((t, active, phi))
                    active += 1
            if hit:
                sp = math.hypot(*v)
                if sp < VMIN:
                    v *= VMIN / sp
                bounces.append(t)
        frames.append((p.copy(), active))
        if active >= N_RINGS and t > breaks[-1][0] + TAIL:
            break
    return frames, bounces, breaks, rings


def search():
    for seed in range(300):
        frames, b, br, _ = simulate(seed)
        if len(br) == N_RINGS and 11 <= br[-1][0] <= 16:
            gaps = np.diff([0] + [x[0] for x in br])
            print(f"seed {seed}: all rings by {br[-1][0]:.1f}s, {len(b)} bounces, longest wait {gaps.max():.1f}s")


def build_audio(bounces, breaks, total):
    n = int(total * SR) + SR
    a = np.zeros(n)
    last, i = -1.0, 0
    for t in bounces:
        if t - last < 0.07:
            continue
        last = t
        s = E.note(THEME[i % len(THEME)], 0.45)
        i += 1
        i0 = int(t * SR)
        a[i0 : i0 + len(s)] += 0.8 * s[: n - i0]
    g = np.random.default_rng(9)
    for k, (t, ring, _) in enumerate(breaks):  # shatter: noise burst + a rising two-note sting
        tt = np.arange(int(0.5 * SR)) / SR
        crash = 0.35 * g.normal(0, 1, len(tt)) * np.exp(-tt / 0.08)
        sting = E.note(60 + 2 * k, 0.5) + E.note(67 + 2 * k, 0.5)
        if k == N_RINGS - 1:
            tt = np.arange(int(1.8 * SR)) / SR
            crash = 0.5 * g.normal(0, 1, len(tt)) * np.exp(-tt / 0.3)
            sting = sum(E.note(m, 1.8) for m in (72, 76, 79, 84)) * 0.8
            sting = np.pad(sting, (0, max(0, len(crash) - len(sting))))
        seg = crash[: len(sting)] + sting[: len(crash)]
        i0 = int(t * SR)
        a[i0 : i0 + len(seg)] += seg[: n - i0]
    a /= max(1.0, np.abs(a).max() / 0.95)
    return a[: int(total * SR)]


def render(seed):
    frames, bounces, breaks, rings = simulate(seed)
    total = len(frames) / FPS
    done = len(breaks) == N_RINGS
    print(f"seed {seed}: {len(frames)} frames ({total:.1f}s), {len(bounces)} bounces, rings broken {len(breaks)}")
    wav = HERE / "audio.tmp.wav"
    E.write_wav(wav, build_audio(bounces, breaks, total))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    bg = E.background()
    rng = np.random.default_rng(seed + 1)
    ring_cols = [E.hsv(k / N_RINGS * 0.85, 0.75, 1.0) for k in range(N_RINGS)]
    shards, trail, shattered = [], [], set()
    bt = np.array(bounces)
    for f, (p, active) in enumerate(frames):
        t = (f + 1) / FPS
        for tb, k, phi in breaks:  # spawn shards for rings that just broke
            if tb <= t and k not in shattered:
                shattered.add(k)
                R = RADII[k]
                for j in range(36):
                    a = phi + GAP / 2 + (2 * math.pi - GAP) * (j + 0.5) / 36
                    sp = rng.uniform(700, 1500)
                    shards.append([CX + R * math.cos(a), CY + R * math.sin(a), sp * math.cos(a), sp * math.sin(a) - 300, a, k, 0.55])
        img = bg.copy()
        glow = Image.new("RGB", (W // 4, H // 4))
        d, gd = ImageDraw.Draw(img), ImageDraw.Draw(glow)
        for k in range(active, N_RINGS):
            R = RADII[k]
            phi0, om = rings[k]
            phi = phi0 + om * t
            a0, a1 = math.degrees(phi + GAP / 2), math.degrees(phi - GAP / 2) + 360
            col = ring_cols[k] if k == active else tuple(int(c * 0.55) for c in ring_cols[k])
            box = [CX - R - TH / 2, CY - R - TH / 2, CX + R + TH / 2, CY + R + TH / 2]
            d.arc(box, a0, a1, fill=col, width=int(TH))
            if k == active:
                gd.arc([c / 4 for c in box], a0, a1, fill=col, width=4)
        alive = []
        for s in shards:
            s[3] += G * 0.6 / FPS
            s[0] += s[2] / FPS
            s[1] += s[3] / FPS
            s[6] -= 1 / FPS
            if s[6] > 0 and s[1] < H + 30:
                L = 16 * s[6] / 0.55
                dx, dy = -math.sin(s[4]) * L, math.cos(s[4]) * L
                c = tuple(int(ch * min(1, s[6] / 0.3)) for ch in ring_cols[s[5]])
                d.line([s[0] - dx, s[1] - dy, s[0] + dx, s[1] + dy], fill=c, width=int(TH))
                gd.line([(s[0] - dx) / 4, (s[1] - dy) / 4, (s[0] + dx) / 4, (s[1] + dy) / 4], fill=c, width=3)
                alive.append(s)
        shards = alive
        x, y = CX + p[0], CY + p[1]
        trail.append((x, y))
        trail = trail[-12:]
        for j, (tx, ty) in enumerate(trail[:-1]):
            k = (j + 1) / len(trail)
            r = BR * (0.4 + 0.6 * k)
            d.ellipse([tx - r, ty - r, tx + r, ty + r], fill=(int(255 * k * 0.5), int(255 * k * 0.5), int(255 * k * 0.5)))
        recent = bt[(bt <= t) & (bt > t - 0.15)]
        flash = math.exp(-(t - recent[-1]) / 0.06) if len(recent) else 0.0
        r = BR * (1 + 0.25 * flash)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
        gd.ellipse([(x - r) / 4, (y - r) / 4, (x + r) / 4, (y + r) / 4], fill=(200, 200, 200))
        glow = glow.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
        img = Image.fromarray(np.minimum(255, np.asarray(img, np.uint16) + (np.asarray(glow, np.uint16) * 3) // 2).astype(np.uint8))
        d = ImageDraw.Draw(img)
        left = N_RINGS - active
        last_break = max([b[0] for b in breaks if b[0] <= t], default=-9)
        pop = math.exp(-(t - last_break) / 0.12)
        if left > 0:
            E.text(d, (W / 2, 250), "ONE BALL. TEN RINGS.", 62, (255, 255, 255))
            pulse = 1 + 0.04 * math.sin(t * 6)
            E.text(d, (W / 2, 360), "CAN IT ESCAPE?", int(96 * pulse), (255, 220, 60), 10)
            E.text(d, (W / 2, 1600), f"RINGS LEFT: {left}", int(84 * (1 + 0.25 * pop)), ring_cols[active], 9)
        else:
            k = min(1, (t - last_break) / 0.25)
            E.text(d, (W / 2, 330), "IT ESCAPED!", int(80 + 60 * k), (90, 255, 120), 12)
            E.text(d, (W / 2, 470), f"all {N_RINGS} rings in {last_break:.1f}s", 56, (255, 255, 255))
            E.text(d, (W / 2, 1600), "RINGS LEFT: 0", 84, (90, 255, 120), 9)
            lt = t - last_break - 0.9
            if lt > 0:  # sub goal end card in the space the rings left
                pop = lambda x: min(1.0, max(0.0, x / 0.18)) * (1 + 0.15 * math.exp(-max(0, x - 0.18) / 0.1))
                E.text(d, (W / 2, 820), "SUB GOAL", max(1, int(90 * pop(lt))), (110, 230, 230), 10)
                E.text(d, (W / 2, 935), "EVERY SUBSCRIBER = +1 RING", max(1, int(54 * pop(lt - 0.25))), (255, 255, 255), 8)
                nxt = N_RINGS + min(SUBS, int(SUBS * max(0, lt - 0.5) / 0.6))
                E.text(d, (W / 2, 1060), f"NEXT VIDEO: {nxt} RINGS", max(1, int(76 * pop(lt - 0.5))), (255, 220, 60), 10)
                E.text(d, (W / 2, 1180), "subscribe to make it harder", max(1, int(50 * pop(lt - 0.9))), (255, 120, 120), 7)
        if t - last_break < 0.1:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.25 * (1 - (t - last_break) / 0.1))
        ffp.stdin.write(img.tobytes())
        if f % 300 == 0:
            print(f"frame {f}/{len(frames)}", flush=True)
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}" + ("" if done else " (did not escape every ring)"))


if __name__ == "__main__":
    if "--search" in sys.argv:
        search()
    else:
        render(int(os.environ.get("SEED", "212")))
