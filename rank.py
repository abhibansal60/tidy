import csv, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

HERE = Path(__file__).parent
for line in (HERE.parent / ".env").read_text().splitlines():
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())

QUESTIONS = {
    "topic": Choice(
        instructions="What is this channel mainly about, judged from its recent video titles?",
        criteria={
            "ai_software": "AI, machine learning, programming, software engineering, dev tools, systems, computer science",
            "science_tech": "Science, math, hardware, engineering, or other genuinely interesting technical explainers",
            "other_educational": "Educational content outside tech: history, finance, self-improvement, languages, etc.",
            "entertainment": "Gaming, vlogs, comedy, reactions, music, sports, celebrity, lifestyle",
            "other": "None of the above",
        },
    ),
    "depth": Score(
        instructions="How substantive is this channel's content, judged from its titles?",
        criteria=[
            "Clickbait, drama, or hype with no real information",
            "Shallow news recaps, listicles, or surface-level overviews",
            "Solid tutorials or explainers that teach something concrete",
            "Deep technical work: detailed builds, rigorous analysis, or expert-level teaching",
        ],
    ),
    "slop": Noul(
        instructions=(
            "Is this channel slop: clickbait or outrage titles, breathless AI hype, "
            "recycled news, get-rich-quick pitches, or mass-produced low-effort content?"
        ),
    ),
}
TOPIC_VALUE = {"ai_software": 1.0, "science_tech": 0.75, "other_educational": 0.4, "entertainment": 0.1, "other": 0.0}


def fetch_titles(ch):
    r = subprocess.run(
        ["yt-dlp", "--flat-playlist", "-I", "1:12", "--print", "%(title)s",
         f"https://www.youtube.com/channel/{ch['id']}/videos"],
        capture_output=True, text=True, timeout=90, cwd=HERE, env={**os.environ, "PATH": f"{HERE/'.venv/bin'}:{os.environ['PATH']}"},
    )
    return [t for t in r.stdout.splitlines() if t.strip()]


def judge(client, ch):
    try:
        titles = fetch_titles(ch)
    except Exception as e:
        return {**ch, "error": f"fetch: {e}"}
    if not titles:
        return {**ch, "error": "no videos"}
    r = client.system_one(state={"channel": ch["title"], "recent_video_titles": titles}, questions=QUESTIONS)
    a = r.answers
    topic_p = a["topic"].probabilities
    topic = sum(TOPIC_VALUE[k] * p for k, p in topic_p.items())
    depth = a["depth"].score / 3
    slop = a["slop"].noul
    # ponytail: fixed weights, tune against your own gut check of the output
    quality = 0.5 * topic + 0.3 * depth + 0.2 * (1 - slop)
    tier = "good" if quality >= 0.6 and slop < 0.5 else "worse" if quality < 0.35 or slop > 0.75 else "bad"
    return {**ch, "topic": a["topic"].choice, "depth": round(depth, 2), "slop": round(slop, 2),
            "quality": round(quality, 3), "tier": tier, "titles": titles[:4]}


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = list(csv.DictReader((HERE / "yt/subscriptions.csv").open()))
    chans = [{"id": r["Channel ID"], "title": r["Channel title"]} for r in rows][:limit]
    with TypeSafeClient() as client, ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda c: judge(client, c), chans))
    (HERE / "results.json").write_text(json.dumps(results, indent=1))
    ok = sorted([r for r in results if "tier" in r], key=lambda r: -r["quality"])
    with (HERE / "ranking.md").open("w") as f:
        for tier in ("good", "bad", "worse"):
            f.write(f"\n## {tier} ({sum(r['tier']==tier for r in ok)})\n")
            for r in ok:
                if r["tier"] == tier:
                    f.write(f"- {r['title']} — q={r['quality']} topic={r['topic']} depth={r['depth']} slop={r['slop']}\n")
        errs = [r for r in results if "error" in r]
        f.write(f"\n## unjudged ({len(errs)})\n" + "".join(f"- {r['title']}: {r['error']}\n" for r in errs))
    print(f"done: {len(ok)} judged, {len(results)-len(ok)} failed -> ranking.md")


if __name__ == "__main__":
    main()
