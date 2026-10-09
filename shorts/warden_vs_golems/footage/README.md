# 1 Warden vs 10 Iron Golems, v3 (smooth)

The v2 setup (40x40 glass arena, tracking camera, same honest rules) re-recorded with
**smooth capture**. This is a new real fight, so its result is its own. Clips are 720x1280,
30 fps, h264 (CRF 20), no audio, HUD hidden. `../D_castle_187.mp4` still applies.

**What changed for smoothness:**
- **Slow-motion capture:** the game ran at quarter speed (`/tick rate 5`) while recording, and
  each clip was then sped back up 4x to real game speed. Game logic and the fight are unchanged,
  just slower in real time, but every output frame has 4x more rendering behind it.
- **Smoother camera entity:** the camera rides an invisible armor stand, whose position the client
  interpolates every frame. The old item-display camera stepped once per game tick.

Measured with `../../tools/shake.py` (duplicate frames are frames where the picture froze while
the camera was moving):

| Clip | v2 duplicate frames | v3 duplicate frames | v2 jitter p95 | v3 jitter p95 |
| --- | --- | --- | --- | --- |
| A_lineup | 25.6% | **0.0%** | 13.2 px | **3.9 px** |
| B_fight | 4.6% | **1.6%** | 4.0 px | **2.8 px** |

## Result: the golems win, 3 of 10 left

| | Start | End |
| --- | --- | --- |
| Warden health | 500 | **0** (dies at **32.8 s** in `B_fight`) |
| Golems alive | 10 | **3** |
| Golems' combined health | 1000 | **270** (100, 100, 70) |

The Warden killed 7 golems, about one every 3.8 s (8.2, 12.0, 15.8, 19.6, 23.4, 27.2, 31.0 s).
After the 7th kill it had 9.5 health left and died 1.8 s later. Same rules as before: no effects,
damage or kill commands during the fight, the Warden got its natural dig cooldown, and NoAI was
used for the lineup only, released 1.0 s into `B_fight`.

| Clip | What happens |
| --- | --- |
| `A_lineup.mp4` (9.6 s) | Everyone frozen: high behind the line of golems, gliding over them to face the Warden. |
| `B_fight.mp4` (35.9 s, one continuous take) | AI released at **1.0 s**. Golem deaths at the times above, Warden death at **32.8 s** (near the north glass wall), then 3 s of the survivors. Frames at every death were checked; the action is in frame each time. |
| `B_fight_telemetry.csv` | Every ~0.06 s of game time: `clip_time_s, warden_health, golems_alive, golems_total_health, event`. Clip time is game time from the start of `B_fight.mp4` (it already accounts for the 4x retiming); readings can lag the picture by up to ~0.1 s. |
| `C_aftermath.mp4` (7.4 s) | Slow orbit from above the wall line around the 3 survivors. |
