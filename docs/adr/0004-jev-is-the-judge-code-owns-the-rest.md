# Jev is the sole judge; code owns the rest

Every quality judgment comes from Jev as typed probability distributions. Code owns arithmetic, dates, persistence, policy, caps and side effects. The design exists to make Jev the reason automation is cheap and fast:

- One Jev call per evidence sample bundles all independent dimensions, so tokens scale with channels, not questions.
- Evidence is compact (titles, short descriptions, dates), not transcripts or full pages.
- Judgments are keyed by evidence hash. Unchanged evidence is not re-judged; a policy change re-derives proposals with zero Jev calls.
- Channels judged in parallel; a cheap first pass on stale or unchanged channels, deeper evidence only when evidence sufficiency is low.

Alternatives rejected: a hand-tuned heuristic score (conflates dimensions, cannot read meaning) and a general LLM prompt-and-parse loop (slower, costlier, no calibrated distributions). Cached judgments about API-derived evidence expire with YouTube's refresh window; owner labels do not.
