"""Thumbnail for the demo video: the speed contrast and the twist, from the stored eval results. No channel names.

Usage: PYTHONPATH=.venv/lib/python3.14/site-packages /tmp/vid/bin/python -m evals.demo_thumbnail --out thumb.png
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG, INK, DIM, JEV, HOT, WARN = (10, 12, 16), (245, 247, 250), (140, 148, 160), (61, 232, 151), (255, 170, 90), (255, 84, 84)
BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"


def f(path, size):
    return ImageFont.truetype(path, size)


def seconds(data_dir, name):
    return json.loads((Path(data_dir) / name).read_text())["wall_ms"] / 1000


def mmss(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def draw(data_dir):
    jev = seconds(data_dir, "experiment_2.json")
    other = seconds(data_dir, "eval_claude_claude-sonnet-5_default.json")
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):  # faint vertical gradient
        shade = int(10 + 14 * y / H)
        d.line((0, y, W, y), fill=(shade, shade + 2, shade + 6))
    d.text((W // 2, 60), "8 AI MODELS JUDGED MY 110 YOUTUBE CHANNELS", font=f(BOLD, 40), fill=DIM, anchor="mm")
    d.text((300, 320), f"{jev:.0f}s", font=f(BLACK, 270), fill=JEV, anchor="mm")
    d.text((940, 335), mmss(other), font=f(BLACK, 215), fill=HOT, anchor="mm")
    d.text((300, 492), "JEV", font=f(BLACK, 56), fill=JEV, anchor="mm")
    d.text((940, 492), "SONNET 5", font=f(BLACK, 56), fill=HOT, anchor="mm")
    d.text((620, 320), "vs", font=f(BOLD, 54), fill=DIM, anchor="mm")
    d.rectangle((0, 560, W, H), fill=WARN)
    d.text((W // 2, 640), "NONE COULD PREDICT WHAT I'D KEEP", font=f(BLACK, 62), fill=(15, 8, 8), anchor="mm")
    return img


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    ap.add_argument("--out", type=Path, default=Path("tidy_thumbnail.png"))
    args = ap.parse_args()
    draw(args.data_dir).save(args.out)
