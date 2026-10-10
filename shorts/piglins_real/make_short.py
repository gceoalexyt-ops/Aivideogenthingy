#!/usr/bin/env python3
"""Render "Never Walk Into the Nether Without Gold" (first person, real footage): a Minecraft fact Short.

All footage in footage/ is real first-person survival gameplay with the HUD visible, recorded in
Minecraft Java Edition on the channel's own account (see footage/README.md); piglin behaviour is
vanilla AI. Reuses the clip streaming, zoom and voice helpers from ../water_elevator and the
captions from ../nether_bed.

    SUBS=232 python shorts/piglins_real/make_short.py   # -> shorts/piglins_real/piglins_real_short.mp4
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
OUT = HERE / "piglins_real_short.mp4"

_spec = importlib.util.spec_from_file_location("water_elevator", HERE.parent / "water_elevator" / "make_short.py")
WE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WE)
N, V = WE.N, WE.V
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
bump = V.bump
RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
GOLD, CYAN = (255, 200, 40), (110, 230, 230)
N.KEYWORDS = {
    "nether": RED, "without": RED, "gold": GOLD, "golden": GOLD, "helmet": GOLD, "ignore": GREEN,
    "ignored": GREEN, "ingots": GOLD, "trade": GREEN, "loot": GREEN, "brutes": RED, "anyway": RED,
    "never": RED, "mine": RED, "block": GOLD, "turn": RED, "goal": CYAN, "diamond": CYAN,
    "subscribe": RED, "subscriber": RED, "attacks": RED, "piglins": ORANGE,
}  # fmt: skip
# brighten the dark Nether footage a little so it reads on a phone
LUT = [int(255 * (i / 255) ** 0.8) for i in range(256)] * 3

# name, narration, clip, clip start (None = continue), clip end (None = play at 1x), label, colour
BEATS = [
    ("hook", "Never walk into the Nether without gold.", "A_no_gold_chase", 0.3, 4.3, None, None),
    ("helmet", "Wear just one piece of gold armor,", "B_gold_helmet", 0.4, 2.6, "GOLD HELMET ✓", (190, 140, 20)),
    ("calm", "and piglins completely ignore you.", "B_gold_helmet", None, 11.0, "IGNORED ✓", (30, 140, 60)),
    ("barter", "Throw them gold ingots, and they trade you random loot.", "C_barter", 1.0, 10.6,
     "BARTERING", (190, 140, 20)),
    ("brute", "But brutes don't care about gold. They attack anyway.", "D_brute", 0.0, 4.2,
     "PIGLIN BRUTE ✗", (170, 30, 30)),
    ("angry", "And never mine a gold block near them. Even with the helmet, they turn on you.",
     "E_angry_gold", 0.6, 5.6, "DON'T MINE GOLD ✗", (170, 30, 30)),
    ("subs", f"Sub goal: every new subscriber is one diamond block in my castle. We're at {SUBS}. Subscribe!",
     f"F_castle_{SUBS}", 0.0, None, None, None),
]  # fmt: skip
# clip-time sound cues: clip -> [(time, kind)]
CUES = {
    "A_no_gold_chase": [(3.3, "hit")],
    "B_gold_helmet": [(1.0, "equip")],
    "C_barter": [(1.4, "throw"), (2.3, "throw"), (3.3, "throw"), (7.5, "pop"), (8.5, "pop"), (9.5, "pop")],
    "D_brute": [(1.0, "hit"), (3.5, "hit")],
    "E_angry_gold": [(1.2 + 0.25 * i, "mine") for i in range(7)] + [(2.8, "pop"), (4.1, "hit")],
}


def hit_sfx():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(31)
    thump = np.sin(2 * np.pi * np.cumsum(np.linspace(180, 60, n)) / SR) * np.exp(-t / 0.06)
    return 0.7 * thump + 0.35 * g.normal(0, 1, n) * np.exp(-t / 0.02)


def equip_sfx():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    return 0.2 * (np.sin(2 * np.pi * 1400 * t) + 0.6 * np.sin(2 * np.pi * 2100 * t)) * np.exp(-t / 0.08)


def mine_tick():
    n = int(0.06 * SR)
    g = np.random.default_rng(14)
    return 0.3 * np.convolve(g.normal(0, 1, n), np.ones(5) / 5, "same") * np.exp(-np.arange(n) / (0.012 * SR))


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

    hits = []
    for clip, cues in CUES.items():
        for ct, kind in cues:
            tg = global_t(clip, ct)
            if kind == "hit":
                add(tg, hit_sfx(), 1.0)
                if tg is not None:
                    hits.append(tg)
            elif kind == "mine":
                add(tg, mine_tick(), 0.8)
            elif kind == "equip":
                add(tg, equip_sfx())
            elif kind == "throw":
                add(tg, V.sfx("whoosh"), 0.6)
            else:
                add(tg, V.sfx(kind), 0.7)
    S = {s.name: s for s in scenes}
    for name in ("helmet", "barter", "brute", "angry", "subs"):
        add(S[name].start - 0.1, V.sfx("whoosh"), 0.5)
    add(S["calm"].start + S["calm"].w["ignore"], V.sfx("ding"), 0.8)
    sub = S["subs"]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(0, SUBS, max(1, SUBS // 20)):
        add(t0d + (t1d - t0d) * i / SUBS, V.sfx("pop"), 0.45)
    add(t1d, V.sfx("chime"))
    mix = voice + 0.7 * fx + 0.1 * N.music(n, [(h, 0.5) for h in hits])
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
        img = clip.frame().point(LUT)
        recent = [x for x in hits if 0 <= t - x < 0.5]
        bf = math.exp(-(t - recent[-1]) / 0.12) if recent else 0.0
        k = 1.0 + 0.05 * lt / sc.D + 0.08 * math.exp(-lt / 0.12) + 0.1 * bf
        img = WE.zoom(img, k)
        if bf > 0.05:
            sh = 18 * bf
            img = img.transform(img.size, Image.AFFINE, (1, 0, sh * math.sin(t * 90), 0, 1, sh * math.cos(t * 70)))
            img = Image.blend(img, Image.new("RGB", (W, H), (220, 20, 20)), 0.35 * bf)
        if b[5]:
            V.paste_center(img, V.pill(b[5], 64, b[6]), W / 2, 330, V.pop_scale(lt - 0.15))
        if b[0] == "hook":
            V.paste_center(img, V.text_img("NO GOLD?", 130, GOLD, 14), W / 2, 720, V.pop_scale(lt - 0.02))
            V.paste_center(img, V.text_img("YOU'RE DEAD", 110, RED, 12), W / 2, 850, V.pop_scale(lt - 0.25))
        if b[0] == "barter" and lt >= sc.w["random"]:
            V.paste_center(img, V.pill("LEATHER  ·  SOUL SAND  ·  QUARTZ", 46, (30, 30, 40)), W / 2, 1500,
                           V.pop_scale(lt - sc.w["random"]))  # fmt: skip
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
