"""Original soundtrack for the mail-cleanup demo, synthesized from scratch (no samples, no licensing).
Cues follow demo_mail_video.SCENES. Reuses demo_music.py's synthesis primitives. Needs numpy.

Usage: python -m evals.demo_mail_music --out music.wav
Mux:   ffmpeg -i mail_demo.mp4 -i music.wav -c:v copy -c:a aac -b:a 192k -shortest mail_demo_with_music.mp4
"""

import argparse
from pathlib import Path

import numpy as np

from evals.demo_music import CHORDS, SR, hat, hz, kick, lowpass, place, tone, write

BPM = 100
BEAT = 60 / BPM
# title(0-6) team(6-13) sorting(13-21) cost(21-27) result(27-32.5) close(32.5-36)
CUES = {"title": 0, "team": 6, "sorting": 13, "cost": 21, "result": 27, "close": 32.5, "end": 36}


def chime(track, at):
    for k, note in enumerate((81, 88, 93)):  # bright rising ping when the cost figure lands
        place(track, tone(hz(note), 0.9, "sine", 0.002, 0.8), at + k * 0.07, 0.2)


def render(duration=36.0):
    rng = np.random.default_rng(11)
    track = np.zeros(int(duration * SR))
    bars = int(duration / (BEAT * 4)) + 1
    for bar in range(bars):
        start = bar * BEAT * 4
        bass, triad = CHORDS[(bar // 2) % 4]
        in_title = start < CUES["team"]
        in_team = CUES["team"] <= start < CUES["sorting"]
        in_sorting = CUES["sorting"] <= start < CUES["cost"]
        in_cost = CUES["cost"] <= start < CUES["result"]
        in_result = CUES["result"] <= start < CUES["close"]
        closing = start >= CUES["close"]
        # pad: always present, thinner during the cost reveal so the chime and number land clean
        for note in triad:
            place(track, lowpass(tone(hz(note + 12), BEAT * 4, "saw", 0.4, 0.6), 30) * 0.5, start,
                 0.08 if in_cost else 0.13)
        if closing and bar % 2 == 0:
            place(track, tone(hz(triad[0]), 4.5, "sine", 0.1, 3.5), start, 0.22)
        # kick + bass drive the sorting scene (matches the flying-dot animation's energy)
        if in_sorting or in_result:
            for beat in range(4):
                at = start + beat * BEAT
                if in_sorting:
                    place(track, kick(), at, 0.85)
                place(track, tone(hz(bass - 12 + (12 if beat % 2 else 0)), BEAT * 0.9, "sine", 0.01, 0.15), at, 0.45)
        elif in_team:
            place(track, kick(), start, 0.4)
        # hats: build through team, full through sorting, thin for cost/result
        if not in_title:
            step = BEAT / 2
            for i in range(8):
                if in_team and i % 2:
                    continue
                if (in_cost or in_result) and i % 4:
                    continue
                place(track, hat(rng, open_=(i % 4 == 3 and in_sorting)), start + i * step,
                     0.55 if in_sorting else 0.35)
        # arpeggio hook over the chord
        if in_sorting or in_team or in_result:
            for i in range(16):
                note = triad[[0, 1, 2, 1][i % 4]] + (12 if in_sorting else 0)
                place(track, tone(hz(note), BEAT / 4 * 0.9, "square" if in_sorting else "sine", 0.004, 0.08),
                     start + i * (BEAT / 4), 0.1 if in_sorting else 0.08)
    chime(track, CUES["cost"] + 1.4)  # the $0.45 figure lands at cost scene + ~1.4s ease-in
    track *= np.minimum(1, np.minimum(np.arange(len(track)) / (1.2 * SR), (len(track) - np.arange(len(track))) / (2.0 * SR)))
    peak = np.max(np.abs(track))
    return track / peak * 0.85


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("mail_demo_music.wav"))
    ap.add_argument("--duration", type=float, default=36.0)
    args = ap.parse_args()
    write(args.out, render(args.duration))
