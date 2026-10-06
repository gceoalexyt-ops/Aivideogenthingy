"""Shared end scene for the Shorts: the subscriber-goal castle.

Every subscriber means one diamond block placed inside the castle. Shorts call `line(count)` for the
narration and `render(...)` for each frame of the scene. Set the count with the SUBS environment variable.
"""

from __future__ import annotations

import math
import os

import numpy as np

SUBS = int(os.environ.get("SUBS", "19"))


def line(count=SUBS):
    return (
        f"Sub goal: every new subscriber means one diamond block in my castle. We're at {count}. "
        "Subscribe, and the next one is yours."
    )


def register(E):
    sb = E.noise((128, 128, 132), 8)
    sb[[3, 7, 11, 15], :] = (86, 86, 90)
    for r0, c in ((0, 7), (4, 15), (8, 7), (12, 15)):
        sb[r0 : r0 + 3, c] = (86, 86, 90)
    E.TEX["stone_bricks"] = E.rgba(sb)
    r, c = np.mgrid[0:16, 0:16]
    d = E.noise((100, 228, 226), 8)
    d[(r == 0) | (r == 15) | (c == 0) | (c == 15)] = (40, 160, 164)
    d[(r + c) % 7 == 0] = (214, 255, 255)
    E.TEX["diamond_block"] = E.rgba(d)


def castle_blocks():
    b = {}
    for x in range(-5, 6):
        for z in range(3, 14):
            if x not in (-5, 5) and z not in (3, 13):
                continue
            for y in range(3):
                if z == 3 and x == 0 and y < 2:
                    continue
                b[(x, y, z)] = {"*": "stone_bricks"}
            if (x + z) % 2 == 0:
                b[(x, 3, z)] = {"*": "stone_bricks"}
    for cx, cz in ((-5, 3), (5, 3), (-5, 13), (5, 13)):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for y in range(5):
                    b[(cx + dx, y, cz + dz)] = {"*": "stone_bricks"}
                if (dx + dz) % 2 == 0:
                    b[(cx + dx, 5, cz + dz)] = {"*": "stone_bricks"}
    return b


def slots(n):
    out = []
    for i in range(n):
        row, col = divmod(i, 7)
        out.append((-3 + col, 0, 5 + row))
    return out


_cache = {}


def render(E, V, N, lt, scene, count=SUBS):
    """One frame of the sub-goal scene; `scene` is the N.Scene for the narration line."""
    if "castle" not in _cache:
        _cache["castle"] = E.blocks_faces(castle_blocks())
    a = -0.35 + 0.06 * lt
    cam = E.Cam.look((math.sin(a) * 13, 10.5, 8 - math.cos(a) * 13), (0, 0.6, 8.4))
    faces = list(E.TREE_FACES) + list(_cache["castle"])
    t0 = scene.w["every"]
    t1 = scene.w["we're"] + 0.3
    shown = 0 if lt < t0 else min(count, 1 + int((lt - t0) / max(0.05, (t1 - t0) / count)))
    for i, (x, y, z) in enumerate(slots(shown)):
        faces += E.blocks_faces({(x, y, z): {"*": "diamond_block"}})
    img = E.render_env(cam, lt)
    E.draw_faces(img, cam, faces)
    W = img.width
    V.paste_center(img, V.pill("SUB GOAL", 70, (40, 150, 160)), W / 2, 330, V.pop_scale(lt - scene.w["goal"]))
    V.paste_center(img, V.pill("1 SUBSCRIBER = 1 DIAMOND BLOCK", 46, (30, 30, 40)), W / 2, 440,
                   V.pop_scale(lt - scene.w["diamond"]))  # fmt: skip
    if shown:
        age = lt - t1 if shown == count else 0.5
        V.paste_center(img, V.pill(f"DIAMOND BLOCKS: {shown}", 64, (30, 120, 200)), W / 2, 560,
                       1 + 0.15 * V.bump(age, 0, 0.3))  # fmt: skip
    if lt >= scene.w["subscribe"]:
        pulse = 1 + 0.05 * math.sin(lt * 8)
        V.paste_center(img, V.pill("SUBSCRIBE  ➜  +1 DIAMOND", 62, (210, 40, 40)), W / 2, 1600,
                       V.pop_scale(lt - scene.w["subscribe"]) * pulse)  # fmt: skip
    return img, (t0, t1, count)
