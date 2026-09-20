"""Original soundtrack for the demo video, synthesized from scratch (no samples, no licensing).

The arrangement follows the scene cuts in demo_video.SCENES: a soft open, a building pulse for the race, a chime when
Jev finishes, a thin drop for the honest finding, and a lift into the closing loop. Needs numpy.
Usage: python -m evals.demo_music --out music.wav [--duration 69]
Mux:   ffmpeg -i demo.mp4 -i music.wav -c:v copy -c:a aac -b:a 192k -shortest demo_with_music.mp4
"""

import argparse
import struct
from pathlib import Path
import wave

import numpy as np

SR, BPM = 44100, 112
BEAT = 60 / BPM
# scene starts in seconds: title, terminal, race, cost, repeat, finding, loop, guardrails
CUES = {"title": 0, "terminal": 6, "race": 11, "cost": 36, "repeat": 43, "finding": 49, "loop": 56, "close": 64}
CHORDS = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [48, 52, 55]), (55, [55, 59, 62])]  # Am F C G: bass, triad


def hz(note):
    return 440 * 2 ** ((note - 69) / 12)


def env(n, attack, release):
    a, r = int(attack * SR), int(release * SR)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, max(a, 1))
    e[n - r:] *= np.linspace(1, 0, max(r, 1))
    return e


def tone(freq, dur, kind="sine", attack=0.005, release=0.1):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "saw":
        w = 2 * ((t * freq) % 1) - 1
    elif kind == "square":
        w = np.sign(np.sin(2 * np.pi * freq * t)) * 0.6
    else:
        w = np.sin(2 * np.pi * freq * t)
    return w * env(n, attack, min(release, dur))


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


def kick():
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (48 * t + 90 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 14)


def hat(rng, open_=False):
    n = int((0.16 if open_ else 0.05) * SR)
    noise = rng.standard_normal(n)
    return (noise - lowpass(noise, 6)) * np.exp(-np.arange(n) / SR * (22 if open_ else 70)) * 0.35


def place(track, sound, at, gain=1.0):
    i = int(at * SR)
    if i < len(track):
        end = min(len(track), i + len(sound))
        track[i:end] += sound[:end - i] * gain


def chime(track, at):
    for k, note in enumerate((81, 88, 93)):  # bright rising ping when Jev finishes
        place(track, tone(hz(note), 0.9, "sine", 0.002, 0.8), at + k * 0.07, 0.22)


def render(duration):
    rng = np.random.default_rng(7)
    track = np.zeros(int(duration * SR))
    bars = int(duration / (BEAT * 4)) + 1
    for bar in range(bars):
        start = bar * BEAT * 4
        bass, triad = CHORDS[(bar // 2) % 4]
        sec = start
        in_title, in_term = sec < CUES["terminal"], sec < CUES["race"]
        in_race = CUES["race"] <= sec < CUES["repeat"]
        in_repeat = CUES["repeat"] <= sec < CUES["finding"]
        in_finding = CUES["finding"] <= sec < CUES["loop"]
        in_loop = CUES["loop"] <= sec < CUES["close"]
        closing = sec >= CUES["close"]
        # pad: always present, thinner in the finding scene
        for note in triad:
            place(track, lowpass(tone(hz(note + 12), BEAT * 4, "saw", 0.4, 0.6), 30) * 0.5, start, 0.09 if in_finding else 0.13)
        if closing and bar % 2 == 0 and start >= CUES["close"]:
            place(track, tone(hz(triad[0]), 4.5, "sine", 0.1, 3.5), start, 0.25)
        # bass and kick drive the race, cost and loop scenes
        if in_race or in_loop or in_repeat:
            for beat in range(4):
                at = start + beat * BEAT
                if not in_repeat:
                    place(track, kick(), at, 0.9)
                place(track, tone(hz(bass - 12 + (12 if beat % 2 else 0)), BEAT * 0.9, "sine", 0.01, 0.15), at + 0.0, 0.5)
        elif in_term:
            place(track, kick(), start, 0.5)
        # hats build through the terminal scene, run full through race, thin for repeat
        if not in_title and not in_finding:
            step = BEAT / 2
            for i in range(8):
                if in_term and i % 2:
                    continue
                if in_repeat and i % 4:
                    continue
                place(track, hat(rng, open_=(i % 4 == 3 and in_race)), start + i * step, 0.6 if in_race or in_loop else 0.4)
        # arpeggio: the melodic hook, sixteenth notes over the chord
        if in_race or in_loop or in_repeat or in_finding:
            for i in range(8 if in_finding else 16):
                note = triad[[0, 1, 2, 1][i % 4]] + (24 if in_loop else 12)
                place(track, tone(hz(note), BEAT / 4 * 0.9, "square" if in_race else "sine", 0.004, 0.08),
                      start + i * (BEAT / 2 if in_finding else BEAT / 4), 0.11 if in_race or in_loop else 0.09)
    chime(track, CUES["race"] + 9.1 / 20)  # Jev's time (9.1 s) at the race's 20x speed
    track *= np.minimum(1, np.minimum(np.arange(len(track)) / (1.5 * SR), (len(track) - np.arange(len(track))) / (2.5 * SR)))
    peak = np.max(np.abs(track))
    return track / peak * 0.85


def write(path, mono):
    data = (np.clip(mono, -1, 1) * 32767).astype("<i2")
    stereo = np.repeat(data[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(stereo.tobytes())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("demo_music.wav"))
    ap.add_argument("--duration", type=float, default=69.0)
    args = ap.parse_args()
    write(args.out, render(args.duration))
