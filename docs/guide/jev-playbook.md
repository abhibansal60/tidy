# Jev playbook: what we learned building Tidy

For us, when we build the next classification use case. Everything here comes from the Tidy work (110 subscriptions, 8 models, 66 human labels) and points at the code or notes where the evidence lives. Live TypeSafe docs (docs.typesafe.ai) stay the source of truth for the API; this file is about judgment and method.

## 1. What Jev is good for, and what it is not

Jev returns typed answers with probabilities, not text. In our runs it averaged about 0.43 seconds per call (max 2.1 s), roughly 1,000 input tokens per call, and cost about $0.004 for 110 channels at TypeSafe's published $0.042 per million input tokens with free output.

Good fit:
- Narrow judgments over many items: routing, triage, tagging, scoring, filtering, "is this evidence enough".
- Decisions where you want a probability you can threshold, and where speed and cost decide whether you can run it on everything.
- A cheap first pass that decides what an expensive model or a person looks at.

Poor fit:
- Open-ended writing, explanation, or multi-step reasoning.
- Questions whose answer is personal taste. All 8 models, Jev included, scored 0.43 to 0.52 against our own keep or drop labels (0.5 is a coin flip).
- Anything irreversible without a human approval step.

## 2. Designing the questions (`tidy/judge.py`)

- One narrow judgment per question. We used relevance, apparent value, packaging risk (clickbait), evidence sufficiency, and later watch likelihood.
- Pick the primitive by what the answer means: Score for a degree along ordered levels, Noul for yes or no, Choice for one of a set. Write Score levels as concrete situations that stand on their own.
- Bundle independent questions over the same state in one call. They run in parallel and cannot see each other.
- Question IDs are for code, not sent to the model. Put the full meaning in the instructions.
- State is named JSON. Put facts Jev must not compute in it precomputed by code (`_facts`: uploads per month, days since last upload, median length). Code owns arithmetic, dates and counts.
- Evidence rendering matters less than expected: adding video descriptions cost 54% more tokens and gave no clear gain. Titles were often too thin, so keep an "evidence sufficiency" question.
- Cache judgments by evidence hash, schema id and interests key, and expire them with the evidence.

## 3. Confidence and thresholds

- Confidence measures how concentrated the distribution is. It is not correctness and not permission to act.
- A Noul near 0.5 means undecided, not medium.
- Set thresholds on your own labeled data, not on demo numbers.
- Never act on one dimension alone. Where we allowed two independent judges on one dimension (Jev plus a second model both rating value low), we recorded the decision in ADR 0005.
- Cascade: Jev screens everything; a stronger model is asked only about the few Jev flags (`tidy/escalate.py`).

## 4. How to evaluate (`evals/`)

Order matters. Each step answers a different question.

1. **Same inputs for every judge.** One evidence file, one prompt, one JSON schema (`evals/claude_baseline.py`, `evals/codex_baseline.py`). Freeze the item set; we once let 29 later-collected channels leak in and had to rerun.
2. **Speed.** Whole-run wall time and per-call median and p95. Say what the baseline is. Coding CLIs add per-call overhead; our 21 to 48 times became 3 to 6 times in independent direct-API tests.
3. **Cost.** Measure tokens; price them at published rates and cite the page (`evals/list_price.py`). Subscription CLIs report tokens, not dollars. Never invent a price; label projections as projections (our Fable 5.1 number).
4. **Repeatability.** Run the same items twice, no cache, report mean absolute change (`evals/repeat.py`). Jev moved 3 to 4 times less than Sonnet 5.
5. **Agreement between judges** (Spearman). This shows consistency only. High agreement with an expensive model does not make either right. Use it to justify a cheaper judge, not to claim accuracy.
6. **Truth.** Compare against human labels with AUC and a bootstrap interval (`evals/labeled_accuracy.py`). This is the test that mattered.
7. **Label noise.** Relabel a subset blind, later, and measure self-agreement. Ours was 10 of 13 (about 77%), which caps how well anything can score and made our 85% automation gate unrealistic.
8. **A simple baseline.** Our watch-history count scored 0.69 (interval 0.59 to 0.80) and beat every model. Always test the boring signal before crediting a model.

## 5. What we learned about the task

- Quality is not taste. Models agree with each other and still do not know what a person keeps. Revealed behavior (what the person actually does) beat model judgment.
- Descriptions added cost, not signal. Thin evidence is a real failure mode: ask for sufficiency.
- Automation for a personal-taste question is not worth its risk. Propose, then let the owner approve.

## 6. Architecture rules that held up

- Jev judges. Code decides thresholds, caps, budgets and every side effect.
- Dry run by default; `--execute` only when the owner says so.
- Check the whole batch budget before the first mutation, not half-way through.
- Audit every action; expire API-derived data on the provider's schedule (30 days for YouTube).
- Private data stays local and out of git; use aliases in anything public (`docs/adr/0003`).

## 7. Mistakes we made (so we do not repeat them)

- Judged with the wrong schema, so `propose` found no cached judgments (the CLI now defaults to profile settings).
- Let extra items into an eval set; a resumed run reported only its resumed wall time.
- Cited a public benchmark for the wrong claim (an independent 25 times result was attributed as 3 to 6 times). Check each source's baseline before quoting.
- Contaminated a blind relabel by showing metadata.
- Compared a CLI-run baseline to direct-API claims without naming the difference.

## 8. Communicating results

- Name the baseline in the same sentence as the multiplier.
- Lead with the negative or surprising result; put caveats in the body, not a footnote.
- Keep one version for developers (numbers and method) and one for everyone else (three numbers and one sentence on what Jev is). Test the plain one on three non-developers for ten seconds.
- Public posts and demos use aliases and aggregate numbers only.

## 9. Checklist for a new use case

1. State the decision, who owns it, and the cost of a wrong answer. If wrong is irreversible, keep a human approval.
2. Write 3 to 6 narrow questions; pick primitives; write concrete Score levels.
3. Decide what code computes (counts, dates, rates) and what Jev sees.
4. Collect at least a few hundred labeled examples, more than we had (66). Reserve a held-out set and relabel a slice blind to measure label noise.
5. Run the eval in section 4 in order, with a simple non-model baseline included.
6. Write the go or no-go rule before you see results, for example "AUC at least X with interval above Y, repeatability at least Z, cost below W".
7. Decide the cascade: what Jev screens, what an expensive model or person sees.
8. Ship behind dry run, caps and audit. Re-measure monthly on fresh labels.
9. Data rules: what may leave the machine, retention, and (for company data) provider compliance. Amol mentioned a SOC 2 compliant, US zero-data-retention Jev variant may be a few months away; unverified, so confirm with TypeSafe before relying on it.

## 10. Where things live

- Question design and caching: `tidy/judge.py`, `tidy/store.py`
- Policy and cascade: `tidy/policy.py`, `tidy/escalate.py`
- Eval harness: `evals/` (runners, `compare.py`, `repeat.py`, `labeled_accuracy.py`, `list_price.py`)
- Decisions: `docs/adr/`; research notes: `docs/research/`
- Posts and drafts: `docs/post/`

## Open questions

- How much labeled data does a work task need before Jev's probabilities can be trusted at a threshold?
- Does the near-parity with frontier models hold on tasks with a real answer (routing, triage), where ground truth exists?
- How well does confidence track correctness once labels are good? We could not test it with noisy taste labels.
