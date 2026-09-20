# Project decisions

The application is named Tidy (package `tidy`, data under `.tidy/`). Jev is the model it uses. Names must never include YouTube, YT or variants (YouTube API branding rules).

Read README.md for the current phase and runnable commands. HANDOFF.md, when
present locally, is the historical Claude handoff; it contains private data and
is not tracked. It does not override the decisions below.

- The owner is learning and experimenting with Jev and intends to write publicly
  about the results. Keep experiments measurable and explanations honest about
  evidence limitations. Public examples and tests use synthetic identities; public writing uses aliases (ADR 0003).
- Prefer exceptional content, especially AI/software/technical material. Some
  music and comedy are welcome; removing entertainment is a low concern. These
  are starting preferences, not categorical bans or mutation authorization.
- Python and SQLite are approved. Reuse old work only when useful; there is no
  requirement to retain old architecture or scoring policy.
- Current scope: subscription inventory, read-only evidence collection with a 30-day
  retention limit, Jev judgments, review and labeling, owner-approved unsubscribes,
  gated automatic actions (closed by default) and watch-history discovery. See
  docs/adr/0005 and README.md.
- Jev supplies typed judgments. Code owns arithmetic, dates, persistence, policy,
  and side effects. Preserve raw answers and evidence provenance in future work.
- Vocabulary is in `CONTEXT.md`; reasons for the big decisions are in `docs/adr/`.
- Jev is the judge and the reason automation is cheap and fast: one bundled call
  per evidence sample, compact evidence, judgments cached by evidence hash
  (ADR 0004). Do not add heuristic quality scores beside it.
- Mutations (`unsubscribe`, later `subscribe`) are dry-run by default, use the
  separate write token, and recheck the live list first (ADR 0002). Manual
  `approve` batches stay valid (owner approved batch 1, six channels, and batch 2, five channels, on
  2026-09-19; later batches need fresh approval). Owner authorized gated autonomy on 2026-09-19
  (ADR 0005): automatic actions run only in an owner-started run, per action type
  only after the calibration gate holds, within caps, never on one dimension
  alone. Until a gate holds, propose only and collect owner labels.
- Retention: cached API metadata, evidence samples and Jev judgments about them
  expire within 30 days of the fetch; a `purge` command drops them (and channels
  that turn private or missing). Owner labels are kept. No scraping. Details and
  open questions in `docs/research/youtube-api-policy.md`.
- Reusability is a later goal, not day 1: others may run this with their own
  credentials. Keep owner taste (topics, thresholds, caps) in per-user config and
  labels, not code, and per-user state under `--data-dir`. No hosted multi-user
  service without a policy review (see `docs/research/`).
- Account identity, OAuth files, subscription lists, databases, raw experiment
  outputs, and original handoff stay outside Git. Never publish without an
  explicit request. Preserve useful historical artifacts locally.
