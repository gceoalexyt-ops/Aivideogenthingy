"""Record the "5 ways to survive a 300-block fall" Short footage.

Usage: python3 clutch.py OUTDIR [A B C D E F G H] [--diamonds N]

Survival mode with the HUD visible. Every clutch take is checked in game: the player's
Health is read from the server right after landing, and a take is kept only if it is 20.0
(full) and the player did not die. Natural health regeneration is off, so the hearts can't
quietly refill. Failed takes are retried.
"""
import argparse
import math
import os
import random
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elevator
from elevator import build_castle, set_gui
from shotlib import PLAYER, SERVER, WIN, Recorder, camera_path, cmd, define, orbit, reload, run, setup_camera, sleep, stop, write_pack, xdo
from shots import TPS, area, common

OUT = "."
LOG = os.path.join(SERVER, "logs", "latest.log")
FX, FZ = 5000, 0  # forest centre; the A pillar stands here
SPOTS = {"B": (4986, -14), "C": (5014, 0), "D": (5000, 14), "E": (4986, 0), "F": (5000, -14), "G": (5014, 14)}
DROP_Y = 100  # feet height for the 79-block clutch falls (ground top is y=21)
RESULTS = []


def clip(name):
    return os.path.join(OUT, name + ".mp4")


class LogWatch:
    """Read what the server logged after this point."""

    def __init__(self):
        self.pos = os.path.getsize(LOG)

    def text(self):
        with open(LOG) as f:
            f.seek(self.pos)
            return f.read()


def health():
    w = LogWatch()
    cmd(f"data get entity {PLAYER} Health")
    sleep(0.6)
    m = re.findall(rf"{PLAYER} has the following entity data: ([\d.]+)f", w.text())
    return float(m[-1]) if m else None


def died(text):
    return re.search(rf"{PLAYER} (fell from a high place|hit the ground too hard|died)", text) is not None


def gamerules():
    cmd("difficulty normal", "gamerule natural_health_regeneration false", "gamerule keep_inventory true",
        "gamerule immediate_respawn true", "gamerule fall_damage true", "gamerule spawn_phantoms false",
        "gamerule spawn_mobs false", "gamerule spawn_monsters false", "time set 6000", "weather clear")


def forest():
    """Plains with scattered oak and birch woods around the fall spots."""
    area(FX, FZ, 96)
    cmd(f"tp {PLAYER} {FX} 120 {FZ}", "gamemode spectator " + PLAYER)
    sleep(3)
    for y in range(21, 41, 4):
        cmd(f"fill {FX - 60} {y} {FZ - 60} {FX + 60} {y + 3} {FZ + 60} air")
    rng = random.Random(7)
    keep_clear = [(FX, FZ)] + list(SPOTS.values())
    placed = 0
    while placed < 90:
        x, z = FX + rng.randint(-58, 58), FZ + rng.randint(-58, 58)
        if any(abs(x - a) < 5 and abs(z - b) < 5 for a, b in keep_clear):
            continue
        tree = rng.choice(["oak", "oak", "birch", "fancy_oak"])
        cmd(f"place feature minecraft:{tree} {x} 21 {z}")
        placed += 1
    for _ in range(25):
        x, z = FX + rng.randint(-55, 55), FZ + rng.randint(-55, 55)
        cmd(f"place feature minecraft:flower_plain {x} 21 {z}")
    sleep(3)
    cmd(f"fill {FX} 21 {FZ} {FX} 318 {FZ} stone")  # the build-limit pillar for A


def survivor(x, y, z, yaw, pitch, item=None):
    """Survival player, full health and food, empty inventory except one item in slot 1."""
    cmd("kill @e[tag=cam]", "gamemode survival " + PLAYER, "clear " + PLAYER, "effect clear " + PLAYER,
        f"effect give {PLAYER} instant_health 1 10 true", f"effect give {PLAYER} saturation 1 10 true",
        f"tp {PLAYER} {x} {y} {z} {yaw} {pitch}")
    if item:
        cmd(f"item replace entity {PLAYER} hotbar.0 with {item}")
    sleep(0.5)
    xdo("key", "--window", WIN, "1")


def ground(x, z, r=2):
    cmd(f"kill @e[type=minecraft:oak_boat]", f"fill {x - r} 21 {z - r} {x + r} 24 {z + r} air",
        f"fill {x - r} 20 {z - r} {x + r} 20 {z + r} grass_block")


def drop_take(name, spot, target_cmds=(), item=None, hold=2.0, during_fall=None, expect_survive=True,
              attempts=6):
    """Stand on an invisible barrier at DROP_Y looking straight down, remove it, record the fall.

    Keeps the first take where the outcome matches expect_survive (full health, or dead).
    """
    x, z = spot
    for attempt in range(1, attempts + 1):
        ground(x, z)
        cmd(*(target_cmds(x, z) if callable(target_cmds) else [c.format(x=x, z=z) for c in target_cmds]))
        cmd(f"setblock {x} {DROP_Y - 1} {z} barrier")
        survivor(x + 0.5, DROP_Y, z + 0.5, 0, 90, item)
        sleep(4)
        if health() != 20.0:
            sleep(2)
        tmp = clip(name) + ".take.mp4"
        w = LogWatch()
        rec_start = time.time()
        with Recorder(tmp):
            sleep(1.5)
            t_drop = time.time()
            cmd(f"setblock {x} {DROP_Y - 1} {z} air")
            if during_fall:
                during_fall(t_drop)
            sleep(max(0.0, t_drop + 2.75 + hold - time.time()))
        hp = health()
        dead = died(w.text())
        ok = (hp == 20.0 and not dead) if expect_survive else dead
        print(f"{name} take {attempt}: health={hp} died={dead} -> {'KEEP' if ok else 'retry'}", flush=True)
        if ok:
            os.replace(tmp, clip(name))
            RESULTS.append({"clip": name, "attempts": attempt, "drop_at": round(t_drop - rec_start, 2),
                            "landing_at": round(t_drop - rec_start + 2.7, 2), "health_after": hp, "died": dead})
            return True
        os.remove(tmp)
        sleep(2)
    print(f"{name}: no successful take", flush=True)
    RESULTS.append({"clip": name, "attempts": attempts, "failed": True})
    return False


# ---------------------------------------------------------------- shots

def a_freefall_hook():
    x, z = FX, FZ
    survivor(x + 0.5, 319, z + 0.5, -90, 50)
    sleep(5)
    rec_start = time.time()
    with Recorder(clip("A_freefall_hook")):
        sleep(3.0)  # take in the view from the top of the world
        xdo("keydown", "w")
        sleep(0.45)  # step off the edge
        xdo("keyup", "w")
        t_fall = time.time()
        elevator.look(0, 270, 0.9)  # look straight down as the ground rushes up
        sleep(max(0.0, t_fall + 5.2 - time.time()))  # stop ~1 s before impact
    cmd(f"tp {PLAYER} {x + 3.5} 22 {z + 3.5}")  # catch the player before the ground does
    RESULTS.append({"clip": "A_freefall_hook", "fall_from_y": 319, "step_off_at": round(t_fall - rec_start, 2),
                    "note": "ends ~1 s before impact; player is teleported to safety after recording"})


def b_splat():
    cmd("gamerule immediate_respawn false")
    sleep(1)
    drop_take("B_splat", SPOTS["B"], hold=3.2, expect_survive=False, attempts=1)
    shot = os.path.join(OUT, "death_screen.png")
    os.system(f"ffmpeg -loglevel error -y -f x11grab -video_size 720x1280 -i :99 -frames:v 1 {shot}")
    print("death screen saved to", shot, flush=True)


def water_clicks(t_drop):
    """Spam right-click around the one tick the ground is in reach (one click per tick at most)."""
    t = t_drop + 2.30
    while t < t_drop + 2.95:
        sleep(max(0.0, t - time.time()))
        xdo("click", "3")
        t += 0.068


def c_water_bucket():
    drop_take("C_water_bucket", SPOTS["C"], item="water_bucket", hold=2.0, during_fall=water_clicks, attempts=int(os.environ.get("ATTEMPTS", 12)))


def d_slime_block():
    drop_take("D_slime_block", SPOTS["D"], ["setblock {x} 20 {z} slime_block"], hold=4.5)


def e_cobweb():
    # Cobwebs are crossed vertical planes, invisible edge-on from straight above, so use a 3x3 patch two
    # high on a stone pad: the webs around the landing spot show in perspective as the ground comes up.
    drop_take("E_cobweb", SPOTS["E"], lambda x, z: [f"fill {x - 2} 20 {z - 2} {x + 2} 20 {z + 2} stone",
                                                    f"fill {x - 1} 21 {z - 1} {x + 1} 22 {z + 1} cobweb"],
              hold=2.5)


def f_powder_snow():
    drop_take("F_powder_snow", SPOTS["F"], ["setblock {x} 20 {z} powder_snow", "setblock {x} 21 {z} powder_snow"],
              hold=2.5)


def g_boat():
    drop_take("G_boat", SPOTS["G"], ['summon oak_boat {x}.5 21 {z}.5 {{Rotation:[0f,0f]}}'], hold=2.5, attempts=2)


def orbit_pose(cx, cy, cz, ang, r, h):
    """Camera on a circle around (cx, cy, cz) at angle ang (0 = north side), looking at the centre."""
    x = cx + r * math.sin(math.radians(ang))
    z = cz - r * math.cos(math.radians(ang))
    yaw = math.degrees(math.atan2(-(cx - x), cz - z))
    return x, cy + h, z, yaw, math.degrees(math.atan2(h, r))


def h_castle(n):
    x, z = 5300, 0
    build_castle(x, z, n, flat=True)  # one layer, so every diamond block can be counted from above
    cmd("time set 11900")  # the sun is setting in the west
    cx, cz = x + 6.5, z + 6.5
    # Start low on the east side looking west into the sunset, circle round the south side while rising,
    # then crane up to nearly overhead so all the diamonds are in view at the end.
    keys = [(0, *orbit_pose(cx, 21.5, cz, 95, 24, 6)), (6 * TPS, *orbit_pose(cx, 21.5, cz, 150, 20, 12)),
            (12 * TPS, *orbit_pose(cx, 21.5, cz, 215, 16, 18)), (18 * TPS, cx - 2.5, 41, cz, -90, 82)]
    set_gui(True)
    elevator.shoot("H_castle_60" if n == 60 else f"H_castle_{n}", camera_path(keys), 18.6)
    cmd("time set 6000")


SHOTS = {"A": a_freefall_hook, "B": b_splat, "C": c_water_bucket, "D": d_slime_block, "E": e_cobweb,
         "F": f_powder_snow, "G": g_boat}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("shots", nargs="*")
    ap.add_argument("--diamonds", type=int, default=60)
    ap.add_argument("--no-forest", action="store_true")
    args = ap.parse_args()
    OUT = elevator.OUT = args.out
    os.makedirs(OUT, exist_ok=True)
    write_pack()
    elevator.GUI_HIDDEN = False
    gamerules()
    if not args.no_forest:
        forest()
    for letter in args.shots or [*SHOTS, "H"]:
        print("shot", letter, flush=True)
        h_castle(args.diamonds) if letter == "H" else SHOTS[letter]()
    set_gui(False)
    cmd("gamemode spectator " + PLAYER, "gamerule immediate_respawn true")
    import json
    with open(os.path.join(OUT, "results.json"), "a") as f:
        for r in RESULTS:
            f.write(json.dumps(r) + "\n")
