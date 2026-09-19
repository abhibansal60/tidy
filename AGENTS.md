# Project decisions

Read README.md for the current phase and runnable commands. HANDOFF.md, when
present locally, is the historical Claude handoff; it contains private data and
is not tracked. It does not override the decisions below.

- The owner is learning and experimenting with Jev and intends to write publicly
  about the results. Keep experiments measurable and explanations honest about
  evidence limitations. Public examples and tests use synthetic identities.
- Prefer exceptional content, especially AI/software/technical material. Some
  music and comedy are welcome; removing entertainment is a low concern. These
  are starting preferences, not categorical bans or mutation authorization.
- Python and SQLite are approved. Reuse old work only when useful; there is no
  requirement to retain old architecture or scoring policy.
- Current implementation scope is preservation and read-only subscription import.
  API-fed scoring remains contingent on resolving YouTube's derived-data and
  retention requirements. Later phases require an incremental review.
- Jev supplies typed judgments. Code owns arithmetic, dates, persistence, policy,
  and side effects. Preserve raw answers and evidence provenance in future work.
- Subscription changes require explicit recorded approval and a dry-run path.
  The only mutation is `unsubscribe` (dry-run by default), which acts solely on
  subscriptions recorded by `approve`, uses a separate write-scope token, rechecks
  the live list first, and stops on ambiguous outcomes. Owner approval for the
  first batch was given 2026-09-19; later batches need fresh approval.
- Account identity, OAuth files, subscription lists, databases, raw experiment
  outputs, and original handoff stay outside Git. Never publish without an
  explicit request. Preserve useful historical artifacts locally.
