"""Charts for docs/research/jev-calibration-audit.md from the private run files. Needs matplotlib.

Usage: python -m evals.calibration_charts [--out .tidy/calibration] [--to docs/assets/calibration]
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from evals import calibration as cal  # noqa: E402
from evals.calibration_audit import DATASETS, OUT  # noqa: E402

# dataviz reference palette, first three categorical slots (validated all-pairs, light surface)
SYSTEMS = {"jev": ("Jev", "#2a78d6", "o"), "haiku": ("Haiku 4.5", "#eb6834", "s"),
           "tfidf": ("TF-IDF + LR", "#1baf7a", "^")}
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
TITLES = {"banking77": "Banking77 (77 intents)", "nlbse": "NLBSE'24 issues (bug, feature, question)"}
MIN_BIN = 5  # reliability bins with fewer items are too noisy to plot


def scored(out, dataset, system):
    path = out / f"{dataset}_{system}.json"
    if not path.exists():
        return None
    items = {i["id"]: i for i in json.loads((out / f"manifest_{dataset}.json").read_text())["items"]}
    res = {k: v for k, v in json.loads(path.read_text())["results"].items() if "error" not in v}
    return {"top_prob": [v["top_prob"] for v in res.values()],
            "correct": [v["label"] == items[k]["label"] for k, v in res.items()],
            "p_candidate": [v["p_candidate"] for v in res.values()],
            "truth": [items[k]["candidate_is_true"] for k in res]}


def _axes(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def _figure(suptitle):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), facecolor=SURFACE)
    fig.suptitle(suptitle, color=INK, fontsize=13, x=0.01, ha="left")
    return fig, axes


def reliability_chart(out, to, conf_key, truth_key, name, suptitle, xlabel, ylabel):
    fig, axes = _figure(suptitle)
    for ax, dataset in zip(axes, DATASETS):
        _axes(ax, TITLES[dataset], xlabel, ylabel)
        ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--")
        ax.annotate("perfect calibration", (0.62, 0.55), color=MUTED, fontsize=8, rotation=38)
        for system, (label, color, marker) in SYSTEMS.items():
            s = scored(out, dataset, system)
            if not s:
                continue
            bins = [b for b in cal.reliability(s[conf_key], s[truth_key]) if b["n"] >= MIN_BIN]
            xs, ys = [b["mean_conf"] for b in bins], [b["accuracy"] for b in bins]
            ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=6,
                    label=f"{label} (n={len(s[conf_key])}, ECE {cal.ece(s[conf_key], s[truth_key]):.2f})")
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right")
    fig.tight_layout()
    fig.savefig(to / name, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def risk_coverage_chart(out, to):
    fig, axes = _figure("Answer only the most confident items: how many wrong answers remain?")
    for ax, dataset in zip(axes, DATASETS):
        _axes(ax, TITLES[dataset], "share of items answered (coverage)", "error among answered")
        ax.axhline(0.05, color=MUTED, linewidth=1, linestyle="--")
        ax.annotate("5% error", (0.88, 0.035), color=MUTED, fontsize=8)
        for system, (label, color, marker) in SYSTEMS.items():
            s = scored(out, dataset, system)
            if not s:
                continue
            curve = cal.risk_coverage(s["top_prob"], s["correct"])
            ax.plot(*zip(*curve), color=color, linewidth=2, label=f"{label} (n={len(s['correct'])})")
            ax.plot(*curve[-1], color=color, marker=marker, markersize=6)
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 0.5)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(to / "risk_coverage.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--to", type=Path, default=Path("docs/assets/calibration"))
    args = ap.parse_args()
    args.to.mkdir(parents=True, exist_ok=True)
    reliability_chart(args.out, args.to, "top_prob", "correct", "reliability_choice.png",
                      "Choice: when a system says p, is it right p of the time?",
                      "stated probability of the chosen label (bin mean)", "share correct")
    reliability_chart(args.out, args.to, "p_candidate", "truth", "reliability_noul.png",
                      "Noul: \"is this item label C?\" probability against the truth",
                      "stated probability of yes (bin mean)", "share actually yes")
    risk_coverage_chart(args.out, args.to)
    print(sorted(p.name for p in args.to.glob("*.png")))


if __name__ == "__main__":
    main()
