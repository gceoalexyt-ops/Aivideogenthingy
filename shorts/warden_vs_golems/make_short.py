#!/usr/bin/env python3
"""Render "1 Warden vs 10 Iron Golems": a fight Short cut from a real, unrigged Minecraft fight.

The fight in footage/ was recorded in Minecraft Java Edition on the channel's own account, with
vanilla AI on a vanilla server (see footage/README.md). Its telemetry CSV (Warden health and golems
alive over time) drives everything result-dependent: the narration, the health bar, the golem
counter, the speed-ramps and the slow-motion finish. So the video always tells what really happened.

    SUBS=187 python shorts/warden_vs_golems/make_short.py   # -> shorts/warden_vs_golems/warden_short.mp4
    FOOTAGE=footage/v2 ...                                   # use another take
"""

from __future__ import annotations

import csv
import importlib.util
import math
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
FOOT = HERE / os.environ.get("FOOTAGE", "footage")
os.environ.setdefault("SUBS", "187")
SUBS = int(os.environ["SUBS"])
OUT = HERE / "warden_short.mp4"

_spec = importlib.util.spec_from_file_location("water_elevator", HERE.parent / "water_elevator" / "make_short.py")
WE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WE)
N, V, SG = WE.N, WE.V, WE.SG
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
ease, clamp01, bump = V.ease, V.clamp01, V.bump
RED, YELLOW, GREEN, WHITE, ORANGE = N.RED, N.YELLOW, N.GREEN, N.WHITE, N.ORANGE
TEAL, CYAN = (60, 200, 210), (110, 230, 230)
LAG = 0.2  # server readings trail the picture slightly


# ----------------------------------------------------------------------------------------- telemetry
def load_telemetry(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append((float(r["clip_time_s"]) - LAG, float(r["warden_health"]), int(r["golems_alive"]), r["event"]))
    total = max(r[2] for r in rows)
    deaths = [r[0] for r in rows if r[3] == "golem_death"]
    wd = [r[0] for r in rows if r[3] == "warden_death"]
    return rows, total, deaths, (wd[0] if wd else None)


def at(rows, t):
    """Warden health and golems alive at clip time t (linear health between samples)."""
    prev = rows[0]
    for r in rows:
        if r[0] > t:
            k = clamp01((t - prev[0]) / max(1e-3, r[0] - prev[0]))
            return prev[1] + (r[1] - prev[1]) * k, prev[2]
        prev = r
    return rows[-1][1], rows[-1][2]


def number_word(n):
    words = "zero one two three four five six seven eight nine ten eleven twelve".split()
    return words[n] if 0 <= n < len(words) else str(n)


# ----------------------------------------------------------------------------------------- script
def build_beats(rows, total, deaths, warden_death):
    golems_win = warden_death is not None
    final = warden_death if golems_win else deaths[-1]
    hp_close, alive_close = at(rows, final - 1.4)
    survivors = at(rows, final + 0.5)[1]
    dead = total - survivors
    first = deaths[0] if deaths else final - 6
    mid = deaths[len(deaths) // 2] if len(deaths) > 2 else (first + final) / 2
    tw = number_word(total).capitalize()
    if golems_win:
        climax = f"{number_word(alive_close).capitalize()} golems left, and the Warden has {int(round(hp_close))} health!"
        verdict = f"The golems win! {number_word(survivors).capitalize()} survived, but {number_word(dead)} died taking it down."
        stamp = ("IRON GOLEMS WIN", (40, 150, 60))
    else:
        climax = f"One golem left, and the Warden still has {int(round(hp_close))} health!"
        verdict = f"The Warden wins! All {number_word(total)} golems, gone."
        stamp = ("WARDEN WINS", (20, 110, 120))
    # name, text, clip, clip start, clip end (None: play at speed 1 for the line), min duration, label
    beats = [
        ("hook", f"One Warden. {tw} iron golems. Comment who you think wins!", "A_lineup", 0.0, None, 0, None),
        ("start", "Fight! The Warden has five hundred health, and hits like a truck.", "B_fight", 0.8, first + 0.6, 0, None),
        ("pace", "It's killing a golem every few seconds.", "B_fight", first + 0.6, mid, 0, None),
        ("chip", "But the golems keep swinging.", "B_fight", mid, final - 4.0, 0, None),
        ("climax", climax, "B_fight", final - 4.0, final - 1.0, 0, None),
        ("final", "And...", "B_fight", final - 1.0, final + 0.6, 2.6, None),
        ("verdict", verdict, "C_aftermath", 0.5, None, 0, stamp),
        ("guess", "Did you guess right? Tell me in the comments.", "C_aftermath", None, None, 0, None),
        ("subs", SG.line(SUBS), f"D_castle_{SUBS}", 7.0, None, 0, None),
    ]
    return beats, final, golems_win


KEYWORDS = {
    "warden": TEAL, "golems": WHITE, "iron": WHITE, "comment": YELLOW, "wins": YELLOW, "fight": RED,
    "five": RED, "hundred": RED, "truck": RED, "killing": RED, "swinging": YELLOW, "health": RED,
    "survived": GREEN, "died": RED, "gone": RED, "guess": YELLOW, "comments": YELLOW,
    "goal": CYAN, "diamond": CYAN, "subscriber": RED, "subscribe": RED, "yours": CYAN,
}  # fmt: skip


# ----------------------------------------------------------------------------------------- HUD
def golem_icon(alive, size=58):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body = (214, 206, 196) if alive else (90, 90, 90)
    d.rectangle((3, 1, 12, 14), fill=body, outline=(40, 40, 40))
    d.rectangle((5, 5, 6, 6), fill=(150, 30, 30) if alive else (50, 50, 50))
    d.rectangle((9, 5, 10, 6), fill=(150, 30, 30) if alive else (50, 50, 50))
    d.rectangle((7, 7, 8, 11), fill=(170, 160, 150) if alive else (70, 70, 70))
    d.line((3, 9, 12, 9), fill=(110, 140, 70) if alive else (60, 60, 60))
    im = im.resize((size, size), Image.NEAREST)
    if not alive:
        x = ImageDraw.Draw(im)
        x.line((6, 6, size - 6, size - 6), fill=(220, 40, 40), width=6)
        x.line((size - 6, 6, 6, size - 6), fill=(220, 40, 40), width=6)
    return im


def draw_hud(img, hp, alive, total, flash):
    d = ImageDraw.Draw(img)
    x0, x1, y = 90, 990, 250
    V.paste_center(img, V.text_img("WARDEN", 46, TEAL, 6), x0 + 110, y - 52)
    V.paste_center(img, V.text_img(f"{int(round(hp))}/500", 42, WHITE, 6), x1 - 110, y - 52)
    d.rounded_rectangle((x0, y - 22, x1, y + 22), 14, fill=(20, 20, 24), outline=(255, 255, 255), width=4)
    w = (x1 - x0 - 12) * clamp01(hp / 500)
    if w > 2:
        d.rounded_rectangle((x0 + 6, y - 16, x0 + 6 + w, y + 16), 10, fill=(220, 40 + int(160 * flash), 40))
    size, gap = 64, 18
    start = W / 2 - (total * size + (total - 1) * gap) / 2
    for i in range(total):
        icon = golem_icon(i < alive, size)
        img.paste(icon, (round(start + i * (size + gap)), 330), icon)
    V.paste_center(img, V.pill(f"GOLEMS LEFT: {alive}", 50, (70, 70, 80)), W / 2, 450, 1 + 0.2 * flash)


# ----------------------------------------------------------------------------------------- main
def main():
    rows, total, deaths, warden_death = load_telemetry(FOOT / "B_fight_telemetry.csv")
    beats, final, golems_win = build_beats(rows, total, deaths, warden_death)
    N.KEYWORDS = KEYWORDS
    voices = WE.synth([b[1] for b in beats])
    lens = {b[2]: WE.clip_len(FOOT / f"{b[2]}.mp4") for b in beats}

    scenes, plan, t = [], [], 0.0
    c_after = None
    for b, v in zip(beats, voices):
        name, text, clip, c0, c1, dmin, _ = b
        vd = len(v) / SR
        D = max(vd + 0.05 + (0.9 if name == "subs" else 0.25), dmin)
        if c0 is None:
            c0 = c_after or 0.0
        if c1 is not None:
            span = c1 - c0
            D = max(D, span / 2.6)  # never faster than 2.6x
            speed = span / D
        else:
            speed = 1.0 if name != "hook" else max(1.0, (lens[clip] - c0) / D)
            avail = lens[clip] - c0
            if avail / speed < D:
                speed = max(0.6, avail / D)
        c_after = c0 + speed * D
        _, starts = V.word_times(text, vd)
        scenes.append(N.Scene(name, text, t, D, starts))
        plan.append((FOOT / f"{clip}.mp4", c0, speed))
        t += D
    total_t = t
    print(f"duration {total_t:.1f}s  result: {'golems' if golems_win else 'warden'} win")

    def global_t(ct):
        """Global time at which fight clip time ct plays."""
        for s, (p, c0, sp), b in zip(scenes, plan, beats):
            if b[2] == "B_fight" and c0 <= ct <= c0 + sp * s.D:
                return s.start + (ct - c0) / sp
        return None

    # ---- audio
    n = int(total_t * SR) + SR
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

    S = {s.name: i for i, s in enumerate(scenes)}
    add(0.05, N.boom_sfx(), 0.35)
    add(scenes[S["start"]].start, V.sfx("chime"), 0.8)
    death_g = [global_t(d) for d in deaths]
    for tg in death_g:
        add(tg, WE_thud(), 0.9)
        add(tg, V.sfx("pop"), 0.6)
    t_final = global_t(final)
    add(t_final, N.boom_sfx(), 0.9)
    add(scenes[S["verdict"]].start + 0.05, V.sfx("chime"))
    for s in scenes[1:]:
        if s.name not in ("pace", "chip", "climax", "final"):
            add(s.start - 0.1, V.sfx("whoosh"), 0.5)
    sub = scenes[S["subs"]]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(0, SUBS, max(1, SUBS // 20)):
        add(t0d + (t1d - t0d) * i / SUBS, V.sfx("pop"), 0.5)
    add(t1d, V.sfx("chime"))
    ducks = [(t_final - 0.05, 1.2)] if t_final else []
    mix = voice + 0.7 * fx + 0.11 * N.music(n, ducks)
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    wav = HERE / "audio.tmp.wav"
    V.write_wav(wav, mix[: int(total_t * SR)])

    # ---- video
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
    ]  # fmt: skip
    ffp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(total_t * FPS)
    clip, cur = None, -1
    for f in range(frames):
        t = f / FPS
        idx = max(i for i, s in enumerate(scenes) if s.start <= t)
        sc, b = scenes[idx], beats[idx]
        lt = t - sc.start
        if idx != cur:
            if clip:
                clip.close()
            clip, cur = WE.Clip(*plan[idx]), idx
        img = clip.frame()
        k = 1.0 + 0.05 * lt / sc.D + (0.08 * math.exp(-lt / 0.12) if b[0] in ("hook", "start", "verdict", "subs") else 0)
        recent = [tg for tg in death_g if tg is not None and 0 <= t - tg < 0.4]
        hitf = math.exp(-(t - recent[-1]) / 0.12) if recent else 0.0
        fin = math.exp(-(t - t_final) / 0.18) if t_final and t >= t_final else 0.0
        k += 0.06 * hitf + 0.12 * fin
        img = WE.zoom(img, k)
        if hitf + fin > 0.05:
            sh = 16 * (hitf + 1.5 * fin)
            img = img.transform(img.size, Image.AFFINE, (1, 0, sh * math.sin(t * 90), 0, 1, sh * math.cos(t * 70)))

        if b[2] == "B_fight":
            p, c0, sp = plan[idx]
            ct = c0 + lt * sp
            hp, alive = at(rows, ct)
            draw_hud(img, hp, alive, total, hitf + fin)
            if sp > 1.35:
                V.paste_center(img, V.pill(f"{sp:.1f}×", 40, (40, 40, 48)), 980, 560)
            elif sp < 0.7:
                V.paste_center(img, V.pill("SLOW-MO", 40, (40, 40, 48)), 960, 560)
            for tg in death_g:
                if tg is not None and 0 <= t - tg < 0.7:
                    V.paste_center(img, V.text_img("-1 GOLEM", 70, RED, 10), W / 2, 640 - 60 * (t - tg), V.pop_scale(t - tg, 0.15))
        if b[0] == "hook":
            V.paste_center(img, V.text_img("1 WARDEN", 120, TEAL, 14), W / 2, 330, V.pop_scale(lt - 0.05))
            V.paste_center(img, V.text_img("VS", 90, YELLOW, 12), W / 2, 450, V.pop_scale(lt - 0.35))
            V.paste_center(img, V.text_img(f"{total} IRON GOLEMS", 110, WHITE, 14), W / 2, 570, V.pop_scale(lt - 0.6))
        if b[6]:
            V.paste_center(img, V.pill(b[6][0], 80, b[6][1]), W / 2, 420, V.pop_scale(lt - 0.05, 0.25))
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
        if t_final and 0 <= t - t_final < 0.25:
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.7 * (1 - (t - t_final) / 0.25))
        ffp.stdin.write(img.tobytes())
        if f % 150 == 0:
            print(f"frame {f}/{frames}", flush=True)
    clip.close()
    ffp.stdin.close()
    if ffp.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


def WE_thud():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(13)
    f = np.linspace(150, 50, n)
    return 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.06) + 0.25 * g.normal(0, 1, n) * np.exp(-t / 0.02)


if __name__ == "__main__":
    main()
