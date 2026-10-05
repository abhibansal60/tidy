# Jev alternatives: decision memo (2026-10-01)

Scope: free or near-free fallback for Jev in `tidy` (email, 6-way Choice) and `career-ops/local/jev_triage.py` (job Score + Noul). Read-only research: nothing in `~/code/jev` or `~/code/career-ops` was edited, no crontab touched, no email text or address left this machine, no key printed.

## Bottom line

1. **Keep Jev for both workloads and top up credits.** At the list price it costs about $0.22/month for emails and about $0.55/month for jobs (arithmetic below). Nothing I could test beats that on quality, and none of it is cheaper in any way that matters.
2. **Free fallback for email: sentence embeddings + logistic regression trained on the cached Jev labels.** It matched Jev on 69% of a stratified test set (macro-F1 0.685), but that number is inflated by sender leakage. On the 63 test emails whose sender never appears in training, it fell to **accuracy 0.556, macro-F1 0.395** (independent review). It is a degraded mode only, not a Jev replacement.
3. **Haiku 4.5** is the "good and simple" paid option: about $22/month uncached (~28x Jev), likely a few dollars a month with prompt caching of the static rubric/candidate prefix plus Batch (estimate, not measured).
4. **openjev.com is SemIf** (formerly OpenJev; MIT; the repo's homepage field is `openjev.com`). It is the best *zero-shot* option tested: on 30 emails it agreed with Jev 67% of the time, where Ollama scored 43% and Laya 37%, with no training. But it took **35 s per email** on this CPU, and its confidence is uncalibrated out of the box (ECE 0.275). Good idea, needs a GPU.
5. **Laya is real but unusable zero-shot** on this task; measured macro-F1 0.295 (near chance). Other repos named "openjev" are unrelated, and the PyPI package `openjev` is a 1 KB stub.
6. **career-ops: put the $5 on Jev.** At ~875 input tokens per call, $5 covers about 136,000 calls. That is about 9 months of 500 jobs/day, or about 6.5 months if email runs on the same credit. Pricing comes from your own cost note and secondary sources (see "Not verified"); check the console's usage page after the first daily run.

## Comparison

Quality = agreement with Jev's own cached labels (not ground truth). Test set: 480 stratified emails from local data (100 each Needs Reply / Spam / Sales, 60 each Action Needed / Updates / Promos). Because the set is class-balanced, accuracy is not the natural-mix accuracy.

| Candidate | n | Acc | Macro-F1 | Recall Needs Reply | Recall Spam | Confidence flags errors (AUROC) | ECE | Latency (8-core CPU) | Cost/mo (200 emails + 500 jobs/day) | Effort | Risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev (reference) | , | , | , | , | , | , | , | not re-measured | ~$0.8 | none | credits ran out; pricing not on primary source |
| MiniLM-L6 embeddings + LR (class-balanced) | 480 | 0.685 | 0.685 | 0.73 | 0.70 | 0.765 | 0.056 | 33 ms/item (batched) | $0 | low | learns Jev's mistakes; needs retrain on drift |
| Same, no class weights | 480 | 0.538 | 0.528 | 0.58 | 0.43 | 0.732 | 0.142 | 33 ms | $0 | low | misses rare classes |
| Laya 0.3.22, English checkpoint, zero-shot | 480 | 0.312 | 0.295 | 0.12 | 0.49 | 0.614 | 0.185 | 2,706 ms/item | $0 | medium | see "Candidates" |
| Ollama qwen2.5:3b-instruct, answer probability read off logits | 30 only | 0.433 | 0.357 | 0.57 | 0.00 | 0.747 | 0.459 | 8,174 ms/item | $0 | medium | too slow and weak; n is tiny |
| SemIf / openjev.com, Qwen3.5-4B Q4_K_M via llama.cpp, direct option logits, uncalibrated | 30 only | 0.667 | 0.640 | 0.57 | 0.33 | 0.735 | 0.275 | 35,553 ms/item (median) | $0 | medium | local, nothing leaves the machine; too slow on CPU; 8 days since last push |
| DeBERTa-v3 zero-shot NLI | not measured | , | , | , | , | , | , | , | $0 | , | see "Not verified" |
| Claude Haiku 4.5 | not run (hosted; no email text allowed) | , | , | , | , | , | , | not measured | ~$22 uncached, a few $ with caching + Batch (est.) | low | sends email text to a third party |
| TypeSafe free credit | , | , | , | , | , | , | , | , | $5 credit reported by blogs | none | not confirmed on a primary source |

Measured numbers come from `results.jsonl` in the session scratchpad, produced by scripts that read only local files. Metrics are computed against Jev's cached verdict, so a high score means "behaves like Jev", not "is right".

The n=30 rows use the same 30 emails (every 16th of the 480), so they compare with each other directly. On those 30, accuracy was MiniLM+LR 0.733, SemIf 0.667, Ollama qwen2.5:3b 0.433, Laya 0.367. With n=30, a 95% interval on 0.667 is roughly 0.49 to 0.81, so SemIf vs MiniLM+LR is a tie within noise; SemIf's lead over Laya and Ollama (20 vs 11 and 13 of 30) is likely real.

## Candidates

### openjev.com = SemIf: legitimate, best zero-shot, too slow on CPU
- [openjev.com](https://openjev.com/) is the browser demo of [TheoLeeCJ/SemIf-OpenJev](https://github.com/TheoLeeCJ/SemIf-OpenJev); the repo's GitHub homepage field is `openjev.com`. MIT, 4,632 stars, created 2026-09-16, last push 2026-09-23, 5 contributors. Its README says it was "formerly OpenJev" and is "not affiliated with or endorsed by TypeSafe".
- What it is: an interface reproduction, not a trained model. It prompts a frozen Qwen3.5-4B with the state, question and lettered options. It reads the answer-letter logits from one forward pass and softmaxes them. Its own [METHOD.md](https://github.com/TheoLeeCJ/SemIf-OpenJev/blob/main/docs/METHOD.md) says it "does not reproduce Jev's undisclosed model or training". It ships Choice-style option probabilities. Noul is a 2-option Choice; Score is not a native ordinal type (you'd compute an expected level over ordered options yourself).
- Calibration: its own [CALIBRATION.md](https://github.com/TheoLeeCJ/SemIf-OpenJev/blob/main/docs/CALIBRATION.md) says raw probabilities are "conditional on the supplied options and uncalibrated". It offers a per-workload temperature fit on labelled rows. On your emails, raw ECE was 0.275. Fitting a temperature on the cached Jev labels would fix confidence but not accuracy.
- Its own benchmark: 0.845 agreement on a 102-row TypeSafe public subset vs 0.883 for published Jev (its README table). Not independently checked.
- Measured here (CPU llama.cpp backend, 8 threads, Q4_K_M GGUF, `--mode direct`, 30 emails): 0.667 accuracy, macro-F1 0.640, 35.6 s median per email. 200 emails/day would take about 2 CPU-hours daily. 500 jobs/day with two questions each would take several CPU-hours, unless its `shared` mode (prefill state once) cuts that substantially; not measured.
- Privacy: fully local; no text leaves the machine. Install pins `torch==2.10.0` and needed a separate Python 3.12 env (your default is 3.14).
- Verdict: the right design for a free Jev-shaped fallback, and the only zero-shot option that came close to Jev here. It needs a GPU to be practical.

### Other repos named openjev: unrelated
- GitHub has at least seven more unrelated OpenJev/openjev projects, e.g. [razorback16/openjev](https://github.com/razorback16/openjev) (Apache-2.0, Jev wire-compatible server on a 26B DiffusionGemma, needs NVIDIA or Apple silicon; README advertises free hosting on Codiv, a third party that would receive your text, not called), [ekzhang/openjev-sglang](https://github.com/ekzhang/openjev-sglang) (B200 on Modal), [SiliconLabAI/OpenJev](https://github.com/SiliconLabAI/OpenJev). All were created 2026-09-17 to 09-20.
- PyPI [`openjev`](https://pypi.org/project/openjev/) is version 0.0.1 by an unrelated author, two files of 1,102 and 696 bytes, linked to `github.com/balys/openjev`, which returns 404. **Treat as a placeholder or typosquat; do not `pip install openjev`.** SemIf is installed from its Git repo, not from PyPI.

### jevgrep: unrelated to your problem
[dzhng/jevgrep](https://github.com/dzhng/jevgrep) (MIT, 1,919 stars, v0.7.1 on 2026-09-30) is a code-search CLI that calls Jev. It is a consumer of Jev, not a replacement, and needs a Jev-compatible key. Many forks exist. Not a candidate.

### Laya: real, maintained, not good zero-shot
- [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya): Apache-2.0, 29,355 stars, latest release v0.3.22 on 2026-09-29, 30 contributors, created 2026-09-18. Weights at [convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya), PyPI [`laya` 0.3.22](https://pypi.org/project/laya/). 421M-parameter ModernBERT-large; outputs Choice probabilities, Score and Noul, so the contract matches.
- Its own model card says base checkpoints "are near chance on typed-decisions zero-shot" and that the fine-tuned `laya-typed-decisions` checkpoint scores 0.766 vs 0.362 for the base on its own benchmark (not on your data).
- My measurement agrees: macro-F1 0.295, accuracy 0.312, Needs Reply recall 0.12. Install warned that the checkpoint "ships invalid temperatures", so its confidence is uncalibrated (ECE 0.185 measured).
- CPU latency was 2.7 s/item, versus the 33 ms the project reports on a T4 GPU.
- Fine-tuning it on your data would need a GPU and its Kaggle notebook, which means uploading email text to Kaggle. Not done.
- Star count (29k in 13 days) is context, not evidence of quality.

### Other names found, not tested
[ikermoel/open-alternative-jev](https://github.com/ikermoel/open-alternative-jev) (Apache-2.0; own README says it is not wire-compatible and wants a GPU for good results). Search results also mention "Kev" (LoRA on Qwen3.5) and Verdict; I did not verify either.

## Cost arithmetic (assumptions stated)

- Jev: $0.042 per million input tokens, output free, per your own `docs/research/opus-5-5-plus-jev-cost.md` and secondary blogs. About 875 input tokens per call gives $0.0000368 per call. 200 emails/day x 30 = 6,000 calls = **$0.22/month**; 500 jobs/day x 30 = 15,000 calls (job prompts are shorter; same figure used) = **$0.55/month**. $5 of credit covers about 136,000 calls, roughly two years of email alone.
- Haiku 4.5: $1/MTok input, $5/MTok output, Batch API half price ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)). Assumed ~1,400 input and ~15 output tokens per email (prompt with category rubric, structured output) = $0.0015/call, so about **$9/month for email** and **$13/month for jobs** at ~$0.00085/call; half that with Batch. These token counts are my estimates, not measured.
- Embeddings+LR, Laya, Ollama: $0 marginal; CPU time only.

## Recommendation

| Workload | Primary | Runner-up | Why |
|---|---|---|---|
| Job triage (career-ops) | **Jev, with the $5 top-up** | Haiku 4.5 (~$13/month est.) | ~$0.55/month at the list price, so $5 lasts ~9 months (review measured ~730 input tokens per job call and 613 pending jobs today; ~$0.56/month). I have no reference labels for jobs, so no alternative could be measured. Job postings are public data, so a hosted fallback (Haiku, or SemIf on a rented GPU) has no privacy cost there. `jev_triage.py` already keeps the old shortlist when fewer than half the jobs get judged, a safe failure mode. |
| Email triage (tidy) | Jev, same credit | MiniLM + LR as an offline fallback (needs an ADR, see below); SemIf if you get a GPU | Jev costs ~$0.22/month. The free fallback reaches only 0.73 recall on Needs Reply and 0.70 on Spam against Jev's labels, so its verdicts should always go to REVIEW, never auto-act. |

Ranked runner-ups overall: (1) MiniLM + LR for email, free, measured on 480; (2) SemIf, free and zero-shot, best untrained quality, needs a GPU; (3) Haiku 4.5, paid, not measured on your data; (4) Laya, only after fine-tuning, which needs a GPU.

## Two project rules the email fallback runs into

- **AGENTS.md: "Jev is the judge… Do not add heuristic quality scores beside it."** A learned fallback classifier is not a heuristic score, but it is a second judge. Record it in an ADR before building it.
- **Retention: Gmail-derived judgments expire after 30 days** (`RETENTION_DAYS = 30` in `tidy/mail.py`; AGENTS.md). The 42k-row benchmark used here will age out, and a classifier trained on it is arguably derived data under the same rule. Decide in the same ADR whether a trained model may outlive its training rows. If not, retrain monthly from the live 30-day window and delete the old model.

## Swap plan (no edits applied)

**career-ops: no code change.** Top up $5 at console.typesafe.ai and let the next daily run go.

**tidy (only after the ADR above):**

1. **New file `tidy/local_judge.py`** (~20 lines), returning the existing `MailJudgment`:
   ```python
   # sketch
   from datetime import datetime, timezone
   import joblib
   from sentence_transformers import SentenceTransformer
   from .mail import MailJudgment, _state
   SCHEMA_ID = "mail-v2-local"  # separate cache key: never mistaken for a Jev verdict (ADR 0004)
   _enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
   _clf, _labels = joblib.load(".tidy/local_clf.joblib")  # LogisticRegression(class_weight="balanced"), label order

   def classify(message, owner_email):
       s = _state(message, owner_email)
       f = s['facts']  # must match the training text in emb.py exactly
       text = f"From: {s['sender']}\nSubject: {s['subject']}\n{s['snippet']}\nunsub:{bool(f['list_unsubscribe_header'])} direct:{f['addressed_directly']}"
       probs = dict(zip(_labels, map(float, _clf.predict_proba(_enc.encode([text]))[0])))
       top = max(probs, key=probs.get)
       return MailJudgment(message["id"], message["thread_id"], "local-minilm-lr", top, probs[top], probs,
                           {"input_tokens": 0, "output_tokens": 0}, datetime.now(timezone.utc).isoformat(), s["facts"])
   ```
2. **New script `tidy/train_local.py`**: read live `mail-v2` judgments joined to message text, fit, dump `(clf, labels)`.
3. **`tidy/mail.py` `classify_batch`**: when `classify()` returns an error string, call `local_judge.classify` and cache under `local_judge.SCHEMA_ID`. Note `classify()` catches only `TypeSafeError`; network errors raise past it.
4. **`propose()`**: if `judgment.model == "local-minilm-lr"`, return REVIEW, checked before the BULK_SPLIT branch. Never ARCHIVE/TRASH/SPAM from a fallback verdict.
5. Add one test: a fallback verdict always proposes REVIEW.

## Caveats on my own measurements

- Labels are Jev's, so every number is agreement with Jev. A model that matches Jev perfectly inherits its errors.
- **Sender leakage (measured in review):** 86.9% of test emails have a sender that also appears in train; 18.1% share a thread. MiniLM+LR on unseen senders (n=63): acc 0.556, macro-F1 0.395. A fallback must be re-measured with a sender-grouped split (`GroupShuffleSplit`).
- The embedding classifier trained on 42,172 of the same cache it was tested on. Recurring senders (newsletters, notifications) likely appear in both train and test, so 0.685 is probably **optimistic** for new senders. I did not deduplicate by sender.
- Test set is class-balanced; natural-mix accuracy will differ (Promos and Updates are 77% of the cache).
- Laya was run with one prompt format and no fine-tuning.
- Latencies were measured while other jobs shared the CPU; treat them as upper bounds.

## Not verified, and how to check

| Item | How to check |
|---|---|
| Jev price and $5 free credit | Primary docs index (`docs.typesafe.ai/llms.txt`) has no pricing; `docs.typesafe.ai/pricing` and `typesafe.ai/pricing` returned 404. Check console.typesafe.ai billing page when logged in. Figures here come from your own cost note and blogs. |
| DeBERTa-v3 NLI zero-shot | Three attempts did not finish on this CPU (the model never reached its first item within 280 s; I did not find the cause, possibly tokenizer conversion on Python 3.14 / transformers 5). Retry in a clean Python 3.12 venv. |
| Ollama quality beyond 30 items; larger models | `python oll.py <model> 480` in the scratchpad takes about 65 min on this CPU for a 3B model. |
| Haiku 4.5 accuracy | Needs your approval to run on synthetic emails (hosted API). Existing mail evals in `.tidy/` cover channel judgments, not email. |
| Job triage quality of any alternative | No Jev scores for jobs are stored (`data/shortlist.md` has none). Save one Jev run's `fit`/`senior` values, then compare. |
| Laya fine-tuned checkpoint (`laya-typed-decisions`) | Its card claims 0.766 on its own benchmark; not run, and fine-tuning on your emails needs a GPU. |
| Codiv hosting, Kev, Verdict | Not tested. Codiv is hosted, so only try it on job postings (public data) with your approval. |
| SemIf beyond 30 emails; calibrated; `shared` mode speed for jobs | Rerun `semif-score --mode direct --backend llamacpp` on the 480 (≈4.7 h on this CPU), then `benchmarks/calibrate.py` with Jev labels. |
| Laya "invalid temperatures" cause | Issue-tracker search on the Laya repo; I only saw the install-time warning. |
