# Short: Why Phantoms Keep Attacking You

`phantom_short.mp4`: 18.5 s, 1080×1920, 30 fps, first person, at night. It loops: the last line
("So tonight, go to bed. Otherwise,") leads back into the first ("These will hunt you every single night."),
and the last frame matches the first.

`make_short.py` reuses the first-person renderer from `../enderman/make_short.py`. It adds a night palette,
stars and a moon, and phantom, cat and bed models. It takes about 3 minutes on a CPU.

## Beats

| Time | Beat |
|---|---|
| 0 s | Night sky full of circling phantoms; one dives into your face |
| 2.3 s | "It's your fault": the camera drops to an unused bed |
| 4 s | Counter: nights without sleep 1, 2, 3, then phantoms spawn |
| 7.5 s | Walk to the bed, fade to black, wake up at sunrise: counter back to 0 ✓ |
| 10.5 s | "Dying resets it too": a "You Died!" screen, with "(just sleep)" |
| 13 s | A cat appears and the phantoms fly away |
| 15 s | Daylight: a phantom catches fire and burns up |
| 17 s | Back to the opening shot: "So tonight, go to bed. Otherwise…" (loop) |

## Fact check

- Phantoms spawn at night when you haven't slept for 3 or more in-game days.
- Sleeping in a bed resets that counter, and so does dying.
- Phantoms avoid cats.
- Phantoms burn in sunlight.

## Upload details

**Title:** Why Phantoms Keep Attacking You 👻 #minecraft

**Description:**
Phantoms only spawn if you haven't slept for 3 nights. Sleep once and the counter resets. Bonus: cats scare
them away, and they burn in daylight.
Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.

**Tags:** minecraft, minecraft shorts, phantom, minecraft tips, minecraft facts, minecraft mobs

**Pinned comment idea:** "How many nights have you gone without sleeping? 😴"

## Rebuild

```bash
pip install pillow numpy kokoro-onnx soundfile   # plus ffmpeg
python shorts/phantom/make_short.py
```
