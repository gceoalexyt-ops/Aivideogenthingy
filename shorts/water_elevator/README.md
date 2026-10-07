# Short: The Water Elevator (real Minecraft footage)

`water_elevator_short.mp4`: 30.4 s, 1080×1920, 30 fps. It's cut entirely from real gameplay in `footage/`,
recorded in vanilla Minecraft Java Edition 26.3 on the channel's own account (see `footage/README.md`).

| Beat | Clip | Label |
|---|---|---|
| "This launches you thirty blocks up, in seconds." | A: first-person launch up a 32-block tube | WATER ELEVATOR |
| Build a 1-wide tube of water sources | C: tube built, water poured (2× speed) | 1×1 TUBE + WATER |
| Soul sand at the bottom pushes you up | D: soul sand placed, bubble column starts | SOUL SAND = UP ↑ |
| "Thirty two blocks. Zero effort." | B: outside view riding up | 32 BLOCKS |
| A magma block drags you down | E: first person pulled down | MAGMA = DOWN ↓ |
| Kelp turns flowing water into source blocks | F: kelp stack placed and broken | KELP ➜ SOURCE WATER |
| Bubble columns refill your air | G: HUD visible, air bar refills | AIR REFILLS ✓ |
| Sub goal: 1 subscriber = 1 diamond block | H: castle with exactly 60 diamond blocks | counter up to 60 |

## Upload details

**Title:** Minecraft Water Elevator in 10 Seconds 🫧 #minecraft

**Description:**
Soul sand under a column of water launches you straight up. Magma pulls you down, kelp fills the tube with
source blocks in seconds, and you can't drown inside it.
Sub goal: every new subscriber means one diamond block in my castle!

**Tags:** minecraft, minecraft shorts, water elevator, bubble column, soul sand, minecraft tips, minecraft build

## Rebuild with a new subscriber count

1. Re-shoot the castle: `tools/elevator.py OUTDIR H --diamonds <N>` (on the `claude/nice-galileo-7k9ihz`
   branch, in the session that has Minecraft). Copy `H_castle_<N>.mp4` into `footage/`.
2. `SUBS=<N> python shorts/water_elevator/make_short.py`
