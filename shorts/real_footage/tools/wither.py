"""Wither vs Warden: test fight, lineup, full fight with telemetry, aftermath, night castle.

Usage:
  python3 wither.py test                       (unrecorded, fast-forwarded check that they fight)
  python3 wither.py OUTDIR shoot [--slow 4] [--diamonds 187]

Honest fight: no effects, damage or kill commands while it runs. mob_griefing is off so the
Wither can't break the arena (it doesn't change combat damage). The Warden gets the dig cooldown a
naturally emerged Warden has. NoAI holds the Warden for the lineup only; the Wither spends the lineup
in its own invulnerable charge-up.
"""
import argparse
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elevator
import shotlib
from clutch import orbit_pose
from elevator import set_gui
from shotlib import FN, PLAYER, SERVER, Recorder, camera_path, cmd, reload, run, sleep, stop, write_pack
from shots import TPS, area, common

LOG = os.path.join(SERVER, "logs", "latest.log")
AX, AZ, SIZE, ROOF = 6300, 0, 50, 46  # floor x..x+49, z..z+49 at y=20; glass roof at y=46
CX, CZ = AX + SIZE / 2, AZ + SIZE / 2
WARDEN_Z, WITHER_Z = AZ + 14, AZ + 36
OUT = "."


def clip(name):
    return os.path.join(OUT, name + ".mp4")


def arena():
    area(CX, CZ, 64)
    common()
    cmd("gamerule mob_griefing false", "difficulty normal", "time set 6000", "weather clear",
        f"tp {PLAYER} {CX} {ROOF + 10} {AZ - 20}", "gamemode spectator " + PLAYER, "kill @e[tag=cam]")
    sleep(2)
    x0, z0, x1, z1 = AX - 1, AZ - 1, AX + SIZE, AZ + SIZE
    for y in range(21, ROOF + 1, 5):  # clear the volume in slabs (fill is capped at 32768 blocks)
        cmd(f"fill {x0 - 4} {y} {z0 - 4} {x1 + 4} {min(y + 4, ROOF)} {z1 + 4} air")
    cmd(f"fill {x0 - 4} 17 {z0 - 4} {x1 + 4} 19 {z1 + 4} dirt",
        f"fill {x0 - 4} 20 {z0 - 4} {x1 + 4} 20 {z1 + 4} grass_block",
        f"fill {AX} 20 {AZ} {AX + SIZE - 1} 20 {AZ + SIZE - 1} polished_deepslate",
        f"fill {AX + 2} 20 {AZ + 2} {AX + SIZE - 3} 20 {AZ + SIZE - 3} deepslate_tiles",
        f"fill {x0} 20 {z0} {x1} {ROOF} {z0} glass", f"fill {x0} 20 {z1} {x1} {ROOF} {z1} glass",
        f"fill {x0} 20 {z0} {x0} {ROOF} {z1} glass", f"fill {x1} 20 {z0} {x1} {ROOF} {z1} glass",
        f"fill {x0} {ROOF} {z0} {x1} {ROOF} {z1} glass")
    cmd("kill @e[type=wither]", "kill @e[type=warden]", "kill @e[type=wither_skull]", "kill @e[type=item]",
        "kill @e[type=experience_orb]")


def spawn(frozen_warden=True, invul=0, frozen_wither=False):
    ai = "1b" if frozen_warden else "0b"
    wai = "1b" if frozen_wither else "0b"
    cmd(f"summon warden {CX} 21 {WARDEN_Z} {{NoAI:{ai},PersistenceRequired:1b,Rotation:[0f,0f],"
        f"Tags:[\"fighter\"],Brain:{{memories:{{\"minecraft:dig_cooldown\":{{value:{{}},ttl:1200000L}}}}}}}}",
        f"summon wither {CX} 24 {WITHER_Z} {{NoAI:{wai},PersistenceRequired:1b,Rotation:[180f,0f],Invul:{invul},"
        f"Tags:[\"fighter\"]}}")


def state():
    """(warden_hp, wither_hp); 0.0 when that mob is gone."""
    pos = os.path.getsize(LOG)
    cmd("data get entity @e[type=warden,limit=1] Health", "data get entity @e[type=wither,limit=1] Health")
    deadline = time.time() + 1.5
    wa = wi = None
    while time.time() < deadline and (wa is None or wi is None):
        sleep(0.03)
        with open(LOG) as f:
            f.seek(pos)
            lines = [l.split("System chat: ", 1)[1] for l in f.read().splitlines() if "System chat: " in l]
        vals = []
        for l in lines:
            m = re.match(r"(Warden|Wither) has the following entity data: ([\d.]+)f", l)
            vals.append((m.group(1), float(m.group(2))) if m else ("none", 0.0) if "No entity" in l else None)
        vals = [v for v in vals if v]
        if len(vals) >= 2:
            a, b = vals[0], vals[1]
            wa = a[1] if a[0] == "Warden" else 0.0
            wi = b[1] if b[0] == "Wither" else 0.0
    return wa, wi


def setup_tracking():
    """Each tick: aim at the midpoint of the two fighters; the camera sits south of it, further back and
    higher the further apart they are; eased, and clamped inside the arena below the roof."""
    lo_x, hi_x = (AX + 1) * 100, (AX + SIZE - 1) * 100
    lo_z, hi_z = (AZ + 1) * 100, (AZ + SIZE - 1) * 100
    lo_y, hi_y = 2300, (ROOF - 1) * 100
    f = lambda name, lines: open(os.path.join(FN, "shot", name + ".mcfunction"), "w").write("\n".join(lines) + "\n")
    get = lambda who, axis, s: f"execute store result score {s} cam run data get entity @e[type={who},limit=1] Pos[{axis}] 100"
    f("wmid", [get("warden", 0, "#ax"), get("warden", 1, "#ay"), get("warden", 2, "#az"),
               get("wither", 0, "#bx"), get("wither", 1, "#by"), get("wither", 2, "#bz"),
               "scoreboard players add #ay cam 150",  # aim at the Warden's chest
               "scoreboard players operation #mx cam = #ax cam", "scoreboard players operation #mx cam += #bx cam",
               "scoreboard players operation #mx cam /= #two cam",
               "scoreboard players operation #my cam = #ay cam", "scoreboard players operation #my cam += #by cam",
               "scoreboard players operation #my cam /= #two cam",
               "scoreboard players operation #mz cam = #az cam", "scoreboard players operation #mz cam += #bz cam",
               "scoreboard players operation #mz cam /= #two cam",
               # separation (Manhattan) drives how far back and how high the camera sits
               "scoreboard players operation #sx cam = #ax cam", "scoreboard players operation #sx cam -= #bx cam",
               "execute if score #sx cam matches ..-1 run scoreboard players operation #sx cam *= #neg cam",
               "scoreboard players operation #sy cam = #ay cam", "scoreboard players operation #sy cam -= #by cam",
               "execute if score #sy cam matches ..-1 run scoreboard players operation #sy cam *= #neg cam",
               "scoreboard players operation #sz cam = #az cam", "scoreboard players operation #sz cam -= #bz cam",
               "execute if score #sz cam matches ..-1 run scoreboard players operation #sz cam *= #neg cam",
               "scoreboard players operation #sep cam = #sx cam", "scoreboard players operation #sep cam += #sy cam",
               "scoreboard players operation #sep cam += #sz cam"])
    f("solo", [  # only one fighter left: aim at it
        "execute if entity @e[type=warden] run " + get("warden", 0, "#mx"),
        "execute if entity @e[type=warden] run " + get("warden", 1, "#my"),
        "execute if entity @e[type=warden] run " + get("warden", 2, "#mz"),
        "execute if entity @e[type=wither] run " + get("wither", 0, "#mx"),
        "execute if entity @e[type=wither] run " + get("wither", 1, "#my"),
        "execute if entity @e[type=wither] run " + get("wither", 2, "#mz"),
        "scoreboard players set #sep cam 600"])
    ease = lambda tgt, cur, k: [f"scoreboard players operation #d cam = {tgt} cam",
                                f"scoreboard players operation #d cam -= {cur} cam",
                                f"scoreboard players operation #d cam /= {k} cam",
                                f"scoreboard players operation {cur} cam += #d cam"]
    clamp = lambda s, lo, hi: [f"execute if score {s} cam matches ..{lo} run scoreboard players set {s} cam {lo}",
                               f"execute if score {s} cam matches {hi}.. run scoreboard players set {s} cam {hi}"]
    lines = ["execute if entity @e[type=warden] if entity @e[type=wither] run function shots:shot/wmid",
             "execute unless entity @e[type=warden] run function shots:shot/solo",
             "execute unless entity @e[type=wither] run function shots:shot/solo",
             # back = 12 + 0.7*sep, up = 7 + 0.35*sep (in 1/100 blocks)
             "scoreboard players operation #back cam = #sep cam", "scoreboard players operation #back cam *= #seven cam",
             "scoreboard players operation #back cam /= #ten cam", "scoreboard players add #back cam 1200",
             "scoreboard players operation #up cam = #sep cam", "scoreboard players operation #up cam *= #seven cam",
             "scoreboard players operation #up cam /= #twenty cam", "scoreboard players add #up cam 700",
             "scoreboard players operation #tcx cam = #mx cam",
             "scoreboard players operation #tcy cam = #my cam", "scoreboard players operation #tcy cam += #up cam",
             "scoreboard players operation #tcz cam = #mz cam", "scoreboard players operation #tcz cam += #back cam"]
    lines += clamp("#tcx", lo_x, hi_x) + clamp("#tcy", lo_y, hi_y) + clamp("#tcz", lo_z, hi_z)
    lines += ease("#tcx", "#cx", "#k") + ease("#tcy", "#cy", "#k") + ease("#tcz", "#cz", "#k")
    lines += ease("#mx", "#fx", "#kf") + ease("#my", "#fy", "#kf") + ease("#mz", "#fz", "#kf")
    lines += [f"execute store result storage shots:cam {a} double 0.01 run scoreboard players get #{a} cam"
              for a in ("cx", "cy", "cz", "fx", "fy", "fz")]
    lines += ["function shots:shot/camtp with storage shots:cam"]
    f("track", lines)
    f("camtp", ["$tp @e[tag=cam,limit=1] $(cx) $(cy) $(cz) facing $(fx) $(fy) $(fz)"])
    mx, mz = int(CX * 100), int((WARDEN_Z + WITHER_Z) / 2 * 100)
    cmd("scoreboard players set #two cam 2", "scoreboard players set #neg cam -1",
        "scoreboard players set #seven cam 7", "scoreboard players set #ten cam 10",
        "scoreboard players set #twenty cam 20", "scoreboard players set #k cam 12", "scoreboard players set #kf cam 8",
        f"scoreboard players set #fx cam {mx}", "scoreboard players set #fy cam 2300", f"scoreboard players set #fz cam {mz}",
        f"scoreboard players set #cx cam {mx}", "scoreboard players set #cy cam 3600",
        f"scoreboard players set #cz cam {mz + 2400}")
    reload()
    sleep(1)


def fight(name, timeout=120):
    slow = shotlib.SLOW
    rows, events = [], []
    with Recorder(clip(name)) as rec:
        t0 = rec.started
        run("track")
        sleep(1.0 * slow)
        # Release the Wither to finish its invulnerable charge-up (it doesn't attack while charging, and its
        # end-of-charge explosion can't reach the Warden 22 blocks away). Release the Warden the moment the
        # charge-up ends, so both start the fight together.
        cmd("data merge entity @e[type=wither,limit=1] {NoAI:0b}")
        events.append((1.0, "wither_charge_start"))
        while True:
            pos = os.path.getsize(LOG)
            cmd("data get entity @e[type=wither,limit=1] Invul")
            sleep(0.12)
            with open(LOG) as fh:
                fh.seek(pos)
                m = re.findall(r"Wither has the following entity data: (-?\d+)", fh.read())
            if m and int(m[-1]) <= 0:
                cmd("data merge entity @e[type=warden,limit=1] {NoAI:0b}")
                events.append((round((time.time() - t0) / slow, 3), "fight_start"))
                break
        prev_wa, prev_wi, end_at, phase2 = 500.0, 300.0, None, False
        while True:
            t = (time.time() - t0) / slow
            wa, wi = state()
            if wa is None or wi is None:
                continue
            rows.append((round(t, 3), wa, wi))
            if not phase2 and 0 < wi <= 150:
                events.append((round(t, 3), "wither_phase2"))
                phase2 = True
            if wa == 0.0 and prev_wa > 0.0:
                events.append((round(t, 3), "warden_death"))
            if wi == 0.0 and prev_wi > 0.0:
                events.append((round(t, 3), "wither_death"))
            prev_wa, prev_wi = wa, wi
            if (wa == 0.0 or wi == 0.0) and end_at is None:
                end_at = t
            if end_at is not None and t - end_at > 3.0:
                break
            if end_at is None and t > timeout + 13.0:
                events.append((round(t, 3), "timeout"))
                end_at = t
                break
            sleep(0.25)
    stop()
    winner = "warden" if prev_wi == 0.0 and prev_wa > 0 else "wither" if prev_wa == 0.0 and prev_wi > 0 else "draw"
    ev = {}
    for t, e in events:
        ev.setdefault(t, []).append(e)
    with open(os.path.join(OUT, name + "_telemetry.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clip_time_s", "warden_health", "wither_health", "event"])
        for t, wa, wi in rows:
            w.writerow([t, wa, wi, ";".join(ev.get(t, []))])
    return winner, prev_wa, prev_wi, events, rows


def winner_pos(winner):
    pos = os.path.getsize(LOG)
    cmd(f"data get entity @e[type={winner},limit=1] Pos")
    sleep(0.8)
    with open(LOG) as f:
        f.seek(pos)
        m = re.findall(r"entity data: \[([-\d.]+)d, ([-\d.]+)d, ([-\d.]+)d\]", f.read())
    return tuple(float(v) for v in m[-1]) if m else (CX, 21.0, CZ)


def shoot(diamonds):
    arena()
    cmd(f"tp {PLAYER} {CX} 30 {AZ + 25}")
    sleep(2)
    # Lineup: the Wither's charge-up (Invul ticks count down while it glows and grows) runs through it
    spawn(frozen_warden=True, invul=220, frozen_wither=True)  # 220 ticks: the vanilla charge-up
    sleep(1)
    keys = [(0, CX + 10, 23, AZ + 25, 90, -5), (5 * TPS, CX + 4, 25.5, AZ + 25, 95, 2),
            (9 * TPS + 10, CX - 2, 22.5, WARDEN_Z - 5, 0, -6)]
    elevator.shoot("A_lineup", camera_path(keys), 9.5)
    setup_tracking()
    winner, wa, wi, events, rows = fight("B_fight")
    print("FIGHT", json.dumps({"winner": winner, "warden_hp": wa, "wither_hp": wi, "events": events,
                               "length": rows[-1][0]}), flush=True)
    if winner in ("warden", "wither"):
        x, y, z = winner_pos(winner)
        x, z = min(max(x, AX + 10), AX + SIZE - 10), min(max(z, AZ + 10), AZ + SIZE - 10)
        h = 5 if winner == "warden" else 4
        keys = [(0, *orbit_pose(x, y + 1.5, z, 200, 9, h)), (7 * TPS, *orbit_pose(x, y + 1.5, z, 290, 8, h))]
        elevator.shoot("C_aftermath", camera_path(keys), 7.3)
    if os.environ.get("NO_CASTLE") != "1":
        import clutch
        clutch.OUT = elevator.OUT
        clutch.h_castle_named(diamonds, f"D_castle_{diamonds}", final_overhead=True, night=True)
    return winner


def test(sprint_ticks=2400):
    arena()
    cmd(f"tp {PLAYER} {CX} 30 {AZ + 25}")
    sleep(2)
    spawn(frozen_warden=False, invul=0)
    sleep(1)
    cmd(f"tick sprint {sprint_ticks}")
    t0, log = time.time(), []
    while time.time() - t0 < 300:
        sleep(1.5)
        wa, wi = state()
        log.append((round(time.time() - t0, 1), wa, wi))
        print("test", log[-1], flush=True)
        if wa == 0.0 or wi == 0.0:
            break
    cmd("tick sprint stop", "kill @e[type=wither]", "kill @e[type=warden]", "kill @e[type=wither_skull]")


if __name__ == "__main__":
    if sys.argv[1] == "test":
        write_pack()
        test()
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("mode")
    ap.add_argument("--slow", type=int, default=4)
    ap.add_argument("--diamonds", type=int, default=187)
    a = ap.parse_args()
    OUT = elevator.OUT = a.out
    os.makedirs(OUT, exist_ok=True)
    shotlib.SLOW = a.slow
    # The Wither targets living entities: keep it from shooting at the camera stand
    shotlib.CAM_NBT = "Invisible:1b,Marker:1b,NoGravity:1b,Silent:1b,Invulnerable:1b,"
    write_pack()
    elevator.GUI_HIDDEN = os.environ.get("MC_GUI_HIDDEN") == "1"
    set_gui(True)
    shoot(a.diamonds)
