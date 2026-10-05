# Motion studio rules

## Render contract
- Every film is a pure function of time: `window.seek(t)` paints frame t.
- No CSS transitions, no setTimeout, no requestAnimationFrame in render mode, no state carried between frames. Seeded noise only (`rng(seed)` from motion.js), never Math.random.
- Easing is closed-form springs from motion.js. Tiny overshoot on UI, none on type. Any value with more than one target uses `track()`.
- Lay out against `W` and `H`, never fixed pixels, so 9:16, 1:1 and 16:9 come from one timeline.
- Render with `node render.mjs`, H.264 yuv420p, CRF 16.

## Look
- Banned defaults: centered title on gradient, everything fading in, corner labels and frame borders, glow on UI chrome, generic particle bursts.
- One display face, one UI face. One accent color unless the brief says otherwise.
- Every 2 to 4 seconds something new must happen on screen.

## Spring presets (k, d)
- Snappy (buttons, toggles, leading edges): 320, 30
- Default (cards, containers, camera): 170, 26
- Heavy (big type, 3D objects, logo lockups): 90, 20
- Playful (mascots, stickers, visible overshoot): 220, 12

## Sound
- Score and SFX are synthesized in code unless a track is supplied.
- Place hits on the beat grid (beats.json, or a fixed BPM). Loudness -14 LUFS.

## Loop before you show me anything
1. Render one frame per beat as a contact sheet and LOOK at it.
2. Score it 1-10 on: hook in first 2s, readability at phone size, motion quality, variety, brand accuracy, sound sync.
3. Fix the 3 worst problems. Repeat until every score is 8+.
4. Only then do the full render.
