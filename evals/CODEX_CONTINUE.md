# Codex continuation: finish the Astra and Sol evals

Read `evals/CODEX_PROMPT.md` first; every constraint there still applies (no channel names or IDs in reports, never read `data/`, `.env`, `secrets/` or token files, do not modify `tidy/`, no commits of private outputs, no `--execute` of Tidy mutations, only the named models).

## State when this was written
- `evals/codex_baseline.py` and `tests/test_codex_baseline.py` exist and are committed. The full suite passes.
- `.tidy/eval_codex_gpt-5.6-sol_default.json`: complete, 110 of 110 channels.
- `.tidy/eval_codex_gpt-6-astra_default.json`: partial, 42 of 110 answered; 68 failed when Codex quota ran out.
- No low-effort pass, no repeatability run and no labeled-accuracy run exists for either model yet.

## Do, in order
1. **Resume support (TDD, small).** Add `--resume` to `evals/codex_baseline.py`: when `--out` (or the default file) exists, keep every channel that already has `answers` and ask only for the rest, then write the merged file with the same shape and the original channel order. Failing test with a fake `ask_fn` first (assert only the failed channels are re-asked). Run the full suite.
2. **Finish Astra.** `python -m evals.codex_baseline --model gpt-6-astra --resume`. If quota runs out again, stop, keep the merged partial file, and report the counts and the error category only.
3. **Low-effort passes** for both models (`--effort low`), if the CLI accepts an effort setting; name files by model and effort.
4. **Repeatability** for each model: the first 30 channels sorted by channel ID, two runs, as `evals/repeat.py` does for Claude. Write `.tidy/eval_repeat_codex_<model>.json`.
5. **Compare:** `python -m evals.compare .tidy/experiment_2.json <every .tidy/eval_*.json>` then `python -m evals.labeled_accuracy` with the same files. Paste both outputs.

## Report (plain text, short)
Per model: channels answered, error categories, wall time, per-call median and p95, tokens, cost or why null, rank agreement with Jev per dimension, repeatability, labeled-accuracy AUCs with intervals. List anything not run and why.
