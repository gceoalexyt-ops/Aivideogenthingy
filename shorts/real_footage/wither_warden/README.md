# Wither vs Warden: real footage

All new clips from Minecraft Java Edition 26.3, signed in as the channel's own account
(Frontgate). The client ran Fabulously Optimized against an unmodded vanilla server, so all mob AI
and combat is vanilla. Clips are 720x1280, 30 fps, h264 (CRF 20), no audio, HUD hidden.
Recorded with the smooth capture: the game ran at quarter speed while recording and each clip was
retimed 4x back to real game speed. The camera rides an interpolated, invulnerable armor stand.

## Result: the Wither wins

| | At fight start (12.0 s) | End |
| --- | --- | --- |
| Warden health | 500 | **0** (dies at **88.6 s** in `B_fight`) |
| Wither health | 300 | **246** at the end of the clip (243 when the Warden died, regenerating after) |

The fight lasted **76.6 s**, from both being released (12.0 s) to the Warden's death (88.6 s). The
Wither never dropped below half health, so **phase 2 (wither armor) never triggered**.

**Notable moments** (from the telemetry):
- **Wither skull volleys:** from ~14 s the Warden loses about 8 health every 1–1.5 s, from skulls
  fired while the Wither hovers out of melee reach.
- **Warden sonic booms:** 12 of them. From **30.3 s** the Wither takes exactly 10 damage every
  ~5.1 s (30.3, 35.4, 40.5, 45.6, 50.7, 55.8, 60.9, 66.0, 71.1, 76.2, 81.3, 86.4 s), the Warden's
  ranged attack against a target it can't reach. In between, the Wither regenerates about
  1 health per second.
- **Charge-up:** 1.0 to 12.0 s. The Wither glows blue and grows, invulnerable, then bursts as the
  fight begins.

## How it was kept fair

- No effects, damage or kill commands during the fight.
- **mob_griefing was turned off**, so the Wither can't break the arena. This only affects blocks;
  combat damage is unchanged.
- The Warden got the dig cooldown a naturally emerged Warden has (otherwise a `/summon`'d Warden
  burrows away within seconds).
- NoAI froze both for the lineup only. In `B_fight` the Wither is released at 1.0 s to run its
  vanilla 11 s charge-up (invulnerable, not attacking; its end-of-charge explosion can't reach the
  Warden 22 blocks away). The Warden is released the moment the charge-up ends (12.0 s), so both
  start at full health. A first take was thrown out because the charge-up ended during the
  lineup, and the Wither hit the frozen Warden before the fight started.

## Clips

| Clip | What happens |
| --- | --- |
| `A_lineup.mp4` (9.6 s) | Both frozen, 22 blocks apart under the glass roof. Starts behind the glowing, charging Wither looking at the Warden, cranes up overhead and turns, ends behind the Warden facing the Wither. |
| `B_fight.mp4` (91.7 s, one continuous take) | 1.0 s: Wither charge-up starts. 12.0 s: both released (`fight_start`). Skull volleys, then sonic booms from 30.3 s. Warden death at **88.6 s** under the Wither, then 3 s more. The camera tracks the midpoint of the two, rising and pulling back as they separate, always inside the arena. Frames were checked at the charge, through the fight and at the death; both are in frame throughout. |
| `B_fight_telemetry.csv` | Every ~0.1 s of game time: `clip_time_s, warden_health, wither_health, event`. Events are `fight_start`, `warden_death` / `wither_death`, and `wither_phase2` (not triggered in this fight). The Wither's charge-up start (1.0 s) is noted here because sampling began at release. Clip time is game time from the start of `B_fight.mp4`, already accounting for the 4x retiming; readings can lag the picture by up to ~0.1 s. |
| `C_aftermath.mp4` (7.3 s) | The tracking camera follows the winning Wither around the empty arena. |
| `D_castle_187.mp4` (18.7 s) | Night: lanterns on the battlements and on the pile light the diamonds. Starts high above the gate and cranes down to the pile. Exactly **187 diamond blocks**, counted in game: an 11x11 layer, an 8x8 layer and 2 on top. The last 3 s are straight down over the pile, with no towers in frame. |

The arena is 50x50 with a deepslate floor, glass walls and a glass roof at y=46 (26 blocks up).
Re-shoot with `../tools/wither.py OUTDIR shoot [--slow 4] [--diamonds N]`. `../tools/wither.py test`
runs an unrecorded fast-forward check that they fight.
