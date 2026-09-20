# Codex task: pre-release review of Tidy (read-only unless a fix is small and safe)

Work in the repository root, about to become public. Save quota: do not print files back, do not run evals or any `--execute`, do not read `.tidy/`, `data/`, `secrets/`, `.env`, `token*.json`. Read only `git ls-files` content. Run the tests once at the start and once at the end: `.venv/bin/python -m unittest discover -s tests -q`.

## Review, in this order
1. **Secrets and privacy.** Scan tracked files and full git history (`git log -p`) for keys, tokens, refresh tokens, emails other than `example.com`, real channel IDs or titles, absolute home paths, anything that identifies the owner beyond the public commit author. Report file and line, not the value.
2. **Safety of mutations.** Read `tidy/mutate.py`, `tidy/youtube.py`, `tidy/__main__.py`. Confirm: every unsubscribe or subscribe path is dry-run by default, budget-checked before the first call, audited, gated by owner approval or the closed gate, capped per run, bound to the verified account, and never retried on an unknown outcome. Look for any path that mutates without `--execute`, double-spends quota, or skips the account check.
3. **Correctness.** Read `tidy/policy.py`, `tidy/review.py`, `tidy/judge.py`, `tidy/discovery.py`, `tidy/store.py`. Look for wrong thresholds, off-by-one, retention (30-day purge) gaps, cache-key mistakes, and any place API-derived data could outlive 30 days.
4. **Install and packaging.** Read `install.sh`, `pyproject.toml`, `requirements.txt`. Would `curl -fsSL .../install.sh | sh` on a clean machine with Python 3.14 work? Is the install script safe to pipe to a shell (no eval, no network beyond git and pip, no secret access)? Are the dependency pins and `requires-python` right?
5. **README and docs.** Read `README.md` and `docs/agent-setup.md`. Could a new human reach a working `tidy propose` in under 15 minutes using only these? Could a coding agent follow the runbook without asking questions it should not need to ask? List missing steps, wrong commands (check each command against `tidy --help`), stale claims, clutter. Check every link and path exists.
6. **Public-release hygiene.** LICENSE present and correct, no internal-only docs that embarrass or mislead, honest claims (speed measured through coding CLIs; Fable 5.1 cost is a projection), no scary defaults.

## Output (under 40 lines)
`BLOCKER`, `SHOULD FIX`, `NICE TO HAVE` lists, each item as `path:line: problem. fix.` You may fix `SHOULD FIX` items directly if the change is under 10 lines and tests still pass; commit nothing, push nothing. End with a one-line verdict: ship, or ship after fixing the blockers.
