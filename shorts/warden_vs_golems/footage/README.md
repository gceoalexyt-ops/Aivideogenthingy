# 1 Warden vs 10 Iron Golems, v2 (glass arena)

A re-shoot of `../` in a camera-friendly arena: 40x40 deepslate floor with **glass walls**, and
a fight camera that can't be blocked. The setup is otherwise the same: Minecraft Java 26.3, the
Frontgate account, the Fabulously Optimized client against an unmodded vanilla server. Clips are
720x1280, 30 fps, h264 (CRF 20), no audio, HUD hidden. `../D_castle_187.mp4` still applies.

## Result: the golems win, 4 of 10 left

| | Start | End |
| --- | --- | --- |
| Warden health | 500 | **0** (dies at **30.6 s** in `B_fight`) |
| Golems alive | 10 | **4** |
| Golems' combined health | 1000 | **310** (three at 100, one at 10) |

The Warden killed 6 golems, one about every 3.8 s (8.0, 11.8, 15.6, 19.3, 23.1, 26.8 s). It went
from 62.5 to 0 health in the last 3.8 s.

**Same honest rules:** no effects, damage or kill commands during the fight. The Warden got the
dig cooldown a naturally emerged Warden has (otherwise a `/summon`'d one burrows away within
seconds), and NoAI held everyone still for the lineup only, released 1.0 s into `B_fight`.

## Clips

| Clip | What happens |
| --- | --- |
| `A_lineup.mp4` (9.7 s) | Everyone frozen: the camera starts high behind the line of 10 golems, glides over them and ends facing the Warden. |
| `B_fight.mp4` (33.9 s, one continuous take) | AI released at **1.0 s**. Golem deaths at 8.0 / 11.8 / 15.6 / 19.3 / 23.1 / 26.8 s, Warden death at **30.6 s** (near the west glass wall), then 3 s of the survivors. Each tick the camera aims at the midpoint of the Warden and the golems within 7 blocks of it, eases towards a spot 11 blocks south and ~15 up (about 55° down), and is clamped inside the arena. Frames at every death were checked: the Warden and the golems on it are in frame each time. |
| `B_fight_telemetry.csv` | Every 0.25 s: `clip_time_s, warden_health, golems_alive, golems_total_health, event` (`golem_death` / `warden_death` on the reading where first seen). Clip time counts from the start of `B_fight.mp4`; server readings can lag the picture by up to ~0.3 s. |
| `C_aftermath.mp4` (7.7 s) | Slow orbit from above the wall line around the 4 survivors. |
