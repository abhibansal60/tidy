"""Thumbnail for the mail-cleanup demo video: one honest number, no hype framing, no red banner.
No real subject lines, senders, or addresses; every figure is an aggregate, measured not estimated.

Usage: PYTHONPATH=.venv/lib/python3.14/site-packages /tmp/vid/bin/python -m evals.demo_mail_thumbnail --out thumb.png
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
TOP, BOTTOM = (11, 14, 19), (17, 22, 29)  # subtle vertical gradient, not flat
INK, DIM, JEV = (245, 247, 250), (140, 148, 160), (61, 220, 151)
REGULAR = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"
SEMIBOLD = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"


def f(path, size):
    return ImageFont.truetype(path, size)


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def draw(unread=12158, cost=0.45):
    img = Image.new("RGB", (W, H), TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=lerp(TOP, BOTTOM, y / H))
    d.text((W // 2, 108), "TIDY · AI INBOX CLEANUP", font=f(SEMIBOLD, 28), fill=DIM, anchor="mm")
    d.line((W // 2 - 60, 148, W // 2 + 60, 148), fill=(48, 54, 61), width=2)
    d.text((W // 2, 320), f"${cost:.2f}", font=f(BLACK, 230), fill=JEV, anchor="mm")
    d.text((W // 2, 470), f"to sort {unread:,} unread emails", font=f(SEMIBOLD, 42), fill=INK, anchor="mm")
    d.text((W // 2, 520), "measured, not estimated", font=f(REGULAR, 26), fill=DIM, anchor="mm")
    d.text((W // 2, 640), "built on Jev · written with Claude · reviewed with Codex", font=f(REGULAR, 24), fill=DIM, anchor="mm")
    return img


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("mail_thumbnail.png"))
    args = ap.parse_args()
    draw().save(args.out)
