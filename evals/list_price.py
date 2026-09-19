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
PROJECT = {"claude-fable-5-1": "claude-opus-5"}  # no run yet: assume the reference model's output length


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


def project(model, reference, prompt_tokens):
    """Cost of `model` if it wrote as many output tokens as the already-run `reference` model."""
    price_in, price_out = PRICES[model]
    return {"model": model, "projected_from": reference["model"], "channels": reference["channels"],
            "output_tokens": reference["output_tokens"],
            "usd": round((prompt_tokens * reference["channels"] * price_in + reference["output_tokens"] * price_out) / 1e6, 4)}


def all_estimates(data_dir, prompt_tokens):
    rows = [row for path in sorted(Path(data_dir).glob("eval_*_*.json"))
            if "repeat" not in path.name and (row := estimate(path, prompt_tokens))]
    have = {r["model"] for r in rows}
    for model, ref in PROJECT.items():
        base = next((r for r in rows if r["model"] == ref), None)
        if model not in have and base:
            rows.append(project(model, base, prompt_tokens))
    return rows


def prompt_tokens(data_dir):
    samples = eval_samples(store.connect(Path(data_dir) / "inventory.sqlite3"), data_dir)
    chars = [len(prompt_for(judge._state(s, judge.DEFAULT_INTERESTS, False))) for s in samples]
    return sum(chars) / len(chars) / CHARS_PER_TOKEN


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    args = ap.parse_args()
    per_channel = prompt_tokens(args.data_dir)
    print(f"prompt: ~{per_channel:.0f} tokens per channel")
    for row in all_estimates(args.data_dir, per_channel):
        print(json.dumps(row))


if __name__ == "__main__":
    main()
