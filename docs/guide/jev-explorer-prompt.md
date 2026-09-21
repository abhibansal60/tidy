# Jev explorer session prompt

Paste the block below into a new Claude Code or Codex session opened in the Tidy repo. It walks the ranked ideas in `docs/research/jev-ecosystem-ideas.md` one at a time, using the method in `docs/guide/jev-playbook.md`.

```text
You are helping me explore TypeSafe's Jev (a System One decision model: Choice, Score, Noul) through a series of small, measured experiments. Work in this repo (Tidy, github.com/abhibansal60/tidy). We do ONE idea at a time, and we stop after each for my go-ahead.

Read first, in order: AGENTS.md, docs/guide/jev-playbook.md, docs/research/jev-ecosystem-ideas.md (its ranked table and the compliance section), docs/adr/0003 to 0005, then the code you will reuse: tidy/judge.py and evals/. If a memory file for this repo exists, read it.

What we already know (do not re-derive): Jev is fast (about 0.43 s per call), cheap ($0.042 per million input tokens, output free), repeatable (3 to 4 times steadier than Sonnet 5), and agrees closely with frontier models on narrow judgments. No model, Jev included, predicted my personal keep or drop taste (AUC 0.43 to 0.52 on 66 labels); my behavior (watch history) did better (0.69). Independent tests show 3 to 6 times faster on direct APIs; our 21 to 48 times was through coding CLIs, so name the baseline every time. Confidence works as a ranking signal, not a calibrated probability, and Noul, Choice and Score can disagree on the same item. Use a boring baseline (rules, TF-IDF, a small model) in every experiment.

Hard constraints:
- The Jev terms forbid using its output to train an imitating model. Never label a dataset with Jev to train a local classifier. Fitting weights on Jev signals against human labels is allowed but confirm with TypeSafe before publishing a benchmark.
- Public terms reportedly say no confidential data, no SOC 2 or DPA; a compliant variant may come later (unverified). Use only my low-sensitivity mail, public datasets, or synthetic data. No company data.
- Never print, log or commit secrets. Private data stays in .tidy/, data/, secrets/, .env; anything public uses aliases and aggregates.
- No Gmail, Drive, Calendar or YouTube writes without me present and an explicit yes. Dry run by default. Never post or publish without showing me the exact text first.
- TDD in vertical slices, commit and push what is needed, keep git status clean. No em or en dashes in prose.
- Codex: use `codex exec ... < /dev/null`. Codex subagents default to gpt-5.6-terra to save Astra quota. Check my Claude usage before launching research agents.

The ideas, in ranked order (start with 1 unless I say otherwise; 3, 5 and 6 need work data and wait for compliance):
1. Inbox triage with labels from my own behavior versus a rule baseline
8. Label-budget learning curve (how many labels until Jev plus fitted weights beats the baseline)
3. Cascade router: cost per correct decision on real labels (needs data I may not have yet)
2. Injection-aware inbox triage benchmark
4. Label-noise and disagreement finder for triage sets
5. Shadow-mode routing for developer-advocacy or enablement inbound (work data, waits)
6. Jev as judge in internal agent evals at real sample size (work data, waits)
7. Cross-model confidence audit on one labeled set
9. Calendar load triage from my accept and decline history
10. Drive sharing-risk report (read-only; lowest feasibility)

For each idea, follow this template and show me a short written plan before running anything:
1. The decision, who owns it, and the cost of a wrong answer.
2. The question map (3 to 6 narrow questions, primitive for each, concrete Score levels) and what code computes versus what Jev sees.
3. Data: source, size, sensitivity, how labels are obtained (my behavior first, then a labeling sheet), a held-out set, and a blind relabel slice for label noise.
4. Baselines: at least one non-model baseline and one cheap-model baseline.
5. Metrics: AUC or accuracy with bootstrap intervals, abstain-band coverage versus error, repeatability, cost per correct decision, latency, all with the baseline named.
6. A written go or no-go rule, fixed before any results.
7. The artifact for a developer advocate: a short post, a repo folder with the eval scripts, and one honest chart. Plain-language and developer versions.

Begin by confirming this plan in five lines, then ask which idea to start with and what data I can provide.
```
