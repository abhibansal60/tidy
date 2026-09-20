# X post, humanized

Two versions of the same story. Figures checked against the supplied table in `docs/post/CODEX_REVIEW.md`. The repo is private; keep the DM invitation.

## Thread (free account, each post under 280 characters)

1/ Jev judged my 110 YouTube subscriptions in 9 seconds. Sonnet 5 took 3 minutes 8 seconds.
I tested 8 models. None predicted what I'd keep much better than a coin flip. [video]

2/ I timed the others through Claude Code or Codex. Jev was 21 to 48 times faster, including CLI overhead. Pydantic, Vercel and another developer measured 3 to 6 times against direct APIs, and frontier models still win some tasks.

3/ At list API prices, my run came to $0.004 for Jev, $0.03 for Luna, $0.32 for Sonnet 5, $1.03 for Opus 5 and $1.11 for Astra. Fable 5.1 would be about $2 by my projection. I didn't run it.

4/ I compared repeatability on 30 channels over two runs. Jev's scores moved 3 to 4 times less than Sonnet 5's. That's one person's test. Steady scores still need checking against what I want to keep.

5/ I checked all 8 models against my keep or drop labels on 66 channels. Every model, Jev included, scored 0.43 to 0.52. On this measure, 0.5 is a coin flip. My watch history gave me a better predictor.

6/ How often I watched a channel scored 0.69 against those labels (95% interval: 0.59 to 0.80). Better than the models in my test, still imperfect. I wouldn't let that score alone choose my subscriptions either.

7/ In Tidy, I use Jev for judgments and code for thresholds, caps and budgets. I approve every change. No browser agent clicking around: one API call per change. So far, 11 unsubscribes, each signed off by me.

8/ Tidy found 30 channels in my watch history that I don't follow and proposed 13. I declined all of them. I watch those ad hoc, and that's fine.

9/ How I run it: about once a month, started by me. Sync subscriptions, collect evidence, Jev judges, I read the proposals and approve. It never runs on its own. Evidence expires after 30 days, which sets the rhythm. DM me for the repo and setup guide.

## Long post (X Premium)

Jev judged my 110 YouTube subscriptions in 9 seconds. Sonnet 5 took 3 minutes 8 seconds through its coding CLI. Neither predicted what I'd keep much better than a coin flip.

I tested 8 models: Jev, Opus 5, Sonnet 5, Haiku 4.5, Sol, Astra, Terra and Luna. Same four questions and prompts for each: relevance to me, substance, packaging risk and whether there was enough evidence to judge.

Jev's exact time was 9.1 seconds for all 110. Opus 5 also took 3 minutes 8 seconds; Sol took 3m 48s and Haiku 4.5 took 7m 19s. I timed the others through Claude Code or Codex, with 6 calls in flight. The 21 to 48 times speed gap includes CLI overhead. Pydantic, Vercel and another developer measured about 3 to 6 times against direct APIs, and frontier models still win some tasks.

At list API prices, my run came to $0.004 for Jev and $0.03 (Luna) to $1.11 (Astra) for the others. Fable 5.1 would be about $2 by my projection; I didn't run it.

On 30 channels over two runs, Jev's scores moved 3 to 4 times less than Sonnet 5's. That's one person's repeatability test. Steady scores could still miss what I wanted.

I checked every model against my keep or drop labels on 66 channels. All scored between 0.43 and 0.52, with 0.5 meaning a coin flip on this measure. My watch history scored 0.69 (95% interval: 0.59 to 0.80). It was a better predictor in this test, with plenty of uncertainty left.

That's why I keep approval in my hands. In Tidy, Jev supplies judgments and code applies thresholds, caps and budgets, with one API call per change and no browser agent clicking around. I approved each of the 11 unsubscribes so far.

Tidy also found 30 channels I watch but don't follow and proposed 13. I declined all of them. Watching a channel often still wasn't enough reason for me to subscribe.

I run it about once a month, started by me: sync subscriptions, collect evidence, let Jev judge, read the proposals and approve. It never runs on its own. YouTube's API terms require refreshing evidence within 30 days, which sets the rhythm.

DM me for the repo link and setup guide.
