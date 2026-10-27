# Options: gated automatic actions (issue #5)

Written 2026-10-24 during an unattended run. Scope is YouTube `act` (ADR 0005). Mail triage has its own, always-closed
gate (`mail.gate_status`) and is covered only in the last section.

## Where #5 stands

Already merged and tested: `act` with per-action `--gate-*` flags, caps (5 unsubscribes, 3 subscribes from
`profile.json`), the anomaly abort (more eligible unsubscribes than `max(3 × cap, 20% of subscriptions)`), the
two-signal rule, an `auto_actions` row and `audit_events` entry for every attempt, reconciliation of unknown outcomes
from the live list, `resubscribe`, and 30-day trials. `act --execute` refuses a closed calibration gate unless
`--override-gate` is passed (`tidy/__main__.py`, `run_act`).

What does not match ADR 0005 yet:

| ADR 0005 says | Code today | Effect |
|---|---|---|
| gate per action type | one number, `review.agreement`, over every KEEP, WATCH and UNSUBSCRIBE proposal | the gate can open on KEEP matches alone, then let `--gate-unsubscribe` act with no evidence that UNSUBSCRIBE proposals match drop labels |
| gate per action type | SUBSCRIBE is not in `review.AGREES` | `--gate-subscribe` is checked against the unsubscribe/keep number; subscribe has no calibration of its own |
| held-out owner labels | `agreement(..., held_out=None)` everywhere; nothing chooses a split | policy-2 thresholds were set while looking at the same labels, so the number is in-sample |
| trial review | `mutate.trials_due` exists | no command shows it, so ended trials are never surfaced |
| consent per action | open policy question (`docs/research/youtube-api-policy.md`) | not a code question; stays with the owner |

A worked case of the first row: 30 labeled channels, all `keep`, all proposed KEEP. Agreement is 30 of 30, the gate
opens, and `act --execute --gate-unsubscribe` may unsubscribe up to 5 channels even though no UNSUBSCRIBE proposal was
ever checked against a label.

With the labels on hand (66 on the experiment account, per the 2026-09-21 notes, and no Jev dimension better than
chance at predicting them), every design below keeps the gate closed. That is the honest outcome, and it is the point:
the gate should open only when the evidence says so.

## Design A: per-action precision gate on a fixed held-out third (recommended)

For each action type, count only proposals of that type whose channel has a `keep` or `drop` label and falls in a
deterministic held-out split. The rate is precision: of the UNSUBSCRIBE proposals the owner labeled, how many did they
label `drop` (for SUBSCRIBE, `keep`).

```text
held_out(channel_id) = sha256(channel_id) mod 3 == 0         # about one third, stable, no stored state
gate[UNSUBSCRIBE] = gate_status(precision(UNSUBSCRIBE -> drop, held-out labels), profile.gate)
gate[SUBSCRIBE]   = gate_status(precision(SUBSCRIBE   -> keep, held-out labels), profile.gate)
act --execute --gate-unsubscribe   needs gate[UNSUBSCRIBE] open
act --execute --gate-subscribe     needs gate[SUBSCRIBE] open
```

- Cost: small. One function in `review.py`, a flag on `act` and `gate`. The 30-label minimum now applies to labeled
  UNSUBSCRIBE proposals in the held-out third, so the owner needs roughly 90 labeled UNSUBSCRIBE proposals before the
  unsubscribe gate can open. That is slow on purpose.
- Gain: the gate measures the action it unlocks. A wrong unsubscribe is the costly mistake, and precision is exactly
  that rate. The split needs no storage, and owner labels stay untouched (they never expire).
- Risk: the owner may tune thresholds while looking at all labels, including the held-out third. Document "tune on
  the other two thirds" in `docs/reference.md`; code cannot enforce it. The split does not clean today's labels:
  policy-2 was tuned while looking at all 66, so their held-out third is as in-sample as the rest. Only labels given
  after the policy is fixed are truly held out (Design C does that by construction).
- Risk: owner labels are on subscriptions, and SUBSCRIBE proposals are for channels the owner is not subscribed to,
  so they rarely carry a label. gate[SUBSCRIBE] stays closed until candidates get a label source of their own.

## Design B: per-action precision on all labels

Same as A without the split.

- Cost: smallest change. The gate opens about three times sooner.
- Gain: uses every label.
- Risk: in-sample. policy-2 was chosen while looking at these labels, so the rate overstates how well it generalizes.
  This contradicts the "held-out" wording in ADR 0005.

## Design C: prospective shadow ledger

Every `act` run, dry or not, writes its proposals to a new `proposal_log` table (channel, action, policy version,
date). The gate counts only labels the owner gave **after** the proposal was logged, so every label is out-of-time
and held out by construction.

- Cost: a new table and migration, a retention rule (the log holds only IDs and actions, so it can be kept like
  labels), and a labeling flow that shows logged proposals. Several PRs.
- Gain: the strongest evidence. It catches policy drift, because a new policy version starts with an empty ledger.
- Risk: very slow to open at monthly runs. More code than the gate needs today.

## Recommendation

**A**, behind a flag first (`tidy gate --per-action`, `tidy act --per-action-gate`), so today's behaviour is unchanged
until the owner flips it. Under the flag the per-action gate is checked in addition to the pooled one, so it only makes
`act --execute` refuse more often and never makes a mutation more likely; that is what makes it safe to ship. Making
it the default and deleting the pooled check is a later owner decision, because then the per-action gate alone decides.
Add a `tidy trials` command that prints `mutate.trials_due` (small, separate PR). Consider C only if Tidy gets regular
use again.

## Mail (outside ADR 0005)

`mail.gate_status` always reports closed, and the scheduled run on mini uses `--override-gate`. A mail gate would need
mail owner labels. The cheapest source already exists: dashboard actions in the tidy-mail app. "Back to inbox" on an
auto-archived message is a `disagree` label, and leaving it archived for 7 days is a weak `agree`. Recording them needs
a change in the private tidy-mail repo plus a `mail_labels` table here. That is a separate decision, not part of #5.
