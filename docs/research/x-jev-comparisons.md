# Public claims comparing Jev with frontier models

Fetched: 2026-09-19 (Jev launched 2026-09-15, so every source is under 5 days old). Sources are web pages found by search and read via fetch. Numbers are quoted from those pages as summarized by the fetch tool, not re-read from raw HTML, so treat exact figures as "as reported". Affiliation tags: **VENDOR** = TypeSafe, **INDEP** = third party, **AGG** = secondary write-up that repackages vendor numbers.

Not reached: x.com directly (WebFetch returned HTTP 402; Chrome tools not used, so no first-hand X read). X content below is only what a third-party tweet analysis reports.

## Summary answers

1. Speed and cost direction is corroborated by an independent tester (Every: ~25x faster, ~580x cheaper than Fable 5.1). Our 21x-49x speed and 74x-470x cost fall inside or near the vendor and Every ranges.
2. Public accuracy numbers are all "agreement with frontier models", not ground truth. Vendor: Jev 67.8% vs Opus 5 73.1%, Sol 74.1%, Sonnet 5 67.8%. Our rank correlation 0.88-0.97 with Opus is the same kind of measure and looks consistent.
3. Independent tests find Jev slightly to clearly worse than the best frontier model on some tasks (Every 6/7 defects vs 7/7; primeline knowledge-category 90.7% vs Haiku 97.8%), and equal or better on others (commit classification 65.7% vs Haiku 54.8%).
4. Calibration: one independent test (primeline) reports good calibration on public datasets. No public data on whether Jev scores predict one person's keep/drop labels. Our AUC ~0.5 finding is neither supported nor contradicted.
5. Repeatability: only indirect support (primeline framing; Every ran 3 repeats and saw a defect missed in all three). No public 4-12x-vs-Haiku figure.

## 1. TypeSafe's own chart and tables (VENDOR)

- Source: [Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev), 2026-09-15. Headline: Jev 70-500 ms vs 3-329 s for LLMs, "40x-200x faster"; input $0.042/MTok, output free, vs LLM input $0.20-$10/MTok. Homepage multipliers 193.6x faster, 444.6x cheaper, which the post itself calls the higher end of real-world gains.
- What the chart measures: four "workflow evals" designed by TypeSafe's capabilities team; reference labels are the average of GPT-6 Astra and Claude Fable 5.1 (high thinking); "accuracy" is agreement with that reference. No human ground truth (per [Developers Digest](https://www.developersdigest.tech/blog/typesafe-jev-system-one-models-release-guide-2026), [pearpages](https://pearpages.com/blog/2026/09/16/jev-sorted-what-typesafes-system-one-model-actually-is-and-what-is-still-just-a-claim)). TypeSafe discloses bias toward OpenAI and Anthropic models and that pricing "may be subsidized".
- Aggregate table (reproduced by [DEV, Gabriel Anhaia](https://dev.to/gabrielanhaia/your-agent-burns-llm-money-on-switch-statements-jev-claims-444x-less-23l4), [DataCamp](https://www.datacamp.com/blog/system-one-models-jev)):

| Model | Agreement | $/case | Latency |
|---|---|---|---|
| Jev | 67.8% | 0.0004 | 0.4 s |
| GPT-5.6 Luna | 66.8% | 0.0033 | 12.9 s |
| GPT-5.6 Terra | 67.9% | 0.0304 | 10.1 s |
| GPT-5.6 Sol | 74.1% | 0.0836 | 23.3 s |
| Claude Sonnet 5 | 67.8% | 0.1174 | 78.1 s |
| Claude Opus 5 | 73.1% | 0.1761 | 37.8 s |

  (Developers Digest quotes a second table with Jev 76.0%, $0.0001, 0.4 s vs Opus 5 78.4%, $0.4856, 92.1 s, Luna 76.1%, DeepSeek V4 Flash 76.8%; likely the customer-service workflow or a different cut. **UNCLEAR.**)
- Per-workflow: invoice processing Jev 61.8% vs Sol 79.1%; security incidents Jev 61.7% vs Opus 5 66.2%; customer service Jev 76.0% vs Sol 78.3% (DEV, pearpages).
- Error-rate claim: Jev 0% structured-output/tool-call errors; Haiku 4.5 45.5% structured-output errors; Sol 17.0% tool-call errors (DataCamp, quoting the vendor).
- Docs ([System One](https://docs.typesafe.ai/concepts/system-one)): "Calibration is measured across groups of predictions; it does not guarantee that an individual answer is correct." Text input only. No benchmarks or repeatability statement on that page. Flavio Copes ([post](https://flaviocopes.com/jev/), INDEP, updated 2026-09-18) lists limits: cannot reliably count, do math, compare numbers or dates, or extract precise values.

## 2. Independent tests

- **Every, Mike Taylor (head of evals), 2026-09-15.** [Mini-Vibe Check](https://every.to/also-true-for-humans/mini-vibe-check-typesafe-s-jev-judged-everything-i-ve-written-in-0-7-seconds). INDEP (press-access test). Task: 21 yes/no questions over 27 articles plus 10 AI-styled ones (777 judgments). Jev median 0.35 s per passage vs 8.83 s for Fable 5.1 high effort (~25x); 777 judgments in <0.7 s for ~$0.0025; ~580x cheaper. Caught 6 of 7 planted defects vs Fable 7 of 7; missed one defect in all three runs. Verdict: "good but not perfect", an early-warning tool. Small sample.
- **primeline.cc, "Robin", 2026-09-18.** [Jev vs Claude Code: 4 models, 2 real jobs](https://primeline.cc/blog/typesafe-jev-pre-registered-test). INDEP, pre-registered. Models: Jev, Opus 5, Haiku 4.5, GPT-5.6. Calibration on 3,600 items: error 0.012 (yes/no), 0.086 (pick-one), 0.254 (rating scales); confidence >=0.9 is right ~92% of the time; below 0.8 accuracy drops to ~50%. Commits (800): Jev 65.7-65.8%, Opus 5 63.5% (not distinct), GPT-5.6 59.5%, Haiku 54.6-54.8%. Knowledge category (450): Haiku 97.8% vs Jev 90.7%, Haiku wins at every threshold. Cost: 9,750 Jev calls ~$0.38; Haiku input ~24x pricier per token. Caveat by the author: both datasets from one developer's machine, over 56% commits carry Claude co-author trailers.
- **OpenChamber, "What 12,759 Tweets Measured", 2026-09-15..18.** [post](https://openchamber.dev/blog/jev-typesafe-ai/). INDEP aggregator of X posts (26,896 tweets collected). User-reported speedup median 7x (quartiles 2x-20x, n=215); cost reduction median 30x (5x-85x, n=180); latency median 76 ms (n=333). Sample user results: YouTube comment classification 2 min 27 s, $0.20, 319 ms median latency; PR review $0.00007 per PR. About 4.3% of posts negative; critic @NathanFlurry (590k views) called it a "really smart switch statement". I did not see the underlying tweets.
- **The Register, Thomas Claburn, 2026-09-16.** [article](https://www.theregister.com/ai-and-ml/2026/09/16/typesafe-ai-debuts-model-for-machines-that-plays-doom/5296711). Press. Demo: 0.114 s vs 8.566 s for GPT-5.6 Terra; "238x" cheaper vs Fable 5.1 (vendor figures). Notes "hallucination-free" is not a fair comparison as output is not natural language.

## 3. Secondary write-ups (AGG, no new measurements)

[Developers Digest](https://www.developersdigest.tech/blog/typesafe-jev-system-one-models-release-guide-2026), [OrcaRouter](https://www.orcarouter.ai/blog/jev-typesafe-system-one-what-we-know), [explainx fact-check](https://www.explainx.ai/blog/jev-speed-cost-claims-fact-check-2026) (2026-09-19: direction corroborated by Every; multiplier magnitudes unverified), [DataCamp](https://www.datacamp.com/blog/system-one-models-jev), [pearpages](https://pearpages.com/blog/2026/09/16/jev-sorted-what-typesafes-system-one-model-actually-is-and-what-is-still-just-a-claim) (calibration and RLCD training "unverified"). All say: no large independent reproduction yet.

## Where public numbers support ours

- Speed: Every ~25x vs Fable 5.1; vendor 25x-145x vs mid-tier; ours 21x-49x.
- Cost: vendor per case, Sonnet 5 $0.1174 vs Jev $0.0004 is ~293x; Opus 5 ~440x. Ours 74x-470x. Every ~580x. Consistent.
- Agreement: vendor gap to Opus 5 is ~5 points of agreement; our 0.88-0.97 rank correlation fits "close but not identical".
- Calibration on public datasets is good (primeline), consistent with our high repeatability finding only loosely.

## Contradictions and tensions

- Absolute latency: vendor lists Opus 5 at 37.8 s and Sonnet 5 at 78.1 s per case; our CLI runs gave 189 s and 188 s for 110 channels x 4 questions. Different measures (per case vs whole-run through CLI); not a conflict but not comparable. Ratios of 21x-49x are lower than vendor's 100x+ because our Jev total (9.1 s) includes batching for 440 calls.
- Vendor-shape claim "Haiku 4.5 has 45.5% structured-output errors" is not something we saw; not tested by us.
- Frontier models win on some tasks: invoice processing (-17.3 points vs Sol), security incidents (-4.5 vs Opus 5), Haiku on knowledge-category (-7.1 points), Fable on the seventh planted defect.
- Jev beat Haiku 4.5 on commit classification (65.7% vs 54.8%), where cheaper and faster also won on accuracy.
- Our "scores did not predict this owner's labels (AUC ~0.5)" has no public counterpart; the public tests either measure agreement with models or labels from one dev's own data (primeline), where Jev did carry signal.

## UNCLEAR

- Any direct X posts, threads, or a TypeSafe X chart. Not reachable (402); only OpenChamber's tweet statistics were available. No individual post URLs verified.
- Whether the Developers Digest 76.0%/$0.0001 table is a workflow subset or another eval.
- Whether any published test measures run-to-run score variation (our 4-12x vs Haiku claim). Not found.
- Whether Jev's "confidence" is independent of its scores, per primeline's claim that it follows a formula (cited to "Yurin", 738,164 answers). Not seen at source.
- DEV article by Anhaia carries a "2024" date in the fetch output; likely an error (launch was 2026-09-15).
- Whether the numbers in this file match the raw HTML of each page; they were extracted by the fetch summarizer.

## Verdict

**Partly consistent, not in conflict.** Independent and vendor numbers agree with ours on the large effects: Jev is roughly 20x-50x faster and roughly 100x-600x cheaper, and it tracks frontier judgments closely but not perfectly. Nothing public contradicts our AUC ~0.5 result, and nothing supports it either, because every public accuracy figure is agreement with frontier models or a single developer's own labels. Public evidence is thin: one press-access test (Every), one pre-registered single-developer test (primeline), and vendor tables designed by TypeSafe. Repeatability and predicting a personal taste label remain untested publicly.
