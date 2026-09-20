# Codex task: finish the model evals (spend as little quota as possible)

Work in the repository root. `evals/codex_baseline.py` runs one model over the 110 stored channels through `codex exec` and writes `.tidy/eval_codex_<model>_<effort|default>.json`. Sol is complete. Astra has 42 of 110 answered (68 failed on quota). Terra and Luna are not run.

## Rules
- Private data: never read or print `data/`, `.env`, `secrets/`, `.tidy/token*.json`; no channel names or IDs in output; do not touch `tidy/` or the database; no commits, no pushes; only these models: `gpt-6-astra`, `gpt-5.6-terra`, `gpt-5.6-luna`.
- Save your own quota: do not re-read files you already read, do not print result JSON or logs (summaries only, `--quiet`-style: redirect noisy output to a file and print counts), run the test suite once at the end and once after the code change, and do not explore beyond the files named here.
- If a run hits quota, stop the run, keep the partial file, and report. Do not retry in a loop.

## Steps, in priority order (stop after any step if quota is low)
1. **Add `--resume` (TDD, ~15 lines).** If the output file exists, keep every channel that already has `answers`, ask only for the others, write the merged file in the original channel order and same shape. One failing test with a fake `ask_fn` first (only failed channels are re-asked).
2. **Astra:** `python -m evals.codex_baseline --model gpt-6-astra --resume`
3. **Terra:** `python -m evals.codex_baseline --model gpt-5.6-terra`
4. **Luna:** `python -m evals.codex_baseline --model gpt-5.6-luna`
5. **Repeatability (only if quota remains):** for Astra, Terra and Luna, the first 30 channels sorted by channel ID, twice (as `evals/repeat.py` does for Claude); write `.tidy/eval_repeat_codex_<model>.json`. Skip Sol's low-effort and all other effort passes.
6. **Compare:** `python -m evals.compare .tidy/experiment_2.json .tidy/eval_*.json` and `python -m evals.labeled_accuracy .tidy/experiment_2.json .tidy/eval_*.json`. Keep only the final tables.

## Report (plain text, under 25 lines)
Per model: channels answered, error categories with counts, whole-run wall time, per-call median and p95, tokens per channel (input, cached, output), cost (or `null` for Codex), rank agreement with Jev per dimension, repeatability, labeled-accuracy AUC with interval. List anything not run and why. No channel names.
