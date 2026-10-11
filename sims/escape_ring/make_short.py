#!/usr/bin/env python3
"""Render "It grows every bounce. Will it escape?": a physics-simulation Short.

A ball bounces around inside a spinning ring with a gap. Every bounce makes the ball bigger and plays
the next note of "In the Hall of the Mountain King" (Grieg, public domain). The simulation is plain
2D physics (gravity, elastic bounces off the ring and the gap's end caps); nothing is keyframed, so
the run ends when the ball actually gets out. `--search` tries starting conditions and prints the
seeds whose escape lands in a good Short length; render picks the one given by SEED.

    python sims/escape_ring/make_short.py --search        # list good seeds
    SEED=185 python sims/escape_ring/make_short.py           # -> sims/escape_ring/escape_ring_short.mp4
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "escape_ring_short.mp4"
W, H, FPS, SR = 1080, 1920, 60, 44100
SUB = 12  # physics substeps per frame
CX, CY = W / 2, 1010
R, TH = 430.0, 16.0  # ring radius and thickness (px)
GAP = math.radians(28)  # gap width
OMEGA = 2.2  # ring spin (rad/s)
G = 3600.0  # gravity (px/s^2)
R0, GROW = 20.0, 1.4  # starting ball radius, growth per bounce
VMIN = 1700.0  # bounces never leave the ball slower than this
TAIL = 1.6  # seconds after the escape
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# In the Hall of the Mountain King, A minor (MIDI notes), one note per bounce
THEME = [57, 59, 60, 62, 64, 60, 64, 63, 59, 63, 62, 58, 62, 57, 59, 60, 62, 64, 60, 64, 69, 67, 64, 60, 64, 67]


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def simulate(seed, max_t=40.0):
    """Run the physics. Returns per-frame states and the bounce events."""
    rng = np.random.default_rng(seed)
    p = np.array([rng.uniform(-120, 120), rng.uniform(-200, 0)])
    ang = rng.uniform(0, 2 * math.pi)
    v = np.array([math.cos(ang), math.sin(ang)]) * rng.uniform(700, 1100)
    phi0 = rng.uniform(0, 2 * math.pi)
    r, dt = R0, 1 / (FPS * SUB)
    frames, bounces, escaped_at = [], [], None
    inner = R - TH / 2
    t = 0.0
    n_frames = int(max_t * FPS)
    for f in range(n_frames):
        for _ in range(SUB):
            t += dt
            v[1] += G * dt
            p += v * dt
            if escaped_at is not None:
                continue
            phi = phi0 + OMEGA * t
            d = math.hypot(*p)
            hit = None
            if abs(wrap(math.atan2(p[1], p[0]) - phi)) > GAP / 2:
                if d < R and d + r > inner:  # ring wall
                    nrm = p / d
                    if v @ nrm > 0:
                        v -= 2 * (v @ nrm) * nrm
                        hit = "wall"
                    p[:] = nrm * (inner - r)
            else:
                for s in (-1, 1):  # the two ends of the arc
                    e = R * np.array([math.cos(phi + s * GAP / 2), math.sin(phi + s * GAP / 2)])
                    dv = p - e
                    dd = math.hypot(*dv)
                    if dd < r + TH / 2:
                        nrm = dv / max(dd, 1e-6)
                        if v @ nrm < 0:
                            v -= 2 * (v @ nrm) * nrm
                            hit = "cap"
                        p[:] = e + nrm * (r + TH / 2)
                if d - r > R + TH / 2:
                    escaped_at = t
            if hit:
                sp = math.hypot(*v)
                if sp < VMIN:
                    v *= VMIN / sp
                r += GROW
                d = math.hypot(*p)
                if d < R and d + r > inner:
                    p[:] = p / d * (inner - r)
                bounces.append((t, (p + 0) / 1, r))
        frames.append((p.copy(), r, phi0 + OMEGA * (f + 1) / FPS))
        if escaped_at is not None and t > escaped_at + TAIL:
            break
    return frames, bounces, escaped_at


def search():
    for seed in range(400):
        frames, b, esc = simulate(seed)
        if esc and 11 <= esc <= 16 and len(b) >= 40:
            print(f"seed {seed}: escape at {esc:.1f}s after {len(b)} bounces, size x{(R0 + GROW * len(b)) / R0:.1f}")


# ---------------------------------------------------------------- audio
def note(midi, dur=0.5):
    f = 440 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(dur * SR)) / SR
    env = np.exp(-t / 0.18) * np.minimum(1, t / 0.004)
    tone = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    return 0.32 * tone * env


def build_audio(bounces, esc, total):
    n = int(total * SR) + SR
    a = np.zeros(n)
    for i, (t, _, _) in enumerate(bounces):
        lap = i // len(THEME)
        s = note(THEME[i % len(THEME)] + 12 * (lap % 2))
        i0 = int(t * SR)
        a[i0 : i0 + len(s)] += s[: n - i0]
    if esc:  # escape: rising sweep + chord
        t = np.arange(int(1.6 * SR)) / SR
        sweep = 0.25 * np.sin(2 * np.pi * np.cumsum(np.linspace(300, 1400, len(t))) / SR) * np.exp(-t / 0.5)
        chord = sum(note(m, 1.6) for m in (69, 73, 76, 81)) * 0.8
        i0 = int(esc * SR)
        seg = sweep + chord
        a[i0 : i0 + len(seg)] += seg[: n - i0]
    a /= max(1.0, np.abs(a).max() / 0.95)
    return a[: int(total * SR)]


def write_wav(path, a):
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- video
def hsv(h, s=0.85, v=1.0):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    rgb = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return tuple(int(255 * c) for c in rgb)


_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT, size)
    return _fonts[size]


def text(draw, xy, s, size, fill, stroke=8):
    draw.text(xy, s, font=font(size), fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=(0, 0, 0))


def background():
    y = np.linspace(0, 1, H)[:, None]
    top, bot = np.array([18, 10, 40]), np.array([4, 4, 12])
    img = np.broadcast_to((top * (1 - y)[:, :, None] + bot * y[:, :, None]), (H, W, 3))
    return Image.fromarray(img.astype(np.uint8))


def render(seed):
    frames, bounces, esc = simulate(seed)
    total = len(frames) / FPS
    print(f"seed {seed}: {len(frames)} frames ({total:.1f}s), {len(bounces)} bounces, escape {esc}")
    wav = HERE / "audio.tmp.wav"
    write_wav(wav, build_audio(bounces, esc, total))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    bg = background()
    btimes = [b[0] for b in bounces]
    rng = np.random.default_rng(seed + 1)
    particles = []  # [x, y, vx, vy, life, colour]
    trail = []
    shards = None
    bi = 0
    for f, (p, r, phi) in enumerate(frames):
        t = (f + 1) / FPS
        while bi < len(bounces) and btimes[bi] <= t:
            bt, bp, br = bounces[bi]
            col = hsv((bi * 0.037) % 1)
            for _ in range(14):
                a, sp = rng.uniform(0, 2 * math.pi), rng.uniform(150, 650)
                particles.append([CX + bp[0], CY + bp[1], sp * math.cos(a), sp * math.sin(a), 0.5, col])
            bi += 1
        n_b = bi
        col = hsv((max(0, n_b - 1) * 0.037) % 1)
        flash = math.exp(-(t - btimes[n_b - 1]) / 0.08) if n_b else 0.0
        escaped = esc is not None and t >= esc

        img = bg.copy()
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        d = ImageDraw.Draw(img)

        # ring (or its shards after the escape)
        ring_col = hsv((t * 0.05) % 1, 0.7, 1.0)
        if not escaped:
            a0 = math.degrees(phi + GAP / 2)
            a1 = math.degrees(phi - GAP / 2) + 360
            box = [CX - R - TH / 2, CY - R - TH / 2, CX + R + TH / 2, CY + R + TH / 2]
            d.arc(box, a0, a1, fill=ring_col, width=int(TH))
            gd.arc([c / 4 for c in box], a0, a1, fill=ring_col, width=int(TH / 4) + 2)
        else:
            if shards is None:
                shards = []
                for k in range(60):
                    a = phi + GAP / 2 + (2 * math.pi - GAP) * (k + 0.5) / 60
                    x, y = CX + R * math.cos(a), CY + R * math.sin(a)
                    sp = rng.uniform(300, 900)
                    shards.append([x, y, sp * math.cos(a), sp * math.sin(a) - 400, a])
            for s in shards:
                s[3] += G * 0.5 / FPS
                s[0] += s[2] / FPS
                s[1] += s[3] / FPS
                L = 22
                dx, dy = -math.sin(s[4]) * L, math.cos(s[4]) * L
                d.line([s[0] - dx, s[1] - dy, s[0] + dx, s[1] + dy], fill=ring_col, width=int(TH))
                gd.line([(s[0] - dx) / 4, (s[1] - dy) / 4, (s[0] + dx) / 4, (s[1] + dy) / 4], fill=ring_col, width=5)

        # trail
        trail.append((CX + p[0], CY + p[1], r))
        trail = trail[-14:]
        for k, (x, y, rr) in enumerate(trail[:-1]):
            fade = (k + 1) / len(trail)
            c = tuple(int(ch * fade * 0.5) for ch in col)
            rr2 = rr * (0.5 + 0.5 * fade)
            d.ellipse([x - rr2, y - rr2, x + rr2, y + rr2], fill=c)

        # particles
        alive = []
        for q in particles:
            q[3] += 900 / FPS
            q[0] += q[2] / FPS
            q[1] += q[3] / FPS
            q[4] -= 1 / FPS
            if q[4] > 0:
                s = 3 + 8 * q[4]
                d.ellipse([q[0] - s, q[1] - s, q[0] + s, q[1] + s], fill=q[5])
                alive.append(q)
        particles = alive

        # ball
        x, y = CX + p[0], CY + p[1]
        rr = r * (1 + 0.12 * flash)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col, outline=(255, 255, 255), width=5)
        gd.ellipse([(x - rr) / 4, (y - rr) / 4, (x + rr) / 4, (y + rr) / 4], fill=col)

        glow = glow.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        img = Image.fromarray(np.minimum(255, np.asarray(img, np.uint16) + (np.asarray(glow, np.uint16) * 3) // 2).astype(np.uint8))
        d = ImageDraw.Draw(img)

        # text
        if not escaped:
            text(d, (W / 2, 250), "IT GROWS EVERY BOUNCE", 62, (255, 255, 255))
            pulse = 1 + 0.04 * math.sin(t * 6)
            text(d, (W / 2, 360), "WILL IT ESCAPE?", int(96 * pulse), (255, 220, 60), 10)
        else:
            k = min(1, (t - esc) / 0.25)
            text(d, (W / 2, 330), "IT ESCAPED!", int(70 + 60 * k), (90, 255, 120), 12)
            text(d, (W / 2, 470), f"after {len(bounces)} bounces", 56, (255, 255, 255))
        text(d, (W / 2, 1570), f"BOUNCES: {n_b}", int(76 * (1 + 0.15 * flash)), col, 9)
        text(d, (W / 2, 1680), f"SIZE: x{r / R0:.1f}", 54, (230, 230, 230), 7)
        if escaped and t - esc < 0.15:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.5 * (1 - (t - esc) / 0.15))
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
        render(int(os.environ.get("SEED", "185")))
