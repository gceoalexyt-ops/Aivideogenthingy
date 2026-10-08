# 5 ways to survive a 300-block fall: real footage

All new clips from vanilla Minecraft Java Edition 26.3, signed in as the channel's own account
(Frontgate). Clips are 720x1280, 30 fps, h264 (CRF 20), no audio. Everything is in **survival
mode with the HUD visible**, except H.

**Every clutch was verified in game.** Natural health regeneration was off
(`natural_health_regeneration false`), so the hearts can't refill after a landing.
Right after each landing the script read the player's Health from the server, and a take was
kept only if it was `20.0` (full) and the player didn't die. Each kept take below survived on its
first try.

Times are from the start of each clip. The clutch falls start on an invisible barrier block at
y=100, which is removed at the drop time, giving a real 79-block fall to the ground at y=21.
That fall takes 2.65 s in game. While the player stands on the barrier, its thin block outline
is visible below.

| Clip | Fall start | Placement | Landing | Health after |
| --- | --- | --- | --- | --- |
| `A_freefall_hook.mp4` (8.7 s) | Standing on a 1x1 pillar at the build limit (feet y=319), looking down past the pillar. Steps off (real W key) at **3.5 s**, then looks straight down (real mouse) | none | Clip ends at 8.7 s, about 1 s before impact (the forest is close) | n/a (player teleported to safety after recording) |
| `B_splat.mp4` (7.5 s) | 1.5 s | none | ~4.2 s, then the real death screen "You Died! Frontgate fell from a high place" holds to the end | 0 (died) |
| `C_water_bucket.mp4` (6.2 s) | 1.5 s | Water bucket placed by **real right-click** (xdotool), splash at **~3.9 s** | ~4.0–4.2 s, into the water | **20 / 20** |
| `D_slime_block.mp4` (8.8 s) | 1.5 s | Slime block already on the ground (visible below) | ~4.2 s, **bounces** back up and comes down again by the end | **20 / 20** |
| `E_cobweb.mp4` (6.8 s) | 1.5 s | 3x3 patch of cobwebs, 2 high, on a stone pad (single webs are invisible edge-on from straight above) | ~4.2 s, into the webs | **20 / 20** |
| `F_powder_snow.mp4` (6.8 s) | 1.5 s | Powder snow (2 deep) already on the ground | ~4.2 s, sinks into the snow (frost overlay) | **20 / 20** |
| `H_castle_170.mp4` (18.9 s, HUD hidden) | Sunset. Starts low, looking west at the castle against the setting sun, circles round while rising (0–12 s), then cranes up to nearly overhead (12–18.9 s) | | | |

**H:** exactly **170 diamond blocks** (the new sub goal), counted in game. 170 is too many for one
layer in the 11x11 courtyard, so they're an 11x11 layer with a centred 7x7 layer on top (121 + 49),
seen from nearly overhead at the end. Layouts work for any count up to 241.

**Skipped: G_boat.** In two takes, landing on a placed oak boat did **not** cancel fall damage
in 26.3: the player died ("fell from a high place") both times. No boat clip is included.

Re-shoot with `../tools/clutch.py OUTDIR [A B C D E F G H] [--diamonds N]`. The clutch takes
retry automatically until one survives at full health.
