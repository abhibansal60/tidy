# Jev calibration audit on public labeled data

Status: pre-registered plan. Sections 1 to 4 were written and committed before any evaluation call was made.
Results go in section 5 and later; nothing in sections 1 to 4 is edited after results are seen, except the
progress checklist and clearly marked "Deviation" notes.

## 1. Question

TypeSafe's launch post says Jev is "Calibrated: higher confidence means higher accuracy"
([Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev),
2026-09-15). The docs define Choice `confidence` as "a number from 0 to 1 computed from how `probabilities` is
spread" ([Choice primitive](https://docs.typesafe.ai/primitives/choice)). Our Tidy work could not test this:
its labels were one person's taste and were noisy (playbook, open questions). This audit tests it on public
tasks that have a real answer:

1. Does Jev's confidence track correctness well enough to use as an abstain gate (send low-confidence items to
   a person or a stronger model)?
2. Are Jev's Noul values calibrated probabilities on a yes/no question with known truth?
3. How does that compare with a cheap LLM (Claude Haiku 4.5) and a non-model baseline (TF-IDF plus logistic
   regression), on accuracy, repeatability, latency and cost?

The decision this informs: whether a future Tidy or work use case may route on Jev confidence without a
labeled calibration set of its own. The owner of that decision is Abhinav. A wrong "go" means silent misroutes,
so the bar is set on held-out error, not on agreement with another model.

## 2. Data (public only)

| Dataset | Task | Labels | Eval split used | Train split used (baseline only) | Licence |
| --- | --- | --- | --- | --- | --- |
| Banking77 (Casanueva et al. 2020) | 77 fine-grained banking intents from short customer messages | expert-written and labeled | 500 items sampled from the 3,080-item test set | full 10,003-item train set | CC BY 4.0 |
| NLBSE'24 issue report classification (Kallis et al.) | GitHub issue type: bug, feature or question, from 5 repos (react, tensorflow, vscode, bitcoin, opencv) | maintainers' issue labels; multi-label issues excluded by the dataset authors | 500 items sampled from the 1,500-item test set | full 1,500-item train set | public GitHub issues; the repo's licence is listed as "Other" and its LICENSE file is empty, so we download at run time and do not redistribute |

Sources: Banking77 CSVs at `github.com/PolyAI-LDN/task-specific-datasets` (the same URLs the Hugging Face
`PolyAI/banking77` loader uses); NLBSE CSVs at `github.com/nlbse2024/issue-report-classification/data`.

A US CFPB complaints set was the first choice for a support-ticket dataset, but its public API and bulk CSV no
longer include complaint narratives (checked 2026-10-05), so there is no text to classify.

Item text sent to models: Banking77 message as is; NLBSE repository name, title and the first 1,500 characters
of the body. No personal or company data is sent anywhere. Raw model outputs stay in `.tidy/calibration/`
(gitignored); only aggregates are committed.

Sampling is seeded (`random.Random(2026)`) and frozen in a manifest before any model call; every system sees
the same items and the same text.

## 3. Systems and questions

Each item gets two questions in one call:

- **Choice** over all labels (77 or 3). Measures: top label, its probability, and Jev's `confidence`.
- **Noul** "does this item belong to label C?", where C is the true label for a seeded half of the items and a
  random other label for the rest. Truth is known, so the Noul value can be scored as a probability.

| System | How it answers | Confidence signal |
| --- | --- | --- |
| Jev (`jev-latest`, typesafe-sdk) | one `system_one` call, Choice plus Noul bundled (independent questions) | Choice `confidence`, Choice top probability, Noul value |
| Claude Haiku 4.5 (`claude -p`, default effort, tools off, short system prompt, JSON schema) | one call per item, same label list and wording | verbalized probability that its label is right; verbalized P(yes) for the Noul |
| TF-IDF + logistic regression (scikit-learn defaults, word 1-2 grams, `max_iter=2000`) | trained on the train split | predicted class probability; P(C) for the Noul |

Differences named up front: the baseline is supervised on in-domain training data; Jev and Haiku are
zero-shot. Haiku sees both questions in one prompt (they can influence each other); Jev's bundled questions
cannot see each other. Haiku runs through the Claude Code CLI because no direct API key is configured, so its
wall time includes CLI start-up; we report the CLI's API time next to wall time and name which one each
multiplier uses.

Sample sizes and hard caps (enforced in code): Jev and TF-IDF on all 500 items per dataset; Haiku on the first
300 of the same frozen order (to limit subscription usage); a re-run slice of the first 100 items (Jev) and
first 50 items (Haiku), no cache, for repeatability. Hard cap: 1,000 model calls per system per dataset per
run. Expected Jev cost at $0.042 per million input tokens: well under $0.10 in total.

## 4. Analysis plan and go/no-go rule (fixed before results)

Metrics, all on the frozen items, 95% intervals by percentile bootstrap (2,000 resamples, seed 7):

- Accuracy with interval. Paired accuracy difference (Jev minus each baseline) on shared items, with interval.
- Reliability curve: 10 equal-width bins of the confidence signal; per-bin accuracy; expected calibration
  error (ECE, bin-weighted mean of |accuracy - mean confidence|). Brier score for Noul.
- Discrimination: AUROC of the confidence signal for "the top label is correct"; AUROC of Noul for truth.
- Abstain-band table: for thresholds 0.3 to 0.95, coverage (share of items answered) and error among answered.
- Held-out abstain test: split items in two halves by seeded index. On half A pick the lowest threshold whose
  error is at most 5%; apply it to half B and report coverage and error there.
- Repeatability on the re-run slice: top-label agreement and mean absolute change of the confidence signal.
- Latency per call (median, p95) and whole-run wall time, workers named. Cost: Jev at the published
  $0.042 per million input tokens (output free); Haiku as the CLI reports it and as a direct-API list-price
  estimate at $1 input and $5 output per million tokens
  ([Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), checked 2026-10-05).

**Go/no-go for "route on Jev's Choice confidence without a private calibration set"**, decided per dataset and
per signal (`confidence`, top probability); GO only if all hold:

1. Accuracy not worse than Haiku 4.5 by more than 5 points: lower bound of the paired difference interval above -5 points.
2. Confidence ranks correctness: AUROC at least 0.75 with interval lower bound above 0.65.
3. Held-out abstain gate works: the threshold picked on half A gives at most 7.5% error on half B while
   answering at least 50% of half B.
4. Repeatable: top-label agreement at least 95% and mean absolute confidence change at most 0.05 on the re-run slice.

**Noul is "calibrated enough to threshold as a probability"** if ECE is at most 0.10 and AUROC at least 0.85.

Anything else is NO-GO for that dataset and signal, and the use case needs its own labeled calibration set.
Agreement between Jev and Haiku is reported only as consistency, never as accuracy. The non-model baseline is
reported next to every Jev number; if it beats Jev, that leads the summary.

## Progress checklist

- [x] Plan, go/no-go rule and analysis plan committed before any evaluation call
- [ ] Data fetch and frozen manifests (`python -m evals.calibration_audit fetch`)
- [ ] Metrics module with tests (`evals/calibration.py`)
- [ ] TF-IDF baseline run
- [ ] Jev run, both datasets, plus re-run slice
- [ ] Haiku run, both datasets, plus re-run slice
- [ ] Report numbers, charts, go/no-go verdicts
- [ ] Draft post summary (unposted)
- [ ] PR opened and linked
