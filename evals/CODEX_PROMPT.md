# Codex task: run the Tidy channel-judging eval on two more models

You are working in `/home/abhi/code/jev` (the Tidy app). Tidy judges YouTube channels with four narrow questions. Jev (TypeSafe) and Claude models have already been run on the same stored evidence. Your job is to run the identical eval on two OpenAI models through Codex CLI and write results in the same file format, so they can be added to an existing comparison.

## Read first
- `evals/claude_baseline.py`: the Claude runner. Reuse `prompt_for` and `OUTPUT_SCHEMA` from it so every model gets exactly the same prompt, rubric text and JSON schema. Do not reword the prompt.
- `tidy/judge.py`: `QUESTIONS` and `_state` (how evidence is rendered). Use `titles-v1` rendering: `judge._state(sample, judge.DEFAULT_INTERESTS, False)`.
- `evals/compare.py` and `evals/repeat.py`: how results are read and compared.
- `AGENTS.md` and `CONTEXT.md`: binding rules and vocabulary.

## Models
Run these two: **Sol** and **Astra** (use the exact model IDs Codex exposes; list them with the CLI's model listing or `codex --help`). If either name does not match a model you can select, stop and ask the owner; do not substitute another model.

## Build
Create `evals/codex_baseline.py` mirroring `evals/claude_baseline.py`:
- Same CLI: `--model`, `--effort`, `--limit`, `--workers` (default 6), `--out`, `--data-dir` (default `.tidy`).
- Load the stored samples with `store.latest_samples(store.connect(data_dir/"inventory.sqlite3"))`, build each state with `judge._state(...)`, and send `prompt_for(state)` to `codex exec` (check `codex exec --help` for the current flags). Requirements for each call: no tools or file access needed (read-only sandbox, no network beyond the model call), no session persistence, structured output constrained by `OUTPUT_SCHEMA`, one process per channel, 6 in flight at a time.
- Record per channel: `answers` (the four values), `wall_ms` (whole subprocess), token usage if Codex reports it (input, cached input, output), and `cost_usd` if it can be derived from reported usage and published prices (otherwise `null`; never invent prices).
- Write `.tidy/eval_codex_<model>_<effort or default>.json` in exactly this shape, so `evals/compare.py` can read it:
  `{"model": ..., "effort": ..., "workers": 6, "wall_ms": <whole run>, "channels": {"<channel_id>": {"answers": {...}, "wall_ms": ..., "tokens": {...}, "cost_usd": ...}}}`
  Failed channels get `{"error": "<short safe message>", "wall_ms": ...}` instead of `answers`.
- Keep it small and boring, in the style of the existing file. Add a short test with a fake subprocess (no real Codex call) for the parsing and file shape, under `tests/`.

## Run
1. Smoke test with `--limit 2` per model first. Report timings and confirm the output parses.
2. Then run all 110 channels for each model at default effort, plus a second pass for each model at low effort if the CLI supports an effort setting. Name files by model and effort.
3. Run repeatability for each model on the same first 30 channels sorted by channel ID, twice, as `evals/repeat.py` does for Claude. Add a `--provider codex` (or equivalent) path there only if it is a small change; otherwise write the numbers to `.tidy/eval_repeat_codex_<model>.json` from a short script.
4. Compare: `.venv/bin/python -m evals.compare .tidy/experiment_2.json <every eval_codex_*.json and the existing Claude files>`. Then run `python -m evals.labeled_accuracy` with the same files. Paste both outputs in your report.

## Constraints
- The evidence in `.tidy/inventory.sqlite3` comes from the owner's YouTube API data and their private subscription list. It is being sent to a third-party model provider by this task. The owner has asked for this run; do not send it anywhere else, and do not run any model that was not named above.
- Never read or print `.env`, `secrets/`, `.tidy/token*.json`, `data/`, or the owner's labels file. Do not print channel names or IDs in your report; refer to channels by count or rank only. Results files stay under `.tidy/` (gitignored).
- Do not modify `tidy/`, and do not touch the database. No network calls other than the model calls. No `--execute` of any Tidy mutation command. Do not push, and do not commit private outputs.
- Follow TDD for the new script: failing test, then minimal code. Run `.venv/bin/python -m unittest discover -s tests` before finishing; it must pass.
- Use the same 110 channels and the same order as the other systems. If a model fails on more than a few channels, report the error categories, not the raw provider output.

## Report back (plain text, short)
Files created, tests run, per model: wall time, per-call median and 95th percentile, tokens, estimated cost (or why null), error count, rank agreement with Jev per dimension, repeatability numbers, and the labeled-accuracy AUCs. List anything you could not run and why. Do not include channel names.
