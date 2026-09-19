"""Baseline: answer the same Jev questions with Claude Code headless (`claude -p`), timing every call.

Same stored evidence, same rubric text, same concurrency as `tidy judge`. Results go to .tidy/ (private).
Usage: python evals/claude_baseline.py --model haiku --limit 8 --workers 6 [--out .tidy/eval_claude_haiku.json]
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from tidy import judge, store
from tidy.escalate import OUTPUT_SCHEMA, ask, prompt_for  # noqa: F401 (re-exported for other runners)


def eval_samples(db, data_dir, limit=None):
    """The 110 channels every system was judged on; later-collected candidates never join an eval."""
    wanted = json.loads((Path(data_dir) / "experiment_2.json").read_text())["channels"]
    return [s for s in store.latest_samples(db) if s.channel_id in wanted][:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", help="claude --effort level, e.g. low (favours Claude on speed)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    args = ap.parse_args()
    db = store.connect(args.data_dir / "inventory.sqlite3")
    samples = eval_samples(db, args.data_dir, args.limit)
    states = {s.channel_id: judge._state(s, judge.DEFAULT_INTERESTS, False) for s in samples}
    started = time.monotonic()
    with ThreadPoolExecutor(args.workers) as pool:
        replies = list(pool.map(lambda cid: ask(args.model, states[cid], args.effort), states))
    report = {"model": args.model, "effort": args.effort, "workers": args.workers, "channels": dict(zip(states, replies)),
              "wall_ms": round((time.monotonic() - started) * 1000)}
    out = args.out or args.data_dir / f"eval_claude_{args.model}_{args.effort or 'default'}.json"
    out.write_text(json.dumps(report, indent=1))
    ok = [r for r in replies if "answers" in r]
    print(json.dumps({"model": args.model, "n": len(replies), "errors": len(replies) - len(ok), "wall_ms": report["wall_ms"],
                      "cost_usd": round(sum(r.get("cost_usd") or 0 for r in ok), 4)}))


if __name__ == "__main__":
    main()
