#!/usr/bin/env python3
"""Render "Every escape = 3 more balls": a physics-simulation Short.

One ball starts inside a spinning ring with a gap. Every ball that gets out spawns two new balls in
the middle, so the count grows exponentially until it hits TARGET and the ring shatters. Bounces play
"Ode to Joy" (Beethoven, public domain), throttled so a crowd of balls doesn't turn into noise; each
escape pops a little higher. Plain 2D physics, vectorised with numpy (balls don't collide with each
other, only with the ring). Reuses the drawing and audio helpers from ../escape_ring.

    python sims/escape_multiply/make_short.py --search    # list good seeds
    SEED=3 python sims/escape_multiply/make_short.py      # -> sims/escape_multiply/escape_multiply_short.mp4
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
OUT = HERE / "escape_multiply_short.mp4"
_spec = importlib.util.spec_from_file_location("escape_ring", HERE.parent / "escape_ring" / "make_short.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
W, H, FPS, SR, CX, CY, R, TH = E.W, E.H, E.FPS, E.SR, E.CX, E.CY, E.R, E.TH
SUB = 8
GAP = math.radians(50)
OMEGA = 3.0
G = 3200.0
BR = 13.0  # ball radius
VMIN = 1800.0
TARGET = 1000  # the ring shatters when this many balls exist
SPAWN = 3  # new balls per escape
TAIL = 1.5
# Ode to Joy, C major
THEME = [64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 64, 62, 62,
         64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60]  # fmt: skip


def spawn(rng, k):
    a = rng.uniform(0, 2 * math.pi, k)
    sp = rng.uniform(900, 1400, k)
    return rng.normal(0, 8, (k, 2)), np.stack([np.cos(a) * sp, np.sin(a) * sp], 1)


def simulate(seed, max_t=30.0):
    rng = np.random.default_rng(seed)
    P, V = spawn(rng, 1)
    inside = np.ones(1, bool)
    born = np.zeros(1)  # frame each ball appeared, for the pop-in
    phi0 = rng.uniform(0, 2 * math.pi)
    dt = 1 / (FPS * SUB)
    t, frames, bounces, escapes, shatter = 0.0, [], [], [], None
    inner = R - TH / 2
    for f in range(int(max_t * FPS)):
        for _ in range(SUB):
            t += dt
            V[:, 1] += G * dt
            P += V * dt
            if shatter is not None:
                continue
            phi = phi0 + OMEGA * t
            idx = np.nonzero(inside)[0]
            p, v = P[idx], V[idx]
            d = np.hypot(p[:, 0], p[:, 1])
            ang = np.arctan2(p[:, 1], p[:, 0])
            in_gap = np.abs((ang - phi + np.pi) % (2 * np.pi) - np.pi) <= GAP / 2
            hit = np.zeros(len(idx), bool)
            # ring wall
            m = ~in_gap & (d < R) & (d + BR > inner)
            if m.any():
                n = p[m] / d[m, None]
                vn = (v[m] * n).sum(1)
                out = vn > 0
                v[m] -= (2 * vn * out)[:, None] * n
                p[m] = n * (inner - BR)
                hit[np.nonzero(m)[0][out]] = True
            # the two ends of the arc
            for s in (-1, 1):
                e = R * np.array([math.cos(phi + s * GAP / 2), math.sin(phi + s * GAP / 2)])
                dv = p - e
                dd = np.hypot(dv[:, 0], dv[:, 1])
                m = in_gap & (dd < BR + TH / 2)
                if m.any():
                    n = dv[m] / np.maximum(dd[m], 1e-6)[:, None]
                    vn = (v[m] * n).sum(1)
                    into = vn < 0
                    v[m] -= (2 * vn * into)[:, None] * n
                    p[m] = e + n * (BR + TH / 2)
                    hit[np.nonzero(m)[0][into]] = True
            sp = np.hypot(v[:, 0], v[:, 1])
            slow = hit & (sp < VMIN)
            v[slow] *= (VMIN / sp[slow])[:, None]
            P[idx], V[idx] = p, v
            if hit.any():
                bounces.append((t, int(hit.sum())))
            esc = idx[in_gap & (d - BR > R + TH / 2)]
            if len(esc):
                inside[esc] = False
                for _ in esc:
                    escapes.append(t)
                k = min(SPAWN * len(esc), TARGET - len(P))
                if k > 0:
                    np_, nv = spawn(rng, k)
                    P, V = np.vstack([P, np_]), np.vstack([V, nv])
                    inside = np.concatenate([inside, np.ones(k, bool)])
                    born = np.concatenate([born, np.full(k, f)])
                if len(P) >= TARGET:
                    shatter = t
        # escaped balls that fell off-screen stay where they are (not drawn)
        frames.append((P.copy(), inside.copy(), born.copy(), phi0 + OMEGA * (f + 1) / FPS))
        if shatter is not None and t > shatter + TAIL:
            break
    return frames, bounces, escapes, shatter


def search():
    for seed in range(60):
        frames, b, e, sh = simulate(seed)
        if sh and 9 <= sh <= 14:
            first = e[0] if e else None
            print(f"seed {seed}: {TARGET} balls at {sh:.1f}s, first escape {first:.2f}s")


def build_audio(bounces, escapes, shatter, total):
    n = int(total * SR) + SR
    a = np.zeros(n)
    last, i = -1.0, 0
    for t, k in bounces:  # one note per bounce, at most ~11 a second
        if t - last < 0.09:
            continue
        last = t
        s = E.note(THEME[i % len(THEME)] + 12 * ((i // len(THEME)) % 2), 0.4)
        i += 1
        i0 = int(t * SR)
        a[i0 : i0 + len(s)] += 0.8 * s[: n - i0]
    last = -1.0
    for j, t in enumerate(escapes):  # escape pops, climbing in pitch as the count grows
        if t - last < 0.05:
            continue
        last = t
        m = 72 + min(24, int(4 * math.log2(j + 2)))
        s = E.note(m, 0.15) * 0.6
        i0 = int(t * SR)
        a[i0 : i0 + len(s)] += s[: n - i0]
    if shatter:
        tt = np.arange(int(1.8 * SR)) / SR
        g = np.random.default_rng(5)
        crash = 0.5 * g.normal(0, 1, len(tt)) * np.exp(-tt / 0.25)
        chord = sum(E.note(m, 1.8) for m in (60, 64, 67, 72, 76)) * 0.8
        i0 = int(shatter * SR)
        seg = crash + chord
        a[i0 : i0 + len(seg)] += seg[: n - i0]
    a /= max(1.0, np.abs(a).max() / 0.95)
    return a[: int(total * SR)]


def render(seed):
    frames, bounces, escapes, shatter = simulate(seed)
    total = len(frames) / FPS
    print(f"seed {seed}: {len(frames)} frames ({total:.1f}s), {len(escapes)} escapes, shatter {shatter}")
    wav = HERE / "audio.tmp.wav"
    E.write_wav(wav, build_audio(bounces, escapes, shatter, total))
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
    shards = None
    esc_times = np.array(escapes)
    cols = [E.hsv((k * 0.061) % 1) for k in range(TARGET + 2)]
    for f, (P, inside, born, phi) in enumerate(frames):
        t = (f + 1) / FPS
        n_balls = len(P)
        n_esc = int((esc_times <= t).sum())
        broken = shatter is not None and t >= shatter
        recent = esc_times[(esc_times <= t) & (esc_times > t - 0.12)]
        flash = math.exp(-(t - recent[-1]) / 0.08) if len(recent) else 0.0

        img = bg.copy()
        glow = Image.new("RGB", (W // 4, H // 4))
        d, gd = ImageDraw.Draw(img), ImageDraw.Draw(glow)
        ring_col = E.hsv((t * 0.05) % 1, 0.7, 1.0)
        if not broken:
            a0, a1 = math.degrees(phi + GAP / 2), math.degrees(phi - GAP / 2) + 360
            box = [CX - R - TH / 2, CY - R - TH / 2, CX + R + TH / 2, CY + R + TH / 2]
            d.arc(box, a0, a1, fill=ring_col, width=int(TH))
            gd.arc([c / 4 for c in box], a0, a1, fill=ring_col, width=int(TH / 4) + 2)
        else:
            if shards is None:
                shards = []
                for k in range(60):
                    a = phi + GAP / 2 + (2 * math.pi - GAP) * (k + 0.5) / 60
                    sp = rng.uniform(300, 900)
                    shards.append([CX + R * math.cos(a), CY + R * math.sin(a), sp * math.cos(a), sp * math.sin(a) - 400, a])
            for s in shards:
                s[3] += G * 0.5 / FPS
                s[0] += s[2] / FPS
                s[1] += s[3] / FPS
                dx, dy = -math.sin(s[4]) * 22, math.cos(s[4]) * 22
                d.line([s[0] - dx, s[1] - dy, s[0] + dx, s[1] + dy], fill=ring_col, width=int(TH))
                gd.line([(s[0] - dx) / 4, (s[1] - dy) / 4, (s[0] + dx) / 4, (s[1] + dy) / 4], fill=ring_col, width=5)

        xs, ys = CX + P[:, 0], CY + P[:, 1]
        vis = (ys < H + 40) & (xs > -40) & (xs < W + 40)
        for k in np.nonzero(vis)[0]:
            grow = min(1.0, (f - born[k]) / 8 + 0.2)
            r = BR * grow
            x, y = xs[k], ys[k]
            c = cols[k]
            d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline=(255, 255, 255), width=2)
            if inside[k]:
                gd.ellipse([(x - r) / 4, (y - r) / 4, (x + r) / 4, (y + r) / 4], fill=tuple(ch // 2 for ch in c))

        glow = glow.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        img = Image.fromarray(np.minimum(255, np.asarray(img, np.uint16) + (np.asarray(glow, np.uint16) * 3) // 2).astype(np.uint8))
        d = ImageDraw.Draw(img)
        if not broken:
            E.text(d, (W / 2, 250), "EVERY ESCAPE = 3 MORE BALLS", 58, (255, 255, 255))
            pulse = 1 + 0.04 * math.sin(t * 6)
            E.text(d, (W / 2, 360), "HOW MANY CAN IT HOLD?", int(70 * pulse), (255, 220, 60), 10)
        else:
            k = min(1, (t - shatter) / 0.25)
            E.text(d, (W / 2, 330), f"{TARGET} BALLS!", int(80 + 60 * k), (90, 255, 120), 12)
            E.text(d, (W / 2, 470), "the ring couldn't take it", 54, (255, 255, 255))
        E.text(d, (W / 2, 1570), f"BALLS: {n_balls}", int(80 * (1 + 0.12 * flash)), (255, 255, 255), 9)
        E.text(d, (W / 2, 1680), f"ESCAPED: {n_esc}", 54, (230, 230, 230), 7)
        if broken and t - shatter < 0.15:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.5 * (1 - (t - shatter) / 0.15))
        ffp.stdin.write(img.tobytes())
        if f % 300 == 0:
            print(f"frame {f}/{len(frames)}", flush=True)
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    if "--search" in sys.argv:
        search()
    else:
        render(int(os.environ.get("SEED", "3")))
