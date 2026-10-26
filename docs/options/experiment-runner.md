# Options: the Jev experiment runner (issue #3)

Written 2026-10-24 during an unattended run. It builds on the design note already on #3 (2026-10, "what is left on #3").

## Where #3 stands

Merged: `tidy judge --schemas A B` (`tidy/experiment.py`). One bundled Jev call per evidence sample, cached by evidence
hash, schema id and interests key, six channels in parallel, with tokens, latency, cache hits and per-dimension
schema disagreements in the report. `evals/labeled_accuracy.py` already computes AUC with a bootstrap 95% interval
against owner labels.

What the experiment has shown (`docs/guide/jev-playbook.md`, project notes 2026-09-21):

- `titles-desc-v1` costs 54% more input tokens than `titles-v1`, with no clear gain.
- No model predicts the owner's keep/drop labels: all 8, Jev included, scored AUC 0.43 to 0.52 on 66 labels. A blind
  relabel of 13 agreed with the earlier labels 10 times (about 77%), which caps how well anything can score. The
  watch-history count did better (AUC 0.69, interval 0.59 to 0.80).

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

1. **Schema fingerprint.** `schema_hash = sha256(json.dumps({id: q.model_dump(mode="json")}, sort_keys=True), plus
   rendering flags)[:12]` goes into the judgment and the cache key, so an edited question can never reuse old answers
   under the same id. The questions are pydantic `Score` objects, so plain `json.dumps` cannot hash them. Changing the
   cache key misses the cache once for every channel: the next judge run re-calls Jev (about 110 calls per schema).
2. **Pin the model.** A `model` key in `profile.json` holding a concrete model name, not an alias, passed to
   `system_one`. A `reply.model` different from a concrete pin is an error, not silent drift; with an alias the reply
   may name the resolved model, so only record it.
3. **Keep distributions.** `_values` keeps `probabilities`.
4. **Label metric.** Per schema, report AUC of each dimension on labels **outside** the gate's held-out third
   (`sha256(channel_id) mod 3 != 0`, see `docs/options/gated-auto-actions.md`): choosing a schema is tuning, and
   tuning on the gate's third would make the gate in-sample again. `evals.labeled_accuracy.score` needs an adapter
   first: it reads flat numbers for three fixed dimensions (runner values are `{score, confidence}`, and `titles-v2`
   adds `watch_likelihood`), and `auc`/`bootstrap_ci` crash when a sample has only keep or only drop labels.
5. **Report file.** One 0600 JSON per run under the data dir (`experiments/<UTC stamp>.json`), never in Git.

Run protocol: `tidy judge --schemas titles-v1 titles-v2` as a dry run (offline cost), then 8 channels the owner picks
from both keep and drop labels. Stop for review. A full run happens only after the owner approves it.

- Cost: about a day of work, plus a few cents of Jev calls for 8 channels × 2 schemas.
- Gain: every future number is reproducible (fixed schema hash, fixed model, held-out labels). `titles-v2` (watch
  fit) is the one schema aimed at what the labels track, so it is the only comparison worth paying for.
- Risk: 8 channels give a handful of labels, so the intervals stay wide (or undefined). Say so in any write-up.

## Design C: general experiment harness

Experiment manifests (`schemas`, `channels`, `model`, `split`, `repeats`), repeat runs for repeatability, and charts,
folded together with the `evals/` scripts.

- Cost: several PRs. Much of it duplicates `evals/` (`repeat.py`, `labeled_accuracy.py`, `calibration*.py`).
- Gain: one entry point for every experiment and every public number.
- Risk: building infrastructure for a project the owner parked on 2026-09-21. YAGNI until a second use case
  (another account or a work dataset with labels) needs it.

## Recommendation

**B, item 3 first.** It is cheap, closes a reporting gap and needs no owner data. Item 1 is cheap to write but its
first run re-calls Jev for every channel, so merge it just before an approved run. Items 2, 4 and 5 and the 8-channel
run should wait for the owner's go-ahead, because they spend Jev calls and read private labels.
If the owner does not want another run, take **A** and close #3, keeping items 1 and 3 as a separate cleanup.
