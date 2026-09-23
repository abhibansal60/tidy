"""Regenerate the Tidy brand kit (SVG, plus PNG via headless Chrome if available): python docs/assets/brand/make_brand.py"""

from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).parent
INK, MINT, NIGHT, SPARKLE, BADGE = "#0E2A20", "#3DDC97", "#0F1A16", "#F4C542", "#FF5C5C"
FONT = 'font-family="Inter, system-ui, sans-serif"'


def _face():
    return (f'<ellipse cx="206" cy="312" rx="22" ry="27" fill="{INK}"/><ellipse cx="306" cy="312" rx="22" ry="27" fill="{INK}"/>'
            '<circle cx="214" cy="301" r="8" fill="#fff" stroke="none"/><circle cx="314" cy="301" r="8" fill="#fff" stroke="none"/>'
            '<ellipse cx="164" cy="346" rx="22" ry="12" fill="#FF8FA3" fill-opacity=".8" stroke="none"/>'
            '<ellipse cx="348" cy="346" rx="22" ry="12" fill="#FF8FA3" fill-opacity=".8" stroke="none"/>'
            '<path d="M232 344 Q256 368 280 344" fill="none" stroke-width="9"/>')


def _character(under="", body="", badge=""):
    return (f'<g stroke="{INK}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round">'
            '<ellipse cx="256" cy="436" rx="150" ry="14" fill="#000" fill-opacity=".12" stroke="none"/>'
            f'<path d="M86 118 l6 -18 l6 18 l18 6 l-18 6 l-6 18 l-6 -18 l-18 -6 z" fill="{SPARKLE}" stroke-width="5"/>'
            '<line x1="428" y1="196" x2="468" y2="420" stroke="#8B5E3C" stroke-width="14"/>'
            f'<path d="M438 408 L498 398 L512 470 L444 482 Z" fill="{SPARKLE}"/><path d="M458 420 L468 474 M478 416 L488 470" stroke-width="5"/>'
            f'{under}<ellipse cx="206" cy="412" rx="34" ry="16" fill="#1E8F5E"/><ellipse cx="306" cy="412" rx="34" ry="16" fill="#1E8F5E"/>'
            f'<rect x="96" y="150" width="320" height="252" rx="60" fill="{MINT}"/>{body}'
            f'<circle cx="86" cy="300" r="20" fill="{MINT}"/><circle cx="440" cy="298" r="20" fill="{MINT}"/>{_face()}{badge}</g>')


# One character, a costume per area. No third-party logos (e.g. no play-button shapes): generic props only.
BRAND = _character(under=f'<line x1="256" y1="150" x2="256" y2="104"/><path d="M256 70 l7 20 l20 7 l-20 7 l-7 20 l-7 -20 '
                         f'l-20 -7 l20 -7 z" fill="{SPARKLE}" stroke-width="6"/>')
MAIL = _character(body='<path d="M122 176 L256 262 L390 176" fill="none"/>',
                  badge=f'<circle cx="398" cy="158" r="34" fill="{BADGE}"/><text x="398" y="172" text-anchor="middle" {FONT} '
                        f'font-weight="900" font-size="42" fill="{INK}" stroke="none">0</text>')
SUBSCRIPTIONS = _character(
    under=f'<line x1="220" y1="152" x2="180" y2="96"/><line x1="292" y1="152" x2="332" y2="96"/>'
          f'<circle cx="180" cy="96" r="10" fill="{SPARKLE}"/><circle cx="332" cy="96" r="10" fill="{SPARKLE}"/>',
    body='<rect x="128" y="186" width="256" height="190" rx="38" fill="#6BEBB6" stroke-width="7"/>',
    badge='<circle cx="398" cy="158" r="34" fill="#8FB0FF"/><path d="M382 158 l11 12 l21 -24" fill="none" stroke-width="9"/>')


def place(character, x, y, scale):
    return f'<g transform="translate({x} {y}) scale({scale}) translate(-30 -33)">{character}</g>'


def text(x, y, size, weight, color, words, anchor="start", mono=False):
    font = 'font-family="ui-monospace, Menlo, monospace"' if mono else FONT
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" {font} font-weight="{weight}" font-size="{size}" fill="{color}">{words}</text>'


def lockup(bg, word, tag):
    return (f'<rect width="1600" height="600" fill="{bg}"/>' + place(BRAND, 120, 70, 0.92)
            + text(640, 330, 220, 900, word, "tidy") + text(648, 420, 46, 600, tag, "Declutter, safely."))


FILES = {
    "tidy-mascot": (500, 500, place(BRAND, 0, 0, 1)),
    "tidy-mascot-mail": (500, 500, place(MAIL, 0, 0, 1)),
    "tidy-mascot-subscriptions": (500, 500, place(SUBSCRIPTIONS, 0, 0, 1)),
    "tidy-icon": (512, 512, f'<rect width="512" height="512" rx="112" fill="{NIGHT}"/>' + place(BRAND, 56, 56, 0.8)),
    "tidy-lockup-dark": (1600, 600, lockup(NIGHT, "#F5F7FA", MINT)),
    "tidy-lockup-light": (1600, 600, lockup("#F4F7F5", INK, "#1A6650")),
    "tidy-family": (1560, 620, f'<rect width="1560" height="620" fill="{NIGHT}"/>' + "".join(
        place(c, x, 60, 0.9) + text(x + 228, 560, 34, 800, "#F5F7FA", label, "middle")
        for c, x, label in ((BRAND, 40, "Tidy"), (MAIL, 560, "Tidy for mail"), (SUBSCRIPTIONS, 1080, "Tidy for subscriptions")))),
    "tidy-launch-card": (1600, 900, f'<rect width="1600" height="900" fill="{NIGHT}"/>' + place(BRAND, 930, 170, 1.15)
        + text(110, 250, 104, 900, "#F5F7FA", "Meet Tidy.")
        + text(110, 360, 54, 700, "#F5F7FA", "AI cleans your Gmail")
        + text(110, 430, 54, 700, "#F5F7FA", "and YouTube. You stay")
        + text(110, 500, 54, 700, "#F5F7FA", "in charge.")
        + text(110, 600, 40, 600, MINT, "About 45 cents to sort 12,158 emails")
        + f'<rect x="110" y="680" width="620" height="96" rx="20" fill="#1A2A24" stroke="{MINT}" stroke-width="3"/>'
        + text(140, 742, 40, 700, "#F5F7FA", "$ pipx install tidy-ai", mono=True)),
}


def main():
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    for name, (w, h, body) in FILES.items():
        svg = HERE / f"{name}.svg"
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
                       f'<title>Tidy</title>{body}</svg>\n')
        if chrome:
            page = HERE / "_render.html"
            page.write_text(f'<html><body style="margin:0;background:transparent"><img src="{svg.name}" width="{w}" height="{h}"></body></html>')
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                            "--default-background-color=00000000", f"--window-size={w},{h}",
                            f"--screenshot={HERE / (name + '.png')}", page.as_uri()], capture_output=True, check=True)
            page.unlink()


if __name__ == "__main__":
    main()
