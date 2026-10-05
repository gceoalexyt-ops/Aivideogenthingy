#!/usr/bin/env python3
"""Render "Why phantoms keep attacking you": a first-person, loopable YouTube Short.

Phantoms spawn when you haven't slept for three nights; sleeping (or dying) resets the counter, cats scare
them off, and they burn in daylight. Reuses the first-person renderer in ../enderman/make_short.py, adding a
night palette, stars and moon, and phantom, cat and bed models.

    python shorts/phantom/make_short.py       # -> shorts/phantom/phantom_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("enderman", HERE.parent / "enderman" / "make_short.py")
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
N, V = E.N, E.V
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
ease, clamp01, lerp = V.ease, V.clamp01, V.lerp
OUT = HERE / "phantom_short.mp4"

LINES = [
    ("hunt", "These will hunt you every single night."),
    ("fault", "And honestly? It's your fault."),
    ("rule", "Phantoms only spawn if you haven't slept for three nights in a row."),
    ("sleep", "Sleep in a bed once, and the counter resets."),
    ("die", "Dying resets it too, but maybe just sleep."),
    ("cats", "Bonus: phantoms are scared of cats."),
    ("sun", "And they burn in daylight."),
    ("loop", "So tonight, go to bed. Otherwise,"),
]
HOLD = {"hunt": 0.35, "fault": 0.15, "rule": 0.35, "sleep": 0.3, "die": 0.2, "cats": 0.3, "sun": 0.25, "loop": 0.0}
E.LINES = LINES

RED, YELLOW, GREEN, WHITE = N.RED, N.YELLOW, N.GREEN, N.WHITE
TEAL, ORANGE = (120, 230, 200), N.ORANGE
N.KEYWORDS = {
    "hunt": RED, "night": TEAL, "fault": RED, "phantoms": TEAL, "slept": YELLOW, "three": YELLOW,
    "nights": YELLOW, "sleep": GREEN, "bed": GREEN, "resets": GREEN, "dying": RED, "scared": YELLOW,
    "cats": ORANGE, "burn": ORANGE, "daylight": YELLOW, "tonight": TEAL, "otherwise": RED,
}  # fmt: skip

# ----------------------------------------------------------------------------------------- textures
rng = np.random.default_rng(31)
pf = E.noise((128, 148, 208), 8)
pf[6:9, 2:6] = (120, 255, 120)
pf[6:9, 10:14] = (120, 255, 120)
pf[6:9, 3:5] = (210, 255, 210)
pf[6:9, 11:13] = (210, 255, 210)
E.TEX["phantom_face"] = E.rgba(pf)
E.TEX["phantom_skin"] = E.rgba(E.noise((128, 148, 208), 10))
E.TEX["phantom_wing"] = E.rgba(E.noise((170, 186, 232), 10))
cf = E.noise((222, 152, 72), 8)
cf[5:8, 3:6] = (90, 200, 90)
cf[5:8, 10:13] = (90, 200, 90)
cf[6:8, 4] = (20, 20, 20)
cf[6:8, 11] = (20, 20, 20)
cf[9:11, 7:9] = (240, 150, 160)
E.TEX["cat_face"] = E.rgba(cf)
cs = E.noise((222, 152, 72), 8)
cs[::4] = (178, 108, 44)
E.TEX["cat_fur"] = E.rgba(cs)
for k in ("bed_foot", "bed_head", "bed_side"):
    E.TEX[k] = N.V.TEX[k][0]

GRASS_DAY = E.GRASS.copy()
PALETTES = {
    "night": dict(top=(6, 8, 26), hor=(30, 38, 84), cloud=(18, 22, 50), grass=0.32, light=0.42),
    "day": dict(top=(84, 146, 250), hor=(198, 224, 255), cloud=(255, 255, 255), grass=1.0, light=1.0),
}
LIGHT = [1.0]
_current = [None]


def set_palette(name):
    if _current[0] == name:
        return
    p = PALETTES[name]
    E.SKY_TOP, E.SKY_HOR, E.CLOUD = (np.array(p[k], float) for k in ("top", "hor", "cloud"))
    E.GRASS = GRASS_DAY * p["grass"] * (np.array((0.8, 0.9, 1.3)) if name == "night" else 1)
    E.GRASS_AVG = E.GRASS.reshape(-1, 3).mean(0)
    LIGHT[0] = p["light"]
    E.tex_tile.cache_clear()
    _current[0] = name


E.shade_of = lambda n: (0.8 + 0.2 * n[1] - 0.13 * abs(n[2])) * LIGHT[0]

STARS = np.random.default_rng(8).normal(0, 1, (260, 3))
STARS[:, 1] = np.abs(STARS[:, 1]) + 0.08
STARS /= np.linalg.norm(STARS, axis=1, keepdims=True)
MOON_DIR = np.array([0.35, 0.62, 0.7]) / np.linalg.norm([0.35, 0.62, 0.7])


def draw_sky_night(img, cam):
    d = ImageDraw.Draw(img)
    for i, s in enumerate(STARS):
        pr = cam.project(cam.pos + s * 500)
        if pr:
            (x, y), _ = pr
            r = 2 + (i % 3 == 0)
            d.rectangle((x - r, y - r, x + r, y + r), fill=(235, 235, 255))
    c = cam.pos + MOON_DIR * 500
    right = np.cross(MOON_DIR, [0, 1, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, MOON_DIR)
    pts = []
    for a, b in ((-1, 1), (1, 1), (1, -1), (-1, -1)):
        pr = cam.project(c + (right * a + up * b) * 26)
        if not pr:
            return
        pts.append(pr[0])
    d.polygon(pts, fill=(236, 236, 214))


# ----------------------------------------------------------------------------------------- models
def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def phantom(pos, yaw, pitch, t, flap_speed=11.0, size=1.6):
    M = E.Ry(yaw) @ E.Rx(-pitch)
    flap = 0.55 * math.sin(t * flap_speed)
    skin, wing = {"*": "phantom_skin"}, {"*": "phantom_wing"}

    def b(lo, hi, look, pivot=(0, 0, 0), R=np.eye(3)):
        sc = lambda v: tuple(c * size for c in v)  # noqa: E731
        return E.box(sc(lo), sc(hi), look, M, pos, sc(pivot), R)

    f = []
    f += b((-0.3, -0.1, -0.45), (0.3, 0.12, 0.45), skin)
    f += b((-0.22, -0.12, 0.45), (0.22, 0.14, 0.78), {"*": "phantom_skin", "+z": "phantom_face"})
    f += b((-0.14, -0.06, -0.95), (0.14, 0.08, -0.45), skin)
    f += b((-0.07, -0.04, -1.35), (0.07, 0.06, -0.95), skin)
    f += b((-1.35, -0.03, -0.35), (-0.3, 0.03, 0.35), wing, (-0.3, 0, 0), Rz(flap))
    f += b((0.3, -0.03, -0.35), (1.35, 0.03, 0.35), wing, (0.3, 0, 0), Rz(-flap))
    return f


def cat(pos, yaw, t):
    M = E.Ry(yaw)
    fur = {"*": "cat_fur"}
    f = []
    f += E.box((-0.15, 0, -0.22), (0.15, 0.42, 0.12), fur, M, pos)
    f += E.box((-0.17, 0.4, -0.08), (0.17, 0.68, 0.24), {"*": "cat_fur", "+z": "cat_face"}, M, pos)
    f += E.box((-0.15, 0.68, 0.02), (-0.06, 0.78, 0.1), fur, M, pos)
    f += E.box((0.06, 0.68, 0.02), (0.15, 0.78, 0.1), fur, M, pos)
    sw = 0.3 * math.sin(t * 3)
    f += E.box((-0.04, 0, -0.62), (0.04, 0.07, -0.2), fur, M, pos, (0, 0, -0.2), E.Ry(sw))
    return f


BED_X, BED_Z = 1.0, 3.2


def bed():
    f = []
    f += E.box((0, 0, 0), (1, 0.5625, 1), {"*": "bed_side", "+y": "bed_foot"}, origin=(BED_X, 0, BED_Z))
    f += E.box((0, 0, 0), (1, 0.5625, 1), {"*": "bed_side", "+y": "bed_head"}, origin=(BED_X + 1, 0, BED_Z))
    return f


CENTER = np.array([0.0, 0.0, 7.0])


def circling(i, tp, spread=1.0, lift=0.0):
    a = tp * 0.85 + i * 2.1
    r = (2.4 + 0.9 * i) * spread
    pos = CENTER + np.array([r * math.cos(a), 4.6 + 0.9 * i + 0.4 * math.sin(tp * 1.7 + i) + lift, r * math.sin(a)])
    return pos, -a, -0.15


# ----------------------------------------------------------------------------------------- drawing
def draw_hand(img, t):
    k = LIGHT[0]
    by = 6 * math.sin(t * 3.2)
    d = ImageDraw.Draw(img)
    for poly, col in (
        ([(700, 1920), (900, 1920), (1010, 1585 + by), (850, 1535 + by)], (214, 162, 122)),
        ([(900, 1920), (1080, 1920), (1080, 1640 + by), (1010, 1585 + by)], (176, 128, 94)),
        ([(850, 1535 + by), (1010, 1585 + by), (1080, 1555 + by), (930, 1505 + by)], (232, 184, 146)),
    ):
        d.polygon(poly, fill=tuple(int(c * (0.35 + 0.65 * k)) for c in col))


def draw_poof(img, cam, center, t0, t, cols, n=30, seed=0):
    dt = t - t0
    if not 0 <= dt < 0.8:
        return
    g = np.random.default_rng(seed)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        p = np.array(center, float) + g.uniform(-0.7, 0.7, 3) + g.uniform(-1, 1, 3) * 1.6 * dt
        pr = cam.project(p)
        if not pr:
            continue
        (x, y), z = pr
        s = max(3, cam.f * 0.07 / z) * (1 - dt / 0.8)
        d.rectangle((x - s, y - s, x + s, y + s), fill=cols[g.integers(len(cols))])


def draw_fire_on(img, cam, center, t, size=1.2):
    pr = cam.project(center)
    if not pr:
        return
    (x, y), z = pr
    s = max(8, int(cam.f * 0.55 * size / z))
    for i, (ox, oy) in enumerate(((-0.6, 0.1), (0.0, -0.2), (0.6, 0.1), (-0.3, 0.3), (0.3, 0.35))):
        spr = N.fire_sprite(int(t * 12) + i * 3, s)
        img.paste(spr, (round(x + ox * s - s / 2), round(y + oy * s - s * 0.8)), spr)


def counter_pill(n, col):
    return V.pill(f"NIGHTS WITHOUT SLEEP: {n}", 54, col)


def draw_death(img, lt):
    k = ease(lt / 0.25)
    img.paste(Image.blend(img, Image.new("RGB", (W, H), (150, 0, 0)), 0.55 * k))
    V.paste_center(img, V.text_img("You Died!", 128, WHITE, 0), W / 2, 560, V.pop_scale(lt, 0.25))
    V.paste_center(img, V.text_img("Player was slain by Phantom", 50, (235, 235, 235), 0), W / 2, 690, 1, k)
    d = ImageDraw.Draw(img)
    for i, label in enumerate(("Respawn", "Title Screen")):
        y = 800 + i * 120
        d.rectangle((240, y, 840, y + 90), fill=(110, 110, 110), outline=(30, 30, 30), width=5)
        V.paste_center(img, V.text_img(label, 44, WHITE, 0), W / 2, y + 47)


# ----------------------------------------------------------------------------------------- audio
def phantom_cry():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(7)
    f = 520 - 260 * t / 0.6 + 40 * np.sin(2 * np.pi * 9 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    saw = 2 * (ph / (2 * np.pi) % 1) - 1
    rasp = np.convolve(g.normal(0, 1, n), np.ones(3) / 3, "same")
    env = np.minimum(1, t / 0.04) * np.exp(-t / 0.3)
    return 0.22 * (0.7 * saw + 0.4 * rasp) * env


def meow():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 620 + 380 * np.sin(np.pi * t / 0.5) * (1 + 0.03 * np.sin(2 * np.pi * 7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)
    return 0.16 * s * np.sin(np.pi * t / 0.5) ** 0.6


def crackle(dur):
    n = int(dur * SR)
    g = np.random.default_rng(9)
    out = np.zeros(n)
    for i in g.integers(0, n - 400, int(dur * 40)):
        out[i : i + 300] += g.normal(0, 1, 300) * np.exp(-np.arange(300) / 50) * g.uniform(0.2, 1)
    return 0.12 * out


# ----------------------------------------------------------------------------------------- main
CAM0 = ((0.0, 1.62, 0.0), (0.0, 4.9, 7.0))


def main():
    voices = E.synth()
    scenes, t = [], 0.0
    for (name, text), v in zip(LINES, voices):
        vd = len(v) / SR
        _, starts = V.word_times(text, vd)
        dur = vd + 0.05 + HOLD[name]
        scenes.append(N.Scene(name, text, t, dur, starts))
        t += dur
    total = t
    S = {s.name: s for s in scenes}
    print(f"duration {total:.1f}s")

    t_hit = S["hunt"].start + S["hunt"].D - 0.12
    r = S["rule"]
    t_counts = [r.start + r.w[k] for k in ("haven't", "slept", "three")]
    t_spawn = r.start + r.w["row"]
    sl = S["sleep"]
    t_reset = sl.start + sl.w["resets"]
    t_scared = S["cats"].start + S["cats"].w["scared"]

    # ---- audio
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for s, v in zip(scenes, voices):
        i0 = int(s.start * SR)
        voice[i0 : i0 + len(v)] += v / (np.abs(v).max() + 1e-6) * 0.92
    fx = np.zeros(n)

    def add(t0, s, g=1.0):
        i0 = int(max(0, t0) * SR)
        if i0 < n:
            fx[i0 : i0 + len(s)] += g * s[: n - i0]

    add(0.15, phantom_cry(), 0.8)
    add(t_hit - 0.5, phantom_cry())
    add(t_hit - 0.35, V.sfx("whoosh"))
    add(t_hit, N.boom_sfx(), 0.35)
    add(S["fault"].start + S["fault"].w["fault"], V.sfx("buzz"))
    for tc in t_counts:
        add(tc, V.sfx("pop"))
    add(t_spawn, phantom_cry())
    add(sl.start + sl.D * 0.4, V.sfx("whoosh"), 0.5)
    add(t_reset, V.sfx("chime"))
    add(S["die"].start, N.wah_sfx())
    add(S["cats"].start + S["cats"].w["cats"] - 0.1, meow())
    add(t_scared + 0.2, V.sfx("whoosh"), 0.8)
    add(S["sun"].start, crackle(S["sun"].D))
    add(S["sun"].start + S["sun"].D - 0.35, V.sfx("pop"))
    for name in ("fault", "rule", "die", "cats", "sun", "loop"):
        add(S[name].start - 0.1, V.sfx("whoosh"), 0.5)
    ducks = [(t_hit, 0.4), (S["sleep"].start + S["sleep"].D * 0.4, 0.45)]
    mix = voice + 0.7 * fx + 0.1 * N.music(n, ducks)
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
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(total * FPS)
    for f in range(frames):
        t = f / FPS
        sc = max((s for s in scenes if s.start <= t), key=lambda s: s.start)
        lt, name = t - sc.start, sc.name
        palette, fp, faces, after = "night", True, list(E.TREE_FACES) + bed(), []
        flash, flash_col, pills = 0.0, (255, 255, 255), []
        cam = E.Cam.look(*CAM0)

        if name in ("hunt", "loop"):
            tp = lt if name == "hunt" else lt - sc.D
            for i in range(3):
                pos, yaw, pitch = circling(i, tp)
                if name == "hunt" and i == 0 and t > t_hit - 0.7:
                    k = ease((t - (t_hit - 0.7)) / 0.7)
                    target = cam.pos + cam.fwd * 0.9
                    pos = pos + (target - pos) * k
                    d = target - pos
                    yaw, pitch = math.atan2(d[0], d[2]), math.atan2(d[1], math.hypot(d[0], d[2]))
                faces += phantom(pos, yaw, pitch, t)
            if name == "hunt" and t >= t_hit:
                flash, flash_col = 0.8 * math.exp(-(t - t_hit) / 0.12), (180, 0, 0)
                sh = 0.06 * math.exp(-(t - t_hit) / 0.2)
                cam = E.Cam.look((sh * math.sin(t * 90), 1.62, 0), (sh * 40 * math.sin(t * 70), 4.9, 7.0))
        elif name == "fault":
            k = ease(lt / 0.45)
            cam = E.Cam.look((0, 1.62, 0), np.array(CAM0[1]) * (1 - k) + np.array([BED_X + 1, 0.3, BED_Z + 0.5]) * k)
            for i in range(3):
                faces += phantom(*circling(i, lt + 6), t)
            pills.append(("YOUR FAULT", RED, (W / 2, 520), lt - sc.w["fault"], 80))
            pills.append(("UNUSED BED", (90, 90, 100), "bed", lt - 0.5, 44))
        elif name == "rule":
            cam = E.Cam.look((0, 1.62, 0), (0, 4.6, 7.0))
            got = sum(1 for tc in t_counts if t >= tc)
            if got:
                col = RED if got == 3 else (60, 70, 120)
                pills.append((f"NIGHTS WITHOUT SLEEP: {got}", col, (W / 2, 470), t - t_counts[got - 1], 54))
            if t >= t_spawn:
                for i in range(3):
                    pos, yaw, pitch = circling(i, t - t_spawn)
                    k = ease((t - t_spawn) / 0.4)
                    pos = pos + np.array([0, 12 * (1 - k), 0])
                    faces += phantom(pos, yaw, pitch, t)
                    after.append(("poof", pos, t_spawn + 0.25 + 0.1 * i, [(60, 60, 70), (110, 110, 130)]))
                pills.append(("PHANTOMS SPAWN", (40, 120, 110), (W / 2, 580), t - t_spawn, 54))
        elif name == "sleep":
            a, b = sc.D * 0.38, sc.D * 0.6
            if lt < a:
                k = ease(lt / a)
                cam = E.Cam.look((lerp(0, BED_X + 1, k * 0.7), 1.62, lerp(0, BED_Z - 1.2, k)), (BED_X + 1, 0.2, BED_Z + 0.5))
            elif lt < b:
                cam = E.Cam.look((BED_X + 0.7, 1.62, BED_Z - 1.2), (BED_X + 1, 0.2, BED_Z + 0.5))
                flash, flash_col = clamp01((lt - a) / 0.2) * 0.97, (6, 6, 14)
            else:
                palette = "day"
                cam = E.Cam.look((BED_X + 0.7, 1.62, BED_Z - 1.2), (BED_X + 1, 1.2, BED_Z + 6))
                flash, flash_col = 0.97 * (1 - clamp01((lt - b) / 0.35)), (6, 6, 14)
            if t >= t_reset:
                pills.append(("NIGHTS WITHOUT SLEEP: 0  ✓", (30, 140, 60), (W / 2, 470), t - t_reset, 54))
            elif lt >= b:
                pills.append(("NIGHTS WITHOUT SLEEP: 3", RED, (W / 2, 470), 9, 54))
        elif name == "die":
            for i in range(3):
                faces += phantom(*circling(i, lt + 3), t)
            after.append(("death", lt))
            pills.append(("(just sleep)", (30, 140, 60), (W / 2, 1140), lt - sc.w["maybe"], 56))
        elif name == "cats":
            cam = E.Cam.look((0, 1.62, 0), (-0.1, 1.9, 5.0))
            faces += cat((-0.45, 0, 2.3), math.pi - 0.25, t)
            flee = clamp01((t - t_scared) / 1.2)
            for i in range(3):
                pos, yaw, pitch = circling(i, lt + 2, spread=1 + 3 * flee * flee, lift=6 * flee * flee)
                faces += phantom(pos, yaw, pitch, t)
            pills.append(("CATS SCARE PHANTOMS", (190, 110, 30), (W / 2, 470), t - t_scared, 54))
        elif name == "sun":
            palette = "day"
            cam = E.Cam.look((0, 1.62, 0), (0, 4.0, 7.0))
            pos = np.array([1.6 * math.cos(lt * 1.6), 4.3 + 0.2 * math.sin(lt * 3), 7.0 + 1.6 * math.sin(lt * 1.6)])
            if lt < sc.D - 0.35:
                faces += phantom(pos, -lt * 1.6 - math.pi / 2, -0.1, t)
                after.append(("fire", pos))
            after.append(("poof", pos, sc.start + sc.D - 0.35, [(70, 70, 70), (130, 130, 130), (200, 200, 200)]))
            pills.append(("BURNS IN DAYLIGHT", (200, 90, 20), (W / 2, 470), lt - 0.3, 54))

        set_palette(palette)
        img = E.render_env(cam, t)
        if palette == "night":
            draw_sky_night(img, cam)
        E.draw_faces(img, cam, faces)
        for a in after:
            if a[0] == "poof":
                draw_poof(img, cam, a[1], a[2], t, a[3], seed=int(a[2] * 100))
            elif a[0] == "fire":
                draw_fire_on(img, cam, a[1], t)
            elif a[0] == "death":
                draw_death(img, a[1])
        for text, col, at, age, size in pills:
            if at == "bed":
                pr = cam.project((BED_X + 1, 1.3, BED_Z + 0.5))
                if not pr:
                    continue
                at = pr[0]
            V.paste_center(img, V.pill(text, size, col), at[0], at[1], V.pop_scale(age))
        if fp and name != "die":
            E.draw_crosshair(img)
            draw_hand(img, t)
        N.draw_caption(img, sc.words, sc.starts, lt, y=1300)
        if name in ("fault", "rule", "die", "cats", "sun", "loop") and lt < 0.1:
            flash = max(flash, 0.25 * (1 - lt / 0.1))
            flash_col = (255, 255, 255)
        if flash > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), flash_col), min(0.97, flash))
        ff.stdin.write(img.tobytes())
        if f % 90 == 0:
            print(f"frame {f}/{frames}", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
