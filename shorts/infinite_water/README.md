# Short: Infinite Water, explained

`infinite_water_short.mp4`: a 38 s, 1080×1920, 30 fps vertical video with narration, captions, music and sound effects.
`make_short.py` builds it from scratch with no game assets. It needs no GPU and takes about a minute on a CPU.

## Upload details

**Title:** The 2×2 Hole That Gives You INFINITE Water 💧 #minecraft

**Description:**
Why does a 2×2 hole give you infinite water in Minecraft? When flowing water touches 2 or more source
blocks on its sides and sits on a solid block (or water), it becomes a new source block. Scoop one out
and its neighbors refill it right away. Lava doesn't do this by default.

Follow for more Minecraft mechanics explained in under a minute!
Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.

**Tags:** minecraft, minecraft tips, infinite water, minecraft mechanics, minecraft shorts, survival tips

## Rebuild

```bash
pip install pillow numpy kokoro-onnx soundfile   # plus ffmpeg
python shorts/infinite_water/make_short.py
```
