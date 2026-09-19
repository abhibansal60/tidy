# Is Claude Fable 5.1 more token-efficient than Opus 5? Measured evidence

Fetched: 2026-09-19. Primary = Anthropic pages or the measuring party's own page. Secondary = a third party repeating someone else's number. Several pages were read through an automated summarizer, so figures marked (summarized) should be re-checked against the page before they are quoted publicly. This is a reading of the published evidence, not a benchmark we ran. Items marked **UNCLEAR** conflict or could not be found.

## Summary answers

1. **List price:** Fable 5.1 costs exactly 2x Opus 5 per token, input and output ($10/$50 vs $5/$25). Fable 5.1 cache reads are $0.25 vs Opus 5 $0.50, so 0.5x on cached input.
2. **Output tokens per task:** the evidence conflicts. Independent, broad measurement (Artificial Analysis, whole index) says Fable 5.1 emits MORE tokens than Opus 5. Narrow measurements on tasks both models solve (Snorkel, Devin) say Fable emits fewer.
3. **Cost per task:** the broadest independent number says Fable 5.1 is more expensive: $3.76 vs $2.34 (1.6x) at max effort. Devin, a vendor with a commercial interest, reports Fable 5.1 24% cheaper at medium effort on its coding benchmark.
4. **Speed:** Artificial Analysis shows Fable 5.1 at higher tokens/s than Opus 5 (68.8 vs 51.3), but Firecrawl measured it slower in wall-clock at some effort levels. Mixed.
5. **Tokenizer:** no documented difference between Fable 5.1 and Opus 5. Not measured.
6. **Break-even:** with equal input tokens, Fable must emit about 50% fewer output tokens than Opus, and slightly more than that when input is not negligible (section 7).

## 1. List price per MTok (a)

Source: [Anthropic pricing page](https://platform.claude.com/docs/en/about-claude/pricing), fetched 2026-09-19. Primary.

| Model | Input | Output | Cache read | Batch in/out |
|---|---|---|---|---|
| Fable 5.1 | $10 | $50 | $0.25 (0.025x) | $5 / $25 |
| Fable 5 | $10 | $50 | $1 (0.1x) | $5 / $25 |
| Opus 5 | $5 | $25 | $0.50 (0.1x) | $2.50 / $12.50 |
| Sonnet 5 | $2 | $10 | $0.20 | $1 / $5 |

- Sonnet 5's $2/$10 was introductory; the page says it is now the standard price and the planned $3/$15 rise "will not occur". Some secondary pages still say $15.
- The announcement ([Anthropic, Sept 2026](https://www.anthropic.com/claude-fable-and-mythos-5-1)) says "for typical workloads, costs are reduced by around 25% relative to Fable 5" and "up to around 45%" for complex coding and agentic tasks. That compares Fable 5.1 to Fable 5, not to Opus 5. Primary, vendor claim.

## 2. Output tokens generated (b)

| Value | Unit | Model | Measure | Source | Date | Kind |
|---|---|---|---|---|---|---|
| 143.7M (13.1M at low) | output tokens for the full index | Fable 5.1 | Artificial Analysis Intelligence Index, max effort (low to max is 11x) | [AA article](https://artificialanalysis.ai/articles/claude-fable-5-1) (summarized) | 2026-09-01 | Primary (AA), independent |
| ~1.7x Fable 5 | ratio | Fable 5.1 vs Fable 5 | same index | [OfficeChai](https://officechai.com/ai/claude-fable-5-1-by-far-most-expensive-model-on-artificial-analysis-intelligence-index-costs-57-more-than-opus-5/) quoting AA | 2026-09-02 | Secondary |
| 190M | output tokens | Fable 5.1 (max with fallback) | AA model page | [AA model page](https://artificialanalysis.ai/models/claude-fable-5-1) | fetched 09-19 | Primary |
| 140M | output tokens | Opus 5 (max, adaptive) | AA model page | [AA Opus 5](https://artificialanalysis.ai/models/claude-opus-5) | fetched 09-19 | Primary |
| 130M | output tokens | Fable 5 (max, Opus 4.8 fallback) | AA model page | [AA Fable 5](https://artificialanalysis.ai/models/claude-fable-5) | fetched 09-19 | Primary |
| 370M | output tokens | Sonnet 5 (max) | AA model page | [AA Sonnet 5](https://artificialanalysis.ai/models/claude-sonnet-5) | fetched 09-19 | Primary |
| 58% fewer, 36% faster | ratio, on tasks both solved | Fable 5.1 vs Opus 5 | Snorkel Terminal-Bench+, 27 matched tasks | [Snorkel](https://snorkel.ai/blog/fable-5-1-vs-opus-5-coding-benchmark/) (summarized) | Sept 2026 | Primary (Snorkel), independent, small n |
| ~21K vs ~26K output per task (about 19% fewer); "33% fewer tokens" overall | tokens per task | Fable 5.1 vs Opus 5 | Devin FrontierCode 1.1 Extended, medium thinking | [Devin blog](https://devin.ai/blog/fable-5-1) (summarized) | Sept 2026 (page said "2024", evidently a typo) | Primary, vendor with interest |
| 1.37x low, 1.12x high, 1.30x max more billed tokens | ratio | Fable 5.1 vs Fable 5 | 3 prompts, 57 runs, `claude -p` | [Firecrawl](https://www.firecrawl.dev/blog/is-fable-5-1-cheaper-than-fable-5) (summarized) | 2026-09-07 | Primary (Firecrawl), independent, small n |

Reading:
- Whole-index breadth (AA) points against Fable: 190M vs 140M is 1.36x more tokens than Opus 5 on the model pages. The article figure 143.7M for Fable 5.1 max is not the same as the 190M on the model page; see UNCLEAR.
- Task-level measurements (Snorkel, Devin) point toward Fable using fewer tokens, but only on tasks both models solved (survivorship). Snorkel: Opus solved 5 tasks Fable did not; Fable solved 2 that Opus did not. Fable failures are missing from the token average.
- Fable 5.1 emits more tokens than Fable 5 in two independent sources (AA 1.7x, Firecrawl 1.12x to 1.37x). So the Fable 5.1 vs Fable 5 direction is also not "more efficient" in tokens.
- Sonnet 5 is the most verbose in the index (370M) despite the cheapest rate.

## 3. Cost per task or to run a benchmark (c)

| Value | Model | Measure | Source | Kind |
|---|---|---|---|---|
| $3.76 per task | Fable 5.1 max | AA index | [AA article](https://artificialanalysis.ai/articles/claude-fable-5-1) (2026-09-01) | Primary, independent |
| $3.69 per task, "57% pricier than Opus 5" | Fable 5.1 max | AA index | [OfficeChai](https://officechai.com/ai/claude-fable-5-1-by-far-most-expensive-model-on-artificial-analysis-intelligence-index-costs-57-more-than-opus-5/) (2026-09-02) | Secondary; differs from AA's $3.76 (likely before/after cache repricing) |
| $2.34 per task | Opus 5 max | AA index | same AA article | Primary |
| $3.14 per task | Fable 5 max | AA index | same | Primary |
| $2.72 per task, score 65 | Fable 5.1 xhigh | AA index | same | Primary |
| $2.29 per task | Sonnet 5 | AA index | [AA on X](https://x.com/ArtificialAnlys/status/2072062595482456431) (search snippet) | Primary, snippet only |
| $13,128.86 total | Fable 5.1 | AA index run | AA model page | Primary |
| $7,274.74 total | Opus 5 | AA index run | AA model page | Primary |
| $11,160.86 total | Fable 5 | AA index run | AA model page | Primary |
| $6,998.25 total | Sonnet 5 | AA index run | AA model page | Primary |
| $2.68 vs $3.51 per task (Fable 24% cheaper) | Fable 5.1 vs Opus 5 | Devin FrontierCode, medium | [Devin](https://devin.ai/blog/fable-5-1) | Primary, vendor with interest |
| $7.00 vs $6.88 per agentic build | Fable 5.1 vs Fable 5 | 6 sandboxed builds | [Firecrawl](https://www.firecrawl.dev/blog/is-fable-5-1-cheaper-than-fable-5) | Primary, independent, n=6 |

- AA says the cache read cut ($1 to $0.25) saved about $1.40 per task; without it Fable 5.1 would be about $5.16.
- Firecrawl found the cache discount was worth 15% to 30% of the bill, not the 25% to 45% Anthropic advertised.
- Score-per-dollar: Fable 5.1 scores 66 vs Opus 5's 63 (about 5% higher) for 1.6x the cost. At xhigh, 65 for $2.72 (1.16x Opus cost, 3% higher score).

## 4. Speed (d)

- Output speed, AA model pages (max effort): Fable 5.1 68.8 tok/s; Opus 5 51.3; Fable 5 57.4; Sonnet 5 about 74 (AA via search snippet). Primary.
- TTFT on the same pages: Fable 5.1 252s, Opus 5 68s, Fable 5 108s. These are index-run reasoning latencies at max effort, not interactive latency.
- Snorkel: Fable 5.1 finished 36% faster on matched solved tasks. Firecrawl: Fable 5.1 was "1.36x longer at low, 1.04x at high, 1.61x longer at max" (the page summary compares to Opus 5 in one place and to Fable 5 in another).
- Net: higher raw tok/s, but more total time at max effort in at least one measurement. **UNCLEAR.**

## 5. Tokenizer (e)

The pricing page states Claude 4.7 and later models use a newer tokenizer producing "approximately 30% more tokens for the same text", varying by content. Both Fable 5.1 and Opus 5 are later than 4.7. No Anthropic page found says whether they share a tokenizer, and no measurement of tokens-per-text between them was found. Assume the same until shown otherwise.

## 6. Cache-read pricing (f)

Fable 5.1 cache hits are 0.025x base ($0.25/MTok); Opus 5 is 0.1x of $5 ($0.50/MTok). Cache writes are proportional to base (1.25x, 2x), so writes cost 2x Opus. For a loop that re-reads a large stable context many times, Fable's effective input cost is half of Opus's. See workload C below.

## 7. Arithmetic

Notation: I = input tokens, O_o = Opus output tokens, O_f = Fable output tokens. Prices per token: Opus in 5e-6, out 25e-6; Fable in 10e-6, out 50e-6.

Break-even (uncached, same I):
10 I + 50 O_f = 5 I + 25 O_o, so O_f = 0.5 O_o - 0.1 I.
Pure output break-even (I negligible): Fable must emit 50% fewer output tokens. Each input token costs Fable 5e-6 extra, which must be paid back by cutting 0.1 output tokens.

**A. Short classification (I = 800, O_o = 50 JSON tokens).**
- Opus: 800 x 5e-6 + 50 x 25e-6 = $0.00400 + $0.00125 = $0.00525.
- Fable at equal output: $0.00800 + $0.00250 = $0.01050 (2.0x).
- Break-even: O_f = 25 - 80 = -55. Impossible; Fable's input cost alone ($0.008) exceeds Opus's total. Input-dominated tasks cannot favor Fable regardless of verbosity (uncached).

**B. Medium reasoning (I = 2,000, O_o = 8,000).**
- Opus: $0.010 + $0.200 = $0.210. Fable at equal output: $0.020 + $0.400 = $0.420.
- Break-even: O_f = 4,000 - 200 = 3,800, i.e. 52.5% fewer.
- At Snorkel ratio (0.42x, O_f = 3,360): $0.020 + $0.168 = $0.188, 0.90x Opus.
- At Devin's output ratio (21/26 = 0.81, O_f = 6,460): $0.020 + $0.323 = $0.343, 1.63x Opus.
- At AA index ratio (190/140 = 1.36, O_f = 10,880): $0.020 + $0.544 = $0.564, 2.69x Opus.

**C. Long agentic (Devin figures per task: Opus 4.5M cache reads, 85K uncached, 26K out; Fable 3M, 70K, 21K).**
- Opus: 4.5 x $0.50 + 0.085 x $5 + 0.026 x $25 = $2.25 + $0.425 + $0.65 = $3.325 (Devin reports $3.51; close, unexplained gap).
- Fable: 3 x $0.25 + 0.07 x $10 + 0.021 x $50 = $0.75 + $0.70 + $1.05 = $2.50 (Devin $2.68). About 25% cheaper, matching Devin's 24%.
- Sensitivity: if Fable had the same 4.5M cache reads and 85K uncached as Opus, its non-output cost is $1.125 + $0.85 = $1.975, so break-even O_f = (3.325 - 1.975)/50e-6 = 27K, about 4% more than Opus's 26K. In cache-heavy loops Fable breaks even at roughly equal output tokens, because cache reads are half price. The gain comes from the cache discount plus Devin's claim that Fable needs fewer turns (3M vs 4.5M reads), not from cheaper output.
- If the AA ratio (1.36x output) held: O_f = 35.4K gives $1.975 + $1.77 = $3.75, 1.13x Opus.

Best-supported output ratio: there is none that is both broad and independent. Independent breadth says about 1.0x to 1.36x (Fable more tokens); independent narrow says 0.42x (Snorkel, survivorship-biased); vendor says 0.81x. Only Snorkel's 0.42x clears the 0.5 output break-even, and Fable wins only if it also matches the cached-input profile.

## UNCLEAR

- AA's article says Fable 5.1 max used 143.7M tokens at $3.76/task; the model page says 190M tokens and $13,129 for "max with fallback". The Opus 5 page shows an index score of 51 versus 63 in the article, so the model pages appear to use a different index version or are stale. Token ratio against Opus 5 in the same run as the article was not retrieved (the article gives cost/task, 1.6x, not Opus tokens).
- Whether Fable 5.1's "adaptive, always-on thinking" (Emergent, secondary) versus Opus 5's effort-controlled thinking makes "max" comparable across the two. Effort names may not equate work done.
- Firecrawl latency comparison target (Opus 5 or Fable 5).
- Devin page date reads 2024; treated as Sept 2026. Devin's gap between computed $3.325 and reported $3.51 for Opus is unexplained.
- Snorkel's absolute token counts and per-task costs were not on the page; only ratios.
- Tokenizer parity between Fable 5.1 and Opus 5.
- Anthropic's own measurements of Fable 5.1 vs Opus 5 tokens per task: none found; the announcement cites Square's "far more efficient per token than Opus 5" with no number.
- No LMArena-style efficiency data was found.
- Figures marked (summarized) were extracted by a summarizer, not read from raw HTML.

## Conclusion

Inconclusive, leaning against "Fable is more efficient" in cost terms. Fable 5.1 costs 2x per token and must emit half the output to break even. The only broad independent measurement (Artificial Analysis) has it emitting more tokens and costing about 1.6x per task ($3.76 vs $2.34) at max effort. Evidence for the requester's belief is narrower: on tasks both models solved, Snorkel saw 58% fewer output tokens and 36% less time, and Devin (a vendor with a stake) saw 24% lower cost at medium effort, driven largely by the 0.025x cache price. Fable can be cheaper in cache-heavy agentic loops at moderate effort; it is not cheaper for input-heavy, short-output work at any verbosity, and a broad reading at max effort favors Opus 5. The claim "fewer tokens when it succeeds" has support; "cheaper per task in general" does not. Cost per task depends on effort level, cache hit rate, and task mix, so measure on the actual workload.
