import subprocess, time, threading, os
os.environ["DISPLAY"] = ":99"
for f in ("map.sqlite", "players.sqlite"):
    try: os.remove(f"/root/.minetest/worlds/short/{f}")
    except FileNotFoundError: pass
ff = subprocess.Popen(["ffmpeg","-loglevel","error","-y","-f","x11grab","-framerate","30","-video_size","720x1280","-i",":99",
                       "-c:v","libx264","-preset","ultrafast","-crf","12","/tmp/claude-0/rec.mkv"], stdin=subprocess.PIPE)
t_rec = time.monotonic()
def hide_hud():
    # wait for the game window, then press F1 (hide HUD) once it's in-game
    for _ in range(60):
        time.sleep(0.5)
        if "BUILT" in open("/tmp/claude-0/mt.log").read():
            break
    time.sleep(1.0)
    w = subprocess.run(["xdotool","search","--name","Minetest"], capture_output=True, text=True).stdout.split()
    print("windows", w)
    if w:
        subprocess.run(["xdotool","windowfocus","--sync",w[-1]])
        subprocess.run(["xdotool","key","--window",w[-1],"F1"])
open("/tmp/claude-0/mt.log","w").close()
threading.Thread(target=hide_hud, daemon=True).start()
mt = subprocess.run(["timeout","240","/usr/games/minetest","--go","--world","/root/.minetest/worlds/short","--name","director",
                     "--logfile","/tmp/claude-0/mt.log"], capture_output=True, text=True)
ff.communicate(b"q", timeout=30)
open("/tmp/claude-0/rec_start","w").write(str(t_rec))
print("rc", mt.returncode, mt.stderr[-300:])
