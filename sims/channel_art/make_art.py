#!/usr/bin/env python3
"""Channel art for the physics-sim channel: profile picture (800x800) and banner (2560x1440).

The banner keeps all text inside YouTube's 1546x423 safe area (centred), so it reads on phones, TVs
and desktop alike; the rings and balls outside it are decoration that can be cropped away.

    python sims/channel_art/make_art.py   # -> sims/channel_art/pfp.png, banner.png
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SS = 2  # supersampling


def bg(w, h, top=(22, 12, 48), bot=(4, 4, 14)):
    y = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top) * (1 - y) + np.array(bot) * y
    return Image.fromarray(np.broadcast_to(arr, (h, w, 3)).astype(np.uint8))


def add_glow(img, layer, radius, gain=1.6):
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    out = np.asarray(img, np.float32) + gain * np.asarray(g, np.float32)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def ring(draws, cx, cy, r, th, gap_at, gap, col):
    a0 = math.degrees(gap_at + gap / 2)
    a1 = math.degrees(gap_at - gap / 2) + 360
    for d in draws:
        d.arc([cx - r, cy - r, cx + r, cy + r], a0, a1, fill=col, width=int(th))


def ball(draws, x, y, r, col, face="happy", look=(1, -0.3)):
    d = draws[0]
    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255), width=max(3, int(r * 0.08)))
    for gd in draws[1:]:  # dim halo only, so the glow doesn't wash the face out
        gd.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(c * 0.45) for c in col))
    lx, ly = look
    for s in (-1, 1):
        ex, ey = x + s * r * 0.3, y - r * 0.12
        er = r * 0.2
        d.ellipse([ex - er, ey - er * 1.15, ex + er, ey + er * 1.15], fill=(255, 255, 255))
        pr = er * 0.55
        px, py = ex + lx * er * 0.4, ey + ly * er * 0.4
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(15, 15, 25))
    mw = r * 0.38
    if face == "happy":
        d.chord([x - mw, y + r * 0.05, x + mw, y + r * 0.6], 0, 180, fill=(40, 10, 30))
    else:  # worried
        d.arc([x - mw * 0.7, y + r * 0.3, x + mw * 0.7, y + r * 0.7], 200, 340, fill=(40, 10, 30), width=max(3, int(r * 0.07)))


def trail(draws, pts, r, col):
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        k = (i + 1) / (n + 1)
        c = tuple(int(ch * k * 0.6) for ch in col)
        rr = r * (0.35 + 0.6 * k)
        draws[0].ellipse([x - rr, y - rr, x + rr, y + rr], fill=c)


def text(d, xy, s, size, fill, stroke=0, anchor="mm"):
    d.text(xy, s, font=ImageFont.truetype(FONT, size), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0))


def pfp():
    S = 800 * SS
    img = bg(S, S, (30, 14, 60), (6, 4, 20))
    glow = Image.new("RGB", (S, S))
    d, g = ImageDraw.Draw(img), ImageDraw.Draw(glow)
    cx, cy, r = S * 0.47, S * 0.53, S * 0.3
    ring((d, g), cx, cy, r, S * 0.035, math.radians(-40), math.radians(62), (90, 230, 255))
    # the ball squeezing out through the gap, top right
    a = math.radians(-40)
    bx, by = cx + (r + S * 0.06) * math.cos(a), cy + (r + S * 0.06) * math.sin(a)
    trail((d,), [(cx + t * (bx - cx) - S * 0.05 * (1 - t), cy + t * (by - cy) + S * 0.08 * (1 - t)) for t in np.linspace(0.35, 0.8, 5)],
          S * 0.11, (255, 90, 160))  # fmt: skip
    ball((ImageDraw.Draw(Image.new("RGB", (1, 1))), g), bx, by, S * 0.12, (255, 90, 160))
    img = add_glow(img, glow, 10 * SS)
    ball((ImageDraw.Draw(img),), bx, by, S * 0.12, (255, 90, 160), "happy", (0.8, -0.6))
    img = img.resize((800, 800), Image.LANCZOS)
    img.save(HERE / "pfp.png")
    # circle-cropped preview, as YouTube shows it
    m = Image.new("L", (800, 800))
    ImageDraw.Draw(m).ellipse([0, 0, 799, 799], fill=255)
    prev = Image.new("RGB", (800, 800), (255, 255, 255))
    prev.paste(img, mask=m)
    prev.save(HERE / "pfp_circle_preview.png")


def banner():
    Wb, Hb = 2560 * SS, 1440 * SS
    img = bg(Wb, Hb)
    glow = Image.new("RGB", (Wb, Hb))
    d, g = ImageDraw.Draw(img), ImageDraw.Draw(glow)
    sx0, sx1 = (Wb - 1546 * SS) / 2, (Wb + 1546 * SS) / 2  # safe area
    sy0, sy1 = (Hb - 423 * SS) / 2, (Hb + 423 * SS) / 2

    # left: the trapped, worried ball (inside the safe area so it always shows)
    cx, cy, r = sx0 + 215 * SS, Hb / 2, 175 * SS
    ring((d, g), cx, cy, r, 14 * SS, math.radians(-30), math.radians(16), (90, 230, 255))
    balls = [(cx - 20 * SS, cy + 40 * SS, 105 * SS, (255, 90, 160), "worried", (0.9, -0.5))]

    # right: decorative rings outside the safe area (cropped on phones)
    deco = [(0.07, 0.22, 130, (255, 200, 60)), (0.30, 0.12, 95, (120, 255, 140)), (0.70, 0.13, 110, (190, 120, 255)),
            (0.93, 0.25, 140, (255, 120, 90)), (0.12, 0.82, 120, (190, 120, 255)), (0.42, 0.88, 90, (255, 120, 90)),
            (0.64, 0.84, 125, (255, 200, 60)), (0.90, 0.78, 100, (120, 255, 140))]
    for k, (fx, fy, rr, col) in enumerate(deco):
        x, y, rr = fx * Wb, fy * Hb, rr * SS
        ring((d, g), x, y, rr, 10 * SS, k * 1.9, math.radians(35), col)
        balls.append((x + rr * 0.25, y + rr * 0.35, rr * 0.33, col, "happy", (math.cos(k * 2.3), -0.5)))
        ball((ImageDraw.Draw(Image.new("RGB", (1, 1))), g), *balls[-1][:4])
    ball((ImageDraw.Draw(Image.new("RGB", (1, 1))), g), *balls[0][:4])

    tx = sx0 + 445 * SS
    text(d, (tx, sy0 + 105 * SS), "THIS BALL IS STUCK.", 92 * SS, (255, 255, 255), 0, "lm")
    text(d, (tx, sy0 + 225 * SS), "EVERY SUBSCRIBER", 74 * SS, (255, 220, 60), 0, "lm")
    text(d, (tx, sy0 + 310 * SS), "MAKES THE GAP BIGGER.", 74 * SS, (255, 220, 60), 0, "lm")
    text(d, (tx, sy0 + 390 * SS), "(he has a family)", 40 * SS, (180, 180, 210), 0, "lm")
    img = add_glow(img, glow, 14 * SS, 1.4)
    for b in balls:
        ball((ImageDraw.Draw(img),), *b)
    img = img.resize((2560, 1440), Image.LANCZOS)
    img.save(HERE / "banner.png")
    # preview with the safe area marked
    prev = img.copy()
    ImageDraw.Draw(prev).rectangle([(2560 - 1546) / 2, (1440 - 423) / 2, (2560 + 1546) / 2, (1440 + 423) / 2], outline=(255, 0, 0), width=4)
    prev.save(HERE / "banner_safe_area_preview.png")


if __name__ == "__main__":
    pfp()
    banner()
    print("wrote pfp.png, banner.png")
