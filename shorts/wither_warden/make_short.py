#!/usr/bin/env python3
"""Render "Wither vs Warden: who wins?": a boss-fight Short cut from a real, unrigged Minecraft fight.

The fight's telemetry (both bosses' health over time) drives every result-dependent part: the
narration, both health bars, hit shakes, the phase-2 alert, speed ramps and the slow-motion finish.
Reuses helpers from ../warden_vs_golems and ../water_elevator.

    SUBS=187 python shorts/wither_warden/make_short.py   # -> shorts/wither_warden/wither_warden_short.mp4
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
FOOT = HERE / "footage"
os.environ.setdefault("SUBS", "187")
SUBS = int(os.environ["SUBS"])
OUT = HERE / "wither_warden_short.mp4"

_spec = importlib.util.spec_from_file_location("warden_vs_golems", HERE.parent / "warden_vs_golems" / "make_short.py")
WG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WG)
WE, N, V, SG = WG.WE, WG.N, WG.V, WG.SG
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
bump, clamp01 = V.bump, V.clamp01
RED, YELLOW, GREEN, WHITE, TEAL, CYAN = N.RED, N.YELLOW, N.GREEN, N.WHITE, WG.TEAL, WG.CYAN
PURPLE = (190, 140, 255)
MAX = {"warden": 500.0, "wither": 300.0}
COL = {"warden": TEAL, "wither": PURPLE}
LAG = 0.1


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append((float(r["clip_time_s"]) - LAG, float(r["warden_health"]), float(r["wither_health"]), r.get("event", "")))
    ev = {}
    for t, _, _, e in rows:
        for name in (e or "").split(";"):
            if name and name not in ev:
                ev[name] = t
    return rows, ev


def at(rows, t):
    prev = rows[0]
    for r in rows:
        if r[0] > t:
            k = clamp01((t - prev[0]) / max(1e-3, r[0] - prev[0]))
            return prev[1] + (r[1] - prev[1]) * k, prev[2] + (r[2] - prev[2]) * k
        prev = r
    return rows[-1][1], rows[-1][2]


def big_hits(rows, thresh=18.0):
    """Clip times where either boss loses a big chunk of health quickly."""
    hits, last = [], -9
    for a, b in zip(rows, rows[1:]):
        drop = (a[1] - b[1]) + (a[2] - b[2]) * 1.6
        if drop >= thresh and b[0] - last > 0.6:
            hits.append(b[0])
            last = b[0]
    return hits


def build_beats(rows, ev):
    if "wither_death" in ev:
        winner, loser, final = "warden", "wither", ev["wither_death"]
    elif "warden_death" in ev:
        winner, loser, final = "wither", "warden", ev["warden_death"]
    else:
        raise SystemExit("no death event in telemetry (timeout?) — handle a draw before rendering")
    wi = 0 if winner == "warden" else 1
    li = 1 - wi
    end_hp = at(rows, final + 0.3)[wi]
    close_hp = at(rows, final - 1.4)[li]
    half = 0.8 + (final - 0.8) * 0.45
    hw, hwi = at(rows, half)
    ahead = "Warden" if hw / MAX["warden"] >= hwi / MAX["wither"] else "Wither"
    p2 = ev.get("wither_phase2")
    beats = [
        dict(name="hook", text="The Wither versus the Warden. Comment who you think wins!", clip="A_lineup", c0=0.0, c1=None),
        dict(name="start", text="Fight! The Warden has five hundred health. The Wither has three hundred, and it can fly.",
             clip="B_fight", c0=0.8, c1=half if not p2 or p2 > half + 2 else max(1.5, p2 - 2.5)),
    ]  # fmt: skip
    if p2 and p2 < final - 5:
        beats.append(dict(name="phase2", text="The Wither drops to half health, and its armor turns on!",
                          clip="B_fight", c0=None, c1=min(final - 4.0, p2 + 3.0), alert=p2))  # fmt: skip
    else:
        beats.append(dict(name="mid", text=f"Halfway through, the {ahead} is ahead.", clip="B_fight", c0=None, c1=final - 4.0))
    beats += [
        dict(name="climax", text=f"The {loser.capitalize()} is down to {int(round(close_hp))} health!", clip="B_fight", c0=None, c1=final - 1.0),
        dict(name="final", text="And...", clip="B_fight", c0=None, c1=final + 0.6, dmin=2.6, final=final),
        dict(name="verdict", text=f"The {winner.capitalize()} wins, with {int(round(end_hp))} health left!", clip="C_aftermath",
             c0=0.3, c1=None, stamp=(f"{winner.upper()} WINS", COL[winner])),
        dict(name="guess", text="Did you guess right? Tell me in the comments.", clip="C_aftermath", c0=None, c1=None),
        dict(name="subs", text=SG.line(SUBS), clip=f"D_castle_{SUBS}", c0=7.0, c1=None),
    ]  # fmt: skip
    return beats, final, winner


def draw_bars(img, hp_warden, hp_wither, flash):
    d = ImageDraw.Draw(img)
    for i, (who, hp) in enumerate((("wither", hp_wither), ("warden", hp_warden))):
        y = 220 + i * 120
        x0, x1 = 90, 990
        V.paste_center(img, V.text_img(who.upper(), 44, COL[who], 6), x0 + 100, y - 48)
        V.paste_center(img, V.text_img(f"{int(round(hp))}/{int(MAX[who])}", 40, WHITE, 6), x1 - 100, y - 48)
        d.rounded_rectangle((x0, y - 20, x1, y + 20), 14, fill=(20, 20, 24), outline=(255, 255, 255), width=4)
        w = (x1 - x0 - 12) * clamp01(hp / MAX[who])
        if w > 2:
            base = (150, 90, 220) if who == "wither" else (40, 180, 190)
            c = tuple(min(255, int(v + 90 * flash)) for v in base)
            d.rounded_rectangle((x0 + 6, y - 14, x0 + 6 + w, y + 14), 10, fill=c)


def main():
    rows, ev = load(FOOT / "B_fight_telemetry.csv")
    beats, final, winner = build_beats(rows, ev)
    N.KEYWORDS = {**WG.KEYWORDS, "wither": PURPLE, "versus": YELLOW, "fly": PURPLE, "three": RED, "armor": PURPLE,
                  "half": YELLOW, "ahead": YELLOW, "wins": YELLOW, "down": RED}  # fmt: skip
    voices = WE.synth([b["text"] for b in beats])
    scenes, plan, t, c_after = [], [], 0.0, None
    for b, v in zip(beats, voices):
        vd = len(v) / SR
        D = max(vd + 0.05 + (0.9 if b["name"] == "subs" else 0.25), b.get("dmin", 0))
        path = FOOT / f"{b['clip']}.mp4"
        clen = WE.clip_len(path)
        c0 = b["c0"] if b["c0"] is not None else (c_after or 0.0)
        if b["c1"] is not None:
            span = max(0.3, b["c1"] - c0)
            D = max(D, span / 3.0)
            speed = span / D
        else:
            speed = max(1.0, (clen - c0) / D) if b["name"] == "hook" else 1.0
            if (clen - c0) / speed < D:
                speed = max(0.6, (clen - c0) / D)
        c_after = c0 + speed * D
        _, starts = V.word_times(b["text"], vd)
        scenes.append(N.Scene(b["name"], b["text"], t, D, starts))
        plan.append((path, c0, speed))
        t += D
    total_t = t
    print(f"duration {total_t:.1f}s  winner: {winner}  events: {ev}")

    def global_t(ct):
        for s, (p, c0, sp), b in zip(scenes, plan, beats):
            if b["clip"] == "B_fight" and c0 <= ct <= c0 + sp * s.D:
                return s.start + (ct - c0) / sp
        return None

    hits_g = [g for g in (global_t(h) for h in big_hits(rows)) if g is not None]
    t_final = global_t(final)
    t_p2 = global_t(ev["wither_phase2"]) if "wither_phase2" in ev else None

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

    add(0.05, N.boom_sfx(), 0.4)
    for h in hits_g:
        add(h, WG.WE_thud(), 0.8)
    add(t_p2, V.sfx("buzz"), 0.8)
    add(t_final, N.boom_sfx(), 0.95)
    S = {s.name: s for s in scenes}
    add(S["start"].start, V.sfx("chime"), 0.7)
    add(S["verdict"].start + 0.05, V.sfx("chime"))
    for name in ("verdict", "subs"):
        add(S[name].start - 0.1, V.sfx("whoosh"), 0.5)
    sub = S["subs"]
    t0d, t1d = sub.start + sub.w["every"], sub.start + sub.w["we're"] + 0.3
    for i in range(0, SUBS, max(1, SUBS // 20)):
        add(t0d + (t1d - t0d) * i / SUBS, V.sfx("pop"), 0.5)
    add(t1d, V.sfx("chime"))
    mix = voice + 0.7 * fx + 0.11 * N.music(n, [(t_final - 0.05, 1.2)] if t_final else [])
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
        recent = [h for h in hits_g if 0 <= t - h < 0.4]
        hitf = math.exp(-(t - recent[-1]) / 0.12) if recent else 0.0
        fin = math.exp(-(t - t_final) / 0.18) if t_final and t >= t_final else 0.0
        k = 1.0 + 0.05 * lt / sc.D + (0.08 * math.exp(-lt / 0.12) if b["name"] in ("hook", "start", "verdict", "subs") else 0)
        k += 0.05 * hitf + 0.12 * fin
        img = WE.zoom(img, k)
        if hitf + fin > 0.05:
            sh = 14 * (hitf + 1.6 * fin)
            img = img.transform(img.size, Image.AFFINE, (1, 0, sh * math.sin(t * 90), 0, 1, sh * math.cos(t * 70)))
        if b["clip"] == "B_fight":
            p, c0, sp = plan[idx]
            hpw, hpx = at(rows, c0 + lt * sp)
            draw_bars(img, hpw, hpx, hitf + fin)
            if sp > 1.35:
                V.paste_center(img, V.pill(f"{sp:.1f}×", 40, (40, 40, 48)), 980, 440)
            elif sp < 0.7:
                V.paste_center(img, V.pill("SLOW-MO", 40, (40, 40, 48)), 960, 440)
            if t_p2 and 0 <= t - t_p2 < 2.0:
                V.paste_center(img, V.pill("PHASE 2: WITHER ARMOR", 58, (110, 50, 170)), W / 2, 540, V.pop_scale(t - t_p2))
        if b["name"] == "hook":
            V.paste_center(img, V.text_img("WITHER", 130, PURPLE, 14), W / 2, 330, V.pop_scale(lt - 0.05))
            V.paste_center(img, V.text_img("VS", 90, YELLOW, 12), W / 2, 460, V.pop_scale(lt - 0.35))
            V.paste_center(img, V.text_img("WARDEN", 130, TEAL, 14), W / 2, 590, V.pop_scale(lt - 0.6))
        if b.get("stamp"):
            V.paste_center(img, V.pill(b["stamp"][0], 84, tuple(int(c * 0.6) for c in b["stamp"][1])), W / 2, 420,
                           V.pop_scale(lt - 0.05, 0.25))  # fmt: skip
        if b["name"] == "subs":
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


if __name__ == "__main__":
    main()
