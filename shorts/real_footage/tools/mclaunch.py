"""Launch the vanilla client from ~/mc with the saved Microsoft sign-in, joining localhost."""
import json
import os
import re
import sys

ROOT = os.path.expanduser("~/mc")
VER = "26.3"
GAME = os.path.join(ROOT, "game")
NATIVES = os.path.join(ROOT, "natives")
JAVA = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"
W, H = int(os.environ.get("MC_W", 720)), int(os.environ.get("MC_H", 1280))

OPTIONS = """rawMouseInput:false
pauseOnLostFocus:false
fullscreen:false
enableVsync:false
maxFps:60
inactivityFpsLimit:"minimized"
preferredGraphicsBackend:"vulkan"
onboardAccessibility:false
tutorialStep:none
skipMultiplayerWarning:true
joinedFirstServer:true
renderDistance:6
simulationDistance:6
graphicsPreset:"fast"
renderClouds:"false"
ao:true
entityShadows:false
biomeBlendRadius:0
mipmapLevels:0
particles:0
fov:0.0
bobView:false
narrator:0
soundCategory_master:0.0
showSubtitles:false
guiScale:3
"""


def allowed(rules):
    if not rules:
        return True
    ok = False
    for r in rules:
        os_ = r.get("os", {})
        if os_ and os_.get("name") not in (None, "linux"):
            continue
        if os_.get("arch") == "x86" or "features" in r:
            continue
        ok = r["action"] == "allow"
    return ok


v = json.load(open(os.path.join(ROOT, VER + ".json")))
auth = json.load(open(os.path.join(ROOT, "auth.json")))
os.makedirs(GAME, exist_ok=True)
for d in ("java", "jna", "lwjgl", "netty"):
    os.makedirs(os.path.join(NATIVES, d), exist_ok=True)
opt_path = os.path.join(GAME, "options.txt")
if not os.path.exists(opt_path):
    open(opt_path, "w").write(OPTIONS)

cp = [os.path.join(ROOT, "libraries", l["downloads"]["artifact"]["path"])
      for l in v["libraries"] if allowed(l.get("rules")) and "artifact" in l.get("downloads", {})]
cp.append(os.path.join(ROOT, "versions", VER, VER + ".jar"))

vars_ = {
    "auth_player_name": auth["name"], "version_name": VER, "game_directory": GAME,
    "assets_root": os.path.join(ROOT, "assets"), "assets_index_name": v["assetIndex"]["id"],
    "auth_uuid": auth["uuid"], "auth_access_token": auth["access_token"], "clientid": "",
    "auth_xuid": auth.get("xuid", ""), "version_type": "release", "natives_directory": NATIVES,
    "launcher_name": "shorts-recorder", "launcher_version": "1", "classpath": ":".join(cp),
    "resolution_width": str(W), "resolution_height": str(H),
}


def expand(items, features=()):
    out = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
            continue
        rules = it.get("rules", [])
        if any("features" in r for r in rules):
            if not all(any(f in features for f in r["features"]) for r in rules if "features" in r):
                continue
        elif not allowed(rules):
            continue
        val = it["value"]
        out.extend(val if isinstance(val, list) else [val])
    return [re.sub(r"\$\{(\w+)\}", lambda m: vars_.get(m.group(1), ""), a) for a in out]


jvm = ["-Xms1G", "-Xmx3G", "-XX:+UseZGC"] + expand(v["arguments"]["jvm"])
lc = v.get("logging", {}).get("client", {})
if lc:
    jvm.append(lc["argument"].replace("${path}", os.path.join(ROOT, "assets", "log_configs", lc["file"]["id"])))
game = expand(v["arguments"]["game"], ("has_custom_resolution",))
game += ["--quickPlayMultiplayer", os.environ.get("MC_SERVER", "localhost:25565")]
os.chdir(GAME)
os.execv(JAVA, [JAVA] + jvm + [v["mainClass"]] + game)
