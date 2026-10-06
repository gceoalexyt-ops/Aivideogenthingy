# Short: Name Tag Secrets

`name_tags_short.mp4`: 23.4 s, 1080×1920, 30 fps, first person. It loops: the last line ("So grab a name tag,
and") leads back into the first ("Name any mob Dinnerbone, and this happens."), and the last frame matches the first.

`make_short.py` reuses the first-person renderer from `../enderman/make_short.py`. It adds cow, sheep, rabbit
and vindicator models, an upside-down flip, a rainbow wool cycle, shearing with dropped wool, floating name
labels, and a hand holding a name tag or shears. It takes about 4 minutes on a CPU.

## Beats

| Time | Beat |
|---|---|
| 0 s | First person, name tag in hand, a cow in front of you |
| ~1 s | Named "Dinnerbone", it flips upside down ("UPSIDE DOWN!") |
| 3 s | "Grumm works too": a sheep flips |
| 4.5 s | "jeb_": a sheep cycles through every wool color |
| 8 s | Shear it, and it drops white wool, its real color |
| 10.5 s | "Toast": a brown rabbit gets the black-and-white memorial skin ("IN MEMORY OF TOAST ♥") |
| 15.5 s | "Johnny": a vindicator runs in and attacks the cow, then turns to the sheep |
| 19.5 s | Every named mob lined up: "✓ NEVER DESPAWN" |
| 22 s | Back to the opening shot: "So grab a name tag, and…" (loop) |

## Fact check

- "Dinnerbone" or "Grumm" renders any mob upside down.
- "jeb_" makes a sheep cycle through wool colors. Shearing still drops its original color.
- "Toast" gives a rabbit a special skin. It was added in memory of a player's lost pet rabbit.
- "Johnny" makes a vindicator attack almost any mob.
- Mobs named with a name tag don't despawn.

## Upload details

**Title:** Secret Name Tags in Minecraft 🏷️ #minecraft

**Description:**
Name a mob Dinnerbone and it flips upside down. jeb_ makes rainbow sheep, Toast gives rabbits a memorial
skin, and Johnny turns vindicators against everything. Plus: named mobs never despawn.
Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.

**Tags:** minecraft, minecraft shorts, name tag, dinnerbone, jeb_, minecraft secrets, minecraft easter eggs

**Pinned comment idea:** "What would you name your first pet? 🏷️"

## Rebuild

```bash
pip install pillow numpy kokoro-onnx soundfile   # plus ffmpeg
python shorts/name_tags/make_short.py
```
