# Never Sleep in the Nether: real footage

All new clips from Minecraft Java Edition 26.3, signed in as the channel's own account
(Frontgate). The client ran Fabulously Optimized against an unmodded vanilla server. Clips are
first person, survival mode, **HUD visible** (except F), 720x1280, 30 fps, h264 (CRF 20), no audio.
Recorded with the smooth capture: the game ran at quarter speed while recording and each clip was
retimed 4x back to real speed. Clicks, key presses and looking around are real input (xdotool);
nothing in the explosions was scripted.

Times are from the start of each clip.

| Clip | What happens | Key moments |
| --- | --- | --- |
| `A_bed_boom.mp4` (6.5 s) | Nether crimson forest (230, 87, -224). First person, a red bed on the nylium in front of you, full hearts. A real right-click on the bed: it explodes, fire everywhere, and you die. | Click **2.5 s**, explosion **2.6 s**, death screen from **~3.5 s** |
| `B_death_screen.mp4` (4.0 s) | The real death screen held: **"You Died! Frontgate was killed by [Intentional Game Design]"** (exact 26.3 wording, also in the server log), with the burning crater behind it. | Whole clip |
| `C_crater.mp4` (8.1 s) | After respawning, back in the Nether a few blocks from where the bed was, full hearts. A slow look left and down over the burning crater, then a sweep right across the fire. | Look-around 1.0–6.2 s |
| `D_bed_mining.mp4` (14.1 s) | Y=15 in the Nether: a 3x3 tunnel dug into netherrack, with a bed at the end and three ancient debris hidden one block inside the walls around it. You stand behind a block on the floor and reach over it to right-click the bed. The blast hits you (**20 → 15.4 health**, about 2.3 hearts) but you survive. The crater opens up and the fire starts. You put out the fire in front of you (left-click), step to the edge, turn to the ancient debris the blast uncovered in the left wall, and mine it with a netherite pickaxe (Efficiency V). The other two debris stay visible in the crater walls. | Click/blast **1.6 s**, debris revealed as the smoke clears (~2–3 s), mining starts **~9.7 s** |
| `E_respawn_anchor.mp4` (7.6 s) | Crimson forest. You place a respawn anchor, switch to glowstone and right-click it 4 times (the anchor face lights up a step at a time), then right-click it with an empty hand. **"Respawn point set"** appears above the hotbar. | Place **0.8 s**, charges **2.0 / 2.8 / 3.5 / 4.2 s**, set **5.3 s** (message from ~5.5 s) |
| `F_castle_232.mp4` (5.3 s, HUD hidden) | Castle end card in daylight: from high over the gate down to straight overhead of the pile, with nothing covering it at the end. Exactly **232 diamond blocks**, counted in game (an 11x11 layer, a 10x10 layer, a 3x3 layer and 2 on top). | Overhead from ~3 s |

Notes:
- The D setup (tunnel, bed, debris placement) was built with commands; the bed click, the blast,
  putting out the fire, the step and the mining are real play. In an earlier unrecorded test, walking
  into the crater set the player on fire and they burned to death, which is why the recorded take
  steps only to the edge.
- Natural health regeneration was off, so the 15.4 health after the D blast is exactly what the
  explosion left.

Re-shoot with `../tools/nether.py OUTDIR [A C D E F] [--slow 4] [--diamonds N]`. A also records B.
