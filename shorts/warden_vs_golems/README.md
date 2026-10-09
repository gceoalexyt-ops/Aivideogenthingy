# Short: 1 Warden vs 10 Iron Golems (real, unrigged fight)

`warden_short.mp4`: 34.7 s, 1080×1920. It's cut from a real fight in Minecraft Java Edition on the
channel's account: vanilla server, vanilla AI, and no effects, damage or kill commands
(see `footage/README.md`). **Result: the iron golems win, 4 of 10 survive.** The Warden killed 6, about one every 3.8 s.

The fight's telemetry (`footage/B_fight_telemetry.csv`) drives the narration, the Warden health
bar, the golem counter, the speed ramps (up to 2.6×) and the slow-motion finish. If the fight is
re-shot, the video re-renders with the new real result.

| Beat | What's on screen |
|---|---|
| Hook | Lineup with "1 WARDEN VS 10 IRON GOLEMS" and "Comment who you think wins!" |
| Fight | Live health bar, 10 golem icons crossed off with a "-1 GOLEM" pop per death, speed tags |
| Climax | "Four golems left, and the Warden has 57 health!", then slow-mo, flash and shake on the kill |
| Verdict | "IRON GOLEMS WIN", then "Did you guess right?" |
| Sub goal | Castle with 187 diamond blocks, counted in game |

## Upload details

**Title:** 1 Warden vs 10 Iron Golems… Who Wins? 😳 #minecraft

**Description:**
A real, unrigged fight: vanilla Minecraft, no commands. Did you guess right? 👇
Sub goal: every new subscriber means one diamond block in my castle!

**Tags:** minecraft, minecraft shorts, warden, iron golem, minecraft mob battle, warden vs iron golem, who would win

**Pinned comment:** "How many golems do you think it takes to beat the Warden? Next video we test it 👀"

## Rebuild

`SUBS=<N> python shorts/warden_vs_golems/make_short.py` needs `footage/D_castle_<N>.mp4`.
