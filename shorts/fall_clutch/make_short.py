#!/usr/bin/env python3
"""Render "4 Ways to Survive a 300-Block Fall": a countdown Short cut from real Minecraft footage.

Every clutch in footage/ was recorded in survival on the channel's own account and verified in game
(full health after landing; see footage/README.md). The boat clutch failed in 26.3, so it isn't shown.
Reuses the clip streaming, zoom and voice helpers from ../water_elevator.

    SUBS=170 python shorts/fall_clutch/make_short.py   # -> shorts/fall_clutch/fall_clutch_short.mp4
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
os.environ.setdefault("SUBS", "170")
SUBS = int(os.environ["SUBS"])
OUT = HERE / "fall_clutch_short.mp4"

_spec = importlib.util.spec_from_file_location("water_elevator", HERE.parent / "water_elevator" / "make_short.py")
WE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WE)
N, V, SG = WE.N, WE.V, WE.SG
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
bump = V.bump

RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
BLUE, CYAN = (110, 190, 255), (110, 230, 230)
N.KEYWORDS = {
    "falling": RED, "300": RED, "five": YELLOW, "seconds": YELLOW, "place": YELLOW, "nothing": RED,
    "four": YELLOW, "three": YELLOW, "two": YELLOW, "one": YELLOW, "powder": WHITE, "snow": WHITE,
    "zero": GREEN, "cobwebs": WHITE, "instantly": GREEN, "slime": GREEN, "bounce": GREEN,
    "no": GREEN, "legendary": YELLOW, "water": BLUE, "bucket": BLUE, "clutch": YELLOW, "comments": CYAN,
    "goal": CYAN, "diamond": CYAN, "subscriber": RED, "subscribe": RED, "yours": CYAN,
}  # fmt: skip

SURVIVED = ("SURVIVED ✓  ♥ 20/20", (30, 140, 60))
# name, narration, clip, in-point, speed, clip time of landing (or None), top label, label colour
BEATS = [
    ("hook", "You're falling from 300 blocks. You have five seconds. What do you place?",
     "A_freefall_hook", 4.3, 1.0, None, "300 BLOCK FALL", (190, 40, 40)),
    ("splat", "Place nothing, and this happens.", "B_splat", 1.6, 1.15, 4.2, None, None),
    ("snow", "Number four: powder snow. You sink right in, zero damage.", "F_powder_snow", 1.4, 1.0, 4.2,
     "#4  POWDER SNOW", (90, 120, 160)),
    ("web", "Number three: cobwebs. They catch you instantly.", "E_cobweb", 1.4, 1.0, 4.2,
     "#3  COBWEB", (90, 90, 100)),
    ("slime", "Number two: a slime block. You bounce, and take no damage at all.", "D_slime_block", 1.4, 1.0, 4.2,
     "#2  SLIME BLOCK", (60, 150, 60)),
    ("water", "And number one: the legendary water bucket clutch. Place it right before you hit the ground.",
     "C_water_bucket", 1.2, 0.8, 4.05, "#1  WATER BUCKET", (30, 110, 210)),
    ("comment", "Which one could you actually hit? Tell me in the comments.", "D_slime_block", 4.0, 1.0, None,
     "COMMENT  ⬇", (40, 140, 160)),
    ("subs", SG.line(SUBS), f"H_castle_{SUBS}", 6.0, 1.0, None, None, None),
]  # fmt: skip


def wind(dur, rise=True):
    n = int(dur * SR)
    g = np.random.default_rng(21)
    x = g.normal(0, 1, n)
    out = np.convolve(x, np.ones(40) / 40, "same") * 6
    env = np.linspace(0.3, 1.0, n) if rise else np.ones(n)
    return 0.22 * out * env


def impact():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(22)
    return 0.6 * np.sin(2 * np.pi * np.cumsum(np.linspace(110, 40, n)) / SR) * np.exp(-t / 0.08) + 0.3 * g.normal(0, 1, n) * np.exp(-t / 0.03)


def main():
    missing = [b[2] for b in BEATS if not (FOOT / f"{b[2]}.mp4").exists()]
    if missing:
        raise SystemExit(f"missing footage: {missing} (shoot the castle with --diamonds {SUBS})")
    voices = WE.synth([b[1] for b in BEATS])
    scenes, t = [], 0.0
    for b, v in zip(BEATS, voices):
        vd = len(v) / SR
        _, starts = V.word_times(b[1], vd)
        hold = {"subs": 0.9, "splat": 0.8, "hook": 0.2}.get(b[0], 0.35)
        scenes.append(N.Scene(b[0], b[1], t, vd + 0.05 + hold, starts))
        t += scenes[-1].D
    total = t
    print(f"duration {total:.1f}s")

    plan = []
    for b, s in zip(BEATS, scenes):
        path = FOOT / f"{b[2]}.mp4"
        avail = WE.clip_len(path) - b[3]
        speed = b[4]
        if b[5] is not None:  # make sure the landing happens while the narration still has ~1 s to run
            speed = max(speed, (b[5] - b[3]) / max(0.5, s.D - 1.1))
        if avail / speed < s.D:
            speed = max(speed * 0.6, avail / s.D)
        plan.append((path, b[3], speed))

    def clip_time(i, ct):
        return scenes[i].start + (ct - plan[i][1]) / plan[i][2]

    # ---- audio
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for s, v in zip(scenes, voices):
        i0 = int(s.start * SR)
        voice[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.92
    fx = np.zeros(n)

    def add(t0, snd, g=1.0):
        i0 = int(max(0, t0) * SR)
        if i0 < n:
            fx[i0 : i0 + len(snd)] += g * snd[: n - i0]

    S = {s.name: i for i, s in enumerate(scenes)}
    add(0.0, wind(scenes[0].D), 1.0)
    for s in scenes[1:]:
        add(s.start - 0.1, V.sfx("whoosh"), 0.55)
    landings = {}
    for i, b in enumerate(BEATS):
        if b[5] is None:
            continue
        tl = clip_time(i, b[5])
        landings[b[0]] = tl
        add(scenes[i].start, wind(max(0.2, tl - scenes[i].start)), 0.9)
        if b[0] == "splat":
            add(tl, impact())
            add(tl + 0.15, N.wah_sfx())
        else:
            add(tl, {"water": V.sfx("splash"), "slime": WE_boing(), "snow": V.sfx("whoosh")}.get(b[0], impact()), 0.8)
            add(tl + 0.25, V.sfx("ding"))
    add(clip_time(S["comment"], 4.2), WE_boing(), 0.6)
    sub = scenes[S["subs"]]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(0, SUBS, max(1, SUBS // 20)):
        add(t0d + (t1d - t0d) * i / SUBS, V.sfx("pop"), 0.5)
    add(t1d, V.sfx("chime"))
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
        k = 1.0 + 0.05 * lt / sc.D + 0.08 * math.exp(-lt / 0.12)
        tl = landings.get(b[0])
        if tl is not None and t >= tl:
            k += 0.12 * math.exp(-(t - tl) / 0.15)  # impact punch
            shake = 14 * math.exp(-(t - tl) / 0.12)
            img = img.transform(img.size, Image.AFFINE, (1, 0, shake * math.sin(t * 90), 0, 1, shake * math.cos(t * 70)))
        img = WE.zoom(img, k)
        if b[6]:
            V.paste_center(img, V.pill(b[6], 66, b[7]), W / 2, 330, V.pop_scale(lt - 0.1))
        if b[0] == "hook":
            left = max(0, 5 - int(lt / max(0.1, sc.D) * 5))
            V.paste_center(img, V.text_img(str(left), 220, (255, 230, 60), 18), W / 2, 620, 1 + 0.15 * bump(lt % (sc.D / 5), 0, 0.2))
        if tl is not None and t >= tl + 0.1 and b[0] != "splat":
            V.paste_center(img, V.pill(SURVIVED[0], 60, SURVIVED[1]), W / 2, 450, V.pop_scale(t - tl - 0.1))
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
        N.draw_caption(img, sc.words, sc.starts, lt, y=1330)
        if lt < 0.08 and idx > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.2 * (1 - lt / 0.08))
        ffp.stdin.write(img.tobytes())
        if f % 90 == 0:
            print(f"frame {f}/{frames}", flush=True)
    clip.close()
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


def WE_boing():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 220 + 380 * np.abs(np.sin(2 * np.pi * 2.0 * t)) * np.exp(-t / 0.3)
    return 0.3 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.25)


if __name__ == "__main__":
    main()
