#!/usr/bin/env python3
"""Render "Never look an Enderman in the eyes": a first-person, loopable YouTube Short.

A small software 3D renderer draws a first-person voxel world: a ray-cast ground and dusk sky, textured
blocks and box-model mobs drawn back to front with perspective-correct textures. Narration (Kokoro), captions,
music and sound effects reuse the helpers in ../infinite_water and ../nether_bed.

    python shorts/enderman/make_short.py       # -> shorts/enderman/enderman_short.mp4
"""

from __future__ import annotations

import importlib.util
import math
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N = _load("nether", HERE.parent / "nether_bed" / "make_short.py")
V = N.V
W, H, FPS, SR = V.W, V.H, V.FPS, V.SR
ease, ramp, clamp01, lerp = V.ease, V.ramp, V.clamp01, V.lerp
OUT = HERE / "enderman_short.mp4"

LINES = [
    ("never", "Never look an Enderman in the eyes."),
    ("unless", "Unless you're wearing this."),
    ("stare", "With a carved pumpkin on your head, you can stare right at it, and it won't get angry."),
    ("catch", "The catch? You can barely see."),
    ("tricks", "Two more tricks."),
    ("roof", "Endermen are three blocks tall, so hide under a two block high roof."),
    ("water", "And water hurts them, so stand in it, and they teleport away."),
    ("loop", "So whatever you do,"),
]
HOLD = {"never": 0.55, "unless": 0.35, "stare": 0.1, "catch": 0.15, "tricks": 0.1, "roof": 0.3, "water": 0.35, "loop": 0.0}

RED, ORANGE, YELLOW, GREEN, WHITE = N.RED, N.ORANGE, N.YELLOW, N.GREEN, N.WHITE
PURPLE, BLUE = (205, 130, 255), (110, 180, 255)
N.KEYWORDS = {
    "never": RED, "eyes": PURPLE, "enderman": PURPLE, "endermen": PURPLE, "this": ORANGE, "carved": ORANGE,
    "pumpkin": ORANGE, "stare": YELLOW, "angry": RED, "catch": YELLOW, "barely": RED, "two": YELLOW,
    "tricks": YELLOW, "three": YELLOW, "tall": YELLOW, "roof": GREEN, "water": BLUE, "hurts": RED,
    "teleport": PURPLE, "whatever": YELLOW,
}  # fmt: skip

# ----------------------------------------------------------------------------------------- textures
rng = np.random.default_rng(21)
r16, c16 = np.mgrid[0:16, 0:16]


def noise(base, var):
    return np.array(base, float)[None, None, :] + rng.integers(-var, var + 1, (16, 16, 1))


def rgba(arr, alpha=255):
    out = np.zeros((16, 16, 4), np.uint8)
    out[..., :3] = np.clip(arr, 0, 255)
    out[..., 3] = alpha
    return out


TEX = {}
log = noise((104, 80, 50), 8)
log[:, c16[0] % 4 == 1] *= 0.75
TEX["log"] = rgba(log)
lt = noise((160, 128, 80), 8)
lt[np.abs(np.hypot(r16 - 7.5, c16 - 7.5) - 4) < 0.7] = (120, 92, 56)
TEX["log_top"] = rgba(lt)
leaves = noise((58, 118, 44), 14)
leaves[rng.random((16, 16)) < 0.2] = (34, 76, 28)
TEX["leaves"] = rgba(leaves)
TEX["planks"] = N.V.TEX["planks"][0]
pk = noise((222, 122, 22), 10)
pk[:, (c16[0] % 5) == 0] *= 0.78
TEX["pumpkin"] = rgba(pk)
front = pk.copy()
for poly in (((3, 4), (6, 4), (6, 7)), ((10, 4), (13, 4), (10, 7))):
    pass
carve = np.zeros((16, 16), bool)
carve[4:7, 3:7] = True
carve[4:7, 9:13] = True
carve[10:12, 3:13] = True
carve[12, 4:6] = carve[12, 7:9] = carve[12, 10:12] = True
carve[9, 5] = carve[9, 10] = True
front[carve] = (52, 26, 10)
TEX["pumpkin_face"] = rgba(front)
ptop = pk.copy()
ptop[6:10, 6:10] = (96, 82, 34)
TEX["pumpkin_top"] = rgba(ptop)
ef = noise((24, 22, 30), 4)
ef[7:9, 1:6] = (204, 0, 250)
ef[7:9, 10:15] = (204, 0, 250)
ef[7:9, 2:4] = (232, 150, 255)
ef[7:9, 12:14] = (232, 150, 255)
TEX["ender_face"] = rgba(ef)
efa = ef.copy()
efa[7:9, 1:6] = (255, 80, 255)
efa[7:9, 10:15] = (255, 80, 255)
efa[11:14, 4:12] = (6, 4, 8)
TEX["ender_face_angry"] = rgba(efa)
face = noise((214, 162, 122), 5)
face[:4] = (78, 52, 34)
face[4:6, [0, 15]] = (78, 52, 34)
face[8:10, 3:5] = (250, 250, 250)
face[8:10, 11:13] = (250, 250, 250)
face[8:10, 4] = (50, 70, 160)
face[8:10, 11] = (50, 70, 160)
face[12, 6:10] = (150, 90, 70)
TEX["player_face"] = rgba(face)

GRASS = V.TEX["grass_top"][0][..., :3].astype(float) * np.array((1.0, 0.93, 0.82)) * 0.95
GRASS_AVG = GRASS.reshape(-1, 3).mean(0)
WATER = [f[..., :3].astype(float) * 0.95 for f in V.TEX["water"]]
SKY_TOP, SKY_HOR, CLOUD = np.array((64, 78, 168.0)), np.array((252, 170, 120.0)), np.array((255, 214, 190.0))


@lru_cache(maxsize=1024)
def tex_tile(name, shade_q, fog_q):
    arr = TEX[name].astype(float)
    arr[..., :3] *= shade_q / 20
    k = fog_q / 20
    arr[..., :3] = arr[..., :3] * (1 - k) + SKY_HOR * k
    return Image.fromarray(np.tile(np.clip(arr, 0, 255).astype(np.uint8), (3, 3, 1)), "RGBA")


# ----------------------------------------------------------------------------------------- camera
class Cam:
    def __init__(self, pos, yaw, pitch, fov=78):
        self.pos = np.array(pos, float)
        self.f = (H / 2) / math.tan(math.radians(fov) / 2)
        cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        self.fwd = np.array([sy * cp, sp, cy * cp])
        self.right = np.array([cy, 0.0, -sy])
        self.up = np.cross(self.fwd, self.right)

    @classmethod
    def look(cls, pos, target, fov=78):
        d = np.array(target, float) - np.array(pos, float)
        return cls(pos, math.atan2(d[0], d[2]), math.atan2(d[1], math.hypot(d[0], d[2])), fov)

    def to_cam(self, pts):
        d = pts - self.pos
        return np.stack([d @ self.right, d @ self.up, d @ self.fwd], axis=-1)

    def project(self, p):
        c = self.to_cam(np.asarray(p, float)[None])[0]
        if c[2] < 0.05:
            return None
        return (W / 2 + self.f * c[0] / c[2], H / 2 - self.f * c[1] / c[2]), c[2]


# ----------------------------------------------------------------------------------------- environment
RW, RH = W // 2, H // 2
PX, PY = np.meshgrid(np.arange(RW) + 0.5, np.arange(RH) + 0.5)
WMAP_OFF = 64
WMAP = np.zeros((128, 128), bool)
POOL = [(x, z) for x in range(42, 46) for z in range(-1, 3)]
for x, z in POOL:
    WMAP[x + WMAP_OFF, z + WMAP_OFF] = True


def render_env(cam, t):
    """Ray-cast the ground plane (y = 0) and the sky at half resolution."""
    f2 = cam.f / 2
    dxc = (PX - RW / 2) / f2
    dyc = -(PY - RH / 2) / f2
    d = dxc[..., None] * cam.right + dyc[..., None] * cam.up + cam.fwd
    dn = np.linalg.norm(d, axis=-1)
    dy = d[..., 1]
    k = np.clip(dy / dn * 2.4, 0, 1)[..., None]
    out = SKY_HOR * (1 - k) + SKY_TOP * k
    # clouds
    sky = dy > 0.02
    tc = np.where(sky, (110 - cam.pos[1]) / np.where(sky, dy, 1), 0)
    cx = np.floor((cam.pos[0] + tc * d[..., 0] + t * 3) / 18)
    cz = np.floor((cam.pos[2] + tc * d[..., 2]) / 18)
    h = np.modf(np.sin(cx * 12.9898 + cz * 78.233) * 43758.5453)[0]
    ca = (sky & (np.abs(h) < 0.12)) * np.clip(1 - tc * dn / 1400, 0, 1) * 0.8
    out = out * (1 - ca[..., None]) + CLOUD * ca[..., None]
    # ground
    g = dy < -1e-4
    th = np.where(g, -cam.pos[1] / np.where(g, dy, -1), 0)
    hx = cam.pos[0] + th * d[..., 0]
    hz = cam.pos[2] + th * d[..., 2]
    dist = th * dn
    tx = np.clip((np.mod(hx, 1) * 16).astype(int), 0, 15)
    tz = np.clip((np.mod(hz, 1) * 16).astype(int), 0, 15)
    col = GRASS[tz, tx]
    cell_x = np.clip(np.floor(hx).astype(int) + WMAP_OFF, 0, 127)
    cell_z = np.clip(np.floor(hz).astype(int) + WMAP_OFF, 0, 127)
    wm = g & WMAP[cell_x, cell_z] & (np.abs(hx) < 60) & (np.abs(hz) < 60)
    if wm.any():
        col[wm] = WATER[int(t * 6) % 8][tz[wm], tx[wm]]
    seam = (np.mod(hx, 1) < 0.035) | (np.mod(hz, 1) < 0.035)
    col = np.where(seam[..., None], col * 0.88, col)
    a = np.clip((dist - 10) / 28, 0, 1)[..., None]
    col = col * (1 - a) + GRASS_AVG * a
    b = np.clip((dist - 30) / 90, 0, 1)[..., None]
    col = col * (1 - b) + SKY_HOR * 0.85 * b
    out = np.where(g[..., None], col, out)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.BILINEAR)


# ----------------------------------------------------------------------------------------- geometry
FACE_T = {
    "+x": ([(1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0)], (1, 0, 0)),
    "-x": ([(0, 1, 1), (0, 1, 0), (0, 0, 0), (0, 0, 1)], (-1, 0, 0)),
    "+z": ([(1, 1, 1), (0, 1, 1), (0, 0, 1), (1, 0, 1)], (0, 0, 1)),
    "-z": ([(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)], (0, 0, -1)),
    "+y": ([(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)], (0, 1, 0)),
    "-y": ([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], (0, -1, 0)),
}
UV4 = np.array([(0, 0), (16, 0), (16, 16), (0, 16)], float)
NEIGH = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+z": (0, 0, 1), "-z": (0, 0, -1), "+y": (0, 1, 0), "-y": (0, -1, 0)}


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def box(lo, hi, look, M=np.eye(3), origin=(0, 0, 0), pivot=(0, 0, 0), R=np.eye(3), skip=(), outline=False, clip_y=None):
    """Faces of a box. look: face -> texture name or RGB tuple (or a default under key '*')."""
    lo, hi = np.array(lo, float), np.array(hi, float)
    if clip_y is not None:
        lo[1] = max(lo[1], clip_y - origin[1])
        if lo[1] >= hi[1]:
            return []
    pivot, origin = np.array(pivot, float), np.array(origin, float)
    faces = []
    for name, (corners, n) in FACE_T.items():
        if name in skip:
            continue
        v = lo + (hi - lo) * np.array(corners, float)
        v = (R @ (v - pivot).T).T + pivot
        v = (M @ v.T).T + origin
        faces.append((v, M @ R @ np.array(n, float), look.get(name, look.get("*")), outline))
    return faces


def blocks_faces(blocks):
    """Axis-aligned unit blocks {(x,y,z): {face: tex}} with hidden faces culled."""
    faces = []
    for (x, y, z), look in blocks.items():
        skip = [f for f, (dx, dy, dz) in NEIGH.items() if (x + dx, y + dy, z + dz) in blocks]
        faces += box((0, 0, 0), (1, 1, 1), look, origin=(x, y, z), skip=skip, outline=True)
    return faces


def tree(x, z):
    b = {}
    for y in range(5):
        b[(x, y, z)] = {"*": "log", "+y": "log_top", "-y": "log_top"}
    for y, rad in ((3, 2), (4, 2), (5, 1), (6, 0)):
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                if rad == 2 and abs(dx) == 2 and abs(dz) == 2:
                    continue
                if (x + dx, y, z + dz) not in b:
                    b[(x + dx, y, z + dz)] = {"*": "leaves"}
    return b


TREE_SPOTS = [(-7, 15), (8, 17), (-13, 7), (13, 6), (-3, 26), (16, 25), (27, 15), (34, 20), (49, 13), (56, 22), (38, 30)]
TREES = {}
for spot in TREE_SPOTS:
    TREES.update(tree(*spot))
TREE_FACES = blocks_faces(TREES)

X6, X7 = 20, 40
ROOF = {}
for x in range(X6 + 2, X6 + 5):
    for z in (0, 1):
        ROOF[(x, 2, z)] = {"*": "planks"}
for x in (X6 + 2, X6 + 4):
    for y in (0, 1):
        ROOF[(x, y, 1)] = {"*": "planks"}
ROOF_FACES = blocks_faces(ROOF)

ENDER_DARK, ENDER_MID = (22, 20, 28), (30, 27, 38)


def enderman(pos, yaw, t, walk=0.0, anger=0.0, clip_y=None):
    """Box-model Enderman, 2.9 blocks tall, facing +z at yaw 0."""
    pos = np.array(pos, float)
    if anger > 0:
        pos = pos + np.array([math.sin(t * 61) * 0.04, 0, math.cos(t * 47) * 0.04]) * anger
    M = Ry(yaw)
    swing = 0.38 * walk * math.sin(t * 9)
    face = "ender_face_angry" if anger > 0.5 else "ender_face"
    head_lift = 0.08 * anger
    parts = [
        ((-0.19, 0, -0.06), (-0.06, 1.55, 0.06), (0, 1.55, 0), Rx(swing), ENDER_DARK),
        ((0.06, 0, -0.06), (0.19, 1.55, 0.06), (0, 1.55, 0), Rx(-swing), ENDER_DARK),
        ((-0.25, 1.55, -0.13), (0.25, 2.3, 0.13), (0, 0, 0), np.eye(3), ENDER_MID),
        ((-0.38, 0.8, -0.06), (-0.25, 2.3, 0.06), (0, 2.25, 0), Rx(-swing * 0.8), ENDER_DARK),
        ((0.25, 0.8, -0.06), (0.38, 2.3, 0.06), (0, 2.25, 0), Rx(swing * 0.8), ENDER_DARK),
    ]
    faces = []
    for lo, hi, piv, R, col in parts:
        faces += box(lo, hi, {"*": col}, M, pos, piv, R, clip_y=clip_y)
    faces += box((-0.25, 2.3 + head_lift, -0.25), (0.25, 2.8 + head_lift, 0.25), {"*": ENDER_MID, "+z": face}, M, pos)
    return faces


SHIRT, PANTS, SKIN, HAIR = (64, 150, 104), (58, 66, 128), (214, 162, 122), (78, 52, 34)


def player(pos, yaw, clip_y=None):
    M = Ry(yaw)
    parts = [
        ((-0.25, 0, -0.125), (0, 0.75, 0.125), PANTS),
        ((0, 0, -0.125), (0.25, 0.75, 0.125), PANTS),
        ((-0.25, 0.75, -0.125), (0.25, 1.5, 0.125), SHIRT),
        ((-0.5, 0.75, -0.125), (-0.25, 1.5, 0.125), SKIN),
        ((0.25, 0.75, -0.125), (0.5, 1.5, 0.125), SKIN),
    ]
    faces = []
    for lo, hi, col in parts:
        faces += box(lo, hi, {"*": col}, M, pos, clip_y=clip_y)
    faces += box((-0.25, 1.5, -0.25), (0.25, 2.0, 0.25), {"*": SKIN, "+y": HAIR, "+z": "player_face"}, M, pos)
    return faces


def pumpkin(center, yaw, tilt=0.0, size=1.0):
    s = size / 2
    return box((-s, -s, -s), (s, s, s), {"*": "pumpkin", "+y": "pumpkin_top", "+z": "pumpkin_face"},
               Ry(yaw) @ Rx(tilt), center)  # fmt: skip


# ----------------------------------------------------------------------------------------- face drawing
def clip_near(cs, uv, near=0.06):
    out = []
    n = len(cs)
    for i in range(n):
        a, b = cs[i], cs[(i + 1) % n]
        ua, ub = uv[i], uv[(i + 1) % n]
        ina, inb = a[2] >= near, b[2] >= near
        if ina:
            out.append((a, ua))
        if ina != inb:
            k = (near - a[2]) / (b[2] - a[2])
            out.append((a + (b - a) * k, ua + (ub - ua) * k))
    return out


def homography(src, dst):
    A, bb = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        bb.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        bb.append(v)
    return np.linalg.solve(np.array(A, float), np.array(bb, float))


def shade_of(n):
    return 0.8 + 0.2 * n[1] - 0.13 * abs(n[2])


def draw_faces(img, cam, faces):
    items = []
    for v, n, look, outline in faces:
        c = v.mean(0)
        to_cam = cam.pos - c
        if np.dot(n, to_cam) <= 1e-6:
            continue
        cs = cam.to_cam(v)
        if (cs[:, 2] < 0.06).all():
            continue
        poly = clip_near(cs, UV4)
        if len(poly) < 3:
            continue
        pts = [(W / 2 + cam.f * p[0] / p[2], H / 2 - cam.f * p[1] / p[2]) for p, _ in poly]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if max(xs) < 0 or min(xs) > W or max(ys) < 0 or min(ys) > H:
            continue
        items.append((float(np.linalg.norm(to_cam)), pts, [u for _, u in poly], look, n, outline))
    items.sort(key=lambda it: -it[0])
    d = ImageDraw.Draw(img)
    for dist, pts, uvs, look, n, outline in items:
        sh = shade_of(n)
        fog = clamp01((dist - 22) / 70) * 0.85
        if isinstance(look, tuple):
            col = tuple(int(lerp(c * sh, SKY_HOR[i], fog)) for i, c in enumerate(look))
            d.polygon(pts, fill=col)
            continue
        x0, y0 = max(0, math.floor(min(p[0] for p in pts))), max(0, math.floor(min(p[1] for p in pts)))
        x1, y1 = min(W, math.ceil(max(p[0] for p in pts)) + 1), min(H, math.ceil(max(p[1] for p in pts)) + 1)
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue
        sp, su = pts, uvs
        if len(sp) == 3:
            sp = sp + [(sp[0][0] + sp[2][0] - sp[1][0], sp[0][1] + sp[2][1] - sp[1][1])]
            su = list(su) + [su[0] + su[2] - su[1]]
        idx = [0, 1, 2, 3] if len(sp) == 4 else [0, len(sp) // 4 + 1, len(sp) // 2 + 1, len(sp) - 1]
        try:
            co = homography([(su[i][0] + 16, su[i][1] + 16) for i in idx], [(sp[i][0] - x0, sp[i][1] - y0) for i in idx])
        except np.linalg.LinAlgError:
            continue
        tile = tex_tile(look, round(sh * 20), round(fog * 20))
        patch = tile.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, tuple(co), Image.NEAREST)
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mask).polygon([(p[0] - x0, p[1] - y0) for p in pts], fill=255)
        mask = ImageChops.multiply(mask, patch.getchannel("A"))
        img.paste(patch, (x0, y0), mask)
        if outline and dist < 18:
            d.line(pts + [pts[0]], fill=(30, 22, 18), width=2)


# ----------------------------------------------------------------------------------------- overlays
def make_pumpkin_overlay():
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    ang = np.arctan2(yy - 900, xx - 540)
    rr = 1 + 0.05 * np.sin(ang * 13) + 0.03 * np.sin(ang * 31)
    r = ((np.abs(xx - 540) / 470) ** 4 + (np.abs(yy - 900) / 640) ** 4) ** 0.25
    alpha = np.clip((r - rr * 0.93) / 0.07, 0, 1)
    col = np.array((128, 62, 14.0))[None, None, :] * (0.72 + 0.28 * np.sin(xx / 55)[..., None]) * (0.6 + 0.4 * alpha[..., None])
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = np.clip(col, 0, 255)
    out[..., 3] = (alpha * 245).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


PUMPKIN_OV = make_pumpkin_overlay()


def draw_hand(img, t):
    by = 6 * math.sin(t * 3.2)
    d = ImageDraw.Draw(img)
    front = [(700, 1920), (900, 1920), (1010, 1585 + by), (850, 1535 + by)]
    side = [(900, 1920), (1080, 1920), (1080, 1640 + by), (1010, 1585 + by)]
    top = [(850, 1535 + by), (1010, 1585 + by), (1080, 1555 + by), (930, 1505 + by)]
    d.polygon(front, fill=(214, 162, 122))
    d.polygon(side, fill=(176, 128, 94))
    d.polygon(top, fill=(232, 184, 146))


def draw_crosshair(img):
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    for w, col in ((10, (0, 0, 0)), (4, (255, 255, 255))):
        d.line((cx - 22, cy, cx + 22, cy), fill=col, width=w)
        d.line((cx, cy - 22, cx, cy + 22), fill=col, width=w)


def draw_particles(img, cam, center, t0, t, n=40, seed=0):
    dt = t - t0
    if not 0 <= dt < 0.8:
        return
    rng_p = np.random.default_rng(seed)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        off = rng_p.uniform(-0.6, 0.6, 3) * np.array([1, 2.4, 1]) + np.array([0, 1.4, 0])
        vel = rng_p.uniform(-1, 1, 3) * 1.5
        p = np.array(center, float) + off + vel * dt
        pr = cam.project(p)
        if pr is None:
            continue
        (sx, sy), z = pr
        s = max(3, cam.f * 0.06 / z) * (1 - dt / 0.8)
        col = (200, 60, 255) if rng_p.random() < 0.6 else (120, 20, 170)
        d.rectangle((sx - s, sy - s, sx + s, sy + s), fill=col)


def draw_ruler(img, cam, base, height, label, col, appear):
    k = ease(appear / 0.35)
    if k <= 0:
        return
    a = cam.project(base)
    b = cam.project(np.array(base, float) + np.array([0, height * k, 0]))
    if not a or not b:
        return
    (ax, ay), _ = a
    (bx, by), _ = b
    d = ImageDraw.Draw(img)
    for w, c in ((14, (0, 0, 0)), (7, col)):
        d.line((ax, ay, bx, by), fill=c, width=w)
        d.line((bx - 22, by, bx + 22, by), fill=c, width=w)
        d.line((ax - 22, ay, ax + 22, ay), fill=c, width=w)
    for i in range(1, int(height * k) + 1):
        tb = cam.project(np.array(base, float) + np.array([0, i, 0]))
        if tb and i < height:
            (tx, ty), _ = tb
            d.line((tx - 14, ty, tx + 14, ty), fill=(0, 0, 0), width=8)
            d.line((tx - 14, ty, tx + 14, ty), fill=col, width=4)
    V.paste_center(img, V.pill(label, 46, tuple(int(c * 0.7) for c in col)), bx, by - 56, V.pop_scale(appear - 0.2))


# ----------------------------------------------------------------------------------------- audio
def screech():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    g = np.random.default_rng(6)
    f = 1500 + 420 * np.sin(2 * np.pi * 23 * t) + 300 * np.sin(2 * np.pi * 7 * t)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    hp = np.diff(g.normal(0, 1, n + 1))
    env = np.minimum(1, t / 0.03) * np.exp(-t / 0.5)
    return 0.32 * (0.6 * tone + 0.35 * hp) * env


def vwoop():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = (900 * np.exp(-t / 0.12) + 170) * (1 + 0.08 * np.sin(2 * np.pi * 18 * t))
    return 0.4 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)


# ----------------------------------------------------------------------------------------- main
ENDER_HOME = (0.0, 0.0, 9.0)
CAM0_POS = (0.0, 1.62, 0.0)
CAM0_TARGET = (0.0, 1.25, 9.0)


def synth():
    from kokoro_onnx import Kokoro

    d = V.kokoro_dir()
    k = Kokoro(str(d / V.KOKORO_FILES[0]), str(d / V.KOKORO_FILES[1]))
    out = []
    for _, text in LINES:
        s, sr = k.create(text, voice=N.VOICE, speed=1.1, lang="en-us")
        s = np.asarray(s, np.float32)
        loud = np.nonzero(np.abs(s) > 0.02)[0]
        s = s[max(0, loud[0] - int(0.02 * sr)) : loud[-1] + int(0.06 * sr)]
        n = int(len(s) * SR / sr)
        out.append(np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s).astype(np.float32))
    return out


def main():
    voices = synth()
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

    t_anger = S["never"].start + S["never"].w["eyes"]
    t_scare = t_anger + 0.4
    w7 = S["water"]
    t_touch = w7.start + w7.w["stand"]
    t_tp = w7.start + w7.w["teleport"]

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

    add(t_anger, screech())
    add(t_scare, N.boom_sfx(), 0.55)
    add(t_scare, vwoop())
    for name in ("unless", "tricks", "roof", "water", "loop"):
        add(S[name].start - 0.1, V.sfx("whoosh"), 0.7)
    add(S["unless"].start + 0.1, V.sfx("pop"))
    add(S["stare"].start - 0.05, V.sfx("pop"))
    add(S["stare"].start + S["stare"].w["won't"], V.sfx("ding"))
    add(S["catch"].start + S["catch"].w["barely"], V.sfx("buzz"))
    add(S["tricks"].start + 0.05, V.sfx("chime"))
    add(S["roof"].start + S["roof"].w["three"], V.sfx("pop"))
    add(S["roof"].start + S["roof"].w["two"], V.sfx("pop"))
    add(S["roof"].start + S["roof"].D - 0.35, V.sfx("ding"))
    add(t_touch, V.sfx("splash"), 0.8)
    add(t_tp, vwoop())
    ducks = [(t_anger, 0.9)]
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
        faces = list(TREE_FACES)
        fp, overlay, extra = True, 0.0, []
        flash, flash_col = 0.0, (255, 255, 255)

        if name in ("never", "loop"):
            if name == "loop" or t < t_anger:
                k = ease(t / max(0.01, t_anger)) if name == "never" else 0.0
                target = np.array(CAM0_TARGET) + np.array([0, 1.4, 0]) * k
                pos = np.array(CAM0_POS) + np.array([0, 0, 1.2]) * k
                if name == "loop":
                    pos, target = np.array(CAM0_POS), np.array(CAM0_TARGET)
                cam = Cam.look(pos, target)
                faces += enderman(ENDER_HOME, math.pi, t)
            elif t < t_scare:
                cam = Cam.look((0, 1.62, 1.2), (0, 2.65, 9.0))
                faces += enderman(ENDER_HOME, math.pi, t, anger=1.0)
            else:
                k = ease((t - t_scare) / 0.12)
                cam = Cam.look((0, 1.62, 1.2), (0, lerp(2.65, 2.2, k), 9.0))
                faces += enderman((0, 0, lerp(9.0, 3.0, k)), math.pi, t, anger=1.0)
                extra.append(("particles", (0, 0, 9.0), t_scare))
                shake = 0.05 * math.exp(-(t - t_scare) / 0.3)
                cam = Cam((0 + shake * math.sin(t * 90), 1.62, 1.2), shake * math.sin(t * 77), math.atan2(0.6, 1.8) + shake * math.cos(t * 83))
                flash, flash_col = 0.75 * math.exp(-(t - t_scare) / 0.12), (150, 0, 60)
        elif name == "unless":
            cam = Cam.look(CAM0_POS, (0, 1.9, 9.0))
            faces += enderman(ENDER_HOME, math.pi, t)
            fly = ease((lt - (sc.D - 0.3)) / 0.3)
            ppos = cam.pos + cam.fwd * lerp(2.2, 0.35, fly) + cam.up * (0.06 * math.sin(lt * 4))
            extra.append(("pumpkin", ppos, lt * 2.2 + math.pi, lerp(0.15, 0.0, fly)))
        elif name in ("stare", "catch"):
            sway = 0.15 * math.sin(t * 1.3)
            if name == "catch":
                sway = 0.55 * math.sin(lt * 5.5)
            cam = Cam((0, 1.62, 4.2), sway, math.atan2(1.0, 4.8))
            faces += enderman(ENDER_HOME, math.pi, t)
            overlay = 1.0 if name == "stare" else 1.0
        elif name == "tricks":
            fp = False
            cam = Cam.look((X6 + 0.5, 2.4, -7.0), (X6 + 1.5, 1.3, 0.5))
            faces += ROOF_FACES + player((X6 + 3.5, 0, 0.5), math.pi) + enderman((X6 - 3, 0, 0.5), math.pi / 2, t)
        elif name == "roof":
            fp = False
            cam = Cam.look((X6 + 1.4, 2.1, -5.6), (X6 + 1.9, 1.45, 0.5))
            ex = lerp(X6 - 3.5, X6 + 1.25, ease(lt / (sc.D * 0.55)))
            walking = 1.0 if lt < sc.D * 0.55 else 0.0
            faces += ROOF_FACES + player((X6 + 3.5, 0, 0.45), math.pi)
            faces += enderman((ex, 0, 0.5), math.pi / 2, t, walk=walking)
            extra.append(("ruler", (ex - 0.75, 0, 0.5), 3, "3 BLOCKS", PURPLE, lt - sc.w["three"]))
            extra.append(("ruler", (X6 + 2.25, 0, -0.25), 2, "2 BLOCKS", GREEN, lt - sc.w["two"]))
            if lt > sc.D - 0.45:
                extra.append(("pill", "SAFE ✓", GREEN, (X6 + 3.5, 3.6, 0.45), lt - (sc.D - 0.45)))
        else:  # water
            fp = False
            cam = Cam.look((X7 + 1.2, 2.2, -5.8), (X7 + 1.8, 1.2, 0.5))
            faces += player((X7 + 3.5, -0.7, 0.5), math.pi, clip_y=0.0)
            touch = t_touch - S["water"].start
            tp = t_tp - S["water"].start
            if lt < tp:
                ex = lerp(X7 - 4.0, X7 + 1.6, ease(lt / touch)) if lt < touch else X7 + 1.6
                faces += enderman((ex, 0, 0.5), math.pi / 2, t, walk=1.0 if lt < touch else 0.0, anger=1.0 if lt >= touch else 0.0)
            else:
                faces += enderman((X7 - 6.0, 0, 7.0), math.pi * 0.75, t)
                extra.append(("particles", (X7 + 1.6, 0, 0.5), t_tp))
                extra.append(("particles", (X7 - 6.0, 0, 7.0), t_tp))
            extra.append(("pill", "WATER = DAMAGE", (40, 110, 210), (X7 + 1.6, 3.4, 0.5), lt - sc.w["hurts"]))

        img = render_env(cam, t)
        pump_faces = []
        for e in extra:
            if e[0] == "pumpkin":
                pump_faces = pumpkin(e[1], e[2], e[3], 0.9)
        draw_faces(img, cam, faces)
        if pump_faces:
            img = img.filter(ImageFilter.GaussianBlur(10))
            img = Image.blend(img, Image.new("RGB", (W, H), (20, 10, 30)), 0.35)
            draw_faces(img, cam, pump_faces)
            V.paste_center(img, V.pill("CARVED PUMPKIN", 64, (190, 100, 20)), W / 2, 520, V.pop_scale(lt - 0.15))
        for e in extra:
            if e[0] == "particles":
                draw_particles(img, cam, e[1], e[2], t, seed=int(e[2] * 10))
            elif e[0] == "ruler":
                draw_ruler(img, cam, *e[1:])
            elif e[0] == "pill":
                pr = cam.project(e[3])
                if pr:
                    V.paste_center(img, V.pill(e[1], 54, e[2]), pr[0][0], pr[0][1], V.pop_scale(e[4]))
        if overlay:
            img.paste(PUMPKIN_OV, (0, 0), PUMPKIN_OV)
            if name == "stare" and lt >= sc.w["won't"]:
                V.paste_center(img, V.pill("STILL CALM ✓", 60, (30, 140, 60)), W / 2, 560, V.pop_scale(lt - sc.w["won't"]))
            if name == "catch" and lt >= sc.w["barely"]:
                V.paste_center(img, V.pill("✗ LIMITED VISION", 60, (190, 40, 40)), W / 2, 560, V.pop_scale(lt - sc.w["barely"]))
        if name == "tricks":
            V.paste_center(img, V.pill("+2 TRICKS", 110, (120, 50, 190)), W / 2, 560, V.pop_scale(lt - 0.05, 0.25))
        if fp and name != "unless":
            draw_crosshair(img)
            draw_hand(img, t)
        N.draw_caption(img, sc.words, sc.starts, lt, y=1300)
        if name == "stare" and lt < 0.15:
            flash = max(flash, 0.7 * (1 - lt / 0.15))
            flash_col = (255, 160, 60)
        if name in ("tricks", "loop") and lt < 0.12:
            flash = max(flash, 0.6 * (1 - lt / 0.12))
        if flash > 0:
            img = Image.blend(img, Image.new("RGB", (W, H), flash_col), min(0.9, flash))
        ff.stdin.write(img.tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{frames}", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")
    wav.unlink()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
