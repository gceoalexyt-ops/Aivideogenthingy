# Short: Never Look an Enderman in the Eyes

`enderman_short.mp4`: 19.5 s, 1080×1920, 30 fps, first-person. It loops: the last line ("So whatever you do,")
leads back into the first ("Never look an Enderman in the eyes."), and the last frame matches the first.

`make_short.py` includes a small software 3D renderer: ray-cast ground, dusk sky and clouds, textured blocks
and box-model mobs drawn with perspective-correct textures. Everything is drawn from scratch with no game
assets. It takes about 3 minutes on a CPU.

## Beats

| Time | Beat |
|---|---|
| 0 s | First-person view, an Enderman across the field, camera drifting up toward its eyes |
| 1.4 s | Eye contact: it shakes and screeches, then teleports into your face (jump scare) |
| 2.5 s | "Unless you're wearing this": a carved pumpkin spins in, then flies onto your head |
| 4 s | Pumpkin view: staring right at it, "STILL CALM ✓" |
| 9 s | "The catch? You can barely see": "✗ LIMITED VISION" |
| 10.5 s | "+2 TRICKS" |
| 11.5 s | It's 3 blocks tall (ruler) and can't follow you under a 2-block roof |
| 15 s | Water hurts it: it touches the pool and teleports away |
| 18.5 s | Cut back to the opening shot: "So whatever you do…" (loop) |

## Fact check

- Looking at an Enderman's head angers it.
- Wearing a carved pumpkin prevents that, and limits your view.
- Endermen are about 2.9 blocks tall, so they can't fit under a 2-block-high ceiling.
- Water damages them and makes them teleport.

## Upload details

**Title:** Never Look an Enderman in the Eyes 👀 #minecraft

**Description:**
Wear a carved pumpkin and Endermen won't get angry when you look at them. Plus 2 more tricks: hide under a
2-block roof, or stand in water.
Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.

**Tags:** minecraft, minecraft shorts, enderman, carved pumpkin, minecraft tips, minecraft facts, minecraft tricks

**Pinned comment idea:** "Has an Enderman ever stolen a block from your base? 😭"

## Rebuild

```bash
pip install pillow numpy kokoro-onnx soundfile   # plus ffmpeg
python shorts/enderman/make_short.py
```
