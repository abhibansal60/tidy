# Shot list: "Is it right when it says it is sure?" (35 s, 120 BPM, beat 0.5 s)

Every number comes from `data.js`, exported from the audit runs (docs/research/jev-calibration-audit.md).
Examples are real items: a Banking77 test message and an NLBSE'24 issue title (public data).

| Time | Shot | On screen | SFX |
| --- | --- | --- | --- |
| 0.0-3.0 | Hook | Ring meter counts 0 to 99%. "This AI says it is ... sure." swaps to "Is it right?" with a red underline | whoosh, ticks, thump on 2.0 |
| 3.0-6.0 | Setup | 1,000 dots wave in, counter to 1,000. "real examples, right answers known". Halves: 500 bank chats, 500 GitHub issues | pops |
| 6.0-10.0 | Test 1 example | Chat bubble types "Why did it decline my payment?"; Jev card: declined_card_payment, 100% sure; check: Right | typing clicks, pop |
| 10.0-13.5 | Accuracy | 80% right. Bars: Jev 79.6%, Claude Haiku 79.7%. "Same as Claude Haiku." | clicks |
| 13.5-18.0 | Speed | Race lanes: Jev 0.37 s, Haiku 4.5 7.4 s. "About 20x faster." "4 cents vs $4.79 per 1,000 messages" + footnote naming the baseline | whoosh, pop |
| 18.0-21.5 | Trust holds | Waffle 100: 95 mint, 5 red. "When Jev said 99% or more on bank messages: 95 of 100 right." | pops |
| 21.5-24.5 | Twist | Hard cut, music drops. "Test 2: GitHub issues." Issue card (facebook/react). Jev: feature request, 100% sure. Stamp: maintainers labeled it a question | thump, stamp |
| 24.5-28.0 | Trust breaks | Waffle 100: 81 mint, 19 red. "81 of 100 right." "It said 99%+ on 63% of issues." | pops |
| 28.0-31.0 | Surprise | "A simple word-counting model. No chat AI inside." Bars: bank 79.6 vs 85.2, issues 73.8 vs 73.0 | clicks |
| 31.0-35.0 | Takeaway | "Fast, cheap, steady." "Its confidence is a hint." "Test it on your own examples first." Tidy mascot + source line | thump |
