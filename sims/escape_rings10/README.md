# One Ball. Ten Rings. Can It Escape? (physics-sim channel)

`escape_rings10_short.mp4`: 14.5 s, 1080x1920, 60 fps. No voiceover.

A ball starts inside ten nested rings, each spinning at its own speed and direction (alternating) with a
40° gap. It only touches the innermost ring still standing; getting through that ring's gap shatters it.
Bounces play *Für Elise* (Beethoven, public domain); every break adds a crash and a rising sting.
Seed 212 clears all ten rings in 11.1 s (36 bounces). Plain 2D physics, nothing keyframed.

**Sub goal:** the end card says every subscriber adds +1 ring to the next video. Render with
`SUBS=<count>` and the next video should use `N_RINGS = 10 + SUBS` (capped by what fits on screen).

`upload.json` holds the title, description and tags, and the Post to YouTube workflow uploads it
automatically (see `tools/youtube/README.md`).

Re-render: `SUBS=0 SEED=212 python sims/escape_rings10/make_short.py`
