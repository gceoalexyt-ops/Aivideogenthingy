"""Never walk into the Nether without gold: piglins, first person, HUD visible, survival, real input.

Usage: python3 piglins.py OUTDIR [A B C D E F] [--slow 4] [--diamonds 232]
"""
import argparse
import json
import math
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elevator
import nether as nb
import shotlib
from elevator import set_gui
from nether import N, S, look, nether_tp, query
from shotlib import PLAYER, SERVER, WIN, Recorder, cmd, sleep, write_pack, xdo

LOG = os.path.join(SERVER, "logs", "latest.log")
OUT = "."
RESULTS = {}
# A flat clearing in the crimson forest; the player faces east (+x) towards the piglins
X0, Y0, Z0 = 230, 87, -224
PX, PZ = X0 - 5, Z0
GROUP = [(X0 + 5, Z0 - 2), (X0 + 6, Z0), (X0 + 5, Z0 + 2), (X0 + 7, Z0 + 1)]


def clip(name):
    return os.path.join(OUT, name + ".mp4")


class HealthWatch(threading.Thread):
    """Polls the player's health while a clip records; notes when it drops (clip-time, game seconds)."""

    def __init__(self, rec):
        super().__init__(daemon=True)
        self.rec, self.stop_flag, self.samples = rec, False, []

    def run(self):
        pos = os.path.getsize(LOG)
        while not self.stop_flag:
            cmd(f"data get entity {PLAYER} Health")
            time.sleep(0.25 * shotlib.SLOW / 2)
            with open(LOG) as f:
                f.seek(pos)
                txt = f.read()
                pos = f.tell()
            t = (time.time() - self.rec.started) / shotlib.SLOW
            for m in re.finditer(rf"{PLAYER} has the following entity data: ([\d.]+)f", txt):
                self.samples.append((round(t, 2), float(m.group(1))))

    def hits(self):
        out, prev = [], None
        for t, h in self.samples:
            if prev is not None and h < prev - 0.01:
                out.append((t, round(prev - h, 1), h))
            prev = h
        return out


def record(name, body):
    xdo("key", "--window", WIN, "F3+d")  # clear chat so old messages don't show in the clip
    sleep(0.5)
    with Recorder(clip(name)) as rec:
        hw = HealthWatch(rec)
        hw.start()
        T = lambda: round((time.time() - rec.started) / shotlib.SLOW, 2)
        T.hw = hw
        marks = body(T) or {}
        hw.stop_flag = True
    marks["hits"] = hw.hits()
    marks["health_end"] = hw.samples[-1][1] if hw.samples else None
    RESULTS[name] = marks
    print(name, json.dumps(marks), flush=True)
    return marks


def clearing():
    cmd(N + f"forceload add {X0 - 24} {Z0 - 24} {X0 + 24} {Z0 + 24}")
    cmd("gamemode spectator " + PLAYER)
    nether_tp(PX + 0.5, Y0 + 3, PZ + 0.5, -90, 10)
    sleep(4)
    for xa in (X0 - 26, X0 - 8):
        cmd(N + f"fill {xa} {Y0} {Z0 - 8} {xa + 18} {Y0 + 6} {Z0 + 8} air",
            N + f"fill {xa} {Y0 - 3} {Z0 - 8} {xa + 18} {Y0 - 2} {Z0 + 8} netherrack",
            N + f"fill {xa} {Y0 - 1} {Z0 - 8} {xa + 18} {Y0 - 1} {Z0 + 8} crimson_nylium")
    # Clearing the space opened lava pockets in the terrain around it: turn nearby lava into netherrack
    for xa in range(X0 - 34, X0 + 18, 13):
        for ya in (Y0 - 6, Y0 + 2):
            cmd(N + f"fill {xa} {ya} {Z0 - 16} {xa + 12} {ya + 7} {Z0 + 16} netherrack replace lava")
    cmd(N + f"fill {X0 - 26} {Y0} {Z0 - 8} {X0 + 10} {Y0} {Z0 + 8} crimson_roots replace air",  # a few roots
        N + f"fill {X0 - 26} {Y0} {Z0 - 3} {X0 + 10} {Y0} {Z0 + 3} air")  # keep the walkway clear
    sleep(1)


def reset_scene(piglins=True, brute=False):
    cmd(N + f"kill @e[type=!player,x={X0},y={Y0},z={Z0},distance=..40]")  # clear old mobs, items, the camera
    sleep(0.5)
    if piglins:
        for x, z in GROUP:
            cmd(N + f"summon piglin {x + 0.5} {Y0} {z + 0.5} {{PersistenceRequired:1b,IsImmuneToZombification:1b,"
                    f"Rotation:[90f,0f]}}")
    if brute:
        cmd(N + f"summon piglin_brute {X0 + 4.5} {Y0} {Z0 + 0.5} {{PersistenceRequired:1b,IsImmuneToZombification:1b,"
                f"Rotation:[90f,0f]}}")
    sleep(0.5)


IRON = ["armor.chest iron_chestplate", "armor.legs iron_leggings", "armor.feet iron_boots"]


def player(items, x=None, helmet=None):
    """Survival player in iron armor (normal Nether gear), facing the piglins."""
    nether_tp((PX if x is None else x) + 0.5, Y0, PZ + 0.5, -90, 8)
    nb.survivor(items=items)
    for slot_item in IRON + ([f"armor.head {helmet}"] if helmet else []):
        slot, item = slot_item.split(" ", 1)
        cmd(f"item replace entity {PLAYER} {slot} with {item}")
    sleep(3)


def wait_hit(hw, timeout):
    """Wait (real time) until the first hit lands or `timeout` game seconds pass."""
    end = time.time() + S(timeout)
    while time.time() < end:
        if hw.hits():
            return True
        time.sleep(0.1)
    return False


def a_no_gold():
    reset_scene(piglins=False)
    player([(0, "iron_sword")], x=PX - 9, helmet="iron_helmet")  # start further back, no gold
    for x, z in GROUP[:3]:
        cmd(N + f"summon piglin {x + 0.5} {Y0} {z + 0.5} {{PersistenceRequired:1b,IsImmuneToZombification:1b,"
                f"Rotation:[90f,0f]}}")
    sleep(0.3)

    def body(T):
        sleep(S(0.6))
        m = {"walk": T()}
        xdo("keydown", "w")
        wait_hit(T.hw, 3.5)                   # walk towards them; they notice, charge and land the first hit
        xdo("keyup", "w")
        sleep(S(0.5))
        m["back_off"] = T()
        xdo("keydown", "s")                   # back off
        sleep(S(1.6))
        xdo("keyup", "s")
        return m
    record("A_no_gold_chase", body)


def b_gold_helmet():
    reset_scene()
    player([(0, "golden_helmet")], x=PX - 16)  # start ~21 blocks away, out of their sight

    def body(T):
        sleep(S(1.0))
        m = {"helmet_on": T()}
        xdo("click", "3")                    # right-click equips the gold helmet (armor bar fills a notch)
        sleep(S(1.0))
        m["walk"] = T()
        xdo("keydown", "w")
        sleep(S(5.6))                        # walk right up to them
        xdo("keyup", "w")
        m["arrive"] = T()
        look(-330, 0, 1.4)                   # look around among them
        look(660, 15, 2.0)
        sleep(S(0.6))
        return m
    record("B_gold_helmet", body)


def calm_scene(items, brute=False, piglins=True):
    """Gold helmet on first, then the piglins appear, so they never see the player without gold."""
    reset_scene(piglins=False)
    player(items, helmet="golden_helmet")
    cmd(N + f"kill @e[type=item,x={X0},y={Y0},z={Z0},distance=..40]")
    if piglins:
        for x, z in GROUP:
            cmd(N + f"summon piglin {x + 0.5} {Y0} {z + 0.5} {{PersistenceRequired:1b,IsImmuneToZombification:1b,"
                    f"Rotation:[90f,0f]}}")
    if brute:
        cmd(N + f"summon piglin_brute {X0 + 4.5} {Y0} {Z0 + 0.5} {{PersistenceRequired:1b,IsImmuneToZombification:1b,"
                f"Rotation:[90f,0f]}}")
    sleep(1.5)


def c_barter():
    calm_scene([(0, "gold_ingot 3")])
    xdo("keydown", "w")
    sleep(S(0.5))
    xdo("keyup", "w")
    sleep(2)

    def body(T):
        sleep(S(1.0))
        m = {"throws": []}
        for dx in (-60, 60, 60):
            look(dx, 0, 0.3)
            m["throws"].append(T())
            xdo("key", "--window", WIN, "q")  # throw one gold ingot towards the piglins
            sleep(S(0.6))
        look(-60, 20, 0.5)
        sleep(S(8.5))                         # they admire it (~6 s), then toss something back
        return m
    marks = record("C_barter", body)
    out = query(N + f"execute as @e[type=item,x={X0},y={Y0},z={Z0},distance=..14] run data get entity @s Item",
                f"data get entity {PLAYER} Inventory", wait=1.2)
    marks["items_after"] = [l for l in out if "entity data" in l][:12]
    print("C items", json.dumps(marks["items_after"]), flush=True)


def d_brute():
    calm_scene([(0, "iron_sword")], brute=True, piglins=False)

    def body(T):
        sleep(S(1.0))
        m = {"walk": T()}
        xdo("keydown", "w")
        wait_hit(T.hw, 3.0)                   # the brute attacks despite the gold helmet
        xdo("keyup", "w")
        m["back_off"] = T()
        xdo("keydown", "s")
        sleep(S(2.0))
        xdo("keyup", "s")
        sleep(S(1.2))
        return m
    record("D_brute", body)


def e_angry_gold():
    gx, gz = PX + 2, PZ + 1
    calm_scene([(0, "iron_pickaxe")])
    cmd(N + f"setblock {gx} {Y0} {gz} gold_block")
    nb.aim_at(gx + 0.5, Y0 + 0.5, gz + 0.5, 0.2)
    sleep(1)

    def body(T):
        sleep(S(1.2))
        m = {"mine_start": T()}
        xdo("mousedown", "1")                  # break the gold block in front of the piglins
        sleep(S(1.6))
        xdo("mouseup", "1")
        m["mine_end"] = T()
        look(0, -150, 0.6)                     # look up at the piglins
        wait_hit(T.hw, 3.0)
        m["back_off"] = T()
        xdo("keydown", "s")
        sleep(S(1.8))
        xdo("keyup", "s")
        sleep(S(0.6))
        return m
    record("E_angry_gold", body)
    out = query(N + f"execute if block {gx} {Y0} {gz} gold_block", wait=0.6)
    RESULTS["E_angry_gold"]["gold_block_still_there"] = [l for l in out if l.startswith("Test")]


def f_castle(n):
    from shotlib import camera_path
    from shots import TPS
    x, z = 5300, 0
    elevator.build_castle(x, z, n, flat=False)
    cmd("time set 11950")  # sunset
    cx, cz = x + 6.5, z + 6.5
    keys = [(0, cx + 14, 31, cz + 3, 95, 22), (3 * TPS, cx + 6, 37, cz + 1, 90, 60),
            (4.6 * TPS, cx + 0.8, 37.5, cz, 90, 89.5)]
    keys = [(int(t), *k) for t, *k in keys]
    set_gui(True)
    elevator.shoot(f"F_castle_{n}", camera_path(keys), 4.8)
    set_gui(False)
    cmd("time set 6000")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("shots", nargs="*")
    ap.add_argument("--slow", type=int, default=4)
    ap.add_argument("--diamonds", type=int, default=232)
    a = ap.parse_args()
    OUT = elevator.OUT = nb.OUT = a.out
    os.makedirs(OUT, exist_ok=True)
    shotlib.SLOW = a.slow
    write_pack()
    elevator.GUI_HIDDEN = os.environ.get("MC_GUI_HIDDEN") == "1"
    set_gui(False)
    cmd("difficulty normal", "gamerule natural_health_regeneration false", "gamerule keep_inventory true",
        "gamerule immediate_respawn true", "gamerule mob_griefing true", "gamerule spawn_mobs false",
        "gamerule spawn_monsters false")
    shots = a.shots or list("ABCDEF")
    if set(shots) & set("ABCDE"):
        clearing()
    for s, fn in (("A", a_no_gold), ("B", b_gold_helmet), ("C", c_barter), ("D", d_brute), ("E", e_angry_gold)):
        if s in shots:
            fn()
    if "F" in shots:
        f_castle(a.diamonds)
    json.dump(RESULTS, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print("RESULTS", json.dumps(RESULTS), flush=True)
