"""Download a vanilla Minecraft client (jar, linux libraries, assets) into ~/mc."""
import concurrent.futures as cf
import hashlib
import json
import os
import sys
import urllib.request

ROOT = os.path.expanduser("~/mc")
VER = sys.argv[1]


def fetch(url, dest, sha1=None):
    if os.path.exists(dest) and sha1:
        with open(dest, "rb") as f:
            if hashlib.sha1(f.read()).hexdigest() == sha1:
                return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            if sha1 and hashlib.sha1(data).hexdigest() != sha1:
                raise ValueError("sha1 mismatch " + url)
            with open(dest + ".part", "wb") as f:
                f.write(data)
            os.replace(dest + ".part", dest)
            return True
        except Exception as e:
            if attempt == 4:
                raise
            print("retry", url, e, flush=True)


def allowed(rules):
    if not rules:
        return True
    ok = False
    for r in rules:
        os_ = r.get("os", {})
        if os_ and os_.get("name") not in (None, "linux"):
            continue
        if os_.get("arch") == "x86":
            continue
        if "features" in r:
            continue
        ok = r["action"] == "allow"
    return ok


v = json.load(open(os.path.join(ROOT, VER + ".json")))
jobs = []
c = v["downloads"]["client"]
jobs.append((c["url"], os.path.join(ROOT, "versions", VER, VER + ".jar"), c["sha1"]))
for lib in v["libraries"]:
    if not allowed(lib.get("rules")):
        continue
    a = lib.get("downloads", {}).get("artifact")
    if a:
        jobs.append((a["url"], os.path.join(ROOT, "libraries", a["path"]), a["sha1"]))
ai = v["assetIndex"]
idx_path = os.path.join(ROOT, "assets", "indexes", ai["id"] + ".json")
fetch(ai["url"], idx_path, ai["sha1"])
for name, o in json.load(open(idx_path))["objects"].items():
    h = o["hash"]
    jobs.append((f"https://resources.download.minecraft.net/{h[:2]}/{h}",
                 os.path.join(ROOT, "assets", "objects", h[:2], h), h))
lc = v.get("logging", {}).get("client", {}).get("file")
if lc:
    jobs.append((lc["url"], os.path.join(ROOT, "assets", "log_configs", lc["id"]), lc["sha1"]))

print(len(jobs), "files", flush=True)
done = 0
with cf.ThreadPoolExecutor(16) as ex:
    for f in cf.as_completed([ex.submit(fetch, *j) for j in jobs]):
        f.result()
        done += 1
        if done % 500 == 0:
            print(done, "/", len(jobs), flush=True)
print("DONE", flush=True)
