"""List-price cost of each eval run if it had called the API directly (no coding-tool overhead).

Input is the prompt alone (characters / 3.5, an estimate); output is the measured output tokens.
Prices: platform.claude.com/docs/en/about-claude/pricing and developers.openai.com/api/docs/pricing (Sep 2026).
Usage: python -m evals.list_price [--data-dir .tidy]
"""

import argparse
import json
from pathlib import Path

from tidy import judge, store
from evals.claude_baseline import eval_samples, prompt_for

PRICES = {  # USD per million tokens: (input, output)
    "claude-fable-5-1": (10, 50), "claude-opus-5": (5, 25), "claude-sonnet-5": (2, 10),
    "claude-haiku-4-5-20251001": (1, 5), "haiku": (1, 5),
    "gpt-6-astra": (10, 50), "gpt-5.6-sol": (4, 20), "gpt-5.6-terra": (2, 12), "gpt-5.6-luna": (0.2, 1.2)}
CHARS_PER_TOKEN = 3.5


def estimate(path, prompt_tokens):
    run = json.loads(Path(path).read_text())
    done = [c for c in run["channels"].values() if "answers" in c]
    model = next((k for k in PRICES if k == run["model"] or run["model"].startswith(k)), None)
    if not model or not done:
        return None
    out = sum((c.get("tokens") or {}).get("output_tokens") or 0 for c in done)
    price_in, price_out = PRICES[model]
    return {"model": run["model"], "effort": run.get("effort"), "channels": len(done),
            "output_tokens": out, "usd": round((prompt_tokens * len(done) * price_in + out * price_out) / 1e6, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    args = ap.parse_args()
    samples = eval_samples(store.connect(args.data_dir / "inventory.sqlite3"), args.data_dir)
    chars = [len(prompt_for(judge._state(s, judge.DEFAULT_INTERESTS, False))) for s in samples]
    per_channel = sum(chars) / len(chars) / CHARS_PER_TOKEN
    print(f"prompt: ~{per_channel:.0f} tokens per channel ({len(samples)} channels)")
    for path in sorted(args.data_dir.glob("eval_*_*.json")):
        if "repeat" not in path.name and (row := estimate(path, per_channel)):
            print(json.dumps(row))


if __name__ == "__main__":
    main()
