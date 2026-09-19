# First-hand X posts: Jev against frontier models

Collected 2026-09-19 from x.com search (logged-in, read-only) plus the linked posts. Public posts only. Quotes are short paraphrases; numbers are as the author stated them. This complements `x-jev-comparisons.md`, which had no first-hand X access.

## Posts with numbers

| Author (public handle) | Date | Claim | Baseline | Independent? |
|---|---|---|---|---|
| @typesafeai (vendor), quoting @cramforce (Vercel) | Sep 16 | Jev "won on quality (saturated the eval) and speed (6x)" on an existing classifier eval | Gemini 2.5 Flash Lite | Customer quote, amplified by the vendor |
| @samuelcolvin (Pydantic) | Sep 18 | Sonnet $0.0026 vs Jev $0.001 per call; 2.36 s vs 643 ms; 17-line gist | Sonnet | Independent, one call type |
| @copilot_shogo | Sep 18 | 60 customer messages. 3.2x faster and 3.8x cheaper than GPT-4o-mini; 5.0x faster and 106x cheaper than Sonnet 4.5. "Reproduced neither" of the published 193.6x and 444.6x. Jev's >0.95 answers were right 157 of 157 times, but 49 of the 157 needed a human, and for 18 of those Jev had also said no human was needed | GPT-4o-mini, Sonnet 4.5 | Independent |
| @aimlapi | Sep 17 | Chess blitz, one API call per move. Fable 5.1 outplayed Jev (+16 material, second queen) but burned 6-15 s per move against Jev's ~2.6 s and lost on the clock. Astra mated Jev in 18 moves with 2:27 left | Fable 5.1, GPT-6 Astra | Independent (an API reseller) |
| @MarianPogran | Sep 19 | Real pick-and-place robot task: Jev 27 s vs Astra 1 m 11 s, Jev "much cheaper"; robot capped at 10% speed | GPT-6 Astra | Independent, one task |
| @brian_lovin | Sep 19 | "Jev vs Haiku for auto-tagging links. It's beautiful" (no numbers) | Haiku | Independent |
| @HiromTeachesAI | Sep 16 | "A classifier with a marketing budget. Not a Claude/GPT competitor" | none | Critic, no data |
| @Adukeomololu, @AbhiAbhyyy559 and others | Sep 16-17 | Repeat the launch figures (20-200x faster, 40-400x cheaper; "~190x faster than Sonnet") | vendor's | Relays, no tests |

## What they add to our results

- **Nobody reproduced the headline.** The launch multipliers (193.6x faster, 444.6x cheaper) come from the vendor. Every independent test that names a like-for-like API baseline lands far lower on speed: 6x (Vercel, Gemini Flash Lite), 3.7x (Colvin, Sonnet), 5x (shogo, Sonnet 4.5), 3.2x (shogo, GPT-4o-mini). Cost gaps are big but vary: 2.6x (Colvin) to 106x (shogo).
- **Our 21x to 49x speed gap is against coding-tool CLIs** (`claude -p`, `codex exec`), which add process start and tool overhead per call. Direct API baselines in public tests suggest 3x to 6x. Our post must say what the baseline is, or it repeats the mistake shogo called out ("a multiplier isn't a claim until you name the baseline").
- **Our list-price cost gap (74x to 470x)** sits inside the public range (2.6x to 106x for cheap baselines, larger for frontier ones), but Opus and Fable are the most expensive baselines anyone tested.
- **Accuracy: parity on narrow decisions, frontier models win on open tasks.** Chess is the extreme case, and it also shows the trade Jev makes: Fable played better and lost on time; Astra played better and won. That matches our finding that quality scores are close to frontier models on rank order but say nothing about one person's taste.
- **Calibration got its first independent number.** Above 0.95 confidence Jev was right 157 of 157 times, yet 18 confident answers still missed a human-review need. The lesson matches our "confidence is distribution concentration, not permission to act" rule.

## UNCLEAR

- Whether the AIML API chess run used identical settings for each model, and the game count (one game per matchup was reported).
- Whether shogo's dataset and prompts are public; the thread was truncated in the page text I could read.
- Several posts (Roxx, niyoverse, Sebi and others) are long articles behind links that I did not open.

## Verdict

Partly consistent with our results. Directionally the same everywhere: Jev is much faster and much cheaper, close to frontier models on narrow decisions, and weaker on open-ended tasks. The size of the speed gap is the one place where we would overstate: independent like-for-like tests find 3x to 6x, not 20x to 190x. Report our 21x to 49x as "against coding-tool CLIs", and add a direct-API speed row before claiming more. Repeatability and the weak match to one owner's own labels remain unreplicated by anyone.
