"""How well does each system's raw answers separate the owner's keep and drop labels?

No tuning: AUC per dimension plus one composite fixed in advance. Prints JSON (private inputs).
Usage: python -m evals.labeled_accuracy JEV.json CLAUDE.json... [--data-dir .tidy]
"""

import argparse
import json
from pathlib import Path
import random

from tidy import review, store
from evals.compare import DIMS, jev_values


def auc(pos, neg):
    """P(a random keep scores above a random drop); ties count half."""
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def composite(v):  # fixed in advance: relevance and value up, packaging risk down, equal weight
    return (v["relevance"] / 3 + v["apparent_value"] / 3 + (1 - v["packaging_risk"])) / 3


def bootstrap_ci(pos, neg, n=2000, seed=7):
    rng = random.Random(seed)
    stats = sorted(auc([rng.choice(pos) for _ in pos], [rng.choice(neg) for _ in neg]) for _ in range(n))
    return round(stats[int(.025 * n)], 2), round(stats[int(.975 * n)], 2)


def score(values, labels):
    keep = [k for k, v in labels.items() if v == "keep" and k in values]
    drop = [k for k, v in labels.items() if v == "drop" and k in values]
    out = {"keep": len(keep), "drop": len(drop)}
    for name, f in [("relevance", lambda v: v["relevance"]), ("apparent_value", lambda v: v["apparent_value"]),
                    ("packaging_risk_inverted", lambda v: 1 - v["packaging_risk"]), ("composite", composite)]:
        pos, neg = [f(values[k]) for k in keep], [f(values[k]) for k in drop]
        out[name] = {"auc": round(auc(pos, neg), 2), "ci95": bootstrap_ci(pos, neg)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jev")
    ap.add_argument("claude", nargs="*")
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    args = ap.parse_args()
    db = store.connect(args.data_dir / "inventory.sqlite3")
    labels = review.current_labels(db)
    report = {"labels": {v: sum(x == v for x in labels.values()) for v in ("keep", "drop", "unsure")},
              "jev": score(jev_values(args.jev)[1], labels)}
    for path in args.claude:
        c = json.loads(Path(path).read_text())
        report[f"claude_{c['model']}_{c.get('effort') or 'default'}"] = score(
            {k: v["answers"] for k, v in c["channels"].items() if "answers" in v}, labels)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
