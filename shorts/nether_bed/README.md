# Short: Never Sleep in the Nether

`nether_bed_short.mp4`: 15.7 s, 1080×1920, 30 fps. It's fully animated, with no game assets or footage, and it
loops: the last line ("Just remember,") leads straight back into the first ("Never sleep in the Nether.") and
the last frame matches the first.

## Retention design

| Time | Beat | Why |
|---|---|---|
| 0.0 s | Bed in the Nether, "NEVER SLEEP" on screen, slow push-in | Hook is a command plus a threat |
| ~0.9 s | Bed explodes: flash, shake, flying blocks, fire | Payoff before anyone can swipe |
| 1.5 s | TNT vs bed blast circles (power 4 vs 5) | New visual every 1-2 s |
| 4 s | "You Died!" with "[Intentional Game Design]" and a sad trombone | Real game joke, so people comment and share |
| 6.5 s | "But pros do this on purpose." with a riser | Open loop that holds people to the end |
| 8 s | X-ray: ancient debris is blast-proof, the bed drops in | Reveal |
| 10 s | Second explosion; 3 debris blocks survive, ×3 counter with dings | Reward |
| 12.5 s | Cost cards: bed ✓ vs TNT ✗ | Practical takeaway |
| 14.5 s | Hard cut back to the opening shot: "Just remember," | Seamless loop for rewatches |

## Upload details

**Title:** Never Sleep in the Nether 💀 #minecraft

**Description:**
Beds explode in the Nether and the End (power 5, bigger than TNT's 4), and the death message really is
"[Intentional Game Design]". But ancient debris is blast-proof, so pros blow up beds to find netherite.
Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.

**Tags:** minecraft, minecraft shorts, netherite, ancient debris, bed mining, minecraft facts, minecraft tips

**Pinned comment idea:** "What's the worst way you've died in Minecraft? 💀"

## Rebuild

```bash
pip install pillow numpy kokoro-onnx soundfile   # plus ffmpeg
python shorts/nether_bed/make_short.py
```
Uses the voxel renderer and voice helpers in `../infinite_water/make_short.py`.
