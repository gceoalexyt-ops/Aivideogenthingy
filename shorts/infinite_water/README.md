# Short: Infinite Water, explained

`infinite_water_short.mp4`: a 38 s, 1080×1920, 30 fps vertical video with narration, captions, music and sound effects.
`make_short.py` builds it with no Minecraft assets. It needs no GPU and takes about a minute on a CPU.

The explanation scenes are drawn in code. The dig, pour, scoop, lava and outro scenes cut to real gameplay
recorded in **Luanti** (formerly Minetest), a free, open-source Minecraft-like game whose water follows the same
two-source rule. Those shots carry an on-screen "REAL GAMEPLAY · LUANTI" label so nobody mistakes them for
Minecraft. Set `NO_BROLL=1` to render the fully animated version.

## Upload details

**Title:** The 2×2 Hole That Gives You INFINITE Water 💧 #minecraft

**Description:**
Why does a 2×2 hole give you infinite water in Minecraft? When flowing water touches 2 or more source
blocks on its sides and sits on a solid block (or water), it becomes a new source block. Scoop one out
and its neighbors refill it right away. Lava doesn't do this by default.

Follow for more Minecraft mechanics explained in under a minute!
Gameplay footage recorded in Luanti, an open-source Minecraft-like game.
Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.

**Tags:** minecraft, minecraft tips, infinite water, minecraft mechanics, minecraft shorts, survival tips

## Rebuild

```bash
pip install pillow numpy kokoro-onnx soundfile   # plus ffmpeg
python shorts/infinite_water/make_short.py
```

## Re-record the gameplay

`broll/director.lua` is a Luanti mod that builds the island and films every shot (dig, pour, scoop, lava, orbit)
on a fixed timeline. `broll/record.py` runs Luanti on a virtual display and records it:

```bash
apt-get install minetest xvfb xdotool
mkdir -p ~/.minetest/worlds/short/worldmods/director    # world.mt: gameid = minetest_game
cp broll/director.lua ~/.minetest/worlds/short/worldmods/director/init.lua
Xvfb :99 -screen 0 720x1280x24 &  python3 broll/record.py
```

Then trim from the logged `START` time, crop off the debug line at the top and scale to 1080×1920 to get
`broll/luanti_broll.mp4`.
