"""Record the bubble-column water elevator Short footage.

Usage: python3 elevator.py OUTDIR [letters...] [--diamonds N]
Superflat world: grass top at y=20, dirt 17-19, stone below.
"""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shotlib import (PLAYER, SERVER, WIN, Recorder, camera_path, cmd, define, orbit, reload, run, setup_camera,
                     sleep, stop, write_pack, xdo)
from shots import S, TPS, area, common, reset

OUT = "."
GUI_HIDDEN = True


def clip(name):
    return os.path.join(OUT, name + ".mp4")


def shoot(name, events, seconds, during=None):
    """Spectator-camera shot: camera starts at its first keyframe, chunks render, then record."""
    first = min((e for e in events if e[1].startswith("tp @e[tag=cam")), key=lambda e: e[0])
    define(name, events)
    reload()
    setup_camera(*(float(v) for v in first[1].split()[2:7]))
    sleep(4)
    with Recorder(clip(name)):
        sleep(0.3)
        run(name)
        if during:
            during()
        else:
            sleep(seconds)
    stop()


def set_gui(hidden):
    global GUI_HIDDEN
    if hidden != GUI_HIDDEN:
        xdo("key", "--window", WIN, "F1")
        GUI_HIDDEN = hidden


def tube(x, z, top, floor="stone", water=True, glass="glass", rings=False):
    """1x1 glass tube from y=21 to `top`, optionally full of water source blocks.

    rings: tinted glass every 4 blocks so the speed of the ride reads on camera.
    """
    c = [f"fill {x - 1} 21 {z - 1} {x + 1} {top} {z + 1} {glass}"]
    if rings:
        c += [f"fill {x - 1} {y} {z - 1} {x + 1} {y} {z + 1} light_blue_stained_glass" for y in range(24, top, 4)]
    c += [f"fill {x} 21 {z} {x} {top} {z} {'water' if water else 'air'}",
          f"setblock {x} 20 {z} {floor}"]
    cmd(*c)


def trees(x, z, spots=((-4, 6), (4, 9), (6, 3), (-7, 11), (-3, -5), (8, -2), (1, 13))):
    """A few oaks around the base so the height reads from the top."""
    for dx, dz in spots:
        cmd(f"place feature minecraft:oak {x + dx} 21 {z + dz}")


def player_at(x, y, z, yaw, pitch, mode="survival", effects=("water_breathing", "fire_resistance", "resistance")):
    cmd("kill @e[tag=cam]", f"gamemode {mode} {PLAYER}", "clear " + PLAYER, "effect clear " + PLAYER)
    for e in effects:
        cmd(f"effect give {PLAYER} {e} infinite 4 true")
    cmd(f"tp {PLAYER} {x} {y} {z} {yaw} {pitch}")


def look(dx, dy, seconds, steps=None):
    """Turn the player's head with real relative mouse motion (about 0.15 degrees per pixel)."""
    steps = steps or max(1, int(seconds * 40))
    for i in range(steps):
        a = (i + 1) / steps
        b = i / steps
        e = lambda u: u * u * (3 - 2 * u)
        mx = round(dx * e(a)) - round(dx * e(b))
        my = round(dy * e(a)) - round(dy * e(b))
        if mx or my:
            xdo("mousemove_relative", "--", str(mx), str(my))
        sleep(seconds / steps)


def prepare(x, z, r=12, ground=0):
    area(x, z, 48); common()
    cmd(f"tp {PLAYER} {x + 4} 40 {z + 4}", "gamemode spectator " + PLAYER, "kill @e[tag=cam]", "kill @e[tag=mq]")
    sleep(2)
    reset(x, z, r, depth=ground)


# ---------------------------------------------------------------- shots

def a_rocket_up():
    x, z, top = 3000, 0, 52
    prepare(x, z)
    tube(x, z, top, rings=True)
    trees(x, z)
    sleep(1)
    player_at(x + 0.5, 21, z + 0.5, 0, -90)
    sleep(9)  # let underwater visibility build up, like a player who has been swimming a while
    with Recorder(clip("A_rocket_up")):
        sleep(2.5)
        cmd(f"setblock {x} 20 {z} soul_sand")  # bubbles erupt and launch the player
        sleep(2.9)
        look(160, 1100, 1.4)  # pop out of the top, look down the tube at the ground far below
        sleep(4.5)
    cmd("gamemode spectator " + PLAYER, "effect clear " + PLAYER)


def b_outside_view():
    x, z, top = 3300, 0, 52
    prepare(x, z)
    tube(x, z, top, rings=True)
    trees(x, z, ((-6, 5), (-8, -3), (-4, -8), (-10, 3), (-5, 10)))  # behind the tube, away from the camera
    sleep(1)
    cmd(f'summon mannequin {x + 0.5} 21 {z + 0.5} {{profile:"{PLAYER}",Tags:["mq"],Rotation:[116f,-25f]}}')
    t0, t_top, end = 30, 30 + 52, 215
    yaw = 116.57  # looking from (+6, +3) back at the tube
    ev = [(t0, f"setblock {x} 20 {z} soul_sand")]
    ev += camera_path([(0, x + 6.5, 21.9, z + 3.5, yaw, 4), (t0, x + 6.5, 21.6, z + 3.5, yaw, 2)])
    # Ride along: the camera follows the mannequin every tick (interpolated client side)
    ev += [(t, f"execute at @e[tag=mq,limit=1] run tp @e[tag=cam,limit=1] ~6 ~0.6 ~3 {yaw} 2")
           for t in range(t0 + 1, t_top)]
    ev += orbit(x + 0.5, top + 1.5, z + 0.5, 6.71, 0.6, yaw, yaw + 45, end - t_top, pitch=6, start=t_top)
    shoot("B_outside_view", ev, end / TPS + 0.5)
    cmd("kill @e[tag=mq]")


def c_build_tube():
    x, z, top = 3400, 0, 40
    prepare(x, z)
    cmd(f"setblock {x} 20 {z} stone")
    ev = []
    for i, y in enumerate(range(21, top + 1)):
        t = 15 + 3 * i
        ev.append((t, f"fill {x - 1} {y} {z - 1} {x + 1} {y} {z + 1} glass"))
        ev.append((t, f"setblock {x} {y} {z} air"))
    t_built = 15 + 3 * (top - 21)
    t_water = t_built + 25
    ev.append((t_water, f"setblock {x} {top} {z} water"))
    end = t_water + 150
    ev += camera_path([(0, x + 0.5, 22.5, z + 8, 180, -4), (t_built, x + 0.5, top + 2, z + 8, 180, 8),
                       (t_water, x + 0.5, top + 3, z + 6, 180, 30), (end, x + 0.5, 25, z + 8, 180, 4)])
    shoot("C_build_tube", ev, end / TPS + 0.5)


def d_soul_sand():
    x, z, top = 3500, 0, 34
    prepare(x, z)
    tube(x, z, top)
    ev = [(50, f"setblock {x} 20 {z} soul_sand")]
    ev += camera_path([(0, x + 0.5, 22.4, z + 3.6, 180, 22), (60, x + 0.5, 22.2, z + 3.0, 180, 18),
                       (260, x + 0.5, 27.5, z + 4.2, 180, -12)])
    shoot("D_soul_sand", ev, 13.3)


def e_magma_down():
    x, z, top = 3100, 0, 37
    prepare(x, z)
    tube(x, z, top)
    sleep(1)
    player_at(x + 0.5, top - 0.6, z + 0.5, 0, 90)
    sleep(8)
    with Recorder(clip("E_magma_down")):
        sleep(1.5)
        cmd(f"setblock {x} 20 {z} magma_block")  # whirlpool column forms and drags the player down
        sleep(9)
    cmd("gamemode spectator " + PLAYER, "effect clear " + PLAYER)


def f_kelp_trick():
    x, z, top = 3600, 0, 32
    prepare(x, z)
    tube(x, z, top, floor="sand", water=False)
    cmd(f"setblock {x} {top} {z} water")  # single source at the top: the tube fills with flowing water
    sleep(6)
    ev, t = [], 40
    for y in range(21, top):
        ev.append((t, f"setblock {x} {y} {z} kelp[age=25]"))
        t += 7
    t_break = t + 30
    ev.append((t_break, f"setblock {x} 21 {z} water destroy"))  # break the bottom kelp, the rest follows
    end = t_break + 100
    ev += camera_path([(0, x + 0.5, 22.5, z + 4.5, 180, 8), (40, x + 0.5, 22.5, z + 4.2, 180, 6),
                       (t, x + 0.5, top - 1, z + 4.2, 180, 4), (t_break, x + 0.5, 26.5, z + 7.5, 180, 0),
                       (end, x + 0.5, 26.5, z + 8.5, 180, 0)])
    shoot("F_kelp_trick", ev, end / TPS + 0.5)


def g_air_refill():
    x, z = 3200, 0
    prepare(x, z, 14, ground=-8)
    cmd(f"fill {x - 1} 12 {z - 6} {x + 12} 20 {z + 6} stone",
        f"fill {x} 13 {z - 5} {x + 11} 13 {z + 5} sand",
        f"fill {x} 14 {z - 5} {x + 11} 20 {z + 5} water",
        f"setblock {x + 8} 13 {z} soul_sand")
    for lx in range(x + 1, x + 11, 3):  # sea lanterns light the pool floor
        for lz in (z - 4, z - 1, z + 2, z + 4):
            if (lx, lz) != (x + 8, z):
                cmd(f"setblock {lx} 13 {lz} sea_lantern")
    sleep(2)
    player_at(x + 2.5, 22, z + 0.5, -90, 15, effects=())
    cmd(f"item replace entity {PLAYER} hotbar.0 with diamond_pickaxe")
    sleep(3)
    set_gui(False)
    sleep(1)
    with Recorder(clip("G_air_refill")):
        cmd(f"tp {PLAYER} {x + 2.5} 16 {z + 0.5} -90 10")  # dive in with a full air bar
        sleep(6.5)  # air bubbles pop one by one
        xdo("keydown", "w")
        sleep(3.2)  # swim into the bubble column
        xdo("keyup", "w")
        sleep(4.5)  # pushed up, air bar refills
    set_gui(True)
    cmd("gamemode spectator " + PLAYER)


def diamond_layout(n, inner=11):
    """Positions (dx, dy, dz) for exactly n blocks: the neatest box that fits, else a stepped pile."""
    for h in (3, 2, 4, 1, 5, 6):
        if n % h:
            continue
        per = n // h
        best = None
        for w in range(1, inner - 1):
            if per % w == 0 and per // w <= inner - 2:
                d = per // w
                if best is None or abs(w - d) < abs(best[0] - best[1]):
                    best = (w, d)
        if best and abs(best[0] - best[1]) <= 2:
            w, d = best
            return [(i, y, j) for y in range(h) for i in range(w) for j in range(d)]
    side = math.ceil(math.sqrt(n / 2)) + 1
    pos, y = [], 0
    while len(pos) < n:
        s = max(1, side - y)
        off = (side - s) / 2
        for i in range(s):
            for j in range(s):
                if len(pos) < n:
                    pos.append((round(i + off), y, round(j + off)))
        y += 1
    return pos


def h_castle(n):
    x, z = 3800, 0
    prepare(x + 6, z + 6, 26)
    sb = "stone_bricks"
    c = [f"fill {x} 20 {z} {x + 12} 20 {z + 12} {sb}",
         f"fill {x} 21 {z} {x + 12} 26 {z + 12} {sb} hollow",
         f"fill {x + 1} 26 {z + 1} {x + 11} 26 {z + 11} air"]
    for i in range(0, 13, 2):
        c += [f"setblock {x + i} 27 {z} {sb}", f"setblock {x + i} 27 {z + 12} {sb}",
              f"setblock {x} 27 {z + i} {sb}", f"setblock {x + 12} 27 {z + i} {sb}"]
    for tx, tz in ((x - 1, z - 1), (x + 10, z - 1), (x - 1, z + 10), (x + 10, z + 10)):
        c += [f"fill {tx} 21 {tz} {tx + 3} 30 {tz + 3} {sb} hollow"]
        c += [f"setblock {tx + a} 31 {tz + b} {sb}" for a in (0, 3) for b in (0, 3)]
    c += [f"fill {x + 5} 21 {z + 12} {x + 7} 24 {z + 12} air",
          f"setblock {x + 5} 24 {z + 12} stone_brick_stairs[facing=east,half=top]",
          f"setblock {x + 7} 24 {z + 12} stone_brick_stairs[facing=west,half=top]",
          f"fill {x + 1} 21 {z + 1} {x + 11} 25 {z + 11} air"]
    pos = diamond_layout(n)
    w = max(p[0] for p in pos) + 1
    d = max(p[2] for p in pos) + 1
    ox, oz = x + 1 + (11 - w) // 2, z + 1 + (11 - d) // 2
    c += [f"setblock {ox + i} {21 + y} {oz + j} diamond_block" for i, y, j in pos]
    for lx, lz in ((x + 1, z + 1), (x + 11, z + 1), (x + 1, z + 11), (x + 11, z + 11)):
        c.append(f"setblock {lx} 21 {lz} lantern")
    cmd(*c)
    sleep(2)
    count = count_blocks(x, z, "diamond_block")
    print(f"castle diamond blocks: {count}", flush=True)
    if count != n:
        sys.exit(f"diamond count {count} != {n}")
    cx, cz = x + 6.5, z + 6.5
    ev = camera_path([(0, cx, 24, z + 27, 180, 4), (8 * TPS, cx, 36, z + 17, 180, 42),
                      (13 * TPS, cx, 32.5, cz + 2.2, 180, 72), (18 * TPS, cx, 30.5, cz + 1.2, 180, 82)])
    shoot("H_castle_60" if n == 60 else f"H_castle_{n}", ev, 18.3)


def count_blocks(x, z, block):
    """Count blocks in the castle by swapping them to gold and back; the server reports each count."""
    log = os.path.join(SERVER, "logs", "latest.log")
    size = os.path.getsize(log)
    cmd(f"fill {x - 1} 20 {z - 1} {x + 13} 31 {z + 13} gold_block replace {block}")
    sleep(1.5)
    cmd(f"fill {x - 1} 20 {z - 1} {x + 13} 31 {z + 13} {block} replace gold_block")
    sleep(1.5)
    with open(log) as f:
        f.seek(size)
        counts = [int(m) for m in re.findall(r"Successfully filled (\d+) block", f.read())]
    return counts[0] if len(counts) == 2 and counts[0] == counts[1] else -1


SHOTS = {"A": a_rocket_up, "B": b_outside_view, "C": c_build_tube, "D": d_soul_sand, "E": e_magma_down,
         "F": f_kelp_trick, "G": g_air_refill}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("shots", nargs="*")
    ap.add_argument("--diamonds", type=int, default=60)
    args = ap.parse_args()
    OUT = args.out
    write_pack()
    for letter in args.shots or [*SHOTS, "H"]:
        print("shot", letter, flush=True)
        h_castle(args.diamonds) if letter == "H" else SHOTS[letter]()
    cmd("gamemode spectator " + PLAYER)
