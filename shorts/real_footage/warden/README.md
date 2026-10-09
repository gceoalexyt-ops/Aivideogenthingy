# 1 Warden vs 10 Iron Golems: real footage

All new clips from Minecraft Java Edition 26.3, signed in as the channel's own account
(Frontgate). The client ran the **Fabulously Optimized** modpack (15.0.0-alpha.5 from Modrinth,
Fabric, client-side performance mods only). The local server is unmodded vanilla 26.3, so all
mob AI and combat is vanilla. Clips are 720x1280, 30 fps, h264 (CRF 20), no audio, HUD hidden.

## Result: the golems win, 3 of 10 left

| | Start | End |
| --- | --- | --- |
| Warden health | 500 | **0** (dies at **31.6 s** in `B_fight`) |
| Golems alive | 10 | **3** |
| Golems' combined health | 1000 | **270** (two at 100, one at 70) |

The Warden killed 7 golems, almost one every 3.8 s (7.3, 11.0, 14.8, 18.6, 22.3, 26.1 and
30.1 s). With 300 combined health left, the golems finished it with 1.5 s to spare.

**Nothing was rigged.** No effects, damage or kill commands were used during the fight. There
was one setup tweak: a Warden spawned by `/summon` lacks the dig cooldown a naturally emerged
Warden gets, and in testing it burrowed away within 5 s of a calm start. It was given that
cooldown, which doesn't change its health or damage. NoAI held everyone still for the lineup
only and was released 1.0 s into `B_fight`.

For reference, an earlier take with 20 golems (not included) also ended with the golems
winning: 15 left, 1410 of 2000 combined health.

## Clips

| Clip | What happens |
| --- | --- |
| `A_lineup.mp4` (9.8 s) | Everyone frozen: the camera starts above the golems' wall, glides over the line of 10 golems and ends facing the Warden. |
| `B_fight.mp4` (34.9 s, one continuous take) | AI released at **1.0 s**. First hit on the Warden at ~3–4 s. The camera follows the Warden from 12 up and 10 back, slowly orbiting. Golem deaths at 7.3 / 11.0 / 14.8 / 18.6 / 22.3 / 26.1 / 30.1 s, Warden death at **31.6 s**, then 3 s of the survivors. Near the end the fight is against the east wall and the camera sits just outside it. |
| `B_fight_telemetry.csv` | Every 0.25 s: `clip_time_s, warden_health, golems_alive, golems_total_health, event`. `event` is `golem_death` or `warden_death` on the reading where it was first seen. Clip time counts from the start of `B_fight.mp4`; readings come from the server, so a value can lag the picture by up to ~0.3 s. |
| `C_aftermath.mp4` (7.6 s) | Slow orbit from above the wall line around the surviving golems. |
| `D_castle_187.mp4` (18.9 s) | Sunset crane like the clutch castle. Exactly **187 diamond blocks**, counted in game: an 11x11 layer, an 8x8 layer and 2 on top. The final 3 s are straight down over the pile, with no towers in frame. |

Re-shoot with `../tools/warden.py OUTDIR shoot N [--diamonds D] [--no-castle]`, or run unrecorded
fast-forward test fights with `../tools/warden.py calibrate N [N ...]`.
