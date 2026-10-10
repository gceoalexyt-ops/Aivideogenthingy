# Never walk into the Nether without gold: real footage

All new clips from Minecraft Java Edition 26.3, signed in as the channel's own account
(Frontgate). The client ran Fabulously Optimized against an unmodded vanilla server, so piglin AI,
bartering and combat are vanilla. Clips are first person, survival mode, **HUD visible** (except F),
720x1280, 30 fps, h264 (CRF 20), no audio. Recorded with the smooth capture: the game ran at
quarter speed and each clip was retimed 4x to real speed. Walking, clicking, throwing, mining and
looking around are real input (xdotool).

**Setup (agreed with the user):** the scene was staged with commands. A clearing was made in a
crimson forest at about (230, 87, -224), and lava in the terrain around it was turned to
netherrack after the first takes, when backing off ended in lava. Piglins and the brute were
summoned, and the player was given the items (iron armor as normal Nether gear, plus the gold
helmet, gold ingots and tools). Everything on camera after that is real gameplay and real piglin
behaviour. Times are from the start of each clip; "hit" times come from the player's health,
polled from the server about every 0.1 s.

| Clip | What happens | Key moments |
| --- | --- | --- |
| `A_no_gold_chase.mp4` (5.4 s) | Iron armor, **no gold**. You walk towards 3 piglins across the clearing; they notice, charge and attack; you back off. | Walk **0.6 s**, first hit **3.3 s** (20 → 17.5), back off **3.8 s** |
| `B_gold_helmet.mp4` (12.6 s) | You start about 20 blocks away, out of their sight, and right-click a **gold helmet** on (the armor bar ticks up). You walk right up to the 4 piglins and look around among them. **No attacks, full health throughout.** | Helmet on **1.0 s**, walk 2.0–7.6 s, look around 7.6 s+ |
| `C_barter.mp4` (13.1 s) | Gold helmet on. You throw 3 gold ingots (Q) one at a time towards the piglins. They pick them up, hold them up and admire them, then toss items back, which you pick up. **Barter results this take: 3 leather, 7 soul sand, 5 nether quartz.** | Throws **1.4 / 2.3 / 3.3 s**, admiring ~1.5–8 s, items tossed back ~7–10 s |
| `D_brute.mp4` (4.2 s) | Gold helmet on, a **piglin brute**: it attacks anyway (brutes ignore gold). You back off as soon as it hits. | Brute hits **1.0 s** (→ 12.4) and **3.5 s** (→ 8.7), back off from 1.0 s |
| `E_angry_gold.mp4` (6.6 s) | Gold helmet on, piglins calm. You mine a **gold block** in front of them with an iron pickaxe; they turn on you despite the helmet. You back off. **Works: mining gold angers them.** | Mining **1.2–2.8 s**, first hit **4.1 s** (→ 17.5), back off 4.15 s |
| `F_castle_232.mp4` (4.9 s, HUD hidden) | Sunset castle end card: low against the sunset, rising to straight overhead of the pile, with nothing covering it at the end. Exactly **232 diamond blocks**, counted in game. | Overhead from ~3.5 s |

Notes:
- A (5.4 s) and D (4.2 s) are shorter than the brief's 8–10 s and 6–8 s. With 3–4 piglins or a
  brute the fight escalates fast, and the clips end shortly after backing off so the player isn't
  killed on camera. In earlier takes without iron armor the player died within about 3 s.
- An earlier C take gave 10 blackstone and a fire charge; that take wasn't used because the player
  started it at low health.

Re-shoot with `../tools/piglins.py OUTDIR [A B C D E F] [--slow 4] [--diamonds N]`.
