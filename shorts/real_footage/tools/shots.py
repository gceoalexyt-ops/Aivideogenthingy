"""Record the real-footage clips for the Infinite Lava / Never Dig Straight Down Shorts.

Usage: python3 shots.py OUTDIR [letters...]
Superflat world: grass top at y=20, dirt 17-19, stone below.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shotlib import (PLAYER, WIN, Recorder, camera_path, cmd, define, orbit, reload, run, setup_camera,
                     sleep, stop, write_pack, xdo)

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
TPS = 20
S = "stone"


def clip(name):
    return os.path.join(OUT, name + ".mp4")


def area(x, z, r=40):
    cmd(f"forceload add {x - r} {z - r} {x + r} {z + r}")


def reset(x, z, r=20, depth=0):
    """Restore a flat patch of superflat ground around (x, z)."""
    # /fill is capped at 32768 blocks, so work in 4-block-thick slabs
    for y in range(21, 41, 4):
        cmd(f"fill {x - r} {y} {z - r} {x + r} {y + 3} {z + r} air")
    for y in range(depth, 17, 4):
        cmd(f"fill {x - r} {y} {z - r} {x + r} {min(y + 3, 16)} {z + r} {S}")
    cmd(f"fill {x - r} 17 {z - r} {x + r} 19 {z + r} dirt",
        f"fill {x - r} 20 {z - r} {x + r} 20 {z + r} grass_block",
        f"kill @e[type=item]")


def common():
    cmd("time set 6000", "weather clear", "gamerule random_tick_speed 3", "kill @e[type=item]",
        "effect clear " + PLAYER)


def shoot(name, events, seconds, cam):
    """Define, place camera, wait for chunks to render, then record the shot."""
    first = min((e for e in events if e[1].startswith("tp @e[tag=cam")), key=lambda e: e[0])
    cam = tuple(float(v) for v in first[1].split()[2:7])
    define(name, events)
    reload()
    setup_camera(*cam)
    sleep(4)
    with Recorder(clip(name)):
        sleep(0.3)
        run(name)
        sleep(seconds)
    stop()


def farm(x, z, lava=True, drip=True, cauldron=True):
    """Classic infinite lava farm: block in the air, lava on top, dripstone, cauldron."""
    c = [f"setblock {x} 23 {z} {S}"]
    c += [f"setblock {x + dx} 24 {z + dz} {S}" for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    if lava:
        c.append(f"setblock {x} 24 {z} lava")
    if drip:
        c.append(f"setblock {x} 22 {z} pointed_dripstone[vertical_direction=down,thickness=tip]")
    if cauldron:
        c.append(f"setblock {x} 21 {z} cauldron")
    return c


# ---------------------------------------------------------------- Infinite Lava

def a_water_hole():
    x, z = 1000, 0
    area(x, z); common(); reset(x, z)
    cmd(f"fill {x} 20 {z} {x + 1} 20 {z + 1} air")
    ev = [(40, f"setblock {x} 20 {z} water"), (90, f"setblock {x + 1} 20 {z + 1} water")]
    ev += orbit(x + 1, 20.5, z + 1, 4.2, 3.2, 200, 250, 14 * TPS)
    shoot("a_water_hole", ev, 14, (x + 1, 24, z - 3, 0, 40))


def b_lava_on_block():
    x, z = 1100, 0
    area(x, z); common(); reset(x, z)
    cmd(*farm(x, z, lava=False, drip=False, cauldron=False))
    ev = [(50, f"setblock {x} 24 {z} lava")]
    ev += orbit(x + 0.5, 24.0, z + 0.5, 3.8, 4.2, 150, 215, 13 * TPS)
    shoot("b_lava_on_block", ev, 13, (x, 26, z + 5, 180, 25))


def c_dripstone():
    x, z = 1100, 0
    area(x, z); common()
    cmd(f"setblock {x} 22 {z} air", f"setblock {x} 21 {z} air")
    ev = [(50, f"setblock {x} 22 {z} pointed_dripstone[vertical_direction=down,thickness=tip]")]
    ev += orbit(x + 0.5, 22.6, z + 0.5, 3.6, -0.4, 120, 170, 13 * TPS)
    shoot("c_dripstone", ev, 13, (x + 3, 22, z, 90, -5))


def d_cauldron_filling():
    x, z = 1100, 0
    area(x, z); common()
    cmd(f"setblock {x} 21 {z} air")
    ev = [(30, f"setblock {x} 21 {z} cauldron"), (80, "gamerule random_tick_speed 1200")]
    ev += orbit(x + 0.5, 21.6, z + 0.5, 3.4, 0.9, 200, 235, 19 * TPS)
    shoot("d_cauldron_filling", ev, 19, (x, 22.5, z - 3, 0, 15))
    cmd("gamerule random_tick_speed 3", f"setblock {x} 21 {z} lava_cauldron")


def e_full_cauldron():
    x, z = 1100, 0
    area(x, z); common()
    cmd(f"setblock {x} 21 {z} lava_cauldron")
    ev = camera_path([(0, x + 0.5, 23.6, z - 2.6, 0, 42), (12 * TPS, x + 0.5, 22.9, z - 1.2, 0, 58)])
    shoot("e_full_cauldron", ev, 12, (x + 0.5, 23.6, z - 2.6, 0, 42))


def f_farm_row():
    x0, z = 1200, 0
    xs = [x0 + 3 * i for i in range(5)]
    area(x0 + 6, z); common(); reset(x0 + 6, z, 24)
    for x in xs:
        cmd(*farm(x, z))
    ev = [(40, "gamerule random_tick_speed 500")]
    ev += camera_path([(0, x0 - 4, 27.5, z - 9, -30, 22), (18 * TPS, x0 + 16, 27.5, z - 9, 30, 22)])
    shoot("f_farm_row", ev, 18, (x0 - 3, 25, z - 6, -35, 22))
    cmd("gamerule random_tick_speed 3")


def g_furnace():
    x, z = 1300, 0
    area(x, z); common(); reset(x, z)
    cmd(f"setblock {x} 21 {z} furnace[facing=south]", f"setblock {x - 1} 21 {z} lava_cauldron",
        f"setblock {x + 1} 21 {z} crafting_table")
    items = ('{Items:[{Slot:0b,id:"minecraft:raw_iron",count:64},'
             '{Slot:1b,id:"minecraft:lava_bucket",count:1}]}')
    ev = [(50, f"data merge block {x} 21 {z} {items}")]
    ev += camera_path([(0, x + 0.5, 22.6, z + 4.2, 180, 18), (12 * TPS, x + 0.5, 22.0, z + 2.0, 180, 12)])
    shoot("g_furnace", ev, 12, (x + 0.5, 22.6, z + 4.2, 180, 18))


# ---------------------------------------------------------------- Never Dig Straight Down

def first_person(x, y, z, yaw, pitch):
    cmd("kill @e[tag=cam]", "gamemode survival " + PLAYER, "clear " + PLAYER,
        f"item replace entity {PLAYER} hotbar.0 with diamond_pickaxe",
        f"effect give {PLAYER} resistance infinite 4 true",
        f"effect give {PLAYER} fire_resistance infinite 0 true",
        f"effect give {PLAYER} saturation infinite 0 true",
        f"tp {PLAYER} {x + 0.5} {y} {z + 0.5} {yaw} {pitch}")
    sleep(3)
    xdo("key", "--window", WIN, "1")


def h_dig_down():
    x, z = 1400, 0
    area(x, z); common()
    cmd(f"tp {PLAYER} {x + 0.5} 30 {z + 0.5}")
    sleep(2)
    reset(x, z, 10, depth=-40)
    cmd(f"fill {x} 16 {z} {x} 22 {z} air")
    first_person(x, 16, z, 0, 90)
    sleep(2)
    with Recorder(clip("h_dig_down")):
        sleep(1)
        xdo("mousedown", "1")
        sleep(13)
        xdo("mouseup", "1")
        sleep(1)


def i_fall_into_lava():
    x, z = 1500, 0
    area(x, z); common()
    cmd(f"tp {PLAYER} {x + 0.5} 30 {z + 0.5}")
    sleep(2)
    reset(x, z, 12, depth=-10)
    cmd(f"fill {x - 7} 4 {z - 7} {x + 7} 9 {z + 7} air",
        f"fill {x - 7} 3 {z - 7} {x + 7} 4 {z + 7} lava",
        f"fill {x} 13 {z} {x} 22 {z} air")
    sleep(2)
    first_person(x, 13, z, 0, 90)
    sleep(2)
    with Recorder(clip("i_fall_into_lava")):
        sleep(1)
        xdo("mousedown", "1")
        sleep(4)
        xdo("mouseup", "1")
        sleep(6)
    cmd(f"tp {PLAYER} {x + 0.5} 30 {z + 0.5}", "gamemode spectator " + PLAYER)


def j_staircase():
    x0, z = 1600, 0
    area(x0 + 8, z, 48); common()
    cmd(f"tp {PLAYER} {x0 + 8} 30 {z + 12}")
    sleep(2)
    # Restore ground, then cut it open along z = z+1 so the tunnel is seen from the side.
    for xa in range(x0 - 16, x0 + 32, 16):
        cmd(f"fill {xa} -2 {z - 6} {xa + 15} 16 {z + 16} {S}", f"fill {xa} 17 {z - 6} {xa + 15} 19 {z + 16} dirt",
            f"fill {xa} 20 {z - 6} {xa + 15} 20 {z + 16} grass_block",
            f"fill {xa} -1 {z + 1} {xa + 15} 20 {z + 16} air")
    cmd(f"fill {x0 - 16} -2 {z + 1} {x0 + 31} -2 {z + 16} {S}")
    # Lava cave at the bottom of the stairs
    cx = x0 + 12
    cmd(f"fill {cx} 3 {z - 4} {cx + 12} 9 {z} air", f"fill {cx} 3 {z - 4} {cx + 12} 4 {z} lava",
        f"fill {cx + 1} 10 {z - 3} {cx + 10} 10 {z} air",
        f"fill {cx - 1} 2 {z + 1} {cx + 13} 11 {z + 1} barrier")
    ev, steps = [], 12
    for k in range(steps):
        t = 20 + k * 16
        for y in (21 - k, 22 - k):
            if y <= 20:
                ev.append((t + (22 - k - y) * 5, f"setblock {x0 + k} {y} {z} air destroy"))
    ev.append((20 + steps * 16, f"setblock {cx} 11 {z} air destroy"))
    ev.append((20 + steps * 16 + 5, f"setblock {cx} 10 {z} air destroy"))
    total = 20 + steps * 16 + 80
    ev += camera_path([(0, x0 + 1, 22, z + 13, 180, 5), (20 + steps * 16, x0 + 10, 13, z + 13, 180, 8),
                       (total, x0 + 13, 11, z + 13, 180, 6)])
    shoot("j_staircase", ev, total / TPS + 1, (x0 + 1, 22, z + 13, 180, 5))


def k_obsidian():
    x, z = 1700, 0
    area(x, z); common(); reset(x, z)
    cmd(f"fill {x - 1} 19 {z - 1} {x + 4} 21 {z + 4} {S}", f"fill {x} 21 {z} {x + 3} 21 {z + 3} air",
        f"fill {x} 20 {z} {x + 3} 20 {z + 3} lava")
    # Pour a bucket of water on the lava, then scoop it back up to reveal the obsidian
    ev = [(50, f"setblock {x} 21 {z} water"), (130, f"setblock {x} 21 {z} air")]
    ev += orbit(x + 2, 20.5, z + 2, 4.6, 4.6, 300, 350, 15 * TPS)
    shoot("k_obsidian", ev, 15, None)


# ---------------------------------------------------------------- Sub goal

def l_castle():
    x, z = 1800, 0
    area(x + 6, z + 6); common(); reset(x + 6, z + 6, 26)
    sb = "stone_bricks"
    c = [f"fill {x} 20 {z} {x + 12} 20 {z + 12} {sb}",
         f"fill {x} 21 {z} {x + 12} 26 {z + 12} {sb} hollow",
         f"fill {x + 1} 26 {z + 1} {x + 11} 26 {z + 11} air"]
    for i in range(0, 13, 2):  # crenellations
        c += [f"setblock {x + i} 27 {z} {sb}", f"setblock {x + i} 27 {z + 12} {sb}",
              f"setblock {x} 27 {z + i} {sb}", f"setblock {x + 12} 27 {z + i} {sb}"]
    for tx, tz in ((x - 1, z - 1), (x + 10, z - 1), (x - 1, z + 10), (x + 10, z + 10)):  # corner towers
        c += [f"fill {tx} 21 {tz} {tx + 3} 30 {tz + 3} {sb} hollow",
              f"fill {tx} 31 {tz} {tx} 31 {tz} {sb}", f"fill {tx + 3} 31 {tz} {tx + 3} 31 {tz} {sb}",
              f"fill {tx} 31 {tz + 3} {tx} 31 {tz + 3} {sb}", f"fill {tx + 3} 31 {tz + 3} {tx + 3} 31 {tz + 3} {sb}"]
    c += [f"fill {x + 5} 21 {z + 12} {x + 7} 24 {z + 12} air",  # gate
          f"setblock {x + 5} 24 {z + 12} stone_brick_stairs[facing=east,half=top]",
          f"setblock {x + 7} 24 {z + 12} stone_brick_stairs[facing=west,half=top]",
          f"fill {x + 1} 21 {z + 1} {x + 11} 25 {z + 11} air"]
    # Exactly 19 diamond blocks: a 4x4 pile with 3 on top
    c += [f"fill {x + 4} 21 {z + 4} {x + 7} 21 {z + 7} diamond_block",
          f"setblock {x + 5} 22 {z + 5} diamond_block", f"setblock {x + 6} 22 {z + 5} diamond_block",
          f"setblock {x + 5} 22 {z + 6} diamond_block"]
    for lx, lz in ((x + 1, z + 1), (x + 11, z + 1), (x + 1, z + 11), (x + 11, z + 11)):
        c.append(f"setblock {lx} 21 {lz} lantern")
    cmd(*c)
    # Crane from the gate up over the wall to look down on the diamond pile
    ev = camera_path([(0, x + 6.5, 25, z + 27, 180, 8), (9 * TPS, x + 6.5, 37, z + 18, 180, 52),
                      (20 * TPS, x + 1, 37, z + 16, -150, 55)])
    shoot("l_castle", ev, 20, (x + 6.5, 32, z + 23, 180, 30))


SHOTS = {"a": a_water_hole, "b": b_lava_on_block, "c": c_dripstone, "d": d_cauldron_filling,
         "e": e_full_cauldron, "f": f_farm_row, "g": g_furnace, "h": h_dig_down, "i": i_fall_into_lava,
         "j": j_staircase, "k": k_obsidian, "l": l_castle}

if __name__ == "__main__":
    write_pack()
    for letter in sys.argv[2:] or SHOTS:
        print("shot", letter, flush=True)
        SHOTS[letter]()
    cmd("gamemode spectator " + PLAYER)
