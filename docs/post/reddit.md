# Reddit post draft

Numbers match `docs/post/draft.md` and the eval outputs. Rewrite the first two paragraphs in your own voice before posting; a post that sounds like you survives moderators and readers better than any draft. Check the target subreddit's rules and flair first (I could not read Reddit's rules pages from here).

## r/LLMDevs (experiment angle)

Title: I tested Jev (TypeSafe's decision model) against 7 frontier models on a real task. Faster and far cheaper, but none of them predicted what I actually prefer

Body:

I wanted to see where a "decision model" like Jev fits next to frontier LLMs, so I used a task I had lying around: 110 YouTube subscriptions I hadn't pruned in years. Every model got the same evidence (the last 12 uploads per channel) and the same four narrow questions: relevance to my interests, apparent value, packaging risk (clickbait) and whether the evidence was enough to judge. Jev, Opus 5, Sonnet 5, Haiku 4.5, and Sol, Astra, Terra and Luna through Codex.

Speed and cost first. Jev did all 110 in 9.1 seconds. The others took 3 to 7 minutes, but that's through the Claude Code and Codex CLIs, which add overhead. Independent direct-API tests of Jev found 3 to 6 times faster, so read mine as an upper bound. At list API prices the run cost about $0.004 for Jev and $0.03 to $1.11 for the others. Its rank agreement with Opus 5 was 0.88 to 0.97 on relevance, value and packaging risk, and across two runs of 30 channels its scores moved 3 to 4 times less than Sonnet 5's.

Then the part I care about. I labeled 66 channels keep or drop myself. Against those labels every model, Jev included, scored 0.43 to 0.52 (AUC, so 0.5 is a coin flip). Counting how often I'd watched a channel in the last six weeks from my Google Takeout export scored 0.69, with an interval of 0.59 to 0.80. The models agree with each other and still don't know what I keep. When I relabeled 16 channels blind, I disagreed with my earlier self on 3 of the 13 where I'd picked keep or drop both times, so my own ground truth is noisy.

Caveats: one person, 66 labels, title-level evidence only, and I didn't run Fable 5.1 (its cost in my notes is a projection).

What I built from it is deliberately boring: the model scores, plain code applies thresholds and caps, and I approve every change through the YouTube API, no browser agent. It's Python and SQLite, MIT, and I built it mostly with Claude Code and Codex. Repo, eval scripts and raw method: https://github.com/abhibansal60/tidy

Question for people who evaluate models on personal or subjective tasks: how do you get a ground truth you trust when your own labels are this noisy? And has anyone measured run-to-run repeatability on hosted models properly? I only did 30 channels twice.

## r/SideProject (tool angle)

Title: I built a tool that prunes my YouTube subscriptions: a model scores each channel, code sets the limits, and I approve every change

Body:

I follow 110 YouTube channels and hadn't cleaned the list in years. Going through them by hand felt like a chore, but letting an AI loose on my account felt wrong, so I built something in between.

Tidy pulls the latest uploads from each channel and has Jev (TypeSafe's decision model) score them, all 110 in about 9 seconds for less than a cent. Plain code turns the scores into proposals: keep, review, unsubscribe. It also reads my Google Takeout watch history, so it can suggest channels I watch a lot but don't follow. Nothing changes until I approve it, unsubscribes go through the official YouTube API, and there's a per-run cap.

What surprised me: none of the models I tested, Jev included, could predict which channels I'd keep. Counting how often I'd actually watched a channel did better. I declined all 13 of the channels it suggested I add, because I like watching those ad hoc. So it has unsubscribed 11 channels so far and added none.

It generates a single HTML page to review everything (a map of the feed plus one row per channel). Python 3.14 and SQLite, MIT licensed, one curl line to install. Setup is the honest weak spot: you need your own Google Cloud OAuth client and a TypeSafe key, and there's a prompt in the README you can paste into Claude Code or Codex to walk through it. I built it mostly with Claude Code and Codex.

https://github.com/abhibansal60/tidy

Would you use something like this, and would the setup put you off? I'd like to know where it loses people.

## Media

Safe to attach (no real channel names, aggregate numbers only): `docs/assets/review_page.png` (synthetic data) and the demo video `docs/assets/tidy_demo.mp4` (70 seconds, opens on the thumbnail). Never attach screenshots of your real `.tidy/proposals.html`.

## Where and how

- Start with one subreddit that allows project posts and read its rules first. Do not post the same text in several subreddits on the same day; wait a day and change the angle.
- Put the repo link once, in the body (or the first comment if the subreddit only allows an image or video post). No URL shorteners, no links to your X or LinkedIn posts.
- Stay in the thread for the first two hours and answer in your own words.
