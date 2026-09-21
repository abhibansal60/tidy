# Jev ecosystem: what others built, what works, what nobody has done

Fetched: 2026-09-21 (Jev launched 2026-09-15, so everything here is under a week old). Sources: docs.typesafe.ai pages, TypeSafe legal pages, GitHub READMEs read through `gh api` (raw text), blogs read through fetch, one logged-in read-only pass over X search results. Reddit was not tried (blocked for the browser tool; two WebSearch attempts returned nothing usable). Hacker News was reached only through search snippets. YouTube was not searched.

Evidence tags. **READ** = I read the README or page text myself. **SNIPPET** = only a search-result summary, not opened. **VENDOR** = TypeSafe or a platform selling access to it. **INDEP** = third party with no visible TypeSafe tie (a repo author is not automatically independent of hype; they are independent of the vendor). I did not run any repo's code, so every number is "as the author reports". Repos are days old, mostly 0 to 30 stars, with the exception of jev-align (250 stars) and the awesome lists.

This note does not repeat `x-jev-comparisons.md`, `x-first-hand-posts.md`, `agent-native-integration.md` or `docs/guide/jev-playbook.md`. It builds on them.

## Summary answers

1. **The strongest independent evidence is about method, not about Jev's raw accuracy.** Decomposing a task into narrow questions and fitting weights on your own labels moved Jev from 62.6% to 95.0% on a phishing test, while a plain regex rule scored 91.6% ([jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench), READ). A TF-IDF model matched Jev's zero-shot 98.6% on spam ([jev-spam-eval](https://github.com/bitnovus/jev-spam-eval), READ via fetch). Both say: measure against a boring baseline.
2. **Calibration is real as a ranking signal and unreliable as a probability.** Three independent audits agree on the shape. Ranking is good (AUC 0.90 to 0.91 on toxicity, [Adilmp](https://github.com/Adilmp/does-jev-confidence-mean-anything)). Raw probabilities need recalibration on your data (ECE 0.157 to 0.023 after a two-parameter fit, same repo). The sign of the error depends on question type: Noul underconfident, Choice and Score overconfident ([scienthoon](https://github.com/scienthoon/jev-ood-calibration)). On a task whose rule is not in the text, Jev was right 44.7% of the time while giving its answer 0.74 average probability (same repo).
3. **Email and inbox is the most crowded use case (at least 7 open repos) and the least measured.** Not one repo I read reports precision or recall against human labels for personal or work mail. The nearest are spam and phishing sets with labels from public corpora.
4. **Confidence catches missing facts, not fluent nonsense or polite manipulation.** In a pre-registered 123,805-request test, a 0.8 gate caught 95.5% of "missing fact" states and none of "fluent nonsense", and a sentence claiming a lead had already decided moved the answer on 147 of 200 tickets, while a crude "ignore the instructions" moved 1 of 200 ([willkelly](https://github.com/willkelly/jev-evaluation), READ). This contradicts the casual X claim that Jev "handles prompt injections well" (anjanab, relaying a YouTube review, SNIPPET).
5. **Two constraints affect what we can publish or build.** The TypeSafe Master Customer Agreement forbids using Jev output to distill or train an imitating model (section quoted below). And a claim in jevcal that the customer agreement restricts publishing performance numbers was **not found** in the MCA or Terms text I searched. Ask TypeSafe before a benchmark goes public.
6. **Recommended first project: a personal-inbox triage study where labels come from the owner's own behavior** (idea 1 below), with a label-budget learning curve as a by-product (idea 8). It reuses Tidy's method, needs no new compliance decision for personal mail, and produces the measured number nobody has published.

## 1. Quick wins others built

Fit columns: **(a)** personal email or inbox labeling, **(b)** work support or message routing, **(c)** other daily automations. "Evidence" is what the author measured, not what I verified.

| # | Project (link, author, tags) | What it does | Evidence it works | Reuse or customize |
|---|---|---|---|---|
| 1 | [jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench), anisselbd, INDEP, READ | Jev vs Claude Haiku 4.5 on 2,000 emails, then five narrow signal questions with a fitted logistic regression | One question: Jev 62.6% vs Haiku 81.3%, ECE 0.154 vs 0.097. Five signals plus regression, held-out half: 95.0% (AUROC 0.982) vs regex rule 91.8%. Regex alone on all 2,000: 91.6%. Cost $0.038 per 1,000. Repeat-run label flips 2.2%. Caveat: bodies are LLM-written, labels from a URL feed | (a) Copy the pattern for "needs reply": 4 to 6 Noul signals, then a small regression fitted on your own labels. (b) Same for ticket urgency. (c) Any yes/no target with a cheap rule you can beat. This is the single most reusable result |
| 2 | [jev-spam-eval](https://github.com/bitnovus/jev-spam-eval), bitnovus, INDEP, READ via fetch | Zero-shot ham/spam/phishing with written definitions and enriched input | 5,733 emails: Jev 98.64%, TF-IDF logistic regression 98.87%, ensemble 99.30%. Enrichment (Reply-To, real URL vs visible text, attachment names) added 4.36 points. Labels from public corpora with quality issues | (a) Feed Jev the header facts code extracts, not just body text. (b) Same for inbound support forms. Ignore it as proof Jev beats a trained classifier; it does not |
| 3 | [JevMail](https://github.com/fazlerocks/jevmail), fazlerocks, INDEP, 26 stars, MIT, READ | Read-only Gmail app (`gmail.readonly`), local SQLite, five trays plus urgency 1 to 5 plus "human sender", via Vercel AI Gateway | Self-reported speed and cost only: 1,000 emails in about a minute for about 3 cents. No accuracy figure. Corrections stored beside the original answer | (a) Best starting code: fork, add a "shadow label" column, export corrections as labeled data. Node 22, OAuth Testing mode expires refresh tokens in 7 days |
| 4 | [jev-mail](https://github.com/vynnlee/jev-mail), vynnlee, INDEP, 0 stars, MIT, READ | Gmail worker in Google Apps Script; labels, stars, archives even when the laptop is off | No accuracy claim ("does not promise perfect classification"). Preview mode before enabling. Default thresholds: action 0.55, not-action 0.2, star 0.7, category 0.6. Sends sender, recipient, subject and a 1,000-character snippet to TypeSafe | (a) Shows the three-outcome design: action label, review label, category label. Copy the threshold table as starting values, then refit on labels. Runs inside your Google account, no server |
| 5 | [jevMail](https://github.com/ilyamk/jev-gmail-ai-spam-filter-and-labeling), ilyamk, INDEP, 9 stars, MIT, READ via fetch | Up to 12 custom Gmail labels with plain-English criteria; metadata first, full body only for ambiguous mail; budget cap | None measured. 10,000 messages about $0.42 (arithmetic from list price) | (a) The metadata-first, body-if-unsure cascade is a good privacy pattern: less mail text leaves the machine |
| 6 | [jev-triage](https://github.com/PeterP22/jev-triage), PeterP22, INDEP, READ | Creator comments and DMs: 5 questions, then code picks notify, draft reply, like, hide, archive, human review | Only 12 sample messages, about 750 tokens and $0.00003 each. Design is the value, not the numbers | (b) Copy the safety rules: health mentions never get an automated reply; a lead that also looks like spam goes to a human. Useful for developer-advocacy inbound (DMs, community questions) |
| 7 | [jev-logtriage](https://github.com/jyatesdotdev/jev-logtriage), jyatesdotdev, INDEP, MIT, READ | Six questions in one call per log source; code maps to suppress, watch, review, notify, page. Executes nothing | Demo output only; author notes numbers "move a little from run to run. The gates do not" | (b) and (c) Template for any stream: alerts, CI failures, monitoring email |
| 8 | [jev-align](https://github.com/sutro-sh/jev-align), Sutro, VENDOR-adjacent (a third-party company, no visible TypeSafe tie), 250 stars, Apache-2.0, READ | CLI: Jev scores rows, picks uncertain plus random audit rows for you to label, GEPA rewrites the question definition, you accept or reject | Demo video only; no accuracy numbers in the README I read | (a)(b)(c) Cheapest way to collect the first 100 to 300 labels and improve the question wording. Note the GEPA reflection model is a separate LLM that sees your rows |
| 9 | [jevcal](https://github.com/abhixhek/jevcal), abhixhek, INDEP, 10 stars, MIT, READ, and a different [jevcal](https://github.com/Adilmp/jevcal) by Adilmp (not read) | Fits a threshold to your accuracy target on held-out labels, reports how much traffic still needs an LLM, fails CI on drift | README uses simulator output, no Jev numbers. Adilmp's audit: two-parameter recalibration fitted on one half cut ECE from 0.157 to 0.023 on the other half, AUC unchanged | (a)(b) Use after labeling. Our `evals/labeled_accuracy.py` covers AUC; this adds threshold-to-coverage. Because `jev-latest` moves, keep a frozen labeled set as a drift canary |
| 10 | [jevlens](https://github.com/k4its1t/jevlens), k4its1t, INDEP, MIT, READ | YAML questions, labeled CSV, stores full probability vectors so thresholds can be replayed offline, GitHub Action fails on accuracy regression | No numbers | (b) The replay-without-API-calls idea is worth copying; we already cache judgments by evidence hash |
| 11 | [jev-eval](https://github.com/4esv/jev-eval), 4esv, INDEP, READ | Labeled head-to-head, Jev vs GPT-5.6 Terra, plug-in `data/*.jsonl` for your own task | 300 items per task. Banking77 (77 classes): 0.78 vs 0.85. SST-5: 0.57 vs 0.59. IMDB polarity: 0.97 vs 0.97. ECE 0.11/0.20/0.04 vs 0.08/0.30/0.02. Median latency 0.20 s vs 1.04 s. Speed 5x, cost 41 to 50x. Same text counted as 340 tokens by Jev vs 162 by Terra. Label flips on identical input 1.7% to 3.3%. Terra's stated confidence clustered at 0.98 to 0.99 | (b) Reuse the harness on our own routing labels. It also gives a ready comparison for the "cheap judge vs frontier judge" post |
| 12 | [jev-orderby-bench](https://github.com/yodablocks/jev-orderby-bench), yodablocks, INDEP, MIT, pre-registered, READ | Is `ORDER BY probability` defensible? | Passes 6 of 6 gates on 360 human-labeled rows (boolean inversion 0.036) but only 45 distinct values in 360 rows (2-decimal rounding), 53 rows tie at 0.99. Fails 4 of 6 gates on 306 Amazon ESCI pairs (ECE 0.242). A 40-row batch fails the gate that one row per request passes | (a)(c) If we rank inbox items by Jev probability, break ties in code and do not pack many rows per call without naming them (see item 13) |
| 13 | [willkelly/jev-evaluation](https://github.com/willkelly/jev-evaluation), willkelly, INDEP, MIT, pre-registered, READ | 9 experiments, 28 predictions fixed first, 123,805 requests, $12.69 | Routing ECE 0.075. Sixty tickets in one call scored 1.000 when each question named its ticket by sender and date, 0.420 when it said "Ticket 1". Accuracy at question 200 equals question 1. Sixty questions in one call cost 20x fewer tokens, 8x faster. Confidence AUROC 0.878 pooled, 0.699 within one condition. Pre-computing structure hurt (0.894 source text vs 0.530 edge list) | (a)(b) Batch many emails per call only with named subjects; scan the PROMPTING.md rules. The strongest single independent source |
| 14 | [jev-decision-benchmarks](https://github.com/baibizhe/jev-decision-benchmarks), baibizhe, INDEP, 1 star, READ | Tool selection and abstention (MetaTool, When2Call, BFCL V4) | MetaTool similar-tool 77.79% vs ChatGPT 69.05%, abstain 87.04% vs 50.35% (0-shot). When2Call accuracy 74.84%, but "tool hallucination" 76.36% (picks a tool call when none exists) vs 1.2% for the best fine-tuned baseline. Baselines are 2023 to 2024 paper numbers, protocols differ | (b) Intent routing works when a "none of these" option exists and is scored; do not trust it to abstain unprompted |
| 15 | [Thirty-Cent Judge](https://paddo.dev/blog/thirty-cent-judge), paddo.dev, INDEP, READ | 9,081 low-confidence retail product pairs adjudicated | $0.32 total. Thresholds 0.8 confirm, 0.2 refute, middle abstains: 49% refuted, 21% confirmed, 30% abstained. 48 of 50 hand-read verdicts sound. Author says no calibration test and "the price changed the architecture, not the accuracy" | (b)(c) Three-band gate is the pattern. n=50 by hand, so weak evidence |
| 16 | [Sortwell](https://github.com/Dharundp6/jev-sortwell), Dharundp6, INDEP, MIT, READ via fetch | MCP server: files notes, links, meeting lines by kind and action, append-only | Demo: kind 6 of 6, 424 ms per item. Finding: "an MCP server is not a behaviour change", the agent rarely called the tool | (c) Supports our earlier "skip agent-native" call: a hook, not an optional tool, is what changes behavior |
| 17 | Docs cookbooks: [classification with confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence), [SDE cascade](https://docs.typesafe.ai/cookbooks/sde_cascade), [self-consistency](https://docs.typesafe.ai/cookbooks/consistency_noul_cookbook), [feature discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery), VENDOR, READ | Official examples | 75-class SEC filings, 60 items: forced group 39/60 right, confident (>=0.9) group 27/30, unconfident 12/30, fall back to division 48/60. Feature discovery on 2,000 wine reviews: RMSE 3.09 (mean) to 1.87 (one round) to 1.77 (five rounds), held-out. Self-consistency: probability SD 0.0102, 0.30 to 0.70 band to human | (a)(b) Confidence-to-coarser-answer fallback is a neat trick for label hierarchies (e.g. "work" vs "work/billing"). Feature discovery is the vendor version of item 1 |
| 18 | Evaluator posts: [LangChain](https://www.langchain.com/blog/jev-agent-evals-langsmith), [Arize](https://arize.com/blog/typesafe-jev-llm-judge/), [Langfuse](https://langfuse.com/blog/2026-09-18-using-typesafes-jev-for-evals), READ via fetch | Jev as an eval judge | LangChain: 5 runs, 100% vs Claude 80%, variance 92 to 913x lower, $0.34 vs $28.17 (tiny n, they call it narrow). Langfuse: 91.5% agreement with Fable 5.1 at $160 vs $33,000 per million graded answers (agreement, not truth). Arize repackages vendor and third-party numbers | (c) Weak evidence. Do not cite as accuracy. Useful direction for idea 7 |
| 19 | [jev-skip](https://github.com/valentynkit/jev-skip), valentynkit, INDEP, 3 stars, READ (listing) | YouTube sponsor segments from captions | Reports catching 77% of SponsorBlock's sponsor seconds over 23 videos at $0.0008 per video (README claim, not re-read) | (c) Directly relevant to Tidy's YouTube world; not a subscription use |

Not quick wins, but adjacent: 155-plus projects in [awesome-jev](https://github.com/cobanov/awesome-jev) (285 stars, list dated 2026-09-20, READ) and 4 other awesome lists. [Inbox Zero](https://github.com/elie222/inbox-zero) lists Jev as an optional classifier backend; I did not verify how it is wired. Sentry's Junior and Roomote have pull requests adding Jev for passive Slack reply routing (SNIPPET). jev-scheduler (a hackathon PR, SNIPPET) turns a thread into tentative calendar holds.

### X, first-hand, this session (read-only)

Only three relevant results surfaced and none carries numbers: Nader Dabit, "Jev is really good at intent-based search", showing Gmail search (Sep 18); Adil, "used Jev to triage support tickets; its zero-shot labeling cuts routing time by half" (Sep 19, no method shown); Anjana relaying a YouTube review that calls it the fastest agent for refund detection and support routing (Sep 19). Treat as sentiment, not evidence.

## 2. Patterns

### Recur and work

1. **Narrow questions, several per item, one call.** Every well-scoring result (jev-phishing-bench 95.0%, willkelly 0.980 on tickets, Adilmp AUC 0.91) uses specific yes/no or ordered-level questions. The single vague question is the failure (62.6%).
2. **Fit a small model on top of Jev's signals with your own labels.** jev-phishing-bench (logistic regression), the vendor feature-discovery cookbook (CatBoost) and jevcal (threshold fit) are the same idea. It is what turns Jev from a zero-shot guesser into a feature extractor.
3. **Recalibrate locally, on held-out labels.** About 100 labeled rows gave a large ECE drop in Adilmp's test (0.157 to 0.023, AUC unchanged). The Sacco ledger reports the same compression-toward-the-middle shape on a separate 800-item set ([jev-exploration](https://github.com/SamuelSacco/jev-exploration), read via fetch).
4. **Three bands, not one threshold.** Confirm high, refute low, send the middle to a person or a stronger model: 0.8/0.2 (Thirty-Cent Judge), 0.30/0.70 (vendor insurance cookbook), 0.6/0.85 (vendor confidence-routing page). Pick the numbers on your labels.
5. **Code owns arithmetic, dates and actions.** The vendor limitations page lists math, counting, date comparison and generation as weak ([Jev 1.13 limits](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)). Successful repos precompute facts and keep side effects deterministic (jev-logtriage, jev-triage, our playbook).
6. **Enrich, do not pre-digest.** Adding headers and link targets helped (+4.36 points); rewriting the problem into a structure the program likes hurt (0.894 to 0.530).
7. **Name subjects in batched calls.** 1.000 vs 0.420 (willkelly).
8. **Shadow mode first, then act.** Sortwell, jev-skill-router (shadow mode only logs) and the vendor's own advice.
9. **Beat the boring baseline first.** Regex 91.6%, TF-IDF 98.87%, our own watch-history 0.69. Every honest repo reports one.
10. **Cheap screen, expensive check.** The [OpenRouter verified cascade](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/jev-verified-cascade) and the SDE cascade use Jev to decide whether to escalate. Only vendor and platform evidence so far.

### Fail, or are hype

- **The 193.6x and 444.6x multipliers** (see `x-first-hand-posts.md`); independent like-for-like speed is 3x to 6x, cost 2.6x to 106x. Item 11 above adds 5x speed and 41 to 50x cost against Terra.
- **Agreement with frontier models sold as accuracy.** The vendor table and the Langfuse 91.5% both measure agreement.
- **Reading the probability as a probability.** Audits: T=3.29 (Choice) and 3.40 (Score) overconfident, T=0.66 (Noul) underconfident on the same synthetic set; the same run gave 44.7% accuracy at 0.74 stated probability on an unknowable rule (scienthoon). jev-phishing-bench ECE 0.154.
- **Confidence as an abstention or safety gate.** Fluent nonsense and polite authority text keep confidence near the ceiling (willkelly); 0.8 gate catches 95.5% of missing-fact states, none of nonsense; 86% of answerable tickets sit at exactly 1.00.
- **Tiny benchmarks.** n=5 (LangChain), n=25 (jev-scout), n=50 (Thirty-Cent), n=60 (docs, "cannot measure calibration at all" per Sacco).
- **Tie-heavy sorting and big batches** (45 distinct values in 360 rows; 40-row batching fails).
- **Unprompted abstention** (When2Call tool-hallucination 76.36%).
- **"Deterministic".** Flips of 1.0% to 3.3% on identical input (jev-eval, jev-phishing-bench) versus the vendor's tight SD in one cookbook. Not a contradiction with our "3 to 4 times steadier than Sonnet 5", but not zero.
- **Taste.** Our own result (AUC about 0.5), still unreplicated by anyone.
- **Other languages and text-only.** Docs: English best, no images.

## 3. Compliance facts we can cite (checked this session)

- [Models page](https://docs.typesafe.ai/models.md): "Jev is not trained on customer requests or responses." Limits: 64k tokens per request, 32k for state plus the longest question; rate limit 250,000 tokens/s and 1,200 requests/min, "adjusting dynamically". English primary.
- [Legal index](https://docs.typesafe.ai/legal.md): zero data retention "for enterprise customers"; a Data Processing Agreement covers retention. The index does not mention SOC 2, and I found no SOC 2 statement in the [MCA](https://typesafe.ai/legal/mca) or DPA text (one text search each). A search summary says the models page lists no SOC 2 or ISO 27001 attestation (SNIPPET). The "SOC 2 US ZDR variant in a few months" remains unverified.
- Vercel AI Gateway documents a per-request `zeroDataRetention` option for Jev ([changelog](https://vercel.com/changelog/typesafe-ai-jev-now-available-on-ai-gateway), SNIPPET); scienthoon's run used it (READ). Whether the Gateway path satisfies a company's ZDR requirement is a question for the company and Vercel.
- MCA restriction (fetched text): the customer may not "use the Services or any Output ... to perform model distillation, train a model to imitate the output of the Services, or develop ... a similar or competing product". This matters: **do not label a dataset with Jev and train a local classifier on it.** Fitting a regression on Jev's signals against human labels looks closer to feature use than imitation, but ask. This is a reading of quoted text, not legal advice.
- No benchmark-publication clause found in the MCA or Terms of use (searched for "benchmark", "performance", "publicly", "compet"). The jevcal README says such a restriction exists. **UNCLEAR.**

## 4. Novel opportunities

"Nobody" below means I found no public repo, post or paper that does it, after searching awesome-jev (155 entries), GitHub, X and the web. Absence in a week-old ecosystem is weak evidence; re-check before publishing.

Effort in working days for one person, first useful and publishable version.

### Idea 1. Inbox triage with behavior labels, measured against a rule baseline

- **Problem.** Every inbox repo asks Jev "does this need a reply" and reports no truth. Our own Tidy finding was that revealed behavior beat model judgment.
- **Why Jev fits.** Runs on every message for cents, several Noul signals per call, probabilities feed a fitted model, repeatable runs.
- **Data and labels.** Owner's Gmail via the connector, read-only. Labels from behavior: replied within N days, starred, archived unread, moved to a label. Plus 200 hand labels of "should have replied", relabeled blind two weeks later. Headers and a 1,000-character snippet only.
- **Eval.** Human-label ground truth: the 200 hand labels plus reply behavior. Baselines: (a) sender's historical reply rate, (b) List-Unsubscribe/no-reply header rule, (c) direct-to-me vs cc. Compare Jev zero-shot, Jev signals plus logistic regression, Haiku, and behavior-only baseline. Report AUC with bootstrap intervals, coverage at 95% precision, label self-agreement.
- **Effort.** 5 to 7 days.
- **Risks.** Personal only: third-party senders' text goes to TypeSafe (ZDR via Gateway, headers plus snippet). Wrong-action cost: zero if it only writes a local score; label writes are reversible but keep them off until measured.
- **Public artifact.** Post: "Does a decision model beat 'who usually gets my replies'?" plus a repo with the harness and synthetic-mail fixture, no real mail.

### Idea 2. Injection-aware inbox triage benchmark

- **Problem.** Email is untrusted text. The one measurement (willkelly) shows authority-claiming text moves answers (147 of 200), while crude injections do not. No email-specific corpus or defense comparison exists.
- **Why Jev fits.** Cheap enough to run thousands of adversarial variants; probabilities let us test whether a gate catches insertion.
- **Data and labels.** 300 real-shaped emails, each with a benign version and 3 to 5 attacked versions (authority claim, "already approved", forged headers, fake quoted reply). Ground truth is the benign label; success is answer stability.
- **Eval.** Human label = benign truth by two labelers. Baselines: keyword filter for instruction-shaped phrases; separating untrusted text into its own state field with a header naming it untrusted; a 0.8 confidence gate. Measure flip rate and false-alarm rate.
- **Effort.** 4 to 5 days.
- **Risks.** Low: read-only, synthetic data. Danger is over-claiming "safe".
- **Public artifact.** Benchmark repo plus post. Timely because agents are being given inbox access.

### Idea 3. Cascade router with cost per correct decision on real labels

- **Problem.** Cascades are described (vendor cookbooks, OpenRouter recipe, jevcal simulator) but I found no end-to-end measurement on human-labeled work data of Jev to Haiku to person, with cost per correct decision.
- **Why Jev fits.** The whole point: cheap first pass, probability decides who looks.
- **Data and labels.** 500 support or community messages with human routing labels (or the idea 1 set).
- **Eval.** Human-label ground truth. Baselines: keyword router, always-Haiku, always-Opus, always-Jev. Sweep the low/high thresholds; plot accuracy against total cost and human minutes. Report cost per correct decision and the error rate of the auto-accepted slice.
- **Effort.** 5 to 6 days (uses jevcal for threshold fits).
- **Risks.** Sending work messages needs the ZDR route; escalation to Opus multiplies data exposure. Wrong-action cost: only for auto-accepted slice; keep human review on.
- **Public artifact.** Cost-versus-accuracy curve post with the harness. Strong for a leadership audience.

### Idea 4. Label-noise measurement for triage sets, using Jev as a disagreement finder

- **Problem.** Our relabel showed 77% self-agreement, which capped any score. Most teams never measure their noise ceiling. A search snippet mentions Jev used for "label auditing" in one repo (SNIPPET, not opened), so this may be partly done.
- **Why Jev fits.** Cheap second opinion over every label; confidence-ranked disagreement queue focuses human review.
- **Data and labels.** Any labeled set of 300 or more; blind relabel of the top-disagreement slice and a random slice.
- **Eval.** Ground truth: adjudicated label by a second human. Baseline: random review of the same size. Measure fraction of true label errors found in the top 50 vs random, and corrected-set accuracy.
- **Effort.** 3 to 4 days.
- **Risks.** Low. Danger: Jev's disagreement with humans is not automatically Jev being wrong (a listed caveat on civil_comments annotators).
- **Public artifact.** Short post plus script: "find your bad labels for 30 cents."

### Idea 5. Shadow-mode routing for developer-advocacy or enablement inbound

- **Problem.** Community questions, DMs and internal enablement requests need routing (owner, topic, urgency, needs a human). Sentry Junior and Roomote have PRs for Slack passive routing (SNIPPET), but no measured result.
- **Why Jev fits.** Speed and per-message cost let it read every message; Choice over owners plus Noul "needs human".
- **Data and labels.** 300 to 500 messages, routing decided by the person who handled them. Historical, so shadow-mode is free.
- **Eval.** Human ground truth from who actually handled it; baseline: keyword rules plus last-responder rule. Coverage at 95% precision.
- **Effort.** 6 to 8 days including the data agreement.
- **Risks.** Company data: wait for the ZDR/SOC 2 variant or Gateway ZDR with sign-off. Wrong route is cheap; missed urgent one is not, so bias to human review.
- **Public artifact.** Internal write-up first; sanitized public version with synthetic messages.

### Idea 6. Jev as the judge in internal agent evals, with human labels at real n

- **Problem.** Published Jev-as-judge tests are n=5 (LangChain) or agreement with another model (Langfuse, Arize).
- **Why Jev fits.** Speed and cost make "judge every trace" possible; repeatability matters for regression testing.
- **Data and labels.** 300 or more traces or answers from an internal agent, graded pass/fail by two humans.
- **Eval.** Human ground truth; baselines: Haiku judge, Opus judge, string-match checks. Report accuracy, repeat-run flips, cost, and agreement with humans at the human-human ceiling.
- **Effort.** 5 days.
- **Risks.** Internal traces may contain customer data. Prompt-injection through agent outputs (see idea 2).
- **Public artifact.** Benchmark post for AI enablement audiences.

### Idea 7. Cross-model verbalized-confidence audit on one labeled set

- **Problem.** jev-eval noted Terra's stated confidence clusters at 0.98 to 0.99. Nobody I found compares Jev's probability against several frontier models' verbalized or logprob confidence on the same human-labeled data.
- **Why Jev fits.** Jev's cheap calls make the reference; the comparison tests the "calibrated" marketing claim against the models people already use.
- **Data and labels.** The idea 1 or 3 set, plus a public set for the write-up.
- **Eval.** Human ground truth; baselines: majority-class, each model's stated confidence, temperature-scaled Jev. Metrics: ECE with noise floor (scienthoon method), coverage at fixed error, AUROC of confidence.
- **Effort.** 4 days.
- **Risks.** Possible publishing restriction (see section 3). Frontier-model runs cost more.
- **Public artifact.** Calibration audit post. Adds to a small existing set (Adilmp, scienthoon, Sacco), so novelty is moderate.

### Idea 8. Label-budget learning curve

- **Problem.** Our playbook's first open question: how many labels before a threshold is trustworthy? jevcal says about 100 rows; Adilmp used about 100. Nobody plots threshold quality against 25, 50, 100, 200, 400 labels with intervals.
- **Why Jev fits.** Many cheap runs on stored probability vectors; no re-inference per point.
- **Data and labels.** Idea 1 set plus one public set (civil_comments, Banking77 via jev-eval).
- **Eval.** Human ground truth held out. For each label budget, fit thresholds and recalibration on random subsets (bootstrap 200 draws); report the spread of realized precision and coverage. Baseline: fixed 0.9 threshold, no fitting.
- **Effort.** 3 to 4 days (mostly reuse of idea 1 output).
- **Risks.** Low. Works only if probabilities are stored (they are; use `evals/` cache).
- **Public artifact.** One chart and a rule of thumb: "you need N labels." Highly quotable.

### Idea 9. Calendar load triage from your own accept/decline history

- **Problem.** No one has tested Jev on meeting invites. Questions: is this decision-making or status, do I add value, could it be an email.
- **Why Jev fits.** Small text per invite, cheap to run over a year.
- **Data and labels.** Owner's Calendar via the connector (authentication was still pending in this session), accept/decline and later "was it useful" ratings for 150 meetings.
- **Eval.** Ground truth: own decline history plus 100 blind ratings. Baselines: organizer identity and attendee count rule.
- **Effort.** 4 to 5 days.
- **Risks.** Attendee names and titles are third-party data. Same taste problem as Tidy: expect the behavior baseline to win.
- **Public artifact.** Weak-to-moderate; fun post, low reuse.

### Idea 10. Drive sharing-risk report (read-only)

- **Problem.** Files shared too widely or with sensitive content are found late. A Noul over file title, path and permission summary, with code owning the permission facts.
- **Why Jev fits.** Bounded categories, cheap scan of thousands of files, three-band review.
- **Data and labels.** 300 files from a work Drive with security-reviewed labels; permissions from the Drive connector's permission call.
- **Eval.** Human labels from a security or admin reviewer. Baselines: "public link" and "external domain" rules, filename keywords.
- **Effort.** 5 to 7 days.
- **Risks.** Highest compliance risk here: file text is sensitive. Use metadata only first; content only after ZDR/SOC 2 confirmed. Never change permissions automatically.
- **Public artifact.** Internal only, likely. A synthetic-Drive public demo is possible.

## 5. Ranked table

Scores 1 (low) to 5 (high). Value = usefulness to the owner and employer. Feasibility = data available now, compliance risk low, effort short. Novelty = absence in the public ecosystem. Total is the sum; ties broken by feasibility.

| Rank | Idea | Value | Feasibility | Novelty | Total | Days |
|---|---|---|---|---|---|---|
| 1 | 1. Inbox triage with behavior labels vs rule baseline | 4 | 5 | 4 | 13 | 5 to 7 |
| 2 | 8. Label-budget learning curve | 3 | 5 | 5 | 13 | 3 to 4 |
| 3 | 3. Cascade router, cost per correct decision | 5 | 3 | 4 | 12 | 5 to 6 |
| 4 | 2. Injection-aware inbox benchmark | 4 | 4 | 4 | 12 | 4 to 5 |
| 5 | 4. Label-noise / disagreement finder | 3 | 5 | 3 | 11 | 3 to 4 |
| 6 | 5. Shadow-mode inbound routing (work) | 5 | 2 | 3 | 10 | 6 to 8 |
| 7 | 6. Jev as agent-eval judge at real n | 4 | 3 | 3 | 10 | 5 |
| 8 | 7. Cross-model confidence audit | 3 | 4 | 3 | 10 | 4 |
| 9 | 9. Calendar load triage | 2 | 3 | 4 | 9 | 4 to 5 |
| 10 | 10. Drive sharing-risk report | 4 | 1 | 4 | 9 | 5 to 7 |

Ideas 3, 5 and 6 are the ones that matter most to a company interested in agentic tools, but they need work data, so they wait on the ZDR/SOC 2 answer. Ideas 1, 2, 4 and 8 can start today on data the owner owns or on synthetic and public data.

## UNCLEAR

- Whether TypeSafe's customer agreement restricts publishing benchmarks (jevcal says yes; I did not find it in the MCA or Terms text). Ask TypeSafe before publishing numbers.
- Whether the SOC 2 US ZDR variant exists or when. No source found.
- Whether a Vercel AI Gateway ZDR flag meets a company's compliance bar.
- Whether fitting a regression on Jev's signals against human labels counts as "training a model to imitate the output" under the MCA. Likely not, but not tested.
- How Inbox Zero, Roomote and Sentry Junior wire Jev, and whether any measured anything. Not opened.
- The numbers I read through the fetch summarizer (jev-spam-eval, jev-decision-benchmarks details, Thirty-Cent Judge, Arize) may not match raw pages; jev-eval, jev-orderby-bench, jev-phishing-bench, willkelly, Adilmp, scienthoon, jevcal and jev-benchmarks I read as raw READMEs.
- [jev-benchmarks](https://github.com/AbdelStark/jev-benchmarks) (AbdelStark, READ) reports Jev beating GLiNER2.5 on AG News (0.910 vs 0.700) and Banking77 (0.870 vs 0.610) but scoring 0.480 on DAIR Emotion with poor calibration (Brier 0.846). n=100 per condition; a mixed, small result I did not include in the tables.
- The Sacco ledger [jev-exploration](https://github.com/SamuelSacco/jev-exploration) numbers (19,528-email spam re-analysis, ECE 2.1 to 2.5 times noise floor) were read only through fetch.
- Hacker News, Reddit and YouTube were not searched; the X pass was three search pages, no thread reads.
- Whether Jev's aliases (`jev-latest`, `jev-preview`) will keep results stable; both currently point to 1.13.0 (models page).
- Rollout readiness of the Gmail and Calendar connectors for label writes was not tested; I made no Gmail, Drive or Calendar calls.

## Verdict

**The ecosystem is wide and shallow.** About 155 projects exist, most under a week old, and the best independent work shares one lesson: Jev is a strong, cheap feature extractor whose probabilities need local calibration and a boring baseline next to them. Inbox triage is the most duplicated build and the least measured. The quick wins to reuse now are jev-align (collect labels), jevcal (thresholds), jev-eval (head-to-head), JevMail (read-only Gmail shell), and the jev-phishing-bench pattern (narrow signals plus a fitted regression). The claims to distrust are the speed and cost multipliers, agreement-as-accuracy, and confidence as a safety gate.

**Start with idea 1, folding in idea 8.** It uses data the owner already has, needs no work-data approval, reuses the Tidy harness (`evals/`), tests the one claim nobody has measured (does Jev beat "who usually gets replies" on a real inbox), and yields a learning curve that answers the playbook's first open question. If it works, ideas 3 and 5 become the work version once the ZDR question is answered. If Jev loses to the sender-history baseline, that is itself the publishable result, consistent with the Tidy finding.
