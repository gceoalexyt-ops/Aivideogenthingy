"""Install the Fabulously Optimized .mrpack into ~/mc/fo, plus the Fabric loader profile and libraries.

Usage: python3 foinstall.py PACK_DIR   (PACK_DIR = the unzipped .mrpack)
Every file listed in modrinth.index.json is checked against its sha512.
"""
import hashlib
import json
import os
import shutil
import sys
import urllib.request

ROOT = os.path.expanduser("~/mc")
GAME = os.path.join(ROOT, "fo")
pack = sys.argv[1]
index = json.load(open(os.path.join(pack, "modrinth.index.json")))
mc, loader = index["dependencies"]["minecraft"], index["dependencies"]["fabric-loader"]


def get(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


os.makedirs(GAME, exist_ok=True)
for f in index["files"]:
    dest = os.path.normpath(os.path.join(GAME, f["path"]))
    if not dest.startswith(GAME + os.sep):
        sys.exit("refusing path outside game dir: " + f["path"])
    data = get(f["downloads"][0])
    if hashlib.sha512(data).hexdigest() != f["hashes"]["sha512"]:
        sys.exit("sha512 mismatch: " + f["path"])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "wb").write(data)
    print("ok", f["path"], flush=True)

over = os.path.join(pack, "overrides")
if os.path.isdir(over):
    shutil.copytree(over, GAME, dirs_exist_ok=True)

# Fabric loader profile (libraries + main class) for this Minecraft version
prof = json.loads(get(f"https://meta.fabricmc.net/v2/versions/loader/{mc}/{loader}/profile/json"))
json.dump(prof, open(os.path.join(ROOT, f"fabric-{mc}-{loader}.json"), "w"), indent=1)
for lib in prof["libraries"]:
    g, a, v = lib["name"].split(":")[:3]
    path = f"{g.replace('.', '/')}/{a}/{v}/{a}-{v}.jar"
    dest = os.path.join(ROOT, "libraries", path)
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        data = get(lib.get("url", "https://maven.fabricmc.net/").rstrip("/") + "/" + path)
        if lib.get("sha1") and hashlib.sha1(data).hexdigest() != lib["sha1"]:
            sys.exit("sha1 mismatch: " + path)
        open(dest, "wb").write(data)
    print("lib", lib["name"], flush=True)
print("DONE", prof["mainClass"], flush=True)
