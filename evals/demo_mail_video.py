"""Render the ~36 s Tidy mail-cleanup demo video (MP4). No real subject lines, senders, or email
addresses appear anywhere: every number here is an aggregate, matching how the repo's own public-facing
rules treat personal inbox data. Reuses demo_video.py's drawing primitives (ease, text, palette).

Needs Pillow and imageio-ffmpeg (not project dependencies):
    python3 -m venv /tmp/vid && /tmp/vid/bin/pip install pillow imageio-ffmpeg
    PYTHONPATH=.venv/lib/python3.14/site-packages /tmp/vid/bin/python -m evals.demo_mail_video --out mail_demo.mp4
"""

import argparse
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw

from evals.demo_video import BG, BOLD, DIM, FPS, H, INK, JEV, MONO, SANS, W, ease, text

# Measured, not estimated: real Gmail profile.messagesTotal / a full is:unread pagination count (2026-09-22),
# and real per-message Jev cost from a 10-message live classify run (871.6 avg input tokens/call at
# TypeSafe's published $0.042/M input, output free). See the session's mail-triage/mail-act work.
UNREAD = 12158
TOTAL_MESSAGES = 56679
COST_PER_EMAIL_USD = 871.6 * 0.042 / 1_000_000
BACKLOG_COST_USD = COST_PER_EMAIL_USD * UNREAD
BUCKETS = [("Needs reply", 6, JEV), ("Updates", 44, (140, 170, 255)), ("Promos", 38, (255, 170, 90)), ("Spam", 12, (255, 95, 86))]


def title(d, t, data):
    text(d, (W // 2, 230), f"{UNREAD:,} unread emails.", 66, INK, BOLD, "mm", ease(t / 0.8))
    text(d, (W // 2, 320), "Sitting in one inbox.", 44, DIM, SANS, "mm", ease((t - 1.0) / 0.8))
    text(d, (W // 2, 470), "Nobody reads that by hand.", 32, DIM, SANS, "mm", ease((t - 2.4) / 0.8))
    text(d, (W // 2, 560), "So I built something that would.", 34, JEV, BOLD, "mm", ease((t - 3.6) / 0.8))


def team(d, t, data):
    rows = [("Jev", "reads every email, sorts it into plain categories", JEV),
           ("Claude", "wrote the tool that connects Jev to Gmail", INK),
           ("Codex", "reviewed the code, found real bugs before they shipped", INK)]
    for i, (who, what, color) in enumerate(rows):
        a = ease((t - 0.7 * i) / 0.7)
        text(d, (90, 140 + i * 160), who, 56, color, BOLD, alpha=a)
        text(d, (90, 208 + i * 160), what, 26, DIM, SANS, alpha=a)
    text(d, (W // 2, 640), "Three different AI models, one small tool.", 26, DIM, SANS, "mm", ease((t - 2.6) / 0.8))


def sorting(d, t, data):
    text(d, (W // 2, 66), "Every email gets read once, sorted into a category", 32, INK, BOLD, "mm")
    cx, cy = 200, 380
    d.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), outline=DIM, width=2)
    text(d, (cx, cy), "Inbox", 26, DIM, SANS, "mm")
    cols = 4
    gap = (W - 340) / cols
    for i, (label, pct, color) in enumerate(BUCKETS):
        bx = 340 + gap * i + gap / 2
        by = 560
        p = ease((t - 0.5 - i * 0.35) / 1.4)
        if p <= 0:
            continue
        lx = cx + (bx - cx) * p
        ly = cy + (by - cy) * p
        r = 5 if p < 1 else 0
        if r:
            d.ellipse((lx - r, ly - r, lx + r, ly + r), fill=color)
        if p >= 1:
            shown = int(pct * min((t - 0.5 - i * 0.35 - 1.4) / 0.6, 1)) if t > 0.5 + i * 0.35 + 1.4 else 0
            d.rounded_rectangle((bx - 90, by - 20, bx + 90, by + 60), 10, outline=color, width=2)
            text(d, (bx, by), label, 20, color, BOLD, "mm")
            text(d, (bx, by + 34), f"{shown}%", 22, INK, MONO, "mm")
    text(d, (W // 2, 660), "Needs-reply mail is never auto-archived, only what's confidently bulk mail.", 22, DIM, SANS, "mm",
        ease((t - 3.2) / 0.8))


def cost(d, t, data):
    text(d, (W // 2, 140), "What sorting the whole backlog costs", 34, INK, BOLD, "mm")
    a = ease((t - 0.5) / 0.9)
    text(d, (W // 2, 330), f"${BACKLOG_COST_USD:.2f}", 130, JEV, BOLD, "mm", a)
    text(d, (W // 2, 430), f"to classify all {UNREAD:,} unread emails", 30, INK, SANS, "mm", ease((t - 1.4) / 0.8))
    text(d, (W // 2, 480), "measured from real Jev calls, not estimated", 22, DIM, SANS, "mm", ease((t - 2.0) / 0.8))
    text(d, (W // 2, 600), f"{TOTAL_MESSAGES:,} total messages in the mailbox, for scale", 24, DIM, MONO, "mm", ease((t - 3.0) / 0.8))


def result(d, t, data):
    text(d, (W // 2, 170), "Nothing gets deleted for good.", 44, INK, BOLD, "mm", ease(t / 0.8))
    text(d, (W // 2, 250), "It just gets out of the way.", 36, DIM, SANS, "mm", ease((t - 0.8) / 0.8))
    rows = [("Archive", "reversible, one click to undo"), ("Trash", "recoverable for 30 days"), ("Never", "a permanent delete, ever")]
    for i, (word, note) in enumerate(rows):
        a = ease((t - 1.8 - 0.5 * i) / 0.6)
        text(d, (W // 2, 400 + i * 80), word, 32, JEV if i == 2 else INK, BOLD, "mm", a)
        text(d, (W // 2, 434 + i * 80), note, 20, DIM, SANS, "mm", a)


def close(d, t, data):
    text(d, (W // 2, 300), "Tidy", 90, JEV, BOLD, "mm", ease(t / 0.7))
    text(d, (W // 2, 380), "built on Jev (TypeSafe System One)", 26, DIM, SANS, "mm", ease((t - 0.6) / 0.7))
    text(d, (W // 2, 460), "Written with Claude. Reviewed with Codex.", 24, INK, SANS, "mm", ease((t - 1.2) / 0.7))


SCENES = [(title, 6.0), (team, 7.0), (sorting, 8.0), (cost, 6.0), (result, 5.5), (close, 3.5)]
FADE = 0.4
TOTAL = sum(length for _, length in SCENES)
GBOTTOM = (18, 23, 30)  # subtle vertical gradient instead of flat fill, matches the thumbnail


def _gradient():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(BG, GBOTTOM)))
    return img


def _chrome(image, seconds):
    d = ImageDraw.Draw(image)
    d.rectangle((0, H - 4, W * min(seconds / TOTAL, 1), H), fill=JEV)
    text(d, (W - 24, H - 24), "TIDY", 20, DIM, BOLD, "rm", 0.6)


def frame(seconds, data):
    start = 0.0
    for index, (scene, length) in enumerate(SCENES):
        if seconds < start + length:
            break
        start += length
    local = seconds - start
    image = _gradient()
    scene(ImageDraw.Draw(image), local, data)
    fade = min(1 if index == 0 else local / FADE, (length - local) / FADE, 1)
    image = image if fade >= 1 else Image.blend(_gradient(), image, max(fade, 0))
    _chrome(image, seconds)
    return image


def render(out):
    from imageio_ffmpeg import get_ffmpeg_exe
    ffmpeg = subprocess.Popen([get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "18", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for n in range(int(TOTAL * FPS)):
        ffmpeg.stdin.write(frame(n / FPS, None).tobytes())
    ffmpeg.stdin.close()
    ffmpeg.wait()
    return TOTAL


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("mail_demo.mp4"))
    ap.add_argument("--still", type=float, help="write one PNG at this second instead of the video")
    args = ap.parse_args()
    if args.still is not None:
        frame(args.still, None).save(args.out.with_suffix(".png"))
    else:
        render(args.out)
