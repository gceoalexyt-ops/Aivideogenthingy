"""Tiny toolkit for scripting real Minecraft shots through a local server.

A shot is a list of (tick, command) pairs compiled into a datapack function
that a tick-counter runs, so timing is exact game ticks. The camera is an
item_display with teleport interpolation that the player spectates, which
gives smooth motion between the 20 Hz server ticks.
"""
import json
import math
import os
import subprocess
import time

MC = os.path.expanduser("~/mc")
SERVER = os.path.join(MC, "server")
PACK = os.path.join(SERVER, "world", "datapacks", "shots")
FN = os.path.join(PACK, "data", "shots", "function")
PLAYER = "Frontgate"
DISPLAY = ":99"
WIN = os.environ.get("MC_WIN", "0x200033")


def cmd(*lines):
    with open(os.path.join(SERVER, "console.in"), "a") as f:
        for l in lines:
            f.write(l.strip().lstrip("/") + "\n")


def sleep(s):
    time.sleep(s)


def write_pack():
    os.makedirs(os.path.join(PACK, "data", "minecraft", "tags", "function"), exist_ok=True)
    os.makedirs(os.path.join(FN, "shot"), exist_ok=True)
    json.dump({"pack": {"description": "shots", "min_format": [121, 0], "max_format": [121, 0], "pack_format": 121}},
              open(os.path.join(PACK, "pack.mcmeta"), "w"))
    tags = os.path.join(PACK, "data", "minecraft", "tags", "function")
    json.dump({"values": ["shots:tick"]}, open(os.path.join(tags, "tick.json"), "w"))
    json.dump({"values": ["shots:load"]}, open(os.path.join(tags, "load.json"), "w"))
    open(os.path.join(FN, "load.mcfunction"), "w").write("scoreboard objectives add cam dummy\n")
    open(os.path.join(FN, "tick.mcfunction"), "w").write(
        "execute if score #on cam matches 1 run function shots:step with storage shots:cur\n")
    open(os.path.join(FN, "step.mcfunction"), "w").write(
        "$function shots:shot/$(name)\nscoreboard players add #t cam 1\n")


def ease(t):
    return t * t * (3 - 2 * t)


def lerp_angle(a, b, t):
    d = (b - a + 180) % 360 - 180
    return a + d * t


def camera_path(keys, start=0, smooth=True):
    """keys: [(tick, x, y, z, yaw, pitch), ...] -> per-tick camera teleports."""
    out = []
    for (t0, *a), (t1, *b) in zip(keys, keys[1:]):
        for t in range(t0, t1 + 1):
            u = (t - t0) / max(1, t1 - t0)
            u = ease(u) if smooth else u
            x, y, z = (a[i] + (b[i] - a[i]) * u for i in range(3))
            yaw, pitch = lerp_angle(a[3], b[3], u), a[4] + (b[4] - a[4]) * u
            out.append((start + t, f"tp @e[tag=cam,limit=1] {x:.3f} {y:.3f} {z:.3f} {yaw:.2f} {pitch:.2f}"))
    return out


def orbit(cx, cy, cz, radius, height, yaw0, yaw1, ticks, pitch=None, start=0):
    """Circle the point (cx, cy, cz), always facing it."""
    out = []
    for t in range(ticks + 1):
        u = ease(t / ticks)
        ang = math.radians(yaw0 + (yaw1 - yaw0) * u)
        # Minecraft yaw: 0 = +z (south), 90 = -x (west). Camera sits opposite its view direction.
        x = cx + radius * math.sin(ang)
        z = cz - radius * math.cos(ang)
        y = cy + height
        yaw = math.degrees(math.atan2(-(cx - x), cz - z))
        p = pitch if pitch is not None else math.degrees(math.atan2(height, radius))
        out.append((start + t, f"tp @e[tag=cam,limit=1] {x:.3f} {y:.3f} {z:.3f} {yaw:.2f} {p:.2f}"))
    return out


# An invisible armor stand: the client interpolates its position every frame, so a spectator riding it
# glides smoothly (an item_display camera stepped once per tick and looked shaky).
CAM_ENTITY = "armor_stand"
CAM_NBT = "Invisible:1b,Marker:1b,NoGravity:1b,Silent:1b,"


def setup_camera(x, y, z, yaw, pitch):
    cmd("kill @e[tag=cam]",
        "gamemode spectator " + PLAYER,
        f"tp {PLAYER} {x} {y} {z} {yaw} {pitch}",
        f"summon {CAM_ENTITY} {x} {y} {z} {{Tags:[\"cam\"],{CAM_NBT}Rotation:[{yaw}f,{pitch}f]}}")
    sleep(0.5)
    cmd(f"spectate @e[tag=cam,limit=1] {PLAYER}")


def define(name, events):
    name = name.lower()  # function ids must be lowercase
    lines = []
    for t, c in sorted(events, key=lambda e: e[0]):
        lines.append(f"execute if score #t cam matches {t} run {c.lstrip('/')}")
    open(os.path.join(FN, "shot", name + ".mcfunction"), "w").write("\n".join(lines) + "\n")


def reload():
    cmd("reload")
    sleep(2)


def run(name):
    name = name.lower()
    cmd("scoreboard players set #on cam 0", "scoreboard players set #t cam 0",
        f'data modify storage shots:cur name set value "{name}"', "scoreboard players set #on cam 1")


def stop():
    cmd("scoreboard players set #on cam 0")


SLOW = 1  # >1: record in slow motion (/tick rate 20/SLOW) and speed the video back up to real game speed


class Recorder:
    """Record the X display. With SLOW > 1 the game runs at 1/SLOW speed while recording and the
    clip is retimed to real game speed afterwards, so every output frame has SLOW times more rendering
    and interpolation behind it (much smoother camera motion). Game logic is unchanged, only slower."""

    def __init__(self, path, fps=30, slow=None):
        self.path, self.fps = path, fps
        self.slow = SLOW if slow is None else slow

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.raw = self.path + ".raw.mp4" if self.slow > 1 else self.path
        if self.slow > 1:
            cmd(f"tick rate {20 / self.slow:g}")
            time.sleep(0.4)
        self.p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-draw_mouse", "0", "-framerate", str(self.fps),
             "-video_size", "720x1280", "-i", DISPLAY, "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-pix_fmt", "yuv420p", "-an", self.raw], stdin=subprocess.PIPE)
        self.started = time.time()
        return self

    def __exit__(self, *a):
        self.p.communicate(b"q")
        if self.slow > 1:
            cmd("tick rate 20")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", self.raw, "-vf",
                            f"setpts=PTS/{self.slow},fps={self.fps}", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "16", "-pix_fmt", "yuv420p", "-an", self.path], check=True)
            os.remove(self.raw)


def record(path, seconds, before=None):
    with Recorder(path):
        if before:
            before()
        sleep(seconds)


def xdo(*args):
    subprocess.run(["xdotool", *args], env={**os.environ, "DISPLAY": DISPLAY}, check=False)
