# Ecosystem sims ("who survives?" channel format)

`sim.py` is a small agent-based island. Rabbits wander, eat grass, breed when fed and flee foxes they
can see. Foxes chase the nearest visible rabbit, breed when fed and starve when they can't eat. Grass
regrows. Every boom, crash and extinction comes out of those rules; nothing is keyframed.

Each video folder holds a `make_short.py`, the rendered mp4 and an `upload.json`, which the
**Post to YouTube** workflow picks up. The narrator is Kokoro `am_onyx`.

## foxes_rabbits: "10 foxes vs 100 rabbits. Who survives?"

`foxes_rabbits/foxes_rabbits_short.mp4`: 16.4 s, 1080x1920, 30 fps. This is the real run for seed 0.
The rabbits boom, the foxes catch up and boom, the rabbits recover once, then the foxes eat the last
rabbit in year 23 and starve by year 30, so nobody survives. The narration lines are placed on those
events. The sub goal card reads "every 10 subs = a new species".

Re-render: `SEED=0 python ecosim/foxes_rabbits/make_short.py`
