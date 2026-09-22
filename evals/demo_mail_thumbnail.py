"""Thumbnail variants for the mail-cleanup demo video: real numbers only, no fake claims, but designed
for actual YouTube/X feed conditions (small size, high contrast, one glance). No real subject lines,
senders, or addresses; every figure is an aggregate, measured not estimated.

Usage: PYTHONPATH=.venv/lib/python3.14/site-packages /tmp/vid/bin/python -m evals.demo_mail_thumbnail --out thumb.png --variant a
Variants: a (big stat), b (before/after split), c (notification badge), d (bold headline)
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
TOP, BOTTOM = (11, 14, 19), (17, 22, 29)
INK, DIM, JEV = (245, 247, 250), (140, 148, 160), (61, 220, 151)
RED = (255, 92, 92)
BADGE_INK = (8, 12, 10)  # dark text on RED/JEV badges: white-on-RED is only 3.03:1, this is 6.50:1+ (codex review)
LABEL = (176, 184, 196)  # brighter than DIM for small labels that must survive feed-size downscaling
REGULAR = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"
SEMIBOLD = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
EXBOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"


def f(path, size):
    return ImageFont.truetype(path, size)


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def _bg(top=TOP, bottom=BOTTOM):
    img = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line((0, y, W, y), fill=lerp(top, bottom, y / H))
    return img, d


def _envelope(d, cx, cy, size, color, width=6):
    x0, y0, x1, y1 = cx - size, cy - size * 0.7, cx + size, cy + size * 0.7
    d.rounded_rectangle((x0, y0, x1, y1), size * 0.12, outline=color, width=width)
    d.line((x0 + width, y0 + width, cx, cy + size * 0.15), fill=color, width=width)
    d.line((x1 - width, y0 + width, cx, cy + size * 0.15), fill=color, width=width)


def a(unread=12158, cost=0.45):
    """Big stat hero: the honest number, dead center, impossible to miss at thumbnail size."""
    img, d = _bg()
    d.text((W // 2, 96), "TIDY · AI INBOX CLEANUP", font=f(SEMIBOLD, 30), fill=DIM, anchor="mm")
    d.text((W // 2, 300), f"${cost:.2f}", font=f(BLACK, 260), fill=JEV, anchor="mm")
    d.text((W // 2, 460), f"to sort {unread:,} unread emails", font=f(EXBOLD, 46), fill=INK, anchor="mm")
    d.text((W // 2, 512), "measured, not estimated", font=f(REGULAR, 26), fill=DIM, anchor="mm")
    d.text((W // 2, 650), "built on Jev · written with Claude · reviewed with Codex", font=f(REGULAR, 22), fill=DIM, anchor="mm")
    return img


def b(unread=12158, done=0):
    """Before/after split: the visual comparison format that reads instantly in a feed."""
    img, d = _bg()
    mid = W // 2
    d.line((mid, 60, mid, H - 60), fill=(48, 54, 61), width=2)
    d.text((mid // 2, 130), "BEFORE", font=f(SEMIBOLD, 30), fill=DIM, anchor="mm")
    d.text((mid // 2, 320), f"{unread:,}", font=f(BLACK, 130), fill=RED, anchor="mm")
    d.text((mid // 2, 420), "unread emails", font=f(SEMIBOLD, 32), fill=INK, anchor="mm")
    right_cx = mid + mid // 2
    d.text((right_cx, 130), "AFTER", font=f(SEMIBOLD, 30), fill=DIM, anchor="mm")
    d.text((right_cx, 320), "Sorted", font=f(BLACK, 90), fill=JEV, anchor="mm")
    d.text((right_cx, 420), "in one run, for 45¢", font=f(SEMIBOLD, 30), fill=INK, anchor="mm")
    d.polygon([(mid - 34, 320 - 14), (mid + 34, 320), (mid - 34, 320 + 14)], fill=JEV)
    d.text((W // 2, 610), "AI sorted my inbox. Built on Jev, written with Claude.", font=f(REGULAR, 26), fill=DIM, anchor="mm")
    return img


def c(unread=12158):
    """Notification badge: the one visual everyone already recognizes from their own phone."""
    img, d = _bg((14, 12, 18), (22, 16, 24))
    cx, cy = W // 2, 300
    _envelope(d, cx, cy, 150, INK, width=8)
    label = "12K+" if unread >= 10000 else f"{unread:,}"
    bx, by, br = cx + 150, cy - 105, 78
    d.ellipse((bx - br, by - br, bx + br, by + br), fill=RED)
    d.text((bx, by - 4), label, font=f(BLACK, 54 if len(label) <= 4 else 40), fill=BADGE_INK, anchor="mm")
    d.text((W // 2, 490), "I let AI clean this up", font=f(EXBOLD, 54), fill=INK, anchor="mm")
    d.text((W // 2, 550), f"{unread:,} unread emails, sorted for 45¢", font=f(SEMIBOLD, 30), fill=JEV, anchor="mm")
    d.text((W // 2, 650), "built on Jev · written with Claude · reviewed with Codex", font=f(REGULAR, 22), fill=DIM, anchor="mm")
    return img


def d(unread=12158):
    """Bold headline: maximum legibility at small size, minimal ornamentation, text does the work."""
    img, d = _bg()
    d.text((W // 2, 220), f"{unread:,}", font=f(BLACK, 190), fill=INK, anchor="mm")
    d.text((W // 2, 380), "UNREAD EMAILS", font=f(BLACK, 68), fill=INK, anchor="mm")
    d.rounded_rectangle((W // 2 - 260, 470, W // 2 + 260, 540), 14, fill=JEV)
    d.text((W // 2, 505), "SORTED BY AI FOR 45¢", font=f(EXBOLD, 34), fill=(8, 12, 10), anchor="mm")
    d.text((W // 2, 630), "Jev · Claude · Codex", font=f(REGULAR, 24), fill=DIM, anchor="mm")
    return img


def _checkmark(d, cx, cy, r, color, width=8):
    d.line((cx - r * 0.5, cy, cx - r * 0.1, cy + r * 0.4), fill=color, width=width)
    d.line((cx - r * 0.1, cy + r * 0.4, cx + r * 0.55, cy - r * 0.35), fill=color, width=width)


def e(unread=12158):
    """Before/after split (b) with the recognizable notification-badge icon (c) on each side."""
    img, d = _bg()
    mid = W // 2
    d.line((mid, 60, mid, 430), fill=(48, 54, 61), width=2)
    left_cx, right_cx = mid // 2, mid + mid // 2
    d.text((left_cx, 80), "BEFORE", font=f(SEMIBOLD, 40), fill=LABEL, anchor="mm")
    d.text((right_cx, 80), "AFTER", font=f(SEMIBOLD, 40), fill=LABEL, anchor="mm")
    _envelope(d, left_cx, 280, 95, INK, width=6)
    bx, by, br = left_cx + 92, 280 - 65, 52
    d.ellipse((bx - br, by - br, bx + br, by + br), fill=RED)
    d.text((bx, by - 2), "12K+", font=f(BLACK, 30), fill=BADGE_INK, anchor="mm")
    d.text((left_cx, 400), f"{unread:,} unread", font=f(EXBOLD, 32), fill=INK, anchor="mm")
    _envelope(d, right_cx, 280, 95, JEV, width=6)
    bx2 = right_cx + 92
    d.ellipse((bx2 - br, by - br, bx2 + br, by + br), fill=JEV)
    _checkmark(d, bx2, by, br * 0.7, BADGE_INK, width=9)
    d.text((right_cx, 400), "sorted, 45¢", font=f(EXBOLD, 32), fill=JEV, anchor="mm")
    d.polygon([(mid - 26, 280 - 12), (mid + 26, 280), (mid - 26, 280 + 12)], fill=DIM)
    d.text((W // 2, 470), "I let AI clean this up", font=f(EXBOLD, 46), fill=INK, anchor="mm")
    d.text((W // 2, 650), "built on Jev · written with Claude · reviewed with Codex", font=f(REGULAR, 22), fill=DIM, anchor="mm")
    return img


VARIANTS = {"a": a, "b": b, "c": c, "d": d, "e": e}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("mail_thumbnail.png"))
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="a")
    args = ap.parse_args()
    VARIANTS[args.variant]().save(args.out)
