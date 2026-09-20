# Reddit post draft

Numbers match `docs/post/draft.md` and the eval outputs. Rewrite the first two paragraphs in your own voice before posting; a post that sounds like you survives moderators and readers better than any draft. Check the target subreddit's rules and flair first (I could not read Reddit's rules pages from here).

## Title

I had 8 models judge my 110 YouTube subscriptions. None of them could predict what I'd actually keep

## Body

I follow 110 YouTube channels and hadn't pruned the list in years, so I turned it into a test. I gave the same evidence (the last 12 uploads per channel) and the same four questions to Jev, TypeSafe's decision model, and to seven frontier models: Opus 5, Sonnet 5, Haiku 4.5, and the GPT-5.6 and GPT-6 models through Codex.

Speed and cost came out the way you'd expect. Jev did all 110 in 9 seconds. The others took 3 to 7 minutes, but that's through the Claude Code and Codex CLIs, which add overhead, and people who tested Jev on direct APIs measured 3 to 6 times faster, so treat my number as an upper bound. At list prices the run cost about $0.004 for Jev and between $0.03 and $1.11 for the others.

What I didn't expect: I labeled 66 of the channels keep or drop myself, and every model, Jev included, scored between 0.43 and 0.52 against those labels. 0.5 is a coin flip. What predicted my choices better was just counting how often I'd watched a channel in the last six weeks, from my Google Takeout export. That scored 0.69. The models judge whether a channel is good. I keep things out of habit. When I relabeled 16 of them blind, from memory, I disagreed with my earlier self on 3 of the 13 where I'd picked keep or drop both times, so my own labels are noisy too.

So the tool I ended up with is boring on purpose. The model scores, plain code applies thresholds and caps, and I approve every unsubscribe. No browser agent, one API call per change. It has unsubscribed 11 channels so far. It also found 30 channels I watch a lot but don't follow and proposed adding 13. I turned down all of them, because I like watching those ad hoc.

It's Python and SQLite, MIT licensed, with a one-line install and a prompt in the README you can paste into Claude Code or Codex to set it up. I built it mostly with Claude Code and Codex, which I mention because people will ask.

Repo: https://github.com/abhibansal60/tidy

Two things I'm unsure about. Is 66 labels enough to say anything? The interval on the watch-history number is 0.59 to 0.80. And how do you decide when a channel has earned its place in your feed?

## Media

Safe to attach (no real channel names, aggregate numbers only): `docs/assets/review_page.png` (synthetic data) and the demo video `docs/assets/tidy_demo.mp4` (70 seconds, opens on the thumbnail). Never attach screenshots of your real `.tidy/proposals.html`.

## Where and how

- Start with one subreddit that allows project posts and read its rules first. Do not post the same text in several subreddits on the same day; wait a day and change the angle.
- Put the repo link once, in the body (or the first comment if the subreddit only allows an image or video post). No URL shorteners, no links to your X or LinkedIn posts.
- Stay in the thread for the first two hours and answer in your own words.
