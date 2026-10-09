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
AX, AZ, SIZE = 6000, 0, 30  # arena floor x..x+29, z..z+29 at y=20
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
        f"fill {x0} 20 {z0} {x1} 25 {z1} deepslate_bricks hollow",
        f"fill {AX} 21 {AZ} {AX + SIZE - 1} 25 {AZ + SIZE - 1} air",
        f"fill {AX} 26 {AZ} {AX + SIZE - 1} 26 {AZ + SIZE - 1} air",  # no roof: keep the arena open to the camera
        f"fill {x0} 26 {z0} {x1} 26 {z0} polished_blackstone_brick_wall",
        f"fill {x0} 26 {z1} {x1} 26 {z1} polished_blackstone_brick_wall",
        f"fill {x0} 26 {z0} {x0} 26 {z1} polished_blackstone_brick_wall",
        f"fill {x1} 26 {z0} {x1} 26 {z1} polished_blackstone_brick_wall")
    # Lanterns on the walls so the arena reads well on camera
    for i in range(3, SIZE, 6):
        cmd(f"setblock {AX + i} 24 {AZ} lantern", f"setblock {AX + i} 24 {AZ + SIZE - 1} lantern",
            f"setblock {AX} 24 {AZ + i} lantern", f"setblock {AX + SIZE - 1} 24 {AZ + i} lantern")
    cmd("kill @e[type=item]", "kill @e[type=iron_golem]", "kill @e[type=warden]", "kill @e[type=experience_orb]")


def lineup_positions(n):
    """Golems in rows on the south side, facing the Warden on the north side."""
    per_row = min(n, 10)
    pos = []
    for k in range(n):
        row, col = divmod(k, per_row)
        cnt = min(per_row, n - row * per_row)
        x = CX - (cnt - 1) * 1.25 + col * 2.5
        z = AZ + SIZE - 8 - row * 2.6
        pos.append((x, z))
    return pos


def spawn(n, frozen):
    ai = "1b" if frozen else "0b"
    # A Warden from /summon lacks the dig cooldown a naturally emerged one gets, so it would burrow away
    # within seconds of a calm start. Give it that cooldown (no effect on health or damage).
    cmd(f"summon warden {CX} 21 {AZ + 7} {{NoAI:{ai},PersistenceRequired:1b,Rotation:[0f,0f],Tags:[\"fighter\"],"
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
    keys = [(0, CX + 9, 29.5, AZ + SIZE + 4, 160, 26), (4 * TPS, CX + 4, 28, CZ + 4, 195, 30),
            (9 * TPS + 10, CX - 1.5, 24.5, AZ + 13, 180, 8)]
    elevator.shoot("A_lineup", camera_path(keys), 9.5)

    # B: the fight. Camera pivots around the Warden (follows it every tick, interpolated client side).
    cmd("kill @e[tag=pivot]", f"summon marker {CX} 21 {AZ + 5} {{Tags:[\"pivot\"],Rotation:[180f,0f]}}")
    track = ['execute as @e[tag=pivot,limit=1] rotated as @s positioned as @e[type=warden,limit=1] '
             'run tp @s ~ ~ ~ ~0.25 0',
             'execute as @e[tag=pivot,limit=1] at @s run tp @e[tag=cam,limit=1] ^ ^12 ^-10 '
             'facing entity @e[type=warden,limit=1] feet']
    from shotlib import FN
    open(os.path.join(FN, "shot", "track.mcfunction"), "w").write("\n".join(track) + "\n")
    reload()
    cmd("data merge entity @e[tag=cam,limit=1] {teleport_duration:3}")
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
    tx, tz = min(max(tx, AX + 6), AX + SIZE - 6), min(max(tz, AZ + 6), AZ + SIZE - 6)
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
