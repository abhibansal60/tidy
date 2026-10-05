# Jev confidence reel (35 s, 9:16)

Rendered video: `docs/assets/calibration/jev-confidence-reel.mp4`. Every number comes from `data.js`, exported from the
audit runs in `docs/research/jev-calibration-audit.md`; the two examples are real public dataset items.

```bash
npm i
node render.mjs --fps 60 --sub 2 --w 1080 --h 1920 --out out/silent.mp4
node cues.mjs > cues.json && node sfx.mjs cues.json out/sfx.wav
ffmpeg -y -i out/silent.mp4 -i out/sfx.wav -c:v copy -c:a aac -b:a 192k \
  -af "loudnorm=I=-14:TP=-1,volume=1.5dB,aresample=48000" -ar 48000 -shortest out/final.mp4
```

Shot list: `docs/shotlist.md`. Critique rounds: `docs/review_log.md`. Fonts: Inter and JetBrains Mono (SIL OFL).
