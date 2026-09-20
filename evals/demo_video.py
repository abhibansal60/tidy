"""Render the ~50 s Tidy demo video (MP4) straight from the stored eval results. No channel names appear.

Needs Pillow and imageio-ffmpeg (not project dependencies):
    python3 -m venv /tmp/vid && /tmp/vid/bin/pip install pillow imageio-ffmpeg
    PYTHONPATH=.venv/lib/python3.14/site-packages /tmp/vid/bin/python -m evals.demo_video --out demo.mp4
"""

import argparse
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

from evals import demo_thumbnail, list_price

W, H, FPS, SPEED = 1280, 720, 30, 20  # the race runs at 20x real time
BG, INK, DIM, JEV = (14, 17, 22), (230, 237, 243), (125, 133, 144), (61, 220, 151)
NAMES = {"claude-fable-5-1": "Fable 5.1", "claude-opus-5": "Opus 5", "claude-sonnet-5": "Sonnet 5",
         "claude-haiku-4-5-20251001": "Haiku 4.5", "gpt-6-astra": "Astra", "gpt-5.6-sol": "Sol",
         "gpt-5.6-terra": "Terra", "gpt-5.6-luna": "Luna"}
LANE_OF = {"claude-fable-5-1": "fable", "claude-opus-5": "opus", "claude-sonnet-5": "sonnet", "claude-haiku-4-5-20251001": "haiku",
           "gpt-6-astra": "astra", "gpt-5.6-sol": "sol", "gpt-5.6-terra": "terra", "gpt-5.6-luna": "luna"}
RUNS = [("opus", "Opus 5 · Claude Code", "eval_claude_claude-opus-5_default.json"),
        ("sonnet", "Sonnet 5 · Claude Code", "eval_claude_claude-sonnet-5_default.json"),
        ("haiku", "Haiku 4.5 · Claude Code", "eval_claude_claude-haiku-4-5-20251001_default.json"),
        ("sol", "Sol · Codex", "eval_codex_gpt-5.6-sol_default.json"),
        ("astra", "Astra · Codex", "eval_codex_gpt-6-astra_default.json"),
        ("terra", "Terra · Codex", "eval_codex_gpt-5.6-terra_default.json"),
        ("luna", "Luna · Codex", "eval_codex_gpt-5.6-luna_default.json")]
JEV_USD_PER_MTOK_INPUT = 0.042  # TypeSafe console: "Estimated at $0.042/MTok input. Free output."
LANE = {"fable": (240, 120, 120), "astra": (80, 200, 220), "terra": (120, 190, 255), "luna": (170, 210, 255), "sonnet": (240, 200, 94), "jev": JEV, "opus": (240, 163, 94), "sol": (106, 168, 255), "haiku": (181, 140, 255)}
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
    def seconds(name):  # a resumed run's wall_ms covers only the resumed part: never below summed call time / workers
        run = read(name)
        calls = sum(c.get("wall_ms", 0) for c in run.get("channels", {}).values()) / max(run.get("workers", 6), 1)
        return max(run["wall_ms"], calls if "channels" in run and "effort" in run else 0) / 1000
    jev_tokens = sum(s["input_tokens"] for s in read("experiment_2.json")["schemas"].values())
    estimates = [r for r in list_price.all_estimates(d, list_price.prompt_tokens(d)) if r["channels"] == 110]
    listed = sorted(((LANE_OF[r["model"]], NAMES[r["model"]] + (" (projected)" if "projected_from" in r else ""), r["usd"])
                     for r in estimates if r["model"] in NAMES), key=lambda row: -row[2])
    race = [("jev", "Jev", seconds("experiment_2.json"))]
    for key, label, name in RUNS:  # only runs that answered all 110 channels
        if (d / name).is_file() and sum("answers" in c for c in read(name)["channels"].values()) == 110:
            race.append((key, label, seconds(name)))
    race.sort(key=lambda row: row[2])
    sonnet = d / "eval_repeat_claude-sonnet-5_.json"
    repeat = read(sonnet.name if sonnet.is_file() else "eval_repeat_haiku_low.json")
    baseline = next(k for k in repeat if k.startswith("claude_"))
    other = "Sonnet 5" if "sonnet" in baseline else "Haiku (low)"
    return {"thumb": demo_thumbnail.draw(d), "race": race, "jev_tokens": jev_tokens, "cost": [("jev", "Jev", jev_tokens * JEV_USD_PER_MTOK_INPUT / 1e6)] + listed,
            "repeat": [(label, repeat["jev"][key]["mean_abs_diff"], repeat[baseline][key]["mean_abs_diff"], other)
                       for label, key in (("relevance", "relevance"), ("value", "apparent_value"),
                                          ("packaging risk", "packaging_risk"))]}


def text(d, xy, s, size, color=INK, path=SANS, anchor="la", alpha=1.0):
    d.text(xy, s, font=font(path, size), fill=tuple(int(b + (c - b) * alpha) for b, c in zip(BG, color)), anchor=anchor)


def thumbnail(d, t, data):
    """Placeholder: frame() pastes the pre-rendered thumbnail so a feed's poster frame is the thumbnail."""


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
    text(d, (90, 116), "Others run through coding CLIs (Claude Code, Codex): per-call tool overhead is included.", 20, DIM)
    for i, (key, label, secs) in enumerate(data["race"]):
        y = 165 + i * min(115, 460 // len(data["race"]))
        text(d, (90, y), label, 24, LANE[key], BOLD)
        d.rectangle((90, y + 34, 1190, y + 58), fill=(28, 33, 40))
        d.rectangle((90, y + 34, 90 + int(1100 * min(real / secs, 1)), y + 58), fill=LANE[key])
        if real >= secs:
            text(d, (1190, y + 4), f"{secs:.1f} s" if secs < 60 else f"{int(secs // 60)}m {int(secs % 60):02d}s", 28, LANE[key], BOLD, "ra")
    slowest = max(s for *_, s in data["race"])
    if real >= slowest:
        text(d, (W // 2, 672), f"Jev: {data['race'][1][2] / data['race'][0][2]:.0f}x to {slowest / data['race'][0][2]:.0f}x faster, against coding CLIs",
             28, JEV, BOLD, "mm", ease((real - slowest) / 20))


def cost(d, t, data):
    text(d, (90, 70), "What the same 110 judgments cost", 34, INK, BOLD)
    text(d, (90, 118), f"Jev: {data['jev_tokens']:,} input tokens at $0.042 per million, output free. Others: estimated at list API prices.", 22, DIM)
    lo, hi = math.log10(0.001), math.log10(5)
    x0, span = 330, 700
    step = min(110, 470 // len(data["cost"]))
    for i, (key, label, usd) in enumerate(data["cost"]):
        y = 175 + i * step
        text(d, (90, y + 14), label, 22, LANE[key], BOLD, "lm")
        grow = ease((t - 0.3 * i) / 1.2)
        width = int(span * (math.log10(usd) - lo) / (hi - lo) * grow)
        d.rectangle((x0, y + 2, x0 + span, y + 26), fill=(28, 33, 40))
        d.rectangle((x0, y + 2, x0 + width, y + 26), fill=LANE[key])
        if grow >= 1:
            text(d, (1190, y + 14), f"${usd:.3f}" if usd < 1 else f"${usd:.2f}", 26, LANE[key], BOLD, "rm")
    jev = data["cost"][0][2]
    if any("projected" in label for _, label, _ in data["cost"]):
        text(d, (90, 700), "Projected: no Fable run yet; assumes it writes as many output tokens as Opus 5.", 18, DIM)
    cheapest = min(usd for _, _, usd in data["cost"][1:])
    priciest = max(usd for _, _, usd in data["cost"][1:])
    text(d, (W // 2, 660), f"Jev costs {cheapest / jev:,.0f}x to {priciest / jev:,.0f}x less than the frontier models",
         28, JEV, BOLD, "mm", ease((t - 3) / 0.8))


def repeat(d, t, data):
    text(d, (90, 70), "Run it twice. How far does the score move?", 34, INK, BOLD)
    text(d, (90, 118), "Mean change per channel between two runs (30 channels). Shorter is steadier.", 22, DIM)
    scale = max(row[2] for row in data["repeat"])
    for i, (label, jev, haiku, other) in enumerate(data["repeat"]):
        y = 210 + i * 140
        text(d, (90, y), label, 26, INK, BOLD)
        for j, (name, value, color) in enumerate((("Jev", jev, JEV), (other, haiku, LANE["haiku"]))):
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
    text(d, (90, 124), "Checked against my own keep / drop labels (66 channels). 0.5 = coin flip, 1.0 = perfect.", 22, DIM)
    rows = [("Quality scores", "Jev and all seven others: 0.43 to 0.52", 0.5, DIM, "about 0.5"),
            ("My watch history", "counted from Google Takeout", 0.69, JEV, "0.69")]
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


def loop(d, t, data):
    text(d, (90, 70), "One loop keeps the feed current", 36, INK, BOLD)
    text(d, (90, 122), "Runs when I start it. Prunes what stopped earning its place, finds what I already watch.", 22, DIM)
    steps = [("Sync", "my subscriptions"), ("Watch history", "Google Takeout, counted by code"),
             ("Jev judges", "every channel, seconds"), ("Code decides", "thresholds, caps, budgets")]
    for i, (name, note) in enumerate(steps):
        x, a = 90 + i * 285, ease((t - 0.5 * i) / 0.6)
        d.rounded_rectangle((x, 190, x + 250, 300), 12, outline=tuple(int(b + (c - b) * a) for b, c in zip(BG, JEV if i == 2 else DIM)), width=2)
        text(d, (x + 125, 232), name, 26, JEV if i == 2 else INK, BOLD, "mm", a)
        text(d, (x + 125, 270), note, 15, DIM, SANS, "mm", a)
        if i < 3:
            text(d, (x + 268, 245), "›", 34, DIM, BOLD, "mm", a)
    a = ease((t - 2.4) / 0.7)
    for i, (head, body, color) in enumerate((
            ("Unsubscribe", ("Low quality by Jev AND a second opinion.", "11 channels so far, each approved by me."), (240, 120, 120)),
            ("Subscribe", ("Watched often, not subscribed, quality above a floor.", "30 candidates found, 13 proposed."), JEV))):
        x = 90 + i * 570
        d.rounded_rectangle((x, 360, x + 540, 520), 12, outline=tuple(int(b + (c - b) * a) for b, c in zip(BG, color)), width=2)
        text(d, (x + 24, 386), head, 30, color, BOLD, alpha=a)
        for j, line in enumerate(body):
            text(d, (x + 24, 440 + j * 30), line, 20, INK, SANS, alpha=a)
    text(d, (W // 2, 566), "Caps per run: 5 unsubscribes, 3 subscribes. Owner-started, never unattended.", 20, DIM, SANS, "mm", ease((t - 3.4) / 0.7))
    text(d, (W // 2, 610), "No browser agent clicking around: one API call per change, no model in the click.", 24, INK, BOLD, "mm", ease((t - 4.2) / 0.7))
    text(d, (W // 2, 662), "The feed stays current without me reviewing 110 channels by hand.", 28, JEV, BOLD, "mm", ease((t - 5.0) / 0.7))


def guardrails(d, t, data):
    for i, (word, note) in enumerate((("Jev judges.", "every quality call, in seconds"),
                                      ("Code decides.", "arithmetic, thresholds, caps, budgets"),
                                      ("I approve.", "11 channels unsubscribed, each one signed off. Nothing unattended."))):
        a = ease((t - 0.9 * i) / 0.7)
        text(d, (90, 150 + i * 150), word, 60, JEV if i == 0 else INK, BOLD, alpha=a)
        text(d, (90, 232 + i * 150), note, 26, DIM, SANS, alpha=a)
    text(d, (W // 2, 640), "Tidy · built on Jev (TypeSafe System One)", 26, JEV, SANS, "mm", ease((t - 3) / 0.8))


SCENES = [(thumbnail, 1.5), (title, 6.0), (terminal, 5.0), (race, 25.0), (cost, 7.0), (repeat, 6.0), (finding, 7.0), (loop, 8.0), (guardrails, 5.0)]
FADE = 0.4


def frame(seconds, data):
    start = 0.0
    for index, (scene, length) in enumerate(SCENES):
        if seconds < start + length:
            break
        start += length
    local = seconds - start
    image = data["thumb"].copy() if scene is thumbnail else Image.new("RGB", (W, H), BG)
    if scene is not thumbnail:
        scene(ImageDraw.Draw(image), local, data)
    fade = min(1 if index == 0 else local / FADE, (length - local) / (0.2 if index == 0 else FADE), 1)
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
