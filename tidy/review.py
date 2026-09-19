"""Owner review: labels, agreement with proposals (the calibration gate), labeling sample, Markdown report."""

from datetime import datetime
import json
from pathlib import Path

from . import judge, policy, store, watch_history

VERDICTS = ("keep", "drop", "unsure")
AGREES = {"KEEP": "keep", "WATCH": "keep", "UNSUBSCRIBE": "drop"}  # REVIEW and unsure are excluded
ORDER = ("UNSUBSCRIBE", "REVIEW", "WATCH", "KEEP", "SUBSCRIBE")


def label(db, channel_id, verdict, note="", source="cli"):
    if verdict not in VERDICTS:
        raise ValueError("Verdict must be keep, drop or unsure.")
    with db:
        db.execute("INSERT INTO owner_labels(channel_id, verdict, at, note, source) VALUES (?, ?, ?, ?, ?)",
                   (channel_id, verdict, store.now(), note, source))


def current_labels(db):
    """Latest verdict per channel."""
    return {r["channel_id"]: r["verdict"] for r in db.execute("SELECT channel_id, verdict FROM owner_labels ORDER BY id")}


def import_sheet(db, path):
    """Owner-edited sheet {"channels": [{channel_id, verdict, note}]}; blank verdicts are skipped, bad ones abort."""
    rows = json.loads(Path(path).read_text())["channels"]
    for r in rows:
        if r.get("verdict") and r["verdict"] not in VERDICTS:
            raise ValueError(f"Bad verdict {r['verdict']!r} for {r.get('channel_id')}; use keep, drop or unsure.")
    current, imported = current_labels(db), 0
    for r in rows:
        if r.get("verdict") and current.get(r["channel_id"]) != r["verdict"]:
            label(db, r["channel_id"], r["verdict"], r.get("note", ""), "sheet")
            imported += 1
    return {"imported": imported, "skipped": sum(1 for r in rows if not r.get("verdict"))}


def import_label_file(db, path):
    """Private format {"keep": [titles], "sloppy": [titles]}, matched to subscriptions by title."""
    data = json.loads(Path(path).read_text())
    by_title = {r["title"].casefold(): r["channel_id"] for r in db.execute("SELECT title, channel_id FROM subscriptions")}
    current, imported, unmatched = current_labels(db), 0, []
    for key, verdict in (("keep", "keep"), ("sloppy", "drop")):
        for title in data.get(key, []):
            cid = by_title.get(title.casefold())
            if cid is None:
                unmatched.append(title)
            elif current.get(cid) != verdict:
                label(db, cid, verdict, "imported from label file", "import")
                imported += 1
    return {"imported": imported, "unmatched": unmatched}


def agreement(db, proposals, held_out=None):
    labels, n, agreements = current_labels(db), 0, 0
    for p in proposals:
        verdict = labels.get(p.channel_id)
        if p.action in AGREES and verdict in ("keep", "drop") and (held_out is None or p.channel_id in held_out):
            n += 1
            agreements += AGREES[p.action] == verdict
    return {"n": n, "agreements": agreements, "rate": agreements / n if n else None}


def gate_status(stats, profile):
    gate, reasons = profile["gate"], []
    if stats["n"] < gate["min_labels"]:
        reasons.append(f"{stats['n']} labels, need {gate['min_labels']}")
    elif stats["rate"] is None or stats["rate"] < gate["min_agreement"]:
        reasons.append(f"agreement {stats['rate'] or 0:.2f}, need {gate['min_agreement']}")
    return {"open": not reasons, "reasons": reasons}


def sample_for_labeling(db, judgments, k):
    """Unlabeled channels, round-robin across (value tier, confident?) strata so labels are not all easy cases."""
    labeled, strata = current_labels(db), {}
    for j in sorted(judgments, key=lambda j: j.channel_id):
        value = j.answers["apparent_value"]
        key = (min(3, max(0, int(value["score"]))), value.get("confidence", 1) >= 0.7)
        if j.channel_id not in labeled:
            strata.setdefault(key, []).append(j.channel_id)
    queues, picked = [strata[key] for key in sorted(strata)], []
    while queues and len(picked) < k:
        picked += [q.pop(0) for q in queues][:k - len(picked)]
        queues = [q for q in queues if q]
    return picked


def derive(db, profile, now=None):
    """Proposals from stored samples and cached judgments; channels without a judgment are left out."""
    key = judge.interests_key(profile["interests"], profile["viewing_habits"])
    samples, judgments = [], []
    for s in store.latest_samples(db, now=now):
        j = store.get_judgment(db, s.evidence_hash, profile["schema_id"], key, now)
        if j:
            samples.append(s)
            judgments.append(j)
    trials = {r[0] for r in db.execute("SELECT channel_id FROM trials")}
    history = Path(profile["watch_history_path"]) if profile["watch_history_path"] else None
    if history and history.is_file():  # policy-2: revealed watching plus the two-opinion low-quality cascade
        counts = watch_history.watch_counts(history, profile["watch_window_days"], now)
        proposals = [policy.propose_watch(j, s, profile, counts.get(j.channel_id, 0),
                                          store.get_second_opinion(db, j.channel_id, s.evidence_hash, now),
                                          "trial" if j.channel_id in trials else "active")
                     for j, s in zip(judgments, samples)]
    else:
        proposals = [policy.propose(j, s, profile, "trial" if j.channel_id in trials else "active")
                     for j, s in zip(judgments, samples)]
    return proposals, judgments, samples


def render_report(proposals, judgments, samples, labels):
    by_j, by_s = {j.channel_id: j for j in judgments}, {s.channel_id: s for s in samples}
    lines = ["# Tidy proposals", ""]
    for p in sorted(proposals, key=lambda p: (ORDER.index(p.action), p.channel_id)):
        s, j = by_s[p.channel_id], by_j[p.channel_id]
        age = (f"newest upload {(datetime.fromisoformat(s.fetched_at) - datetime.fromisoformat(s.newest_published_at.replace('Z', '+00:00'))).days} days old"
               if s.newest_published_at else "no uploads")
        lines += [f"## {s.title}: {p.action}", "",
                  f"- Channel: https://www.youtube.com/channel/{p.channel_id}",
                  f"- Evidence: {s.coverage['collected']} of {s.coverage['requested']} videos, {age}",
                  f"- Signals: {'; '.join(p.signals) or 'none'}", "- Dimensions:"]
        for name, a in j.answers.items():
            value = a["score"] if "score" in a else a["noul"]
            conf = f" (confidence {a['confidence']:.2f})" if "confidence" in a else ""
            lines.append(f"  - {name}: {_fmt(name, value)}{conf}")
        lines += ["- Videos:"] + [f"  - [{v['title']}]({v['url']})" for v in s.videos]
        lines += [f"- Owner label: {labels.get(p.channel_id, 'none')}",
                  "- Owner override (keep / drop / unsure): ", "- Note: ", ""]
    return "\n".join(lines)


def _fmt(name, value):
    return f"{value:.1f}" if name in ("relevance", "apparent_value") else f"{value:.2f}"
