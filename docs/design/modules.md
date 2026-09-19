# Module seams

Design target: three deep modules (collector, judge, policy), each with a one-function interface, plus the existing store, YouTube transport and mutation modules. Vocabulary: `CONTEXT.md`. Depth terms follow the codebase-design skill.

## Deep modules

**collector** (`collector.py`)
- Interface: `collect(api, channel_ids, window) -> list[EvidenceSample]`.
- Hides: resolving each channel's uploads playlist, paging `playlistItems`, batching `videos.list` by 50, dropping deleted/private videos, coverage and dates, canonical evidence hash, 30-day expiry stamp, quota accounting, failed-run isolation (a failed channel never replaces a prior sample).
- Seam: `api`, the YouTube transport. Adapters: real HTTP session, fake session in tests. This is a real seam (two adapters). `YouTube.get` widens its resource whitelist to `playlistItems` and `videos` only; still GET only.

**judge** (`judge.py`)
- Interface: `judge(client, samples, schema) -> list[Judgment]`.
- Hides: rendering a compact state per sample (capped titles, truncated descriptions, ages computed by code, owner interests from the profile), one bundled Jev call per sample, parallelism across samples, cache keyed by (evidence hash, schema id, model), latency and usage capture, raw distributions preserved.
- Seam: `client`. Adapters: TypeSafe client (`system_one(state, questions)`, as in `rank.py`), fake returning canned distributions. Real seam.
- This is where token efficiency and speed live (ADR 0004). A schema is data, so comparing schemas (issue #3) means running `judge` twice, not writing new code.

**policy** (`policy.py`)
- Interface: `propose(judgment, coverage, profile, status) -> Proposal`. Pure, no I/O, versioned.
- Hides: dimension combination, evidence-sufficiency handling, never-on-one-dimension, entertainment-alone never unsubscribes, trial-period rules. Changing policy re-derives proposals with no Jev calls.
- No seam needed; tests are input/output tables.

## Supporting modules

- **store** keeps connect and migrations, gains tables for evidence samples, judgments, labels, proposals, and `purge()` (30-day expiry, ADR 0004). Split `import_legacy` and `report` out of it when it next changes; do not do it as a standalone refactor.
- **review** (`review.py`): `label()`, `agreement(labels, proposals)` (the calibration gate, pure), and report rendering. Small, becomes deep only if the gate logic grows.
- **mutate** (existing): gains `subscribe`, and `act(db, api, proposals, gates, caps, execute)` which enforces gates, caps and anomaly abort. The write path stays behind the separate token (ADR 0002).
- **profile**: per-user JSON under `--data-dir` with interests text, thresholds, caps, schema id. Owner taste lives here, not in code (reusability, `AGENTS.md`). Not a module until a second field needs logic.

## Not creating

- No `run.py` orchestrator yet: `__main__` composes collect, judge, propose, act until a second caller exists.
- No `Evidence` or `Judgment` class hierarchy: plain dataclasses.
- No plugin system for other users. A profile file is the reuse story.

## Tests

Tests cross only the interfaces above: fake API session into `collect`, fake client into `judge` (assert one call per sample and that unchanged evidence causes zero calls), tables into `propose`, tmp SQLite for store and purge. No real subscription data.

## Build order

1. `collector` + store tables + `purge` (issue #2).
2. `judge` + schema data + profile (issue #3).
3. `policy` + `review` (issue #4).
4. `act` + `subscribe` (issue #5).
