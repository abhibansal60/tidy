# What the Gmail cleanup costs: Opus 5.5 builds it, Jev runs it

Date: 2026-09-22. All prices are list API prices in USD. "Measured" means read from real usage logs or real
Jev responses; "estimate" means arithmetic on assumptions stated next to it.

## Prices used

| Model | Input / MTok | Output / MTok | Cache read / MTok | Cache write (1 h) / MTok |
|---|---|---|---|---|
| Jev (TypeSafe System One) | $0.042 | free | n/a | n/a |
| Claude Opus 5.5 | $4.00 | $20.00 | $0.20 | $8.00 (2x input) |
| Claude Sonnet 5 | $2.00 | $10.00 | $0.20 | $4.00 (2x input) |

Batch API halves Claude prices. Claude Code sessions use the 1 hour cache, so cache writes are priced at 2x input.

## 1. Running it: Jev per email (measured)

- Average Jev input: 830 tokens per email (50 real inbox emails, 2026-09-22) and 872 tokens (an earlier 10-email run).
- Cost per email: about $0.000036. Output is free.
- Whole unread backlog (12,158 emails): about **$0.43**. Whole mailbox (56,679 emails): about $2.00.
- Rerunning on unchanged mail costs $0: judgments are cached by evidence hash (ADR 0004). The second run in this
  review re-sorted the same 50 emails under a new policy without a single new Jev call.
- Daily cron at a typical 50 new emails a day: about $0.002 a day, under $1 a year.

## 2. Running it with Opus 5.5 instead of Jev (estimate)

Same job, Opus 5.5 as the classifier, one request per email:

- Input: 1,100 to 1,400 tokens (the same email state plus about 250 tokens of category instructions and an output
  schema; Claude's tokenizer counts 1.0x to 1.35x Jev's). The fixed prefix is below the minimum cacheable size, so
  prompt caching does not help.
- Output: 100 to 250 tokens. Opus 5.5 cannot turn thinking off; at `low` effort it still thinks briefly, then
  returns a short JSON answer.
- Per email: $0.0064 to $0.0106, or $0.0032 to $0.0053 with the Batch API.

| Workload | Jev | Opus 5.5 | Opus 5.5 batch | Opus 5.5 / Jev |
|---|---|---|---|---|
| 12,158 unread | $0.43 | $78 to $129 | $39 to $64 | 180x to 300x |
| 56,679 whole mailbox | $2.00 | $363 to $601 | $181 to $300 | 180x to 300x |
| 1 year of daily cron (50/day) | $0.65 | $117 to $194 | n/a (cron wants answers now) | 180x to 300x |

Not measured: we did not run Opus 5.5 over the inbox. Run it on a labeled sample before quoting these as fact.
Also not measured: whether Opus 5.5 sorts better. Jev's Updates/Promos split (below) is a sign of where a stronger
model might add value, but the policy change fixed it for free.

## 3. Building it: Claude as the engineer (measured from session logs)

| Session | Model | API turns | Output tokens | Cache read | Cache write | List cost |
|---|---|---|---|---|---|---|
| Original build (Gmail OAuth, triage, dashboard, cron, Vercel, video) | Sonnet 5 | 570 | 0.30 M | 232.4 M | 2.07 M | **$57.76** |
| Same tokens repriced at Opus 5.5 | Opus 5.5 | | | | | $69.04 |
| This review (bugs, features, this report) | Opus 5.5 | about 40 | 0.03 M | 5.7 M | 0.17 M | **about $3.50** |

Cache reads are about 80% of every build bill: long agent sessions re-read their own context on every turn.
Codex reviews ran on a separate plan and are not included. On a Claude subscription none of this is billed per token;
the numbers are what the same work would cost on the API.

## Bottom line

- One-time: about $60 to $73 of Claude (build plus review) at list prices.
- Ongoing: Jev sorts the entire 12,158-email backlog for 43 cents and a year of daily cleanup for under $1.
- Using Opus 5.5 as the sorter would cost more than the whole build on the very first backlog pass. The split
  that works: the frontier model writes and reviews the code once; Jev makes the thousands of small judgments.

## What the Opus 5.5 review changed (same session)

- Starred mail is never proposed for any action.
- `mail-act` rechecks each message live before Trash/Spam and skips anything moved or starred since the run.
- Message IDs from hand-editable run files are validated before they reach a Gmail URL.
- The daily cron writes one run file per day instead of overwriting, so held proposals are not lost; `mail-act`
  merges several runs, newest run wins, and never reapplies a message applied in any run (both found by Codex).
- Clearly bulk mail that Jev splits between Updates and Promos (together at least 0.9, Needs Reply at most 0.05) now
  archives instead of piling into Review, and Gmail's own Updates/Promotions tab counts as a corroborating signal.
  On 50 real emails the Review pile went from 31 to 7 at zero extra Jev cost.
- The dashboard has an unsubscribe shortlist grouped by sender (one click per sender, still never clicked by Tidy).
