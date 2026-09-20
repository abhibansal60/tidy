# X post, humanized

Two versions of the same story. Figures checked against the supplied table in `docs/post/CODEX_REVIEW.md`. The repo is private; keep the DM invitation.

## Thread (9 posts, each under 280 characters)

Attach `.tidy/tidy_demo.mp4` to post 1. The text below is ready to paste, including numbering. Publish as one connected thread.

1/9 🧵 Jev judged my 110 YouTube subscriptions in 9 seconds. Sonnet 5 via CLI: 3 minutes 8 seconds.

All 8 models scored near chance on what I'd keep.
My watch history did better.

2/9 I timed the others through Claude Code or Codex. Jev was 21 to 48 times faster, including CLI overhead. Pydantic and Vercel report about 3 to 6 times on direct APIs with different baselines. Frontier models still win some tasks.

3/9 At list API prices, my run came to $0.004 for Jev, $0.03 for Luna, $0.32 for Sonnet 5, $1.03 for Opus 5 and $1.11 for Astra. Fable 5.1 would be about $2 by my projection. I didn't run it.

4/9 I compared repeatability on 30 channels over two runs. Jev's scores moved 3 to 4 times less than Sonnet 5's. That's one person's test. Cheap and steady looked useful. Then I checked my own choices.

5/9 I checked the models' composite rankings against my keep or drop labels on 66 channels. All scored 0.43 to 0.52 AUC. That measures whether a keep ranks above a drop; 0.5 is chance. Jev was in the same range.

6/9 How often I watched a channel scored 0.69 AUC (95% interval: 0.59 to 0.80). Better than the models in my test, still imperfect. I wouldn't let that score alone choose my subscriptions either.

7/9 In Tidy, I use Jev for judgments and code for thresholds, caps and budgets. I approve each change, which goes through YouTube's API. So far, 11 unsubscribes, each signed off by me.

8/9 Tidy found 30 channels in my watch history that I don't follow and proposed 13. I declined all of them. I watch those ad hoc, and that's fine.

9/9 I start each review myself: sync subscriptions, collect evidence, run Jev, then read and approve proposals. Tidy expires cached evidence after 30 days.

Repo and setup guide: github.com/abhibansal60/tidy

## Long post (X Premium)

Jev judged my 110 YouTube subscriptions in 9 seconds. Sonnet 5 took 3 minutes 8 seconds through its coding CLI. Both scored near chance on what I'd keep. My watch history did better.

I tested 8 models: Jev, Opus 5, Sonnet 5, Haiku 4.5, Sol, Astra, Terra and Luna. Same four questions and prompts for each: relevance to me, substance, packaging risk and whether there was enough evidence to judge.

Jev's exact time was 9.1 seconds for all 110. Opus 5 also took 3 minutes 8 seconds; Sol took 3m 48s and Haiku 4.5 took 7m 19s. I timed the others through Claude Code or Codex, with 6 calls in flight. The 21 to 48 times speed gap includes CLI overhead. Pydantic and Vercel report about 3 to 6 times on direct APIs with different baselines. Frontier models still win some tasks.

At list API prices, my run came to $0.004 for Jev and $0.03 (Luna) to $1.11 (Astra) for the others. Fable 5.1 would be about $2 by my projection; I didn't run it.

On 30 channels over two runs, Jev's scores moved 3 to 4 times less than Sonnet 5's. That's one person's repeatability test. Steady scores could still miss what I wanted.

I checked every model's composite ranking against my keep or drop labels on 66 channels. All scored between 0.43 and 0.52 AUC. AUC measures whether a channel I'd keep ranks above one I'd drop; 0.5 is chance. My watch history scored 0.69 AUC (95% interval: 0.59 to 0.80). It was a better predictor in this test, with plenty of uncertainty left.

That's why I keep approval in my hands. In Tidy, Jev supplies judgments and code applies thresholds, caps and budgets. Changes go through YouTube's API. I approved each of the 11 unsubscribes so far.

Tidy also found 30 channels I watch but don't follow and proposed 13. I declined all of them. Watching a channel often still wasn't enough reason for me to subscribe.

I start each review myself: sync subscriptions, collect evidence, let Jev judge, then read and approve proposals. Tidy expires cached evidence after 30 days.

Repo and setup guide: github.com/abhibansal60/tidy
