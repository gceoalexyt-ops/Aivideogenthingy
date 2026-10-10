"""Never Sleep in the Nether: first-person, HUD visible, survival, real clicks.

Usage: python3 nether.py OUTDIR [A B C D E F] [--slow 4] [--diamonds 232]
       python3 nether.py test-d     (unrecorded: set off the mining bed from cover, report health)
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elevator
import shotlib
from elevator import set_gui
from shotlib import PLAYER, SERVER, WIN, Recorder, cmd, sleep, write_pack, xdo

LOG = os.path.join(SERVER, "logs", "latest.log")
OUT = "."
N = "execute in minecraft:the_nether run "
RESULTS = {}


def clip(name):
    return os.path.join(OUT, name + ".mp4")


def S(seconds):
    """Real seconds for `seconds` of game time (recording runs slowed)."""
    return seconds * shotlib.SLOW


def query(*commands, wait=0.8):
    pos = os.path.getsize(LOG)
    cmd(*commands)
    sleep(wait)
    with open(LOG) as f:
        f.seek(pos)
        return [l.split("System chat: ", 1)[1] for l in f.read().splitlines() if "System chat: " in l]


def health():
    out = query(f"data get entity {PLAYER} Health")
    m = [re.search(r"entity data: ([\d.]+)f", l) for l in out]
    m = [x for x in m if x]
    return float(m[-1].group(1)) if m else None


def nether_tp(x, y, z, yaw, pitch):
    cmd(f"execute in minecraft:the_nether run tp {PLAYER} {x} {y} {z} {yaw} {pitch}")


def scan(x, z, block, ys):
    """One single-condition test per y (chained ifs print nothing on failure, so they can't be counted)."""
    out = query(*[f"execute in minecraft:the_nether if block {x} {y} {z} {block}" for y in ys], wait=2.0)
    res = [l.startswith("Test passed") for l in out if l.startswith("Test")]
    return res if len(res) == len(ys) else None


def find_ground(x, z, block="#minecraft:nylium", top=100, bottom=32):
    """Highest y in this column with `block` underfoot and 2 air above (None if there isn't one)."""
    ys = list(range(top + 1, bottom - 2, -1))
    air, ground = scan(x, z, "air", ys), scan(x, z, block, ys)
    if air is None or ground is None:
        return None
    at = dict(zip(ys, zip(air, ground)))
    for y in range(top, bottom, -1):
        if at[y - 1][1] and at[y][0] and at[y + 1][0] and at.get(y + 2, (True,))[0]:
            return y
    return None


def is_clear(x, y, z):
    out = query(f"execute in minecraft:the_nether if block {x} {y - 1} {z} #minecraft:nylium "
                f"if block {x} {y} {z} air if block {x} {y + 1} {z} air", wait=0.6)
    r = [l for l in out if l.startswith("Test")]
    return bool(r) and r[0].startswith("Test passed")


def survivor(items=()):
    cmd("kill @e[tag=cam]", "gamemode survival " + PLAYER, "clear " + PLAYER, "effect clear " + PLAYER,
        f"effect give {PLAYER} instant_health 1 10 true", f"effect give {PLAYER} saturation 1 10 true")
    for slot, item in items:
        cmd(f"item replace entity {PLAYER} hotbar.{slot} with {item}")
    sleep(0.5)
    xdo("key", "--window", WIN, "1")


def look(dx, dy, seconds):
    elevator.look(dx, dy, S(seconds))


# ---------------------------------------------------------------- scene A/B/C: bed in the crimson forest

def find_spot():
    cmd(N + "forceload add 160 -290 290 -160")
    cmd("gamemode spectator " + PLAYER)
    for dx, dz in ((0, 0), (6, 0), (-6, 0), (0, 6), (0, -6), (10, 10), (-10, 10), (10, -10), (-10, -10),
                   (16, 0), (-16, 0), (0, 16), (0, -16)):
        x, z = 224 + dx, -224 + dz
        nether_tp(x + 0.5, 110, z + 0.5, 0, 90)  # load the column before testing it
        sleep(4)
        y = find_ground(x, z)
        if y is None or not is_clear(x, y, z):
            continue
        # need a clear 2-high strip 3 blocks south for the bed, and room east for the anchor
        ok = query(*[f"execute in minecraft:the_nether if block {x} {y} {z + k} air if block {x} {y + 1} {z + k} air"
                     for k in (1, 2, 3)], wait=1.0)
        ok = [l for l in ok if l.startswith("Test")]
        if len(ok) == 3 and all(l.startswith("Test passed") for l in ok):
            print("spot ok", x, y, z, flush=True)
            return x, y, z
    return None


def a_bed_boom(spot):
    x, y, z = spot
    cmd("gamerule immediate_respawn false", "difficulty normal")
    # solid nylium under the bed, then the bed itself (foot nearest the player, head pointing away)
    cmd(N + f"fill {x} {y - 1} {z + 1} {x} {y - 1} {z + 3} crimson_nylium",
        N + f"setblock {x} {y} {z + 2} red_bed[facing=south,part=foot]",
        N + f"setblock {x} {y} {z + 3} red_bed[facing=south,part=head]")
    nether_tp(x + 0.5, y, z + 0.5, 0, 38)
    survivor()
    sleep(4)
    w = query("time query daytime", wait=0.3)
    pos = os.path.getsize(LOG)
    with Recorder(clip("A_bed_boom")) as rec:
        sleep(S(2.5))
        t_click = (time.time() - rec.started) / shotlib.SLOW
        xdo("click", "3")  # right-click the bed
        sleep(S(4.0))
    with open(LOG) as f:
        f.seek(pos)
        deaths = [l for l in f.read().splitlines() if "System chat: " + PLAYER in l and
                  re.search(r"was killed|died|blew up|Intentional|suffocated|burned|flames", l)]
    RESULTS["A_bed_boom"] = {"click_at": round(t_click, 2), "death_message": deaths[-1].split("System chat: ")[-1]
                             if deaths else None}
    # B: hold on the real death screen
    with Recorder(clip("B_death_screen")):
        sleep(S(4.0))
    shot = os.path.join(OUT, "death_screen.png")
    os.system(f"ffmpeg -loglevel error -y -f x11grab -video_size 720x1280 -i :99 -frames:v 1 {shot}")
    xdo("mousemove", "--window", WIN, "360", "483", "click", "1")  # Respawn
    sleep(3)
    cmd("gamerule immediate_respawn true")


def c_crater(spot):
    x, y, z = spot
    # Back to the Nether, standing a safe distance from where the bed was, facing the crater
    nether_tp(x + 0.5, y + 1, z - 5.5, 0, 22)
    survivor()
    sleep(4)
    with Recorder(clip("C_crater")):
        sleep(S(1.0))
        look(-260, 40, 2.2)   # slow look left and down over the crater
        look(520, -40, 3.0)   # sweep right across the fire
        sleep(S(0.6))


# ---------------------------------------------------------------- scene D: bed mining at Y=15

DX, DY, DZ = 300, 15, -300  # pocket origin (corridor along +z)


def build_pocket():
    cmd(N + f"forceload add {DX - 16} {DZ - 16} {DX + 16} {DZ + 24}")
    nether_tp(DX + 1.5, DY, DZ + 1.5, 0, 10)
    cmd("gamemode spectator " + PLAYER)
    sleep(4)
    c = [N + f"fill {DX - 4} {DY - 3} {DZ - 4} {DX + 6} {DY + 5} {DZ + 14} netherrack",
         N + f"fill {DX} {DY} {DZ} {DX + 2} {DY + 2} {DZ + 8} air",            # 3x3 corridor, 9 long
         N + f"setblock {DX + 1} {DY + 3} {DZ + 2} glowstone",                 # a little natural light
         N + f"setblock {DX} {DY + 3} {DZ + 6} glowstone",
         # ancient debris hidden in the end walls, within ~3 blocks of where the bed goes
         N + f"setblock {DX + 1} {DY} {DZ + 10} ancient_debris",
         N + f"setblock {DX - 2} {DY + 1} {DZ + 7} ancient_debris",
         N + f"setblock {DX + 4} {DY} {DZ + 8} ancient_debris",
         # the bed at the far end, and a low block to hide behind
         N + f"setblock {DX + 1} {DY} {DZ + 7} red_bed[facing=south,part=foot]",
         N + f"setblock {DX + 1} {DY} {DZ + 8} red_bed[facing=south,part=head]",
         N + f"setblock {DX + 1} {DY} {DZ + 4} netherrack"]
    cmd(*c)
    sleep(1)


def aim_at(tx, ty, tz, seconds):
    """Turn the player's view onto a point with real mouse movement (about 0.15 degrees per pixel)."""
    import math
    out = query(f"data get entity {PLAYER} Pos", f"data get entity {PLAYER} Rotation", wait=0.6)
    pos = rot = None
    for l in out:
        m = re.search(r"entity data: \[([-\d.]+)d, ([-\d.]+)d, ([-\d.]+)d\]", l)
        if m:
            pos = [float(v) for v in m.groups()]
        m = re.search(r"entity data: \[([-\d.]+)f, ([-\d.]+)f\]", l)
        if m:
            rot = [float(v) for v in m.groups()]
    if not pos or not rot:
        return
    ex, ey, ez = pos[0], pos[1] + 1.62, pos[2]
    dx, dy, dz = tx - ex, ty - ey, tz - ez
    yaw = math.degrees(math.atan2(-dx, dz))
    pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    dyaw = (yaw - rot[0] + 180) % 360 - 180
    look(round(dyaw / 0.15), round((pitch - rot[1]) / 0.15), seconds)


def d_bed_mining(record=True):
    build_pocket()
    # Stand behind the low block, close enough to reach the bed over it
    nether_tp(DX + 1.5, DY, DZ + 3.2, 0, 15)  # line of sight just clears the cover block and lands on the bed
    survivor(items=[(0, 'netherite_pickaxe[enchantments={"minecraft:efficiency":5}]')])
    xdo("key", "--window", WIN, "2")  # empty hand for the bed click
    sleep(4)
    pos = os.path.getsize(LOG)
    hp0 = health()
    ctx = Recorder(clip("D_bed_mining")) if record else None
    t0 = time.time()
    if ctx:
        ctx.__enter__()
    try:
        sleep(S(1.5))
        t_click = (time.time() - t0) / shotlib.SLOW
        xdo("click", "3")                  # set the bed off from behind the block
        sleep(S(2.5))
        hp1 = health()
        xdo("key", "--window", WIN, "1")   # pickaxe
        look(0, 200, 0.8)                  # look down into the crater where the bed was
        sleep(S(0.5))
        # Put out any fire where we're about to step (left-clicking fire extinguishes it)
        for fz in (4, 5):
            aim_at(DX + 1.5, DY + 0.15, DZ + fz + 0.5, 0.35)
            xdo("click", "1")
            sleep(S(0.25))
        xdo("keydown", "w")                # one step to the crater's edge
        sleep(S(0.35))
        xdo("keyup", "w")
        sleep(S(0.4))
        aim_at(DX - 1.5, DY + 1.5, DZ + 7.5, 0.7)  # turn (real mouse) to the debris the blast uncovered
        sleep(S(0.3))
        t_mine = (time.time() - t0) / shotlib.SLOW
        xdo("mousedown", "1")
        sleep(S(3.0))
        xdo("mouseup", "1")
        sleep(S(1.5))
    finally:
        if ctx:
            ctx.__exit__(None, None, None)
    with open(LOG) as f:
        f.seek(pos)
        txt = f.read()
    died = re.search(rf"{PLAYER} (was |died|blew up|went up in flames|burned|walked into fire|tried to swim)", txt) is not None
    left = query(*[N + f"execute if block {DX + a} {DY + b} {DZ + c} ancient_debris"
                   for a, b, c in ((1, 0, 10), (-2, 1, 7), (4, 0, 8))], wait=1.0)
    RESULTS["D_bed_mining"] = {"click_at": round(t_click, 2), "health_before": hp0, "health_after_blast": hp1,
                               "died": died, "mine_start_at": round(t_mine, 2),
                               "debris_still_there": [l for l in left if l.startswith("Test")]}
    print("D", json.dumps(RESULTS["D_bed_mining"]), flush=True)
    return hp1, died


# ---------------------------------------------------------------- scene E: respawn anchor

def e_respawn_anchor(spot):
    x, y, z = spot
    ax, az = x + 4, z
    cmd(N + f"fill {ax - 1} {y - 1} {az + 1} {ax + 1} {y - 1} {az + 3} crimson_nylium",
        N + f"fill {ax - 1} {y} {az + 1} {ax + 1} {y + 2} {az + 3} air")
    nether_tp(ax + 0.5, y, az + 0.5, 0, 52)
    survivor(items=[(0, "respawn_anchor"), (1, "glowstone 4")])
    xdo("key", "--window", WIN, "1")
    sleep(4)
    pos = os.path.getsize(LOG)
    with Recorder(clip("E_respawn_anchor")) as rec:
        T = lambda: round((time.time() - rec.started) / shotlib.SLOW, 2)
        sleep(S(0.8))
        times = {"place": T()}
        xdo("click", "3")                         # place the anchor
        sleep(S(0.8))
        xdo("key", "--window", WIN, "2")           # glowstone
        sleep(S(0.4))
        times["charges"] = []
        for _ in range(4):                        # charge 1..4 (the anchor face lights up step by step)
            times["charges"].append(T())
            xdo("click", "3")
            sleep(S(0.7))
        xdo("key", "--window", WIN, "3")           # empty hand
        sleep(S(0.4))
        times["set"] = T()
        xdo("click", "3")                         # set the spawn point
        sleep(S(2.2))
    with open(LOG) as f:
        f.seek(pos)
        txt = f.read()
    times["log"] = [l.split("System chat: ")[-1] for l in txt.splitlines() if "spawn" in l.lower()][-3:]
    RESULTS["E_respawn_anchor"] = times
    print("E", json.dumps(times), flush=True)


# ---------------------------------------------------------------- scene F: castle end card

def f_castle(n):
    import clutch
    from shotlib import camera_path
    from shots import TPS
    x, z = 5300, 0
    elevator.build_castle(x, z, n, flat=False)
    cmd("time set 6000")
    cx, cz = x + 6.5, z + 6.5
    keys = [(0, cx, 40, cz + 13, 180, 50), (3 * TPS, cx + 0.5, 37, cz + 2, -90, 84),
            (5 * TPS, cx + 0.5, 36, cz, -90, 89.5)]
    set_gui(True)
    elevator.shoot(f"F_castle_{n}", camera_path(keys), 5.2)
    set_gui(False)


if __name__ == "__main__":
    if sys.argv[1] == "test-d":
        write_pack()
        cmd("difficulty normal", "gamerule natural_health_regeneration false")
        hp, died = d_bed_mining(record=False)
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("shots", nargs="*")
    ap.add_argument("--slow", type=int, default=4)
    ap.add_argument("--diamonds", type=int, default=232)
    a = ap.parse_args()
    OUT = elevator.OUT = a.out
    os.makedirs(OUT, exist_ok=True)
    shotlib.SLOW = a.slow
    write_pack()
    elevator.GUI_HIDDEN = os.environ.get("MC_GUI_HIDDEN") == "1"
    set_gui(False)  # HUD visible for the first-person clips
    cmd("difficulty normal", "gamerule natural_health_regeneration false", "gamerule keep_inventory true",
        "gamerule fire_damage true")
    spot = None
    shots = a.shots or list("ABCDEF")
    if set(shots) & set("ACE"):
        spot = find_spot()
        print("spot", spot, flush=True)
        if spot is None:
            sys.exit("no crimson forest spot found")
    if "A" in shots:
        a_bed_boom(spot)
    if "C" in shots:
        c_crater(spot)
    if "D" in shots:
        d_bed_mining()
    if "E" in shots:
        e_respawn_anchor(spot)
    if "F" in shots:
        f_castle(a.diamonds)
    json.dump(RESULTS, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print("RESULTS", json.dumps(RESULTS), flush=True)
