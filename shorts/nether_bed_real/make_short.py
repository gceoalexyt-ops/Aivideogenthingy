#!/usr/bin/env python3
"""Render "Never Sleep in the Nether" (first person, real footage): a Minecraft fact Short.

All footage in footage/ is real first-person survival gameplay with the HUD visible, recorded in
Minecraft Java Edition on the channel's own account (see footage/README.md). Reuses the clip
streaming, zoom and voice helpers from ../water_elevator and the captions from ../nether_bed.

    SUBS=232 python shorts/nether_bed_real/make_short.py   # -> shorts/nether_bed_real/nether_bed_real_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
FOOT = HERE / "footage"
os.environ.setdefault("SUBS", "232")
SUBS = int(os.environ["SUBS"])
OUT = HERE / "nether_bed_real_short.mp4"

_spec = importlib.util.spec_from_file_location("water_elevator", HERE.parent / "water_elevator" / "make_short.py")
WE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WE)
N, V = WE.N, WE.V
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
bump = V.bump
RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
PURPLE, CYAN = (200, 140, 255), (110, 230, 230)
N.KEYWORDS = {
    "never": RED, "sleep": RED, "nether": RED, "killer": RED, "intentional": YELLOW, "game": YELLOW,
    "design": YELLOW, "bigger": ORANGE, "tnt": RED, "fire": ORANGE, "pros": YELLOW, "purpose": YELLOW,
    "ancient": PURPLE, "debris": PURPLE, "blast": ORANGE, "proof": GREEN, "netherite": PURPLE,
    "respawn": GREEN, "anchor": GREEN, "goal": CYAN, "diamond": CYAN, "subscribe": RED, "subscriber": RED,
}  # fmt: skip

# name, narration, clip, clip start (None = continue), clip end (None = play at 1x), label, colour
BEATS = [
    ("hook", "Never sleep in the Nether.", "A_bed_boom", 1.9, 4.0, None, None),
    ("killer", "The game even names your killer: Intentional Game Design.", "B_death_screen", 0.0, None, None, None),
    ("tnt", "The blast is bigger than TNT, and it sets everything on fire.", "C_crater", 0.8, 6.2,
     "BIGGER THAN TNT", (190, 70, 20)),
    ("pros", "But pros blow up beds on purpose.", "D_bed_mining", 0.7, 3.4, None, None),
    ("debris", "Ancient debris is blast proof, so the explosion clears everything except the netherite.",
     "D_bed_mining", None, 13.6, "ANCIENT DEBRIS ✓", (110, 50, 170)),
    ("anchor", "Want to respawn in the Nether? Use a respawn anchor instead.", "E_respawn_anchor", 0.5, 7.4,
     "RESPAWN ANCHOR ✓", (30, 140, 60)),
    ("subs", f"Sub goal: every new subscriber is one diamond block in my castle. We're at {SUBS}. Subscribe!",
     f"F_castle_{SUBS}", 0.0, None, None, None),
]  # fmt: skip
# clip-time sound cues: clip -> [(time, kind)]
CUES = {
    "A_bed_boom": [(2.6, "boom")],
    "D_bed_mining": [(1.65, "boom")] + [(9.7 + 0.25 * i, "mine") for i in range(8)],
    "E_respawn_anchor": [(0.8, "pop"), (2.0, "charge"), (2.8, "charge"), (3.5, "charge"), (4.2, "charge"), (5.5, "ding")],
}


def mine_tick():
    n = int(0.06 * SR)
    g = np.random.default_rng(14)
    return 0.3 * np.convolve(g.normal(0, 1, n), np.ones(5) / 5, "same") * np.exp(-np.arange(n) / (0.012 * SR))


def charge(k):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    f = 440 * 2 ** (k / 4) * (1 + 0.5 * t)
    return 0.2 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.1)


def crackle(dur):
    n = int(dur * SR)
    g = np.random.default_rng(9)
    out = np.zeros(n)
    for i in g.integers(0, max(1, n - 400), int(dur * 35)):
        out[i : i + 300] += g.normal(0, 1, 300) * np.exp(-np.arange(300) / 50) * g.uniform(0.2, 1)
    return 0.1 * out


def main():
    voices = WE.synth([b[1] for b in BEATS])
    scenes, plan, t, c_after, prev_clip = [], [], 0.0, None, None
    for b, v in zip(BEATS, voices):
        name, text, clip, c0, c1 = b[:5]
        vd = len(v) / SR
        D = vd + 0.05 + (0.8 if name == "subs" else 0.2)
        path = FOOT / f"{clip}.mp4"
        clen = WE.clip_len(path)
        if c0 is None:
            c0 = c_after if prev_clip == clip else 0.0
        if c1 is not None:
            span = c1 - c0
            D = max(D, span / 2.5)
            speed = span / D
        else:
            speed = 1.0
            if (clen - c0) / speed < D:
                speed = max(0.55, (clen - c0) / D)
        c_after, prev_clip = c0 + speed * D, clip
        _, starts = V.word_times(text, vd)
        scenes.append(N.Scene(name, text, t, D, starts))
        plan.append((path, c0, speed))
        t += D
    total = t
    print(f"duration {total:.1f}s")

    def global_t(clip, ct):
        for s, (p, c0, sp), b in zip(scenes, plan, BEATS):
            if b[2] == clip and c0 <= ct <= c0 + sp * s.D:
                return s.start + (ct - c0) / sp
        return None

    # ---- audio
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for s, v in zip(scenes, voices):
        i0 = int(s.start * SR)
        voice[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.92
    fx = np.zeros(n)

    def add(t0, snd, g=1.0):
        if t0 is None:
            return
        i0 = int(max(0, t0) * SR)
        if i0 < n:
            fx[i0 : i0 + len(snd)] += g * snd[: n - i0]

    booms = []
    for clip, cues in CUES.items():
        ci = 0
        for ct, kind in cues:
            tg = global_t(clip, ct)
            if kind == "boom":
                add(tg, N.boom_sfx(), 1.0)
                add(tg, crackle(2.5), 0.8)
                if tg is not None:
                    booms.append(tg)
            elif kind == "mine":
                add(tg, mine_tick(), 0.8)
            elif kind == "charge":
                add(tg, charge(ci))
                ci += 1
            else:
                add(tg, V.sfx(kind), 0.8)
    S = {s.name: s for s in scenes}
    add(S["killer"].start + 0.1, N.wah_sfx(), 0.8)
    add(S["tnt"].start, crackle(S["tnt"].D), 0.7)
    for name in ("tnt", "pros", "anchor", "subs"):
        add(S[name].start - 0.1, V.sfx("whoosh"), 0.5)
    sub = S["subs"]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(0, SUBS, max(1, SUBS // 20)):
        add(t0d + (t1d - t0d) * i / SUBS, V.sfx("pop"), 0.45)
    add(t1d, V.sfx("chime"))
    mix = voice + 0.7 * fx + 0.1 * N.music(n, [(b, 0.8) for b in booms])
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    wav = HERE / "audio.tmp.wav"
    V.write_wav(wav, mix[: int(total * SR)])

    # ---- video
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(total * FPS)
    clip, cur = None, -1
    for f in range(frames):
        t = f / FPS
        idx = max(i for i, s in enumerate(scenes) if s.start <= t)
        sc, b = scenes[idx], BEATS[idx]
        lt = t - sc.start
        if idx != cur:
            if clip:
                clip.close()
            clip, cur = WE.Clip(*plan[idx]), idx
        img = clip.frame()
        recent = [x for x in booms if 0 <= t - x < 0.6]
        bf = math.exp(-(t - recent[-1]) / 0.15) if recent else 0.0
        k = 1.0 + 0.05 * lt / sc.D + 0.08 * math.exp(-lt / 0.12) + 0.15 * bf
        img = WE.zoom(img, k)
        if bf > 0.05:
            sh = 26 * bf
            img = img.transform(img.size, Image.AFFINE, (1, 0, sh * math.sin(t * 90), 0, 1, sh * math.cos(t * 70)))
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 160, 60)), 0.45 * bf)
        if b[5]:
            V.paste_center(img, V.pill(b[5], 64, b[6]), W / 2, 330, V.pop_scale(lt - 0.15))
        if b[0] == "hook":
            V.paste_center(img, V.text_img("NEVER SLEEP", 120, RED, 14), W / 2, 900, V.pop_scale(lt - 0.02))
            V.paste_center(img, V.text_img("IN THE NETHER", 100, WHITE, 12), W / 2, 1020, V.pop_scale(lt - 0.2))
        if b[0] == "killer":
            V.paste_center(img, V.pill("THIS IS THE REAL MESSAGE", 50, (190, 40, 40)), W / 2, 1500, V.pop_scale(lt - 1.2))
        if b[0] == "subs":
            V.paste_center(img, V.pill("SUB GOAL", 70, (40, 150, 160)), W / 2, 300, V.pop_scale(lt - sc.w["goal"]))
            V.paste_center(img, V.pill("1 SUBSCRIBER = 1 DIAMOND BLOCK", 46, (30, 30, 40)), W / 2, 410,
                           V.pop_scale(lt - sc.w["diamond"]))  # fmt: skip
            t0, t1 = sc.w["every"], sc.w["we're"] + 0.3
            if lt >= t0:
                shown = min(SUBS, 1 + int((lt - t0) / max(0.01, (t1 - t0) / SUBS)))
                V.paste_center(img, V.pill(f"DIAMOND BLOCKS: {shown}", 64, (30, 120, 200)), W / 2, 530,
                               1 + 0.15 * bump(lt - t1, 0, 0.3))  # fmt: skip
            if lt >= sc.w["subscribe"]:
                V.paste_center(img, V.pill("SUBSCRIBE  ➜  +1 DIAMOND", 62, (210, 40, 40)), W / 2, 1600,
                               V.pop_scale(lt - sc.w["subscribe"]) * (1 + 0.05 * math.sin(lt * 8)))  # fmt: skip
        N.draw_caption(img, sc.words, sc.starts, lt, y=1180)
        if lt < 0.08 and idx > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.2 * (1 - lt / 0.08))
        ffp.stdin.write(img.tobytes())
    clip.close()
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
