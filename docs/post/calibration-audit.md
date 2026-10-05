# Calibration audit posts (drafts, not posted)

For people who have never heard of Jev. Numbers come from `docs/research/jev-calibration-audit.md`. Speed and cost
multipliers are against Claude Haiku 4.5 as run here (through the Claude Code CLI, thinking on). Do not post without
the owner's explicit yes on the exact text.

## LinkedIn

An AI that tells you how sure it is. Is it right when it says it is sure?

Jev is a small AI from TypeSafe. You give it a message or a ticket, it picks a category and tells you how confident it is. Its makers say higher confidence means higher accuracy.

I checked that on 1,000 public examples where the right answer is already known: 500 bank customer messages and 500 GitHub issues.

Bank messages: Jev was right 80% of the time. So was Claude Haiku. Jev answered in under half a second, about 20 times faster than Haiku as I ran it, and cost about 4 cents per 1,000 messages. When Jev was very sure, it was right 95% of the time.

GitHub issues: Jev said it was 99% sure on almost two thirds of them. It was right on 81% of those. Very sure did not mean right.

The surprise: an old-school word-counting model, with no chat AI inside, did as well or better on both sets once it had seen public examples.

What I take from it: Jev is fast, cheap and gives the same answer twice. Its confidence is a useful hint on some tasks and not on others. Before you let it act on its own, test it on a few hundred of your own examples.

I wrote the pass or fail rule before running anything. Method, numbers and charts are in the repo. DM me for the link.

## X thread

1/ Jev, an AI from TypeSafe, tells you how sure it is about every answer. Its makers say: more sure means more right. I tested that on 1,000 public examples where the right answer is known. Short answer: sometimes.

2/ Test 1: 500 bank customer messages, 77 categories. Jev was right 80% of the time, same as Claude Haiku. It answered in under half a second, about 20x faster than Haiku as I ran it, at about 4 cents per 1,000 messages.

3/ When Jev was very sure about a bank message, it was right 95% of the time. So far the claim holds.

4/ Test 2: 500 GitHub issues. Bug, feature request or question? Jev said "99% sure" on almost two thirds of them. It was right on 81% of those.

5/ The surprise: an old-school word-counting model, no chat AI inside, trained on public examples, matched or beat Jev on both tests.

6/ My takeaway: Jev is fast, cheap and gives the same answer twice. Its confidence is a hint, not a promise. Test it on a few hundred of your own examples before you let it act alone.

7/ I wrote the pass or fail rule before running anything. Jev missed it on both tests, one by a hair. Method, numbers and charts in the repo. DM me for the link.
