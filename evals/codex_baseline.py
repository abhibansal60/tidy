"""Run Tidy's fixed channel judgment prompt through Codex CLI."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import time

from tidy import judge, store
from evals.claude_baseline import OUTPUT_SCHEMA, prompt_for


def _text(item):
    if not isinstance(item, dict):
        return ""
    for key in ("text", "output_text"):
        if isinstance(item.get(key), str):
            return item[key]
    content = item.get("content", []) if isinstance(item, dict) else []
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        return "".join(parts)
    return ""


def parse_events(stdout):
    """Return structured answer and usage from Codex JSONL events."""
    answer_text = None
    usage = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
        item = event.get("item") or {}
        if item.get("type") in ("agent_message", "message"):
            text = _text(item)
            if text:
                answer_text = text
    if answer_text is None:
        raise ValueError("Codex returned no final message")
    answer_text = answer_text.strip()
    if answer_text.startswith("```"):
        lines = answer_text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        answer_text = "\n".join(lines).strip()
    answer = json.loads(answer_text)
    if not isinstance(answer, dict) or set(answer) != set(OUTPUT_SCHEMA["properties"]):
        raise ValueError("Codex returned an invalid answer shape")
    tokens = {k: usage.get(k) for k in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return answer, tokens


def ask(model, state, effort=None, run=subprocess.run, schema_path=None):
    started = time.monotonic()
    own_schema = schema_path is None
    if own_schema:
        temporary = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(OUTPUT_SCHEMA, temporary)
        temporary.close()
        schema_path = temporary.name
    command = ["codex", "exec", "--ephemeral", "--sandbox", "read-only", "--json",
               "--skip-git-repo-check", "--output-schema", str(schema_path), "--model", model]
    if effort:
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
    command.append("Do not use tools, read files, or access the network. Return only the requested structured answer.")
    try:
        proc = run(command, input=prompt_for(state), capture_output=True, text=True, timeout=300)
        wall = round((time.monotonic() - started) * 1000)
        if proc.returncode:
            return {"error": "codex process failed", "wall_ms": wall}
        try:
            answers, tokens = parse_events(proc.stdout)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {"error": "codex response could not be parsed", "wall_ms": wall}
        return {"answers": answers, "wall_ms": wall, "tokens": tokens, "cost_usd": None}
    except subprocess.TimeoutExpired:
        return {"error": "codex request timed out", "wall_ms": round((time.monotonic() - started) * 1000)}
    finally:
        if own_schema:
            Path(schema_path).unlink(missing_ok=True)


def run_eval(model, effort, data_dir, limit=None, workers=6, ask_fn=ask):
    db = store.connect(Path(data_dir) / "inventory.sqlite3")
    samples = store.latest_samples(db)
    if limit is not None:
        samples = samples[:limit]
    states = {sample.channel_id: judge._state(sample, judge.DEFAULT_INTERESTS, False) for sample in samples}
    started = time.monotonic()
    with ThreadPoolExecutor(workers) as pool:
        replies = list(pool.map(lambda cid: ask_fn(model, states[cid], effort), states))
    return {"model": model, "effort": effort, "workers": workers,
            "wall_ms": round((time.monotonic() - started) * 1000),
            "channels": dict(zip(states, replies))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    args = ap.parse_args(argv)
    report = run_eval(args.model, args.effort, args.data_dir, args.limit, args.workers)
    out = args.out or args.data_dir / f"eval_codex_{args.model}_{args.effort or 'default'}.json"
    out.write_text(json.dumps(report, indent=1))
    ok = sum("answers" in item for item in report["channels"].values())
    print(json.dumps({"model": args.model, "n": len(report["channels"]),
                      "errors": len(report["channels"]) - ok, "wall_ms": report["wall_ms"]}))


if __name__ == "__main__":
    main()
