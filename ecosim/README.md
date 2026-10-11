# Ecosystem sims ("who survives?" channel format)

`sim.py` is a small agent-based island. Rabbits wander, eat grass, breed when fed and flee foxes they
can see. Foxes chase the nearest visible rabbit, breed when fed and starve when they can't eat. Grass
regrows. Every boom, crash and extinction comes out of those rules; nothing is keyframed.

Each video folder holds a `make_short.py`, the rendered mp4 and an `upload.json`, which the
**Post to YouTube** workflow picks up. The narrator is Kokoro `am_onyx`.

## foxes_rabbits: "I put 100 rabbits on an island. Then I added 10 foxes."

`foxes_rabbits/foxes_rabbits_short.mp4`: 17.1 s, 1080x1920, 30 fps. This is the real run for seed 18, with the foxes dropped in after 2 years.
The edit follows the run's own events: an opening close-up that pulls back to the island, the foxes dropping in, a slow-motion cut of the longest real chase, a fast-forward, then the camera on the actual last rabbit until it's caught (year 13), then the foxes starving to nothing (year 20). The rabbits boom, the foxes catch up and boom, then the foxes eat the last
rabbit in year 23 and starve by year 30, so nobody survives. The narration lines are placed on those
events. The sub goal card reads "every 10 subs = a new species".

Re-render: `SEED=18 python ecosim/foxes_rabbits/make_short.py`
