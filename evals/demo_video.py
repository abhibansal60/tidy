"""Render the ~50 s Tidy demo video (MP4) straight from the stored eval results. No channel names appear.

Needs Pillow and imageio-ffmpeg (not project dependencies):
    python3 -m venv /tmp/vid && /tmp/vid/bin/pip install pillow imageio-ffmpeg
    /tmp/vid/bin/python -m evals.demo_video --out demo.mp4
"""

import argparse
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SPEED = 1280, 720, 30, 20  # the race runs at 20x real time
BG, INK, DIM, JEV = (14, 17, 22), (230, 237, 243), (125, 133, 144), (61, 220, 151)
JEV_USD_PER_MTOK_INPUT = 0.042  # TypeSafe console: "Estimated at $0.042/MTok input. Free output."
LANE = {"sonnet": (240, 200, 94), "jev": JEV, "opus": (240, 163, 94), "sol": (106, 168, 255), "haiku": (181, 140, 255)}
SANS, BOLD, MONO = ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
_fonts = {}


def font(path, size):
    return _fonts.setdefault((path, size), ImageFont.truetype(path, size))


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def load(data_dir):
    d = Path(data_dir)
    read = lambda name: json.loads((d / name).read_text())
    seconds = lambda name: read(name)["wall_ms"] / 1000
    repeat = read("eval_repeat_haiku_low.json")
    jev_tokens = sum(s["input_tokens"] for s in read("experiment_2.json")["schemas"].values())
    claude = lambda name: sum(c.get("cost_usd") or 0 for c in read(name)["channels"].values())
    return {"cost": [("jev", "Jev", jev_tokens * JEV_USD_PER_MTOK_INPUT / 1e6),
                     ("opus", "Opus 5", claude("eval_claude_claude-opus-5_default.json")),
                     ("sonnet", "Sonnet 5", claude("eval_claude_claude-sonnet-5_default.json")),
                     ("haiku", "Haiku 4.5", claude("eval_claude_claude-haiku-4-5-20251001_default.json"))],
            "jev_tokens": jev_tokens, "race": [("jev", "Jev", seconds("experiment_2.json")),
                     ("opus", "Opus 5 · Claude Code", seconds("eval_claude_claude-opus-5_default.json")),
                     ("sol", "Sol · Codex", seconds("eval_codex_gpt-5.6-sol_default.json")),
                     ("haiku", "Haiku (low) · Claude Code", seconds("eval_claude_haiku_low.json"))],
            "repeat": [(label, repeat["jev"][key]["mean_abs_diff"], repeat["claude_haiku_low"][key]["mean_abs_diff"])
                       for label, key in (("relevance", "relevance"), ("value", "apparent_value"),
                                          ("packaging risk", "packaging_risk"))]}


def text(d, xy, s, size, color=INK, path=SANS, anchor="la", alpha=1.0):
    d.text(xy, s, font=font(path, size), fill=tuple(int(b + (c - b) * alpha) for b, c in zip(BG, color)), anchor=anchor)


def title(d, t, data):
    text(d, (W // 2, 210), "I follow 110 YouTube channels.", 60, INK, BOLD, "mm", ease(t / 0.8))
    text(d, (W // 2, 300), "Which ones are worth keeping?", 60, INK, BOLD, "mm", ease((t - 0.9) / 0.8))
    text(d, (W // 2, 410), "Each channel needs a judgment call. Who should make it,", 30, DIM, SANS, "mm", ease((t - 2.0) / 0.8))
    text(d, (W // 2, 452), "and how fast, how cheap, how consistently?", 30, DIM, SANS, "mm", ease((t - 2.0) / 0.8))
    text(d, (W // 2, 560), "Same evidence, same four questions: Jev vs frontier models", 28, JEV, BOLD, "mm", ease((t - 3.2) / 0.8))


def terminal(d, t, data):
    d.rounded_rectangle((90, 110, W - 90, H - 110), 14, fill=(22, 27, 34), outline=(48, 54, 61))
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse((120 + i * 30, 138, 136 + i * 30, 154), fill=c)
    command = "$ tidy judge --execute"
    typed = command[:int(t * 14)]
    text(d, (130, 200), typed + ("▌" if t < 3.2 and int(t * 3) % 2 == 0 else ""), 30, INK, MONO)
    if t > 1.8:
        text(d, (130, 262), "110 channels · 4 questions each · 1 call per channel · 6 in flight", 24, DIM, MONO)
    if t > 2.2:
        done = data["race"][0][2]
        p = min((t - 2.2) / 1.2, 1)
        d.rectangle((130, 330, 1150, 356), outline=(48, 54, 61))
        d.rectangle((132, 332, 132 + int(1016 * ease(p)), 354), fill=JEV)
        text(d, (130, 378), f"{int(110 * ease(p))}/110", 24, DIM, MONO)
        if p >= 1:
            text(d, (130, 440), f"judged 110 channels in {done:.1f} s", 40, JEV, BOLD)


def race(d, t, data):
    real = t * SPEED
    text(d, (90, 70), "Same 110 channels. Same prompts. 6 calls in flight.", 34, INK, BOLD)
    text(d, (W - 90, 76), f"{int(real // 60):02d}:{int(real % 60):02d}", 40, INK, MONO, "ra")
    text(d, (W - 90, 124), f"{SPEED}x speed", 20, DIM, SANS, "ra")
    for i, (key, label, secs) in enumerate(data["race"]):
        y = 190 + i * 115
        text(d, (90, y), label, 26, LANE[key], BOLD)
        d.rectangle((90, y + 44, 1190, y + 74), fill=(28, 33, 40))
        d.rectangle((90, y + 44, 90 + int(1100 * min(real / secs, 1)), y + 74), fill=LANE[key])
        if real >= secs:
            text(d, (1190, y), f"{secs:.1f} s" if secs < 60 else f"{int(secs // 60)}m {int(secs % 60):02d}s", 30, LANE[key], BOLD, "ra")
    slowest = max(s for *_, s in data["race"])
    if real >= slowest:
        text(d, (W // 2, 660), f"Jev: {slowest / data['race'][0][2]:.0f}x faster than the slowest, {data['race'][1][2] / data['race'][0][2]:.0f}x faster than Opus 5",
             28, JEV, BOLD, "mm", ease((real - slowest) / 20))


def cost(d, t, data):
    text(d, (90, 70), "What the same 110 judgments cost", 34, INK, BOLD)
    text(d, (90, 118), f"Jev: {data['jev_tokens']:,} input tokens at $0.042 per million, output free. Claude: billed cost via Claude Code.", 22, DIM)
    lo, hi = math.log10(0.001), math.log10(20)
    span = 900
    for i, (key, label, usd) in enumerate(data["cost"]):
        y = 210 + i * 110
        text(d, (90, y), label, 28, LANE[key], BOLD)
        grow = ease((t - 0.5 * i) / 1.2)
        width = int(span * (math.log10(usd) - lo) / (hi - lo) * grow)
        d.rectangle((90, y + 44, 90 + span, y + 70), fill=(28, 33, 40))
        d.rectangle((90, y + 44, 90 + width, y + 70), fill=LANE[key])
        if grow >= 1:
            text(d, (1190, y + 12), f"${usd:.3f}" if usd < 1 else f"${usd:.2f}", 34, LANE[key], BOLD, "ra")
    text(d, (1190, 130), "log scale", 18, DIM, SANS, "ra")
    jev = data["cost"][0][2]
    text(d, (W // 2, 650), f"Jev costs {data['cost'][1][2] / jev:,.0f}x less than Opus 5, {data['cost'][2][2] / jev:,.0f}x less than Sonnet 5",
         28, JEV, BOLD, "mm", ease((t - 3) / 0.8))


def repeat(d, t, data):
    text(d, (90, 70), "Run it twice. How far does the score move?", 34, INK, BOLD)
    text(d, (90, 118), "Mean change per channel between two runs (30 channels). Shorter is steadier.", 22, DIM)
    scale = max(h for _, _, h in data["repeat"])
    for i, (label, jev, haiku) in enumerate(data["repeat"]):
        y = 210 + i * 140
        text(d, (90, y), label, 26, INK, BOLD)
        for j, (name, value, color) in enumerate((("Jev", jev, JEV), ("Haiku (low)", haiku, LANE["haiku"]))):
            yy = y + 42 + j * 36
            text(d, (90, yy), name, 20, DIM)
            grow = ease((t - 0.4 * i) / 1.2)
            d.rectangle((260, yy + 2, 260 + int(760 * value / scale * grow), yy + 24), fill=color)
            if grow >= 1:
                text(d, (270 + int(760 * value / scale), yy), f"{value:.3f}", 20, color, MONO)
        if t - 0.4 * i > 1.4:
            text(d, (1190, y + 20), f"{haiku / jev:.1f}x steadier", 30, JEV, BOLD, "ra", ease(t - 0.4 * i - 1.4))


def finding(d, t, data):
    text(d, (90, 70), "But does the score match what I actually keep?", 36, INK, BOLD)
    text(d, (90, 124), "Checked against my own keep / drop labels (34 channels). 0.5 = coin flip, 1.0 = perfect.", 22, DIM)
    rows = [("Quality scores", "Jev, Opus 5 and Haiku", 0.5, DIM, "about 0.5"),
            ("My watch history", "counted from Google Takeout", 0.80, JEV, "0.80")]
    x0, span = 90, 1100
    for i, (name, note, value, color, shown) in enumerate(rows):
        y = 230 + i * 170
        text(d, (x0, y), name, 30, color, BOLD)
        text(d, (x0, y + 40), note, 22, DIM)
        d.rectangle((x0, y + 82, x0 + span, y + 112), fill=(28, 33, 40))
        d.rectangle((x0, y + 82, x0 + int(span * value * ease((t - 0.8 * i) / 1.2)), y + 112), fill=color)
        if t - 0.8 * i > 1.2:
            text(d, (x0 + span, y), shown, 40, color, BOLD, "ra")
    text(d, (W // 2, 620), "Fast and consistent is not the same as right for one person.", 30, INK, BOLD, "mm", ease((t - 2.8) / 0.8))


def guardrails(d, t, data):
    for i, (word, note) in enumerate((("Jev judges.", "every quality call, in seconds"),
                                      ("Code decides.", "arithmetic, thresholds, caps, budgets"),
                                      ("I approve.", "11 channels unsubscribed, each one signed off. Nothing unattended."))):
        a = ease((t - 0.9 * i) / 0.7)
        text(d, (90, 150 + i * 150), word, 60, JEV if i == 0 else INK, BOLD, alpha=a)
        text(d, (90, 232 + i * 150), note, 26, DIM, SANS, alpha=a)
    text(d, (W // 2, 640), "Tidy · built on Jev (TypeSafe System One)", 26, JEV, SANS, "mm", ease((t - 3) / 0.8))


SCENES = [(title, 6.0), (terminal, 5.0), (race, 25.0), (cost, 7.0), (repeat, 6.0), (finding, 7.0), (guardrails, 5.0)]
FADE = 0.4


def frame(seconds, data):
    start = 0.0
    for scene, length in SCENES:
        if seconds < start + length:
            break
        start += length
    local = seconds - start
    image = Image.new("RGB", (W, H), BG)
    scene(ImageDraw.Draw(image), local, data)
    fade = min(local / FADE, (length - local) / FADE, 1)
    return image if fade >= 1 else Image.blend(Image.new("RGB", (W, H), BG), image, max(fade, 0))


def render(data, out):
    from imageio_ffmpeg import get_ffmpeg_exe
    total = sum(length for _, length in SCENES)
    ffmpeg = subprocess.Popen([get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "18", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for n in range(int(total * FPS)):
        ffmpeg.stdin.write(frame(n / FPS, data).tobytes())
    ffmpeg.stdin.close()
    ffmpeg.wait()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    ap.add_argument("--out", type=Path, default=Path("tidy_demo.mp4"))
    ap.add_argument("--still", type=float, help="write one PNG at this second instead of the video")
    args = ap.parse_args()
    data = load(args.data_dir)
    if args.still is not None:
        frame(args.still, data).save(args.out.with_suffix(".png"))
    else:
        render(data, args.out)
