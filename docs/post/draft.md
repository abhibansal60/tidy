# Post draft: Jev vs frontier models on a real task

Status: DRAFT, numbers final as of 2026-09-20 04:00 IST (all runs complete). No channel names appear anywhere; keep it that way.

Video: `.tidy/tidy_demo.mp4` (1280x720, about 70 s, first frame is the thumbnail). GIF: `.tidy/tidy_demo.gif`.

## X thread

1/ I gave one job to Jev and to seven frontier models: judge my 110 YouTube subscriptions. Same evidence, same four questions, same prompts. Which channels are worth keeping? Here is what happened. [video]

2/ Speed. Jev: 9.1 s for all 110. Through coding CLIs: Sonnet 5 and Opus 5 3m 08s, Terra 3m 35s, Luna 3m 37s, Sol 3m 48s, Astra about 4m 07s, Haiku 4.5 7m 19s. That is 21x to 48x. Caveat: CLIs add per-call overhead. Public direct-API tests find 3x to 6x.

3/ Cost at list API prices for the same run: Jev $0.004. Luna $0.03, Terra $0.31, Sonnet 5 $0.32, Sol $0.44, Haiku 4.5 $0.99, Opus 5 $1.03, Astra $1.11. That is 8x to 250x cheaper. Fable 5.1 projects to ~$2 (not measured).

4/ Consistency. Run it twice: Jev's scores moved 3x to 4x less than Sonnet 5's on relevance, value and packaging risk (4x to 12x less than Haiku at low effort). Nobody else has published this, so it is my measurement on 30 channels.

5/ Agreement. On rank order, Jev tracks Opus 5 closely: correlation 0.94 relevance, 0.88 value, 0.97 packaging risk. It is not better. It is close, fast and cheap.

6/ The honest part. I checked every judge against my own keep/drop labels (66 channels). Jev and all seven models scored 0.43 to 0.52, near a coin flip. My watch history scored 0.69. Quality is not taste. No model knew what I would actually keep.

7/ So the design: Jev judges (seconds, cents). Code decides (thresholds, caps, budgets). I approve. 11 channels unsubscribed, each signed off. A watch-history pass proposed 13 channels to add. I took none: it proposes, I decide.

8/ Outside numbers agree on direction, not size: independent tests (Pydantic, Vercel) found Jev 3x to 6x faster on direct APIs and far cheaper, with frontier models ahead on open-ended tasks. Repo: github.com/abhibansal60/tidy

## LinkedIn

Jev judged my 110 YouTube subscriptions in 9 seconds. Sonnet 5 via CLI: 3 minutes 8 seconds.
Both scored near chance on what I'd keep. My watch history did better.

I tested 8 models: Jev, Opus 5, Sonnet 5, Haiku 4.5, Sol, Astra, Terra and Luna. I gave each the same four questions and prompts.

Jev finished in 9.1 seconds. I timed the others through Claude Code or Codex, with 6 calls in flight. That gave Jev a 21 to 48 times speed advantage, including CLI overhead. Pydantic and Vercel report about 3 to 6 times on direct APIs with different baselines. Frontier models still win some tasks.

At list API prices, my run came to $0.004 for Jev and $0.03 (Luna) to $1.11 (Astra) for the others. Fable 5.1 would be about $2 by my projection. I didn't run it.

On 30 channels over two runs, Jev's scores moved 3 to 4 times less than Sonnet 5's. That's one person's repeatability test. Its rank agreement with Opus 5 was 0.88 to 0.97 on relevance, value and packaging risk.

Against my keep or drop labels on 66 channels, every model's composite ranking scored 0.43 to 0.52 AUC. AUC measures whether a keep ranks above a drop; 0.5 is chance. My watch history scored 0.69 AUC (95% interval: 0.59 to 0.80). It predicted my choices better in this test, though imperfectly.

In Tidy, I use Jev for judgments and code for thresholds, caps and budgets. I approve each change, which goes through YouTube's API. So far, I've approved 11 unsubscribes.

A pass through my watch history found 30 channels I watch but don't follow and proposed 13. I declined all of them. Watching a channel often still wasn't enough reason for me to subscribe.

I start each review myself: sync subscriptions, collect evidence, let Jev judge, then read and approve proposals. Tidy expires cached evidence after 30 days.

Repo and setup guide: github.com/abhibansal60/tidy

## Before posting (checklist)

- [x] Codex runs and Sonnet 5 repeatability are in (Astra's wall time is estimated from summed call time, because its run was resumed).
- [ ] Confirm each number against `python -m evals.compare` and `python -m evals.list_price`.
- [ ] Re-check OpenAI list prices on developers.openai.com/api/docs/pricing (the fetched page was summarised).
- [x] Fable 5.1 stays projected (~$2, not measured), decided by the owner.
- [ ] Ask TypeSafe whether they want to review the claims and the repo link.
- [ ] No channel names, IDs or screenshots of the owner's data.
