# Tidy

**Clean up your Gmail inbox and your YouTube subscriptions with AI, without letting AI loose on your account.**

[Jev](https://docs.typesafe.ai) reads each email or channel and gives a typed verdict in well under a second. Plain,
tested code decides what that verdict is allowed to do, and nothing risky happens until you say so.

[![CI](https://github.com/abhibansal60/tidy/actions/workflows/ci.yml/badge.svg)](https://github.com/abhibansal60/tidy/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tidy-ai)](https://pypi.org/project/tidy-ai/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://pypi.org/project/tidy-ai/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/abhibansal60/tidy/blob/main/LICENSE)

<img src="https://raw.githubusercontent.com/abhibansal60/tidy/main/docs/assets/mail_thumbnail.png" alt="Before: 12,158 unread emails. After: sorted, for 45 cents" width="640">

| | Gmail | YouTube |
|---|---|---|
| **Sorts** | every email into Needs Reply, Updates, Promos, Sales or Spam | every channel by relevance, value and how likely you are to watch it |
| **Does on its own** | archives bulk mail, only when a second signal agrees | nothing: every change waits for you |
| **Waits for you** | Trash and Spam, reviewed from a dashboard | unsubscribes and new subscriptions |
| **Never does** | permanently delete anything, touch starred mail, click unsubscribe links | use browser automation or scrape |
| **Measured cost** | $0.43 to sort 12,158 unread emails | a fraction of a cent for 110 channels |

[Mail demo video (MP4)](https://github.com/abhibansal60/tidy/raw/main/docs/assets/tidy_mail_demo.mp4) ·
[YouTube demo video (MP4)](https://github.com/abhibansal60/tidy/raw/main/docs/assets/tidy_demo.mp4) ·
[Cost write-up](https://github.com/abhibansal60/tidy/blob/main/docs/research/opus-5-5-plus-jev-cost.md)

## Install

```bash
pipx install tidy-ai          # or: uv tool install tidy-ai    (or: pip install tidy-ai)
tidy --version
```

Python 3.11 or newer. The command is `tidy`; `tidy-ai` is the same command, in case another `tidy` (HTML Tidy, which
macOS ships) comes first on your PATH. Until the first PyPI release: `pipx install git+https://github.com/abhibansal60/tidy`.

## Set up once (about 10 minutes)

You need two things that only you can create:

1. **A Google OAuth client.** In [Google Cloud Console](https://console.cloud.google.com/): create a project, enable the
   **Gmail API** (and/or **YouTube Data API v3**), set up the OAuth consent screen in Testing mode with yourself as a
   test user, then create an OAuth client of type **Desktop app** and download its JSON.
   Step-by-step: [docs/agent-setup.md](https://github.com/abhibansal60/tidy/blob/main/docs/agent-setup.md#steps).
2. **A TypeSafe API key** for Jev, from [console.typesafe.ai](https://console.typesafe.ai).

Then:

```bash
tidy init --email you@gmail.com --client-secrets ~/Downloads/client_secret_XXXX.json --key-stdin
# paste the TypeSafe key when asked (it is hidden and stored 0600 in ~/.tidy/.env)
tidy doctor                   # checks everything, prints the next command, never prints a secret
```

## Clean up Gmail

```bash
tidy mail-auth                                         # read-only sign-in (a browser opens)
tidy mail-triage --execute --limit 200 --html inbox.html --json run.json
```

Open `inbox.html`: every email with its category, why, and what Tidy proposes, plus an **unsubscribe shortlist**
grouped by sender (links you click yourself). Nothing in Gmail changed yet. When you like what you see:

```bash
tidy mail-auth --write                                 # a second, separate token that can change labels
tidy mail-triage --execute --apply --override-gate --limit 200 --json run.json   # auto-archives bulk mail only
tidy mail-act --run run.json                           # preview the Trash/Spam proposals
tidy mail-act --run run.json --execute                 # apply them (Trash is recoverable for 30 days)
```

`--override-gate` is needed because Tidy cannot yet prove from your own labels that its archiving matches your taste
([why](https://github.com/abhibansal60/tidy/blob/main/docs/adr/0005-gated-owner-started-autonomy.md)). Keep it daily with cron:

```cron
# use the full path from `command -v tidy`; cron has a minimal PATH
0 8 * * * /home/you/.local/bin/tidy mail-triage --execute --apply --override-gate --query "in:inbox newer_than:2d" --json ~/.tidy/runs/$(date +\%F).json
```

## Clean up YouTube

```bash
tidy auth                                             # read-only sign-in
tidy sync                                             # fetch your subscriptions
tidy collect --all --max-units 400 --execute          # recent uploads per channel (YouTube quota: about 300 units)
tidy judge --schemas titles-desc-v1 --execute         # Jev judges every channel
tidy propose --html review.html                       # open it: proposals with reasons and the commands to act
```

<img src="https://raw.githubusercontent.com/abhibansal60/tidy/main/docs/assets/review_page.png" alt="Review page, synthetic data" width="640">

To act: `tidy auth --write`, `tidy approve CHANNEL_ID... --note "why"`, `tidy unsubscribe` (dry run), then
`tidy unsubscribe --execute`. A Google Takeout watch history makes proposals much better: see
[docs/reference.md](https://github.com/abhibansal60/tidy/blob/main/docs/reference.md).

## Let an agent set it up

Paste into Claude Code, Codex or any coding agent:

```text
Set up Tidy (pipx package tidy-ai) for me. Follow https://github.com/abhibansal60/tidy/blob/main/docs/agent-setup.md
exactly. Stop and ask me whenever a step needs my Google account, an API key or a browser. Never print my secrets,
and never run a command with --execute until I say so.
```

Built for agents: every command prints JSON, `tidy doctor` says exactly what is missing and what to run next,
every change is a dry run until `--execute`, and secrets go in through a hidden prompt or stdin, never as arguments.

## Safety

- **Dry run by default.** Nothing changes your account without `--execute`.
- **Two tokens.** Reading and changing use separate OAuth tokens; the change token is only requested when you ask.
- **Gmail cannot be permanently deleted by Tidy.** It never requests the full-access Gmail scope, only `gmail.modify`,
  which can archive, trash and mark spam but cannot erase mail. Trash empties itself after 30 days, as Gmail always does.
- **AI is never enough on its own.** Auto-archive needs a second, code-owned signal (an unsubscribe header, not being
  addressed to you personally, or Gmail's own Updates/Promotions tab). Starred mail is never proposed for anything.
- **Rechecked live.** Before any Trash, Spam or unsubscribe, Tidy re-reads the live account and skips anything you have
  moved, starred or changed since.
- **Capped and budgeted.** Per-run caps, API call budgets checked before the first change, and an audit log.
- **Private files stay private.** Tokens, config, database, dashboards and run files are written owner-only (0600)
  in `~/.tidy`; `tidy doctor` warns about anything readable by others.

Found a problem? See [SECURITY.md](https://github.com/abhibansal60/tidy/blob/main/SECURITY.md).

## What leaves your machine

| Sent to | What | When |
|---|---|---|
| Google | the API calls you run | always, over HTTPS |
| TypeSafe (Jev) | per email: subject, sender, first 1,000 characters of text, two yes/no facts; per channel: its name and description, recent video titles, descriptions and lengths, and the interests (and optional viewing habits) you set in your profile | `mail-triage --execute`, `judge --execute` |
| Anthropic (optional) | the same channel evidence, for a second opinion | only `escalate --execute` |

Nothing else. No telemetry, no server, no account with us.

## Cost

Jev costs $0.042 per million input tokens and output is free. An email is about 830 tokens, so sorting 12,158 emails
cost $0.43, and a year of daily runs costs under $1. Rerunning on mail it has already seen costs nothing (judgments
are cached). The same job on a frontier model would be roughly 180 to 300 times more:
[the numbers](https://github.com/abhibansal60/tidy/blob/main/docs/research/opus-5-5-plus-jev-cost.md).

## Commands

| Command | What it does |
|---|---|
| `init`, `doctor` | first-run setup; check what is missing (offline) |
| `mail-auth [--write]` | Gmail sign-in (read, or label changes) |
| `mail-triage` | classify inbox mail; `--apply` auto-archives bulk mail |
| `mail-act` | apply reviewed Trash/Spam proposals from run files |
| `auth [--write]`, `sync` | YouTube sign-in; fetch subscriptions |
| `collect`, `judge`, `escalate` | gather evidence; Jev judges; optional second opinion |
| `propose`, `label`, `gate` | review page; record your verdicts; check the automation gate |
| `approve`, `unsubscribe`, `act`, `resubscribe` | change YouTube subscriptions (dry run until `--execute`) |
| `discover` | channels you watch a lot but do not follow |
| `report`, `purge` | counts; delete data past the 30-day retention |

`tidy COMMAND --help` for options. Full reference: [docs/reference.md](https://github.com/abhibansal60/tidy/blob/main/docs/reference.md).

## FAQ

**Why not just ask ChatGPT or Claude to clean my inbox?** You can, but by our estimate you would pay 180 to 300 times more per email,
wait longer, and trust one model's word with your account. Tidy uses AI only for the judgment and keeps every rule
that touches your account in small, tested code.

**Will it delete an important email?** It cannot permanently delete anything. It never touches starred mail, only
archives on its own when two independent signals agree, and Trash is recoverable for 30 days.

**Is my data used to train anything?** Tidy has no server. What goes to TypeSafe is listed above; see their terms.

**Where is my data?** `~/.tidy` (or `./.tidy` inside a cloned checkout, or `$TIDY_DATA_DIR`). Delete the folder to
remove everything; revoke access at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## More

[Jev playbook](https://github.com/abhibansal60/tidy/blob/main/docs/guide/jev-playbook.md) ·
[Design decisions](https://github.com/abhibansal60/tidy/tree/main/docs/adr) ·
[Research and evals](https://github.com/abhibansal60/tidy/tree/main/docs/research) ·
[Changelog](https://github.com/abhibansal60/tidy/blob/main/CHANGELOG.md) ·
[Contributing](https://github.com/abhibansal60/tidy/blob/main/CONTRIBUTING.md)

Not affiliated with Google, YouTube or TypeSafe. MIT licensed. Use at your own risk.
