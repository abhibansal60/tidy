"""Repeatability: judge the same channels twice per system with no cache; report how much answers move.

Usage: python -m evals.repeat --n 30 --model haiku --effort low
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics

from tidy import experiment, judge, store
from evals.claude_baseline import ask, eval_samples
from evals.compare import DIMS


def jev_run(client, samples):
    result = judge.judge(client, samples, "titles-v1")  # no db: never cached
    return {j.channel_id: {d: j.answers[d].get("score", j.answers[d].get("noul")) for d in DIMS} for j in result.judgments}


def claude_run(model, effort, samples, workers=6):
    states = {s.channel_id: judge._state(s, judge.DEFAULT_INTERESTS, False) for s in samples}
    with ThreadPoolExecutor(workers) as pool:
        replies = list(pool.map(lambda cid: ask(model, states[cid], effort), states))
    return {cid: r["answers"] for cid, r in zip(states, replies) if "answers" in r}


def spread(a, b):
    ks = [k for k in a if k in b]
    return {d: {"mean_abs_diff": round(statistics.mean(abs(a[k][d] - b[k][d]) for k in ks), 3),
                "max_abs_diff": round(max(abs(a[k][d] - b[k][d]) for k in ks), 3)} for d in DIMS} | {"channels": len(ks)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    args = ap.parse_args()
    samples = sorted(eval_samples(store.connect(args.data_dir / "inventory.sqlite3"), args.data_dir), key=lambda s: s.channel_id)[:args.n]
    with experiment.typesafe_client() as client:
        jev = spread(jev_run(client, samples), jev_run(client, samples))
    claude = spread(claude_run(args.model, args.effort, samples), claude_run(args.model, args.effort, samples))
    report = {"n": len(samples), "jev": jev, f"claude_{args.model}_{args.effort}": claude}
    (args.data_dir / f"eval_repeat_{args.model}_{args.effort}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
