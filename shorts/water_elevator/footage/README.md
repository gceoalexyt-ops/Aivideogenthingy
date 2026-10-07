# Bubble-column water elevator: real footage

All new clips from vanilla Minecraft Java Edition 26.3, signed in as the channel's own
account (Frontgate), with the same setup as `../README.md`. Each clip is 720x1280, 30 fps,
h264 (CRF 20) with no audio. The HUD is hidden (F1) except in G. Times are from the start
of each clip.

| Clip | What happens |
| --- | --- |
| `A_rocket_up.mp4` (11.7 s) | First person at the bottom of a 32-block glass tube full of water, looking straight up; tinted rings every 4 blocks show the speed. Soul sand goes in at **2.5 s**, bubbles erupt and launch the player. The player pops out the top at **~5.3 s** and looks down the tube at the oak trees far below (5.4–6.8 s), then bobs at the top. Real mouse input. |
| `B_outside_view.mp4` (11.5 s) | Outside the tube. The camera rides alongside a player mannequin (Frontgate skin) as it launches at **1.8 s** and rises to the top by **4.4 s**, then slowly orbits it bobbing out of the top. |
| `C_build_tube.mp4` (13.2 s) | The glass tube builds up one layer every 0.15 s from **1.0 s** to **3.9 s** while the camera cranes up. Water is poured at the top at **5.2 s** and flows down the tube to the bottom by ~12 s. |
| `D_soul_sand.mp4` (13.6 s) | Close-up at the bottom of a still-water tube. Soul sand appears at **2.8 s** and the upward bubble column starts; the camera cranes up with the bubbles. |
| `E_magma_down.mp4` (10.5 s) | First person at the top of a 16-block tube, looking down. Magma goes in at **1.5 s**, the whirlpool bubbles start and pull the player down onto the magma by ~3 s; the rest is the player held at the bottom (trim as needed). |
| `F_kelp_trick.mp4` (13.2 s) | Close-up of a tube of flowing water (single source at the top). Kelp is placed from the bottom up, one every 0.35 s, from **2.3 s** to **5.8 s**. The bottom kelp is broken at **7.7 s** and the whole stack breaks, leaving a tube full of still source water. The camera pulls back to show it. |
| `G_air_refill.mp4` (14.2 s) | **HUD visible.** First person diving into a sea-lantern-lit pool with a bubble column ahead. The air bar drains 8 → 2 bubbles (0–8.7 s) and the player swims forward (real W key) from **6.5 s**. They enter the column at **~8.7 s** and the air bar refills (9.5–11 s) with no health lost. |
| `H_castle_60.mp4` (18.6 s) | Stone-brick castle with **exactly 60 diamond blocks** inside (a 5×4×3 pile, counted in game). The camera cranes from the gate (0 s) up over the wall (8 s) and down to the diamonds (13 s+). No towers are in frame for the final 5 s. |

## Re-shooting

`../tools/elevator.py OUTDIR [A B C D E F G H] [--diamonds N]` reshoots any clip.
`--diamonds` sets the castle count. The pile is laid out as the neatest box that fits, or a
stepped pile, then counted in game before recording, and the run stops if the count is off.
For a count other than 60, the clip is saved as `H_castle_<N>.mp4`.
