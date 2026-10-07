# Real Minecraft footage

Raw clips recorded from vanilla Minecraft Java Edition 26.3, signed in with the
channel's own Microsoft account (Frontgate) and connected to a local server.
Each clip is 720x1280, 30 fps, h264 (CRF 20) with no audio and the HUD hidden (F1).
Times below are from the start of each clip.

| Clip | What happens |
| --- | --- |
| `a_water_hole.mp4` | Empty 2x2 hole; water poured in two opposite corners (~2.3 s, ~4.8 s) and the other two corners fill as sources. Slow orbit. |
| `b_lava_on_block.mp4` | Stone block in the air with a rim; lava placed on top at ~2.8 s. Orbit from above. |
| `c_dripstone.mp4` | Low angle under the block; pointed dripstone appears at ~2.8 s, then lava drip particles. |
| `d_cauldron_filling.mp4` | Cauldron placed at ~1.8 s under the dripping dripstone; it fills with lava naturally (random tick speed raised) around 5–8 s. |
| `e_full_cauldron.mp4` | Slow push-in on a full lava cauldron. |
| `f_farm_row.mp4` | Row of 5 farms; cauldrons fill one by one while the camera dollies along the row. |
| `g_furnace.mp4` | Furnace next to a lava cauldron; it's fuelled with a lava bucket at ~2.8 s and lights up. Push-in. |
| `h_dig_down.mp4` | First person, looking straight down, mining block after block from ~1 s to ~14 s. |
| `i_fall_into_lava.mp4` | First person, mining down; the floor breaks at ~3–4 s and the player falls into a lava cave. |
| `j_staircase.mp4` | Side cutaway: a 1x2 staircase mined down step by step, opening into a lava cave at ~11 s. |
| `k_obsidian.mp4` | Lava pool; water poured at ~2.8 s (lava hisses), water scooped back at ~6.8 s to reveal the obsidian. |
| `l_castle.mp4` | Stone-brick castle; camera cranes from the gate up over the wall (0–9 s) to the pile of exactly 19 diamond blocks. A corner tower covers part of the view in the last ~2 s. |

## How it was recorded

`tools/` holds the scripts. They keep the game in `~/mc`, outside the repo:

- `mcdl.py VERSION` downloads the client jar, Linux libraries and assets from Mojang.
- `mcauth.py` signs in with Microsoft's device code flow (the owner signs in at
  microsoft.com/link), then exchanges the token through Xbox Live, XSTS and Minecraft services.
  The token is saved to `~/mc/auth.json` and never printed.
- `mclaunch.py` starts the client under Xvfb with the Vulkan backend (Mesa lavapipe) and joins
  `localhost`, where the vanilla server runs in creative superflat.
- `shots.py OUTDIR [letters]` builds each scene with server console commands and runs a
  datapack tick timer. It records with `ffmpeg -f x11grab`. Camera moves come from a
  spectated `item_display` with teleport interpolation, and first-person mining is real mouse input via `xdotool`.
