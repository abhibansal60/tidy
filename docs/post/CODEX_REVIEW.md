# Codex task: review and tighten the launch posts (no posting)

Repo `/home/abhi/code/jev`. Review `docs/post/x-humanized.md` (X thread of 8 posts, plus a long version) and the LinkedIn text in `docs/post/draft.md`. Edit those two files only. Do not post anything, do not run evals, do not read `data/`, `.env`, `secrets/`, or `.tidy/token*`. Keep output short to save quota.

## Goal
Make both posts as likely to spread as an honest post can be, without a false or inflated claim. The story: 8 AI models judged 110 YouTube subscriptions; Jev was far faster and cheaper and steadier; none predicted what the owner keeps; the owner's watch history did better; Tidy lets Jev judge, code set limits, the owner approve.

## Check, in this order
1. **Facts.** Every number must match the table below. Fix or cut anything that does not. Never add a number.
2. **Honesty.** Keep the caveats: speed is measured through coding CLIs (public direct-API tests find 3 to 6 times); Fable 5.1 cost is a projection; repeatability is one person's test on 30 channels; watch history is a better predictor, not a perfect one. Do not let an edit turn any of these into a stronger claim.
3. **Hook.** Post 1 must make a stranger stop scrolling in the first line. Try two or three alternatives; pick the best; keep the contrast (9 seconds vs 3 minutes 8 seconds) and the surprise (none predicted the owner's choices).
4. **Thread shape.** Each post under 280 characters, one idea each, a reason to read the next one. The last post keeps "DM me for the repo link". LinkedIn: strong first two lines (before "see more"), short paragraphs, no bullets of bold labels, ends on a concrete point, keeps the DM line.
5. **Plain human voice.** No em or en dashes, no "not X but Y", no stock openers ("here's the thing", "let's dive in"), no rule-of-three padding, no hype words (game-changing, revolutionary, unlock), no emojis, no hashtags stack (at most two on LinkedIn). First person, specific, dry humor is fine.
6. **Privacy.** No channel names, IDs, handles of critics, or screenshots of the owner's data. Only the tool names, model names and the numbers below.

## Numbers you may use (verified; sources in `docs/post/draft.md` and `.tidy/` outputs)
- Task: 110 subscriptions, same four questions and prompts for every model. Models: Jev plus Opus 5, Sonnet 5, Haiku 4.5, Sol, Astra, Terra, Luna (Fable 5.1 projected only).
- Wall time for all 110 (CLIs for the others; 6 calls in flight): Jev 9.1 s; Sonnet 5 and Opus 5 3m 08s; Terra 3m 35s; Luna 3m 37s; Sol 3m 48s; Astra about 4m 07s (estimated from call times); Haiku 4.5 7m 19s. So 21 to 48 times faster than the CLIs.
- Cost at list API prices for the run: Jev $0.004; Luna $0.03; Terra $0.31; Sonnet 5 $0.32; Sol $0.44; Haiku 4.5 $0.99; Opus 5 $1.03; Astra $1.11; Fable 5.1 about $2 (projected). So 8 to 250 times cheaper.
- Repeatability (30 channels, two runs): Jev's scores moved 3 to 4 times less than Sonnet 5's.
- Match to the owner's own keep or drop labels (66 channels: 23 keep, 43 drop): every model, Jev included, scored 0.43 to 0.52 (0.5 is a coin flip). Watch history scored 0.69 (95% interval 0.59 to 0.80).
- Rank agreement with Opus 5: 0.88 to 0.97 on relevance, value, packaging risk.
- Tidy so far: 11 unsubscribes, each approved by the owner. Watch-history discovery found 30 channels, proposed 13, owner declined all.
- Outside tests (only if you cite them): direct-API tests by Pydantic (3.7x vs Sonnet), Vercel (6x vs Gemini Flash Lite) and another developer (3.2x to 5x) found Jev 3 to 6 times faster; Every measured about 25x faster against Fable 5.1 (a large baseline). Frontier models still win some tasks on TypeSafe's own chart. TypeSafe's own launch claims are higher and vendor-made.

## Report (under 15 lines)
The edits you made and why, the alternatives you rejected for post 1, and anything you could not verify. Leave the final wording in the two files.
