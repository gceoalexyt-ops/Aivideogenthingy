#!/usr/bin/env python3
"""Render "The Water Elevator": a Short cut from real Minecraft footage (footage/), with narration,
word-by-word captions, zoom punches, labels, sound effects, music and the subscriber-goal ending.

The footage was recorded in vanilla Minecraft Java Edition on the channel's own account
(see footage/README.md). Captions, labels, voice and music reuse the helpers in ../nether_bed.

    SUBS=60 python shorts/water_elevator/make_short.py   # -> shorts/water_elevator/water_elevator_short.mp4

The castle clip must match the count: footage/H_castle_<SUBS>.mp4.
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
SUBS = int(os.environ.get("SUBS", "170"))
OUT = HERE / "water_elevator_short.mp4"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N = _load("nether", HERE.parent / "nether_bed" / "make_short.py")
SG = _load("sub_goal", HERE.parent / "sub_goal.py")
V = N.V
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
ease, clamp01, bump = V.ease, V.clamp01, V.bump

RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
BLUE, CYAN = (110, 190, 255), (110, 230, 230)
N.KEYWORDS = {
    "launches": YELLOW, "thirty": YELLOW, "seconds": YELLOW, "tube": BLUE, "water": BLUE, "source": BLUE,
    "soul": ORANGE, "sand": ORANGE, "straight": GREEN, "up": GREEN, "magma": RED, "down": RED,
    "kelp": GREEN, "drown": RED, "air": BLUE, "goal": CYAN, "diamond": CYAN, "subscriber": RED,
    "subscribe": RED, "yours": CYAN,
}  # fmt: skip

# name, narration, clip, in-point (s), playback speed, label, label colour
BEATS = [
    ("hook", "This launches you thirty blocks up, in seconds.", "A_rocket_up", 2.0, 1.0, "WATER ELEVATOR", (30, 110, 210)),
    ("build", "Build a one block wide tube, and fill it with water source blocks.", "C_build_tube", 0.8, 2.0, "1×1 TUBE + WATER", (30, 110, 210)),
    ("soul", "Put soul sand at the bottom, and the bubbles push you straight up.", "D_soul_sand", 2.2, 1.0, "SOUL SAND = UP ↑", (200, 110, 30)),
    ("ride", "Thirty two blocks. Zero effort.", "B_outside_view", 1.4, 1.0, "32 BLOCKS", (30, 140, 60)),
    ("magma", "Use a magma block instead, and it drags you down.", "E_magma_down", 1.0, 1.0, "MAGMA = DOWN ↓", (190, 40, 40)),
    ("kelp", "Pro tip: kelp turns flowing water into source blocks, so you can fill it in seconds.", "F_kelp_trick", 2.0, 1.4, "KELP ➜ SOURCE WATER", (40, 140, 70)),
    ("air", "And you can't drown in it. Bubble columns refill your air.", "G_air_refill", 7.3, 1.0, "AIR REFILLS ✓", (30, 140, 60)),
    ("subs", SG.line(SUBS), f"H_castle_{SUBS}", 7.0, 1.0, None, None),
]  # fmt: skip
HOLD = 0.12


def synth(texts):
    from kokoro_onnx import Kokoro

    d = V.kokoro_dir()
    k = Kokoro(str(d / V.KOKORO_FILES[0]), str(d / V.KOKORO_FILES[1]))
    out = []
    for text in texts:
        s, sr = k.create(text, voice=N.VOICE, speed=1.12, lang="en-us")
        s = np.asarray(s, np.float32)
        loud = np.nonzero(np.abs(s) > 0.02)[0]
        s = s[max(0, loud[0] - int(0.02 * sr)) : loud[-1] + int(0.06 * sr)]
        n = int(len(s) * SR / sr)
        out.append(np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32))
    return out


def clip_len(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout  # fmt: skip
    return float(out)


class Clip:
    """Streams a clip from an in-point at a playback speed, scaled to 1080x1920; holds the last frame."""

    def __init__(self, path, start, speed):
        vf = f"setpts=PTS/{speed},fps={FPS},scale={W}:{H}:flags=lanczos"
        cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(start), "-i", str(path), "-vf", vf,
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]  # fmt: skip
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.last = Image.new("RGB", (W, H))

    def frame(self):
        buf = self.p.stdout.read(W * H * 3)
        if len(buf) == W * H * 3:
            self.last = Image.frombytes("RGB", (W, H), buf)
        return self.last.copy()

    def close(self):
        self.p.kill()
        self.p.wait()


def zoom(img, k):
    if k <= 1.001:
        return img
    w, h = W / k, H / k
    return img.resize((W, H), Image.BILINEAR, box=((W - w) / 2, (H - h) / 2, (W + w) / 2, (H + h) / 2))


def bubbles(dur):
    n = int(dur * SR)
    g = np.random.default_rng(5)
    out = np.zeros(n)
    for i in g.integers(0, max(1, n - 3000), int(dur * 22)):
        ln = int(g.uniform(0.02, 0.05) * SR)
        t = np.arange(ln) / SR
        f = g.uniform(500, 1400) * (1 + 3 * t)
        out[i : i + ln] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.012) * g.uniform(0.3, 1)
    return 0.08 * out


def main():
    missing = [b[2] for b in BEATS if not (FOOT / f"{b[2]}.mp4").exists()]
    if missing:
        raise SystemExit(f"missing footage: {missing} (re-shoot the castle with --diamonds {SUBS})")
    voices = synth([b[1] for b in BEATS])
    scenes, t = [], 0.0
    for b, v in zip(BEATS, voices):
        vd = len(v) / SR
        _, starts = V.word_times(b[1], vd)
        hold = 0.9 if b[0] == "subs" else HOLD
        scenes.append(N.Scene(b[0], b[1], t, vd + 0.05 + hold, starts))
        t += scenes[-1].D
    total = t
    print(f"duration {total:.1f}s")

    # Slow a clip down (to at most 0.6x of its set speed) if it would run out before its beat ends.
    plan = []
    for b, s in zip(BEATS, scenes):
        path = FOOT / f"{b[2]}.mp4"
        avail = clip_len(path) - b[3]
        speed = b[4]
        if avail / speed < s.D:
            speed = max(b[4] * 0.6, avail / s.D)
        plan.append((path, b[3], speed))

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

    def clip_time(idx, ct):
        """Global time at which clip time ct plays in beat idx."""
        path, start, speed = plan[idx]
        return scenes[idx].start + (ct - start) / speed

    S = {s.name: i for i, s in enumerate(scenes)}
    for s in scenes[1:]:
        add(s.start - 0.1, V.sfx("whoosh"), 0.55)
    add(clip_time(S["hook"], 2.5), V.sfx("pop"))
    add(clip_time(S["hook"], 2.5), bubbles(3.0), 1.2)
    add(clip_time(S["hook"], 5.3), V.sfx("splash"), 0.6)
    add(clip_time(S["build"], 5.2), V.sfx("splash"), 0.5)
    add(clip_time(S["soul"], 2.8), V.sfx("pop"))
    add(clip_time(S["soul"], 2.8), bubbles(scenes[S["soul"]].D - 0.6))
    add(scenes[S["ride"]].start, bubbles(scenes[S["ride"]].D))
    add(clip_time(S["magma"], 1.5), V.sfx("pop"))
    add(clip_time(S["magma"], 1.5), bubbles(2.0))
    for i in range(10):
        add(clip_time(S["kelp"], 2.3 + 0.35 * i), V.sfx("pop"), 0.35)
    add(clip_time(S["kelp"], 7.7), V.sfx("chime"))
    add(clip_time(S["air"], 9.5), V.sfx("ding"))
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
            clip, cur = Clip(*plan[idx]), idx
        img = clip.frame()
        k = 1.0 + 0.05 * lt / sc.D + 0.08 * math.exp(-lt / 0.12)
        img = zoom(img, k)
        if b[5]:
            V.paste_center(img, V.pill(b[5], 62, b[6]), W / 2, 330, V.pop_scale(lt - 0.15))
        if b[0] == "subs":
            V.paste_center(img, V.pill("SUB GOAL", 70, (40, 150, 160)), W / 2, 300, V.pop_scale(lt - sc.w["goal"]))
            V.paste_center(img, V.pill("1 SUBSCRIBER = 1 DIAMOND BLOCK", 46, (30, 30, 40)), W / 2, 410,
                           V.pop_scale(lt - sc.w["diamond"]))  # fmt: skip
            t0, t1 = sc.w["every"], sc.w["we're"] + 0.3
            if lt >= t0:
                shown = min(SUBS, 1 + int((lt - t0) / max(0.02, (t1 - t0) / SUBS)))
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


if __name__ == "__main__":
    main()
