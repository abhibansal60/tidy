# Agent-native integration research for Tidy

Fetched: 2026-09-20. Primary sources: the GitHub repo and API (via `gh`), the project README and docs. Secondary: search snippets. Items marked **UNCLEAR** could not be verified. This is a reading of public pages, not a code audit.

## Summary answers

1. **What it is.** [BuilderIO/agent-native](https://github.com/BuilderIO/agent-native) is a TypeScript framework for "agentic apps": you define an action once (`defineAction`, zod schema) and it is exposed as an agent tool, a React `useActionQuery` call, HTTP, MCP, A2A and CLI. State is SQL (PGlite locally, PostgreSQL in production) on any Nitro host. Requires Node >= 22.22 and pnpm; needs an LLM connection (Builder.io, Anthropic, OpenAI or Ollama) ([README](https://github.com/BuilderIO/agent-native/blob/main/README.md), [docs](https://agent-native.com/docs), fetched 2026-09-20).
2. **Maturity.** Created 2026-03-12, about 5,020 stars, 471 forks, 30 contributors, pushed 2026-09-20 (API), nightly releases daily, issue/PR numbers past 5,450. Very active, very young (6 months), fast-moving (the lock-step `@agent-native/skills@0.2.729` patch releases show constant churn). Vendor-backed by Builder.io.
3. **Creator and Jev.** The one inspectable Jev artifact is Steve Sewell's own merged PR [#5361 "feat(core): add optional Jev tool prefetch"](https://github.com/BuilderIO/agent-native/pull/5361) (2026-09-18, +1618 lines). It is real, tested code. It proves he uses Jev inside his product. It contains no measurement of usefulness (see below).
4. **The claim is only partly verifiable.** No blog post, thread or benchmark by Sewell about Jev was found. A search snippet attributes to his X account ([post 2101117066845831478](https://x.com/Steve8708/status/2101117066845831478)) the line that choosing from preset components based on dynamic data "is an excellent use case for jev and generative UI". I could not open it (login wall, 2 attempts). That is an opinion about a use case, not a measurement.
5. **Recommendation: skip integration; if a UI is wanted, prototype a local Python page.** Details below.

## 1. agent-native facts

| Fact | Value | Source |
|---|---|---|
| Language | TypeScript, React UI, Nitro server | README |
| Toolchain | Node >= 22.22, pnpm 10 | [docs](https://agent-native.com/docs), root `package.json` |
| License | README says MIT. GitHub API reports no license and there is no `LICENSE` file at repo root; root `package.json` says ISC. **UNCLEAR** | README, `gh api`, 2026-09-20 |
| Integration surfaces | HTTP, MCP, A2A, CLI from one action definition | README |
| Data | SQL: PGlite local dev, PostgreSQL production | README |
| Hosting | "any Nitro-compatible host"; Builder.io also sells hosting/gateway. Local run is supported | README, [docs](https://agent-native.com/docs) |
| Telemetry | Not stated in anything read. **UNCLEAR** (search for the word via the API failed) | |
| Repo layout | Monorepo: `packages/`, `templates/`, `mcp-registry`, `.claude`, `.codex`, `.gemini` | `gh api` contents |

How Tidy would plug in: not natively. Actions are TypeScript functions. Tidy is a Python CLI that prints JSON, so an action would `spawn("tidy", ["propose"])` and parse stdout, or read `.tidy/*.db` directly through a JS SQLite driver. The same secret store question follows: agent-native's own settings hold LLM keys (its PR adds a `JEV_API_KEY` tile), so Tidy's `TYPESAFE_API_KEY` and OAuth tokens would live in two places unless the app is pointed at Tidy's `.env`. The framework's centre of gravity is a chat agent that calls tools. Tidy's rule is that Jev judges and code acts. An LLM chat agent that can call `tidy approve`/`unsubscribe` adds a second decision-maker that ADR 0005 does not have.

## 2. What the creator claims about Jev

| Item | Finding |
|---|---|
| Code | PR #5361: optional Jev ranking of a tool catalog before the first agent request, active only when `JEV_API_KEY` is set. Falls back to the existing curated/tool-search path on missing key, error or timeout (750 ms). Catalog capped at 128, metadata only ("callers must not put private content here"). Model `jev-latest`. Source: [PR](https://github.com/BuilderIO/agent-native/pull/5361), file `packages/core/src/agent/jev-tool-prefetch.ts` |
| What was measured | Only unit tests (7/7 focused, 7/7 chat-context, 16 plugin catalogs clean). The PR body reports no accuracy, latency or cost figures and no comparison with the non-Jev path |
| Disconfirming | It is optional and defaults off. That reads as an experiment, not a claim of value. The repo README and the Builder.io blog post on generative UI ([published 2026-05-26](https://www.builder.io/blog/designing-generative-ui-in-an-agent-native-world), author Alice Moore) do not mention Jev |
| Affiliation | Sewell is founder/CEO of Builder.io and the maintainer of agent-native. No evidence found of a TypeSafe affiliation, sponsorship or investment. He is promoting a use case of Jev inside his own product, and the PR makes Jev a feature of that product. Conflict of interest cannot be excluded either way, so treat it as an adopter's opinion, not independent evidence |
| Other public evidence | Independent write-ups exist but are not from him: a [Retriever AI browser-agent benchmark](https://rtrvr.ai/blog/jev-browser-agent-benchmark) (not read in full), and a [Hacker News thread](https://news.ycombinator.com/item?id=49717558) where commenters dispute "can't hallucinate" (a valid but wrong value is possible), say the model needs careful schema design, and call the Doom demo easy because it uses structured game state. No Sewell comment appeared in the thread |

Verdict on the claim as posed ("its creator makes Jev genuinely useful where other demos are hype"): **not established.** The code is real and shows Jev used for one narrow job (ranking tools by description). No published measurement shows it beats the fallback. The hype comparison cannot be made from what is public. Tidy's own measurement (README, "What we measured") is stronger evidence for speed and cost, and weaker for quality: no model predicted which channels the owner keeps.

## 3. Options for a Tidy UI

Effort in days for one person, first usable version, review list plus label plus approve plus gate/run status.

| | A. agent-native app | B. Local web UI (Python stdlib `http.server`, ~200 lines, or one Flask file) | C. Static HTML from `tidy propose` |
|---|---|---|---|
| Effort | 5 to 10 (learn framework, TS actions wrapping the CLI, DB or subprocess bridge, LLM key setup, keep up with releases) | 1 to 2 | 0.5 to 1 |
| New dependencies | Node 22 + pnpm + hundreds of packages + an LLM provider; also PGlite/Postgres | None with stdlib; Flask optional | None |
| Install simplicity | Breaks "Python only" and `curl \| sh`. Two runtimes, two secret stores | Unchanged: ships in the wheel | Unchanged |
| Security surface | Web server, auth layer, agent with tool access, network calls to an LLM host; localhost possible but the framework is built for multi-user hosting | Bind 127.0.0.1 only, random token in the URL, POST-only for label/approve, no OAuth tokens shown | None (a file). Only risk is committing it: keep it under `.tidy/` |
| Fit with rules | Chat agent adds a second decider; defaults come from the framework, not Tidy's dry-run rule. Private data would flow to whatever LLM the agent uses unless carefully limited | Fits: calls the same `approve`/`label` code, dry-run stays the default, data stays local | Fits fully, read-only |
| User value | Nicest interaction (chat plus UI), most future scope, most risk | Covers the two real human tasks: label and approve with one click each, gate status visible | Covers reading proposals; labeling and approving still need the CLI |
| Reversible? | Costly to back out | Cheap | Trivial |

## UNCLEAR

- Whether Sewell has said anything about Jev beyond the X snippet. I could not open X (login wall, 2 attempts, stopped). Nothing was posted, liked or clicked.
- The license of agent-native (README MIT vs no `LICENSE` file vs `ISC` in `package.json`).
- Telemetry of agent-native and of its Builder.io gateway.
- Whether the PR's Jev path was ever measured privately. The PR body does not say.
- Whether the Retriever AI benchmark is independent of TypeSafe (not read).
- Whether a Python CLI can be registered as an agent-native MCP or action source without a TypeScript wrapper. The docs read do not describe it.

## Verdict and next step

**Skip agent-native for Tidy.** It would add a Node stack, a second secret store and a chat agent to a tool whose selling points are one Python install, a JSON CLI and owner-only approval. What it is good at (shared actions across UI and agent) is not Tidy's shape, and Sewell's Jev evidence does not change that: it is a small optional feature in his product, not a validated result about Tidy-like judgment tasks.

**Prototype option B, not A.** Smallest next step: first make `tidy propose --html` write a static page to `.tidy/proposals.html` (option C, under a day, no new files besides the renderer). If the owner finds himself still typing `tidy label` and `tidy approve`, add a 127.0.0.1-only `tidy ui` that serves that page with two POST endpoints wrapping the existing functions, run by the owner, dry run by default. Revisit agent-native only if Tidy grows a hosted, multi-user product, which ADR 0003 and the API policy research argue against.
