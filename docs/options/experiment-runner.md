# Options: the Jev experiment runner (issue #3)

Written 2026-10-24 during an unattended run. It builds on the design note already on #3 (2026-10, "what is left on #3").

## Where #3 stands

Merged: `tidy judge --schemas A B` (`tidy/experiment.py`). One bundled Jev call per evidence sample, cached by evidence
hash, schema id and interests key, six channels in parallel, with tokens, latency, cache hits and per-dimension
schema disagreements in the report. `evals/labeled_accuracy.py` already computes AUC with a bootstrap 95% interval
against owner labels.

What the experiment has shown (`docs/guide/jev-playbook.md`, project notes 2026-09-21):

- `titles-desc-v1` costs 54% more input tokens than `titles-v1`, with no clear gain.
- No Jev dimension predicts the owner's keep/drop labels: AUC 0.32 to 0.52 on 66 blind relabels. The owner agrees
  with their own earlier labels 85% of the time, so label noise does not explain the result. Watch history does
  better (AUC 0.65 to 0.69).

So a larger two-schema run would mostly measure how stable Jev is **between schemas**, not whether either schema is
**right**. Any public write-up has to say that.

Gaps against the issue text:

| Issue asks | Code today |
|---|---|
| save the exact questions | questions live in code under a schema id. Editing `QUESTIONS` without renaming the id reuses old cached answers for up to 30 days |
| pinned model | `reply.model` is recorded, but no `model=` is sent, so the server picks the model. The SDK accepts `system_one(..., model=...)` |
| distributions | stored in the judgment cache, dropped from the report by `experiment._values` |
| hold out owner labels | `review.agreement(held_out=...)` exists; the runner reports no label metric |

## Design A: close #3 on the existing result

Record the result above in the playbook, close #3, and leave the code as it is.

- Cost: nothing to build. The schema-edit cache trap stays (it is a process rule today: rename the schema id when
  questions change, as `mail.SCHEMA_ID` says in a comment).
- Gain: no more spend on a question that already has an answer. It is honest about the limit: quality dimensions do
  not track this owner's taste.

## Design B: harden the runner, then one 8-channel run (recommended)

One small PR, then one run the owner approves:

1. **Schema fingerprint.** `schema_hash = sha256(json(questions, rendering flags))[:12]` goes into the judgment and
   the cache key, so an edited question can never reuse old answers under the same id.
2. **Pin the model.** A `model` key in `profile.json`, passed to `system_one`. A different `reply.model` is an error,
   not silent drift.
3. **Keep distributions.** `_values` keeps `probabilities`.
4. **Held-out metric.** Use the same deterministic third as the gate design (`sha256(channel_id) mod 3 == 0`, see
   `docs/options/gated-auto-actions.md`). Per schema, report AUC of each dimension on held-out labels by reusing
   `evals.labeled_accuracy.score`.
5. **Report file.** One 0600 JSON per run under the data dir (`experiments/<UTC stamp>.json`), never in Git.

Run protocol: `tidy judge --schemas titles-v1 titles-v2` as a dry run (offline cost), then 8 channels the owner picks
from both keep and drop labels. Stop for review. A full run happens only after the owner approves it.

- Cost: about a day of work, plus a few cents of Jev calls for 8 channels × 2 schemas.
- Gain: every future number is reproducible (fixed schema hash, fixed model, held-out labels). `titles-v2` (watch
  fit) is the one schema aimed at what the labels track, so it is the only comparison worth paying for.
- Risk: the held-out third of 66 labels is about 22 channels, so the intervals stay wide. Say so in any write-up.

## Design C: general experiment harness

Experiment manifests (`schemas`, `channels`, `model`, `split`, `repeats`), repeat runs for repeatability, and charts,
folded together with the `evals/` scripts.

- Cost: several PRs. Much of it duplicates `evals/` (`repeat.py`, `labeled_accuracy.py`, `calibration*.py`).
- Gain: one entry point for every experiment and every public number.
- Risk: building infrastructure for a project the owner parked on 2026-09-21. YAGNI until a second use case
  (another account or a work dataset with labels) needs it.

## Recommendation

**B, items 1 and 3 first.** They are cheap and close a silent-reuse trap and a reporting gap, and they need no owner
data. Items 2, 4 and 5 and the 8-channel run should wait for the owner's go-ahead, because they spend Jev calls and
read private labels. If the owner does not want another run, take **A** and close #3, keeping items 1 and 3 as a
separate cleanup.
