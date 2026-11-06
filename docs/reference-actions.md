# Subscription action safeguards

[Back to the command reference](reference.md).

Automatic actions honor the latest owner labels at planning time: `keep` blocks unsubscribe,
`drop` blocks subscribe, and `unsure` blocks both. A label alone never authorizes a change.
The separate manual `approve` / `unsubscribe` flow still represents explicit owner approval.
Even `--override-gate` cannot bypass these automatic-action vetoes. On execution, enabled
actions in an exported proposals file must exactly match current cached evidence, policy,
action and signals. Regenerate stale proposals with `tidy propose --json PATH`.
Duplicate channel entries are refused, and each channel counts only once in calibration.
Dry runs preview the file offline; execution additionally verifies it against current derivation.

`act` turns proposals into subscribes and unsubscribes, only inside an owner-started
run (ADR 0005). It is a dry run unless you pass `--execute`, and both gates are closed
unless you open them:

```bash
.venv/bin/python -m tidy act --proposals proposals.json --gate-unsubscribe   # dry run, offline
.venv/bin/python -m tidy act --proposals proposals.json --gate-unsubscribe --gate-subscribe --execute
.venv/bin/python -m tidy resubscribe CHANNEL_ID... [--execute]              # undo an automatic unsubscribe
```

`proposals.json` is a list of Proposal dicts; `tidy propose --json proposals.json` writes it. Per run, at most 5 unsubscribes and 3
subscribes (`--cap-unsubscribe`, `--cap-subscribe`). A proposal with fewer than two
signals is never acted on. If the eligible unsubscribes exceed the larger of three
times the cap or 20% of active subscriptions, the whole run aborts with no action.
`--execute` uses `token_write.json`, rechecks identity and the live list, acts one
at a time, and writes an audit event for each. Ambiguous outcomes are marked
`unknown`, never retried, and settled against the live list next run. New
subscriptions start a 30-day trial (`mutate.trials_due` lists the ended ones for
review; nothing graduates or gets removed automatically). Each automatic unsubscribe
records its subscription ID, channel and title so `resubscribe` can restore it.

`--execute` refuses a closed calibration gate unless `--override-gate` is passed. Both the
pooled agreement from `tidy gate` and each enabled action's own gate must be open.
The per-action check uses held-out labels on the complete current derivation,
so selecting a file subset cannot hide disagreements (`tidy gate --per-action`).
`--per-action-gate` remains accepted as a backward-compatible no-op.

## History health

History is unknown when the configured export is missing, unreadable, empty, unsupported,
future-dated, or has no event inside `watch_window_days`. In that case `discover` reports
the status and offers no candidates; `propose` sends channels to REVIEW with an unknown-history
reason. It neither claims zero recent watches nor silently enables the no-history policy.
A recent event proves recency only, not that an export covers every watch or the full window.
Timestamps are normalized to UTC: supported zones are UTC, GMT, Indian Standard Time (IST),
and explicit numeric offsets. Unknown timezone labels are unsupported rather than guessed.

## Evidence eligibility and calibration

The watch-based policy (`policy-2-evidence-v1`) requires nonempty video evidence and the
configured sufficiency and value-confidence floors. Insufficient evidence yields REVIEW even
for a watched channel, and cannot support an unsubscribe or subscribe proposal.
Confidence is only an additional veto, not a calibrated probability of correctness or approval.
An unsubscribe also requires the second opinion's evidence-sufficiency floor and the existing
two-judge low-value cascade. No taste threshold changes with these checks.

Upcoming videos without an API duration are omitted from collected samples and counted as
unavailable; their duration is never treated as zero. Other videos from the channel still collect.
The v2 `watch_likelihood` score is diagnostic; current policy does not use it to authorize actions.

Gate agreement is a mapping-based diagnostic: WATCH counts as keep and REVIEW is excluded.
It is not model accuracy. Historical quality labels and sheets shown with model scores are
not independent action-preference validation. Preserve them, resolve their meaning with the
owner, and freeze policy before collecting prospective evaluation labels. The pooled check
remains an additional all-label prerequisite; each enabled action also needs its own held-out
precision gate. Do not tune on that held-out third or lower gates to fit old labels.

