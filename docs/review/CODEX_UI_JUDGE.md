# Codex task: judge the Tidy review page (LLM judge, read-only)

Work in the repository root. Save quota: do not print files back, do not run evals or `--execute`, do not read `.tidy/`, `data/`, `secrets/`, `.env`. Run the tests once at the start (`.venv/bin/python -m unittest discover -s tests -q`).

Judge `tidy/report_html.py`, its tests `tests/test_report_html.py`, and the `propose --html` wiring in `tidy/__main__.py`. To see the page, render synthetic data: `PYTHONPATH=tests .venv/bin/python -c "import test_report_html as t; print(t.build())" > /tmp/page.html` and read that file.

Purpose: a self-contained, read-only HTML page the owner opens locally to review proposals (KEEP, REVIEW, UNSUBSCRIBE, SUBSCRIBE), see the reasons, and copy commands. Rules it must respect: owner approves every change; dry-run default; private and API-derived data stays local and expires after 30 days; no server, no network; agents and humans both use it.

## Score each 1 to 5 with one-line evidence (file:line)
1. **Safety.** Escaping of every YouTube or model string, CSP strength, no external loads, no way for a hostile channel title or video URL to run script or leak data. Try to break it.
2. **Correctness.** Order, counts, gate text, labels, expiry date, dimension scales (0 to 3 versus 0 to 1), edge cases (no videos, no uploads, missing dimensions, zero proposals).
3. **Usability.** Can the owner decide quickly? Filters, density, what is missing (for example search, sort by value, showing the second opinion).
4. **Accessibility.** Contrast in both themes, keyboard use of filters and details, semantics, pressed-state of chips, reduced motion, mobile width.
5. **Honesty.** Does it avoid overstating certainty, and show that the gate is closed and nothing acts automatically?
6. **Simplicity.** Is anything over-built? Anything that should be cut?
7. **Fit with the project rules.** Compare with `docs/adr/0003`, `0004`, `0005` and `AGENTS.md`.

## Output (under 35 lines)
The seven scores, then `BLOCKER`, `SHOULD FIX`, `NICE TO HAVE` items as `path:line: problem. fix.` You may apply a `SHOULD FIX` item directly if it is under 10 lines and tests still pass. Commit nothing and push nothing. End with an overall score out of 35 and a one-line ship verdict.
