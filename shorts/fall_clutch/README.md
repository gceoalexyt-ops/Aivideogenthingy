# Short: 4 Ways to Survive a 300-Block Fall (real Minecraft footage)

`fall_clutch_short.mp4`: 34.6 s, 1080×1920. It's cut entirely from real survival gameplay in `footage/`, with the
HUD visible so viewers can see the hearts. Every clutch was verified in game: full 20/20 health after
landing, with natural regeneration off.

| Beat | Clip |
|---|---|
| Hook: "You're falling from 300 blocks. You have five seconds. What do you place?" with a 5→1 countdown | A: stepping off the build limit |
| "Place nothing, and this happens." | B: real death screen, "fell from a high place" |
| #4 Powder snow, then SURVIVED ✓ ♥ 20/20 | F |
| #3 Cobweb, then SURVIVED ✓ | E |
| #2 Slime block (bounce), then SURVIVED ✓ | D |
| #1 Water bucket clutch, then SURVIVED ✓ | C |
| "Which one could you actually hit? Tell me in the comments." | D (the bounce) |
| Sub goal: 170 diamond blocks | H: castle at sunset, 170 blocks counted in game |

The boat clutch was tested and fails in 26.3 (you die), so it's left out.

## Upload details

**Title:** 4 Ways to Survive a 300 Block Fall 😱 #minecraft

**Description:**
Every clutch is tested in real survival, with full hearts after landing. Which one could you hit? 👇
(The boat clutch doesn't work anymore. We tested it.)
Sub goal: every new subscriber means one diamond block in my castle!

**Tags:** minecraft, minecraft shorts, mlg, water bucket clutch, minecraft clutch, minecraft tips, minecraft survival

**Pinned comment idea:** "We tested the boat clutch too, and it killed us both times 💀 Which one's your go-to?"

## Rebuild

`SUBS=<N> python shorts/fall_clutch/make_short.py` needs `footage/H_castle_<N>.mp4`. Re-shoot it with
`tools/clutch.py OUTDIR H --diamonds <N>` on the `claude/nice-galileo-7k9ihz` branch.
