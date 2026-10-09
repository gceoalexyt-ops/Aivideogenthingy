"""1 Warden vs N Iron Golems: calibration, lineup, full fight with telemetry, aftermath, castle.

Usage:
  python3 warden.py calibrate N [N ...] [--runs R]   (server only, fast-forwarded, nothing recorded)
  python3 warden.py OUTDIR shoot N [--diamonds 187]   (records A, B, C, D)

Nothing in the recorded fight is rigged: no effects, no damage or kill commands while it runs.
NoAI is used only to hold everyone still for the lineup, then released before the fight.
"""
import argparse
import csv
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elevator
from elevator import build_castle, set_gui
from shotlib import (PLAYER, SERVER, Recorder, camera_path, cmd, define, reload, run, setup_camera, sleep, stop,
                     write_pack)
from shots import TPS, area, common
from clutch import orbit_pose

LOG = os.path.join(SERVER, "logs", "latest.log")
AX, AZ, SIZE = 6100, 0, 40  # arena floor x..x+39, z..z+39 at y=20 (v2: bigger, glass walls)
CX, CZ = AX + SIZE / 2, AZ + SIZE / 2
OUT = "."


def clip(name):
    return os.path.join(OUT, name + ".mp4")


def arena():
    area(CX, CZ, 48)
    common()
    cmd(f"tp {PLAYER} {CX} 45 {CZ - 25}", "gamemode spectator " + PLAYER, "kill @e[tag=cam]")
    sleep(2)
    x0, z0, x1, z1 = AX - 1, AZ - 1, AX + SIZE, AZ + SIZE
    for y in range(21, 37, 4):
        cmd(f"fill {x0 - 6} {y} {z0 - 6} {x1 + 6} {y + 3} {z1 + 6} air")
    cmd(f"fill {x0 - 6} 17 {z0 - 6} {x1 + 6} 19 {z1 + 6} dirt",
        f"fill {x0 - 6} 20 {z0 - 6} {x1 + 6} 20 {z1 + 6} grass_block",
        f"fill {AX} 20 {AZ} {AX + SIZE - 1} 20 {AZ + SIZE - 1} polished_deepslate",
        f"fill {AX + 2} 20 {AZ + 2} {AX + SIZE - 3} 20 {AZ + SIZE - 3} deepslate_tiles",
        f"fill {x0} 20 {z0} {x1} 25 {z1} glass hollow",  # glass walls: nothing can block the camera
        f"fill {AX} 20 {AZ} {AX + SIZE - 1} 20 {AZ + SIZE - 1} polished_deepslate",
        f"fill {AX + 2} 20 {AZ + 2} {AX + SIZE - 3} 20 {AZ + SIZE - 3} deepslate_tiles",
        f"fill {AX} 21 {AZ} {AX + SIZE - 1} 25 {AZ + SIZE - 1} air")
    cmd("kill @e[type=item]", "kill @e[type=iron_golem]", "kill @e[type=warden]", "kill @e[type=experience_orb]")


def lineup_positions(n):
    """Golems in rows on the south side, facing the Warden on the north side."""
    per_row = min(n, 10)
    pos = []
    for k in range(n):
        row, col = divmod(k, per_row)
        cnt = min(per_row, n - row * per_row)
        x = CX - (cnt - 1) * 1.25 + col * 2.5
        z = AZ + 28 - row * 2.6
        pos.append((x, z))
    return pos


def spawn(n, frozen):
    ai = "1b" if frozen else "0b"
    # A Warden from /summon lacks the dig cooldown a naturally emerged one gets, so it would burrow away
    # within seconds of a calm start. Give it that cooldown (no effect on health or damage).
    cmd(f"summon warden {CX} 21 {AZ + 13} {{NoAI:{ai},PersistenceRequired:1b,Rotation:[0f,0f],Tags:[\"fighter\"],"
        f"Brain:{{memories:{{\"minecraft:dig_cooldown\":{{value:{{}},ttl:1200000L}}}}}}}}")
    for x, z in lineup_positions(n):
        cmd(f"summon iron_golem {x:.2f} 21 {z:.2f} {{NoAI:{ai},PersistenceRequired:1b,Rotation:[180f,0f],"
            f"Tags:[\"fighter\"]}}")


def release():
    cmd("execute as @e[tag=fighter] run data merge entity @s {NoAI:0b}")


def state():
    """One synchronous reading: (golems_alive, warden_health or None)."""
    pos = os.path.getsize(LOG)
    cmd("execute if entity @e[type=iron_golem]", "data get entity @e[type=warden,limit=1] Health",
        "execute as @e[type=iron_golem] run data get entity @s Health")
    deadline = time.time() + 1.0
    golems = hp = None
    gh = []
    while time.time() < deadline and (golems is None or hp is None or len(gh) < golems):
        sleep(0.03)
        with open(LOG) as f:
            f.seek(pos)
            txt = f.read()
        m = re.search(r"Test passed[.,] [Cc]ount: (\d+)|Test failed", txt)
        if m:
            golems = int(m.group(1)) if m.group(1) else 0
        h = re.search(r"Warden has the following entity data: ([\d.]+)f", txt)
        if h:
            hp = float(h.group(1))
        elif m and re.search(r"No entity was found|Found no elements", txt):
            hp = 0.0
        gh = [float(x) for x in re.findall(r"Iron Golem has the following entity data: ([\d.]+)f", txt)]
    state.golem_health = round(sum(gh), 1) if golems is not None and len(gh) == golems else None
    return golems, hp


def calibrate(ns, runs, sprint_ticks=6000):
    arena()
    cmd("difficulty normal")
    results = []
    for n in ns:
        for r in range(runs):
            cmd("kill @e[type=iron_golem]", "kill @e[type=warden]", "kill @e[type=item]")
            sleep(1)
            spawn(n, frozen=False)
            sleep(0.5)
            t0 = time.time()
            cmd(f"tick sprint {sprint_ticks}")
            # sample while sprinting until one side is gone
            last = None
            while time.time() - t0 < 600:
                sleep(1.0)
                g, hp = state()
                last = (g, hp)
                if g == 0 or hp == 0.0:
                    break
            cmd("tick sprint stop")
            g, hp = state()
            winner = "golems" if hp == 0.0 else ("warden" if g == 0 else "unfinished")
            print(f"N={n} run={r + 1}: golems_left={g} warden_hp={hp} -> {winner} "
                  f"({time.time() - t0:.0f}s wall)", flush=True)
            results.append((n, winner, g, hp))
    cmd("kill @e[type=iron_golem]", "kill @e[type=warden]", "kill @e[type=item]", "kill @e[type=experience_orb]")
    return results


def shoot(n, diamonds, castle=True):
    arena()
    cmd("difficulty normal", "time set 6000")
    spawn(n, frozen=True)
    sleep(2)

    # A: lineup, camera glides from behind the golem ranks over to the Warden
    keys = [(0, CX + 9, 29.5, AZ + SIZE - 3, 160, 26), (4 * TPS, CX + 4, 28, AZ + 26, 195, 30),
            (9 * TPS + 10, CX - 1.5, 24.5, AZ + 19, 180, 8)]
    elevator.shoot("A_lineup", camera_path(keys), 9.5)

    # B: the fight. Each tick the camera aims at the midpoint of the Warden (weight 2) and the golems within
    # 7 blocks of it, eases towards a spot 11 blocks south and 16 up, and is clamped inside the arena.
    from shotlib import FN
    lo_x, hi_x, lo_z, hi_z = (AX + 1) * 100, (AX + SIZE - 1) * 100, (AZ + 1) * 100, (AZ + SIZE - 1) * 100
    f = lambda name, lines: open(os.path.join(FN, "shot", name + ".mcfunction"), "w").write("\n".join(lines) + "\n")
    f("addg", ["execute store result score #tx cam run data get entity @s Pos[0] 100",
               "execute store result score #tz cam run data get entity @s Pos[2] 100",
               "scoreboard players operation #gx cam += #tx cam", "scoreboard players operation #gz cam += #tz cam",
               "scoreboard players add #n cam 1"])
    f("mid", ["execute store result score #mx cam run data get entity @e[type=warden,limit=1] Pos[0] 200",
              "execute store result score #mz cam run data get entity @e[type=warden,limit=1] Pos[2] 200",
              "scoreboard players set #n cam 2", "scoreboard players set #gx cam 0", "scoreboard players set #gz cam 0",
              "execute at @e[type=warden,limit=1] as @e[type=iron_golem,distance=..7] run function shots:shot/addg",
              "scoreboard players operation #mx cam += #gx cam", "scoreboard players operation #mz cam += #gz cam",
              "scoreboard players operation #mx cam /= #n cam", "scoreboard players operation #mz cam /= #n cam"])
    f("track", ["execute if entity @e[type=warden] run function shots:shot/mid",
                # target camera spot, clamped to the arena interior
                "scoreboard players operation #tcx cam = #mx cam",
                "scoreboard players operation #tcz cam = #mz cam", "scoreboard players add #tcz cam 1100",
                f"execute if score #tcx cam matches ..{lo_x} run scoreboard players set #tcx cam {lo_x}",
                f"execute if score #tcx cam matches {hi_x}.. run scoreboard players set #tcx cam {hi_x}",
                f"execute if score #tcz cam matches ..{lo_z} run scoreboard players set #tcz cam {lo_z}",
                f"execute if score #tcz cam matches {hi_z}.. run scoreboard players set #tcz cam {hi_z}",
                # ease camera and look-at point towards their targets
                "scoreboard players operation #d cam = #tcx cam", "scoreboard players operation #d cam -= #cx cam",
                "scoreboard players operation #d cam /= #k cam", "scoreboard players operation #cx cam += #d cam",
                "scoreboard players operation #d cam = #tcz cam", "scoreboard players operation #d cam -= #cz cam",
                "scoreboard players operation #d cam /= #k cam", "scoreboard players operation #cz cam += #d cam",
                "scoreboard players operation #d cam = #mx cam", "scoreboard players operation #d cam -= #fx cam",
                "scoreboard players operation #d cam /= #kf cam", "scoreboard players operation #fx cam += #d cam",
                "scoreboard players operation #d cam = #mz cam", "scoreboard players operation #d cam -= #fz cam",
                "scoreboard players operation #d cam /= #kf cam", "scoreboard players operation #fz cam += #d cam",
                "execute store result storage shots:cam x double 0.01 run scoreboard players get #cx cam",
                "execute store result storage shots:cam z double 0.01 run scoreboard players get #cz cam",
                "execute store result storage shots:cam fx double 0.01 run scoreboard players get #fx cam",
                "execute store result storage shots:cam fz double 0.01 run scoreboard players get #fz cam",
                "function shots:shot/camtp with storage shots:cam"])
    f("camtp", ["$tp @e[tag=cam,limit=1] $(x) 36.5 $(z) facing $(fx) 21.6 $(fz)"])
    wx, wz = int(CX * 100), int((AZ + 13) * 100)
    cmd("scoreboard players set #k cam 10", "scoreboard players set #kf cam 6",
        f"scoreboard players set #mx cam {wx}", f"scoreboard players set #mz cam {wz}",
        f"scoreboard players set #fx cam {wx}", f"scoreboard players set #fz cam {wz}",
        f"scoreboard players set #cx cam {wx}", f"scoreboard players set #cz cam {wz + 1100}")
    reload()
    cmd("data merge entity @e[tag=cam,limit=1] {teleport_duration:2}")
    sleep(1)
    rows, events = [], []
    tele = os.path.join(OUT, "B_fight_telemetry.csv")
    rec = Recorder(clip("B_fight"))
    with rec:
        rec_start = time.time()
        run("track")
        sleep(1.0)
        release()
        t_release = time.time() - rec_start
        prev_g, prev_hp, end_at = n, 500.0, None
        while True:
            t_q = time.time() - rec_start
            g, hp = state()
            if g is None or hp is None:
                continue
            rows.append((round(t_q, 3), hp, g, state.golem_health))
            if g < prev_g:
                for _ in range(prev_g - g):
                    events.append((round(t_q, 3), "golem_death"))
            if hp == 0.0 and prev_hp > 0.0:
                events.append((round(t_q, 3), "warden_death"))
            prev_g, prev_hp = g, hp
            if (g == 0 or hp == 0.0) and end_at is None:
                end_at = time.time()
            if end_at and time.time() - end_at > 3.0:
                break
            if time.time() - rec_start > 600:
                events.append((round(t_q, 3), "timeout"))
                break
            sleep(max(0.0, 0.25 - (time.time() - rec_start - t_q)))
    stop()
    winner = "golems" if prev_hp == 0.0 else ("warden" if prev_g == 0 else "unfinished")
    with open(tele, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clip_time_s", "warden_health", "golems_alive", "golems_total_health", "event"])
        ev = {}
        for t, e in events:
            ev.setdefault(t, []).append(e)
        for t, hp, g, gh in rows:
            w.writerow([t, hp, g, "" if gh is None else gh, ";".join(ev.get(t, []))])
    print(f"FIGHT: N={n} winner={winner} golems_left={prev_g} warden_hp={prev_hp} "
          f"golems_total_health={rows[-1][3]} release_at={t_release:.2f}s length={rows[-1][0]:.1f}s", flush=True)

    # C: aftermath orbit of the winner(s)
    target = "@e[type=warden,limit=1]" if winner == "warden" else "@e[type=iron_golem]"
    pos = os.path.getsize(LOG)
    cmd(f"execute as {target} run data get entity @s Pos")
    sleep(0.8)
    with open(LOG) as f:
        f.seek(pos)
        pts = re.findall(r"entity data: \[([-\d.]+)d, ([-\d.]+)d, ([-\d.]+)d\]", f.read())
    if pts:
        tx = sum(float(p[0]) for p in pts) / len(pts)
        tz = sum(float(p[2]) for p in pts) / len(pts)
    else:
        tx, tz = CX, CZ
    tx, tz = min(max(tx, AX + 9), AX + SIZE - 9), min(max(tz, AZ + 9), AZ + SIZE - 9)
    # Orbit from above the wall line so the camera never passes through a wall
    keys = [(0, *orbit_pose(tx, 21.5, tz, 200, 8, 8)), (7 * TPS, *orbit_pose(tx, 21.5, tz, 280, 7.5, 7.5))]
    elevator.shoot("C_aftermath", camera_path(keys), 7.3)

    # D: castle with exactly `diamonds` blocks, sunset crane like the clutch castle
    if not castle:
        return winner
    import clutch
    clutch.OUT = elevator.OUT
    clutch.h_castle_named(diamonds, f"D_castle_{diamonds}", final_overhead=True)
    return winner


if __name__ == "__main__":
    if sys.argv[1] == "calibrate":
        ap = argparse.ArgumentParser()
        ap.add_argument("mode")
        ap.add_argument("ns", nargs="+", type=int)
        ap.add_argument("--runs", type=int, default=2)
        a = ap.parse_args()
        write_pack()
        calibrate(a.ns, a.runs)
    else:
        ap = argparse.ArgumentParser()
        ap.add_argument("out")
        ap.add_argument("mode")
        ap.add_argument("n", type=int)
        ap.add_argument("--diamonds", type=int, default=187)
        ap.add_argument("--no-castle", action="store_true")
        a = ap.parse_args()
        OUT = elevator.OUT = a.out
        os.makedirs(OUT, exist_ok=True)
        write_pack()
        elevator.GUI_HIDDEN = False  # a freshly launched client shows the HUD
        set_gui(True)
        shoot(a.n, a.diamonds, castle=not a.no_castle)
