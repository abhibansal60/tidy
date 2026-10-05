"""Calibration metrics for the public-data audit (docs/research/jev-calibration-audit.md). Stdlib only."""

import random
import statistics

from evals.labeled_accuracy import auc, bootstrap_ci


def accuracy(correct):
    return sum(correct) / len(correct)


def bootstrap(items, stat, n=2000, seed=7):
    """95% percentile interval of stat(resample of items)."""
    rng = random.Random(seed)
    stats = sorted(stat([rng.choice(items) for _ in items]) for _ in range(n))
    return round(stats[int(.025 * n)], 3), round(stats[int(.975 * n)], 3)


def reliability(conf, correct, bins=10):
    """Non-empty equal-width bins: share correct against mean confidence."""
    groups = {}
    for c, ok in zip(conf, correct):
        groups.setdefault(min(int(c * bins), bins - 1), []).append((c, ok))
    return [{"lo": i / bins, "hi": (i + 1) / bins, "n": len(g), "mean_conf": statistics.mean(c for c, _ in g),
             "accuracy": accuracy([ok for _, ok in g])} for i, g in sorted(groups.items())]


def ece(conf, correct, bins=10):
    return sum(b["n"] * abs(b["accuracy"] - b["mean_conf"]) for b in reliability(conf, correct, bins)) / len(conf)


def brier(p, truth):
    return statistics.mean((x - t) ** 2 for x, t in zip(p, truth))


def auroc(scores, truth):
    """P(a random true item scores above a random false one); ties count half. None if a class is empty."""
    pos, neg = _split(scores, truth)
    return auc(pos, neg) if pos and neg else None


def auroc_ci(scores, truth):
    """95% interval, resampling true and false items separately so every resample has both."""
    pos, neg = _split(scores, truth)
    return bootstrap_ci(pos, neg) if pos and neg else (None, None)


def _split(scores, truth):
    return [s for s, t in zip(scores, truth) if t], [s for s, t in zip(scores, truth) if not t]


def _answered(conf, correct, threshold):
    kept = [ok for c, ok in zip(conf, correct) if c >= threshold]
    return len(kept) / len(conf), (1 - accuracy(kept) if kept else None)


def abstain_table(conf, correct, thresholds):
    """Answer only when confidence >= threshold: coverage and error among the answered."""
    return [dict(zip(("threshold", "coverage", "error"), (t, *_answered(conf, correct, t)))) for t in thresholds]


def heldout_gate(conf, correct, half_a, max_error=0.05):
    """Lowest threshold with error <= max_error on half A, then coverage and error on half B."""
    a = [(c, ok) for c, ok, h in zip(conf, correct, half_a) if h]
    b = [(c, ok) for c, ok, h in zip(conf, correct, half_a) if not h]
    ca, oa = zip(*a) if a else ((), ())
    threshold = next((t for t in sorted(set(ca)) if (_answered(ca, oa, t)[1] or 0) <= max_error), None)
    if threshold is None or not b:
        return {"threshold": None, "a_coverage": 0.0, "b_coverage": 0.0, "b_error": None}
    a_cov, _ = _answered(ca, oa, threshold)
    b_cov, b_err = _answered(*zip(*b), threshold)
    return {"threshold": threshold, "a_coverage": a_cov, "b_coverage": b_cov, "b_error": b_err}


def repeatability(first, second):
    """first/second: item id -> (label, confidence). Shared items only."""
    ids = [k for k in first if k in second]
    return {"items": len(ids),
            "label_agreement": accuracy([first[k][0] == second[k][0] for k in ids]),
            "mean_abs_change": round(statistics.mean(abs(first[k][1] - second[k][1]) for k in ids), 4)}
