# Tidy

Tidy is a personal tool that keeps the owner's YouTube subscription feed full of exceptional content. Jev makes every quality judgment; deterministic code does everything else.

## Language

**Subscription**:
The owner's live link to a channel, with its own subscription ID distinct from the channel ID.
_Avoid_: follow, sub (as a noun for the channel)

**Channel**:
A YouTube creator page, identified by channel ID.
_Avoid_: creator, account

**Evidence sample**:
The bounded, dated set of channel metadata and recent upload titles and descriptions handed to Jev for one judgment, identified by an evidence hash.
_Avoid_: data, context, input

**Jev judgment**:
Jev's typed answer distributions to one bundle of questions about one evidence sample. Includes model version, usage and latency.
_Avoid_: score, rating, result

**Dimension**:
One independent question Jev answers: relevance, apparent value, sensational-packaging risk, evidence sufficiency. Dimensions are never merged into one number.
_Avoid_: metric, factor

**Evidence sufficiency**:
Jev's judgment of whether the evidence sample can support the other dimensions. Insufficient is not negative.
_Avoid_: confidence (confidence is distribution concentration, not agreement with the owner)

**Owner label**:
The owner's independent verdict on a channel (keep, drop, unsure). Ground truth for calibration, never API data.
_Avoid_: annotation, feedback

**Calibration gate**:
The agreement threshold between Jev proposals and held-out owner labels that must hold before an action type may run automatically.
_Avoid_: threshold (that word belongs to policy)

**Policy**:
Versioned deterministic code that turns Jev judgments and evidence coverage into a proposal. Changing policy costs no Jev calls.
_Avoid_: rules, formula

**Proposal**:
A policy output for one channel: `KEEP`, `WATCH`, `REVIEW`, `UNSUBSCRIBE`, or a discovery `SUBSCRIBE`, with the signals that drove it.
_Avoid_: recommendation, decision

**Approval**:
A recorded owner authorization bound to account plus subscription ID. Manual approvals are per batch.
_Avoid_: consent, sign-off

**Review**:
An owner pass over proposals, producing owner labels and overrides.

**Run**:
One owner-started execution: collect, judge, propose, act within caps, audit. Never unattended.
_Avoid_: job, cron

**Caps**:
Per-run maximum counts of automatic unsubscribes and subscribes.

**Mutation**:
Any write to the owner's YouTube subscriptions: `unsubscribe` or `subscribe`.
_Avoid_: change, update

**Candidate**:
A channel not currently subscribed, surfaced by discovery and judged on the same pipeline as subscriptions.
_Avoid_: recommendation, lead

**Trial**:
The 30-day status of an automatically subscribed channel, after which it graduates to normal or is proposed for removal.
_Avoid_: probation
