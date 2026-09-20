# Post draft: Jev vs frontier models on a real task

Status: DRAFT, numbers final as of 2026-09-20 04:00 IST (all runs complete). No channel names appear anywhere; keep it that way.

Video: `.tidy/tidy_demo.mp4` (1280x720, about 60 s). GIF: `.tidy/tidy_demo.gif`.

## X thread

1/ I gave one job to Jev and to seven frontier models: judge my 110 YouTube subscriptions. Same evidence, same four questions, same prompts. Which channels are worth keeping? Here is what happened. [video]

2/ Speed. Jev: 9.1 s for all 110. Through coding CLIs: Sonnet 5 and Opus 5 3m 08s, Terra 3m 35s, Luna 3m 37s, Sol 3m 48s, Astra about 4m 07s, Haiku 4.5 7m 19s. That is 21x to 48x. Caveat: CLIs add per-call overhead. Public direct-API tests find 3x to 6x.

3/ Cost at list API prices for the same run: Jev $0.004. Luna $0.03, Terra $0.31, Sonnet 5 $0.32, Sol $0.44, Haiku 4.5 $0.99, Opus 5 $1.03, Astra $1.11. That is 8x to 250x cheaper. Fable 5.1 projects to ~$2 (not measured).

4/ Consistency. Run it twice: Jev's scores moved 3x to 4x less than Sonnet 5's on relevance, value and packaging risk (4x to 12x less than Haiku at low effort). Nobody else has published this, so it is my measurement on 30 channels.

5/ Agreement. On rank order, Jev tracks Opus 5 closely: correlation 0.94 relevance, 0.88 value, 0.97 packaging risk. It is not better. It is close, fast and cheap.

6/ The honest part. I checked every judge against my own keep/drop labels (34 channels). Jev and all seven models scored 0.45 to 0.60, near a coin flip. My watch history scored 0.80. Quality is not taste. No model knew what I would actually keep.

7/ So the design: Jev judges (seconds, cents). Code decides (thresholds, caps, budgets). I approve. 11 channels unsubscribed, each signed off. A watch-history pass proposed 13 channels to add. I took none: it proposes, I decide.

8/ Outside numbers agree on direction, not size: independent tests (Every, Pydantic) found Jev 3x to 6x faster on direct APIs and far cheaper, with frontier models ahead on open-ended tasks. Code and method: github.com/abhibansal60/tidy

## LinkedIn

I follow 110 YouTube channels and wanted to know which are worth keeping. That is 110 small judgment calls, so I used it as a test: Jev (TypeSafe's System One model) against seven frontier models, same evidence and prompts.

What I measured:
- Speed: 9.1 seconds for all 110 with Jev; 3 to 7 minutes through coding CLIs (Claude Code, Codex), Opus, Sonnet, Haiku, Sol, Astra, Terra and Luna. That is 21x to 48x, but it includes CLI overhead. Public direct-API tests show 3x to 6x, so read it as an upper bound.
- Cost at list API prices for the run: about $0.004 for Jev; $0.03 (Luna) to $1.11 (Astra) for the others.
- Consistency: Jev's scores moved 3x to 4x less between two runs than Sonnet 5's.
- Agreement: rank correlation with Opus 5 of 0.88 to 0.97. Close, not better.

What surprised me: none of them, Jev included, predicted my own keep/drop decisions (0.45 to 0.60 on 34 labels). My watch history did (0.80). A judgment about quality is not a judgment about taste.

So Tidy keeps the roles apart: Jev makes the fast, cheap judgment; code owns thresholds, caps and budgets; I approve every change. Eleven unsubscribes, each approved by me. A watch-history pass that finds channels I watch but do not follow proposed 13 to add (from 30 candidates); I declined all of them. The loop proposes, I decide.

Takeaway: use a decision model where you need many fast, repeatable calls, keep humans on anything irreversible, and measure against your own labels before trusting any score.

## Before posting (checklist)

- [x] Codex runs and Sonnet 5 repeatability are in (Astra's wall time is estimated from summed call time, because its run was resumed).
- [ ] Confirm each number against `python -m evals.compare` and `python -m evals.list_price`.
- [ ] Re-check OpenAI list prices on developers.openai.com/api/docs/pricing (the fetched page was summarised).
- [x] Fable 5.1 stays projected (~$2, not measured), decided by the owner.
- [ ] Ask TypeSafe whether they want to review the claims and the repo link.
- [ ] No channel names, IDs or screenshots of the owner's data.
