# Tidy reference

Full command and design reference. Start with the [README](../README.md) for the quick start and
[agent-setup.md](agent-setup.md) if an agent is doing the setup.

A personal attention-management experiment: learn what Jev's bounded judgments
can tell us about a subscription feed, then calibrate them against the owner's
decisions. Codex helps build the application; deterministic code runs it.

Jev (TypeSafe's System One model) makes every quality judgment; plain code owns thresholds, caps, budgets and
every YouTube change, which goes through the official API (no browser automation). Nothing changes your
subscriptions without your approval, and every command that could is a dry run until you add `--execute`.

## Getting started (long form)

You need Python 3.11+, a Google Cloud project with the YouTube Data API v3 and a Desktop OAuth client, a TypeSafe API
key, and (recommended) your Google Takeout watch history.

1. **Install.** `pipx install tidy-ai`, or see "Run locally" below for a checkout.
2. **Configure.** `tidy init --email you@gmail.com --client-secrets PATH --key-stdin`, then `tidy doctor`. This writes
   `config.json`, `client_secret.json` and `.env` (owner-only) into the data folder. A checkout can instead keep the
   client at `secrets/client_secret.json` and the key in `TYPESAFE_API_KEY`, `./.env` or `../.env`.
3. **Authorize.** `python -m tidy auth` (read-only). Only when you want it to make changes: `python -m tidy auth --write`.
4. **Add your taste.** Export your YouTube watch history from Google Takeout as HTML, save it under `data/`, and set
   `watch_history_path` and a short `viewing_habits` description in `.tidy/profile.json`.
5. **Run the monthly loop** (each step below is safe to rerun):

```bash
python -m tidy sync --max-units 100                       # fetch your live subscriptions
python -m tidy collect --all --max-units 400 --execute   # latest 12 uploads per channel (about 3 units each)
python -m tidy judge --schemas titles-v2 --execute        # Jev judges every channel in seconds
python -m tidy escalate --execute                         # second opinion only for channels Jev flags as low quality
python -m tidy discover --execute                         # optional: unsubscribed channels you watch often
python -m tidy judge --schemas titles-v2 --execute        # judge the discovered ones too
python -m tidy propose > proposals.md                     # read this: KEEP, REVIEW, UNSUBSCRIBE, SUBSCRIBE with the signals
python -m tidy approve CHANNEL_ID... --note "why"         # you decide
python -m tidy unsubscribe                                # dry run of approved unsubscribes
python -m tidy unsubscribe --execute --max-units 500      # apply them
```

`--schemas` must match `schema_id` in `profile.json` (default `titles-desc-v1`; the calibrated profile here uses
`titles-v2`). Use `python -m tidy COMMAND --help` for flags.

### How often to run it

About once a month, started by you. Three limits set the rhythm:

- **Evidence expires after 30 days.** YouTube's API terms require refreshing or deleting API-derived data within 30
  days, so a monthly run keeps the stored evidence and Jev's judgments valid (they are purged automatically after that).
- **Your watch history is a Takeout export you make by hand,** and "recently watched" looks back six weeks by default.
  Re-export it before each monthly run so a channel you started watching is not proposed for removal.
- **Quota is small.** A full run for about 100 channels costs about 300 units for evidence and 50 per unsubscribe against
  a 10,000-unit daily default, and Jev's judgments cost a fraction of a cent.

Nothing runs on a schedule or without you: the automation is gated (per-run caps of 5 unsubscribes and 3 subscribes,
the calibration gate, owner-started runs only). See `docs/adr/0005-gated-owner-started-autonomy.md`.

## Run locally

Tested on Python 3.11 to 3.14 (CI). Use the existing `.venv`, or create one and install the
pinned environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m tidy --help
```

SQLite, OAuth credentials, and local configuration live in the data folder: `--data-dir`, else `$TIDY_DATA_DIR`,
else `./.tidy` when it exists (a checkout), else `~/.tidy`. `--data-dir` selects a separate
account's state and must precede the command. The account is bound to both the
verified Google subject/email and the authorized YouTube channel ID.

## Import the old experiment

On the original machine:

```bash
.venv/bin/python -m tidy import-legacy
.venv/bin/python -m tidy report
```

Other locations can be supplied with `--csv` and `--results`. This command makes
no network calls. It imports the CSV and original result records into SQLite,
identified by a hash of both source files. Repeating the import does not create
duplicates. Legacy records are observations, not live subscription state or
approved decisions. Missing probabilities, model version, and evidence stay
missing.

`rank.py` remains the historical experiment. It fetches via yt-dlp, spends Jev
tokens, and overwrites root-level results. It is not called by the manager.
The original local artifacts have a private checksummed backup under
`data/baseline/`. Neither private artifacts nor that backup are tracked in Git.

## Connect YouTube (one-time owner setup)

1. Create/select a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **YouTube Data API v3**.
3. Configure Google Auth Platform's consent screen. For an external app in
   Testing, add your own Google account as a test user.
4. Create an OAuth client with application type **Desktop app**. Download its
   JSON to `secrets/client_secret.json` inside this project, or pass another
   path using `auth --client-secrets /path/to/client.json`.
5. Copy `config.example.json` to `.tidy/config.json`, setting `expected_email`
   to the Google account you intend to manage. On the original machine this
   private configuration has already been prepared.
6. Run authorization, select the intended personal YouTube identity, then sync:

```bash
.venv/bin/python -m tidy auth
.venv/bin/python -m tidy sync --max-units 100
.venv/bin/python -m tidy report
```

OAuth uses Google's library, a local loopback callback, PKCE, and state validation.
Scopes are YouTube read-only plus OpenID/email to verify the selected account;
broader grants are rejected. `--no-browser` prints the authorization URL instead
of opening it. The browser must reach the same machine's loopback listener; a
remote shell may need local execution or port forwarding. The callback expires
after three minutes. Never paste tokens or callback URLs into chat.

Credentials are stored atomically with mode 0600. The verified email must match
configuration, and later runs must match the database's Google and YouTube
identities. Choosing another Brand Account does not silently replace inventory.

An external OAuth app in Testing receives a refresh token that normally expires
after seven days for these scopes. Reauthorize when necessary; revisit app
publishing configuration before unattended scheduling. Official references:
[desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app),
[refresh tokens](https://developers.google.com/identity/protocols/oauth2).

The inventory commands never read the TypeSafe API key. The owner has rotated the
exposed historical key; future Jev calls will use the private `../.env` file.

## Approved unsubscribes

Mutation is a separate, deliberately narrow path:

```bash
.venv/bin/python -m tidy approve CHANNEL_ID... --note "why / proposal version"
.venv/bin/python -m tidy unsubscribe            # dry run, offline
.venv/bin/python -m tidy auth --write           # one-time, separate token_write.json
.venv/bin/python -m tidy unsubscribe --execute
.venv/bin/python -m tidy sync
```

`approve` binds the owner's approval to the current account and subscription ID.
`--execute` (default `--max-units 500`, which fits 9 deletes at 50 units each; raise it for larger batches, and the whole batch is
checked against the budget before the first delete) rechecks identity and the live subscription list, deletes one
subscription at a time (50 quota units each), records an audit event, and never
retries an ambiguous outcome: it marks it `unknown` and reconciles against the live
list on the next run. A channel re-subscribed under a new ID is skipped and needs
fresh approval. The read-only token never gains write scope.

## Gated automatic actions

`act` turns proposals into subscribes and unsubscribes, only inside an owner-started
run (ADR 0005). It is a dry run unless you pass `--execute`, and both gates are closed
unless you open them:

```bash
.venv/bin/python -m tidy act --proposals proposals.json --gate-unsubscribe   # dry run, offline
.venv/bin/python -m tidy act --proposals proposals.json --gate-unsubscribe --gate-subscribe --execute
.venv/bin/python -m tidy resubscribe CHANNEL_ID... [--execute]              # undo an automatic unsubscribe
```

`proposals.json` is a list of Proposal dicts; `tidy propose --json proposals.json` writes it. Per run, at most 5 unsubscribes and 3
subscribes (`--cap-unsubscribe`, `--cap-subscribe`). A proposal with fewer than two
signals is never acted on. If the eligible unsubscribes exceed the larger of three
times the cap or 20% of active subscriptions, the whole run aborts with no action.
`--execute` uses `token_write.json`, rechecks identity and the live list, acts one
at a time, and writes an audit event for each. Ambiguous outcomes are marked
`unknown`, never retried, and settled against the live list next run. New
subscriptions start a 30-day trial (`mutate.trials_due` lists the ended ones for
review; nothing graduates or gets removed automatically). Each automatic unsubscribe
records its subscription ID, channel and title so `resubscribe` can restore it.

## Evidence pilot

```bash
.venv/bin/python -m tidy collect --channels CHANNEL_ID...     # dry run, offline: plan and quota estimate
.venv/bin/python -m tidy collect --channels CHANNEL_ID... --execute
```

Collects the latest 12 uploads per channel with the read-only token (about 3 quota
units per channel), adds the channels named in `data/owner_labels.json` by title,
and stores dated evidence samples that expire after 30 days. Nothing is sent to Jev yet.

## Schema experiment

```bash
.venv/bin/python -m tidy judge --schemas titles-v1 titles-desc-v1             # dry run, offline
.venv/bin/python -m tidy judge --schemas titles-v1 titles-desc-v1 --execute   # calls Jev
```

Judges the stored, unexpired evidence samples once per schema and prints JSON: for each
channel and schema the raw answers (score and confidence, or Noul probability), tokens and
latency; per-schema totals (tokens, summed and max latency, calls versus cache hits); and per
channel the difference between schemas on each question, flagged at 0.5 or more on a 0-3 score
or 0.3 or more on a Noul. The dry run prints the sample count, calls and a rough input token
estimate (characters divided by 4) without touching the network or needing a key. `--execute`
reads `TYPESAFE_API_KEY` from the environment, or from `.env` in the parent of the current
directory. Repeat runs on unchanged evidence and the same `--interests` cost zero calls.
Cached answers keep their original tokens and latency in the totals.

## Proposals, review and labels

All of these run offline against the local database.

- `profile.json` in the data directory holds your taste: interests, schema id,
  policy thresholds, caps, trial days and the calibration gate. Missing keys use
  defaults; unknown keys or bad types are rejected.
- `python -m tidy propose` turns stored evidence samples and cached judgments
  into proposals (KEEP, WATCH, REVIEW, UNSUBSCRIBE) and prints a Markdown report
  with signals, dimension values, evidence coverage and links. Policy is
  deterministic and versioned; changing `profile.json` or the policy costs no
  Jev calls. Channels without a cached judgment are left out.
- `python -m tidy label CHANNEL_ID keep|drop|unsure [--note ...]` records an owner
  label; `python -m tidy labels import PATH` reads the private
  `{"keep": [...], "sloppy": [...]}` file and matches titles to subscriptions.
- `python -m tidy gate` prints agreement between proposals and your labels
  (REVIEW and unsure labels are excluded) and whether the calibration gate is
  open: at least 30 labels and 85% agreement by default.

## Labeling from a sheet

`tidy labels sheet PATH` reads a JSON file with `{"channels": [{"channel_id", "verdict", "note"}]}`
and records every filled verdict (`keep`, `drop` or `unsure`); blanks are skipped and one bad verdict
applies nothing. Repeating it adds nothing new.

## Evals (Claude Code vs Jev)

`python -m evals.claude_baseline --model haiku --effort low` answers the same questions through
`claude -p`; `python -m evals.repeat` measures run-to-run change; `python -m evals.compare JEV.json CLAUDE.json...`
prints speed, cost and agreement. Outputs stay under `.tidy/` (private).
`python -m evals.codex_baseline --model gpt-6-astra --resume` does the same through Codex CLI (`--resume` re-asks only
failed channels). Every runner uses the original 110 channels in `experiment_2.json`, so later-collected candidates never
join an eval. `python -m evals.list_price` estimates what each run would cost at list API prices (sources in the file),
and `python -m evals.demo_video` renders the demo MP4 from the stored results (needs Pillow and imageio-ffmpeg).
Research notes: `docs/research/` (Fable vs Opus efficiency, public and X comparisons of Jev).

## Discovery from watch history

`tidy discover` (dry run by default) lists channels you watched at least `discovery_min_watches` times (default 3) in
`watch_window_days` that you are not subscribed to, counted from Takeout, never searched. `--execute` collects their
evidence with the read-only token (about 3 quota units each). After `tidy judge`, `tidy propose` gives a SUBSCRIBE
proposal when Jev's value is at least `discovery_min_value` (default 0.5). Nothing subscribes on its own: the subscribe
gate stays closed until the calibration gate opens.

## Policy with watch history and the low-quality cascade

Set `watch_history_path` in `profile.json` (a Google Takeout `watch-history.html`, kept under `data/`) and
`tidy propose` switches to policy-2: watched in the last `watch_window_days` (default 42, six weeks) is KEEP; unwatched goes
to REVIEW; a channel is proposed for UNSUBSCRIBE only when Jev and a second opinion both rate its value below
`low_quality_value` (default 0.5), whatever its watch count. `tidy escalate` (dry run by default) sends only the
channels Jev flags to a stronger model (`--model`, default `claude-opus-5-5`, through Claude Code headless) and stores
the answers with the evidence's 30-day expiry.

## Inventory behavior and quota

- All YouTube requests are GET requests for channels or subscriptions.
- Subscription collection paginates with 50 items per request and stores the
  subscription ID separately from the channel ID.
- Only a complete collection replaces current inventory. Malformed responses,
  failed pages, pagination loops, duplicate channels, wrong-account responses,
  or exhausted budgets leave the last successful inventory intact.
- A missing channel means absent from the observed subscription list, not dead,
  low quality, or deleted by this application. Results are a point-in-time
  observation; avoid editing subscriptions while a sync is running.
- `--max-units` caps YouTube request attempts for a sync. Identity lookup costs
  one unit; each subscription page costs one. Retries count against this local
  estimate. A 383-subscription sync normally costs nine units, plus a separate
  one-unit check during initial authorization. Userinfo/OAuth are outside the
  YouTube quota. Other applications may share your project quota.
- Failed attempts retain an error category and estimated quota use. Reports
  distinguish the latest attempt from the last successful snapshot.
- API subscription metadata expires after 30 days and is purged when a command
  opens the database. An expired snapshot is not presented as current. This is
  on-use cleanup, not a background retention service; periodic cleanup/refresh
  is needed if API data remains stored while the app is idle for longer.

References: [subscriptions.list](https://developers.google.com/youtube/v3/docs/subscriptions/list),
[quota costs](https://developers.google.com/youtube/v3/determine_quota_cost).

## Jev experiments next

The old three-question experiment is a baseline, not a required architecture.
Its combined score conflated relevance, depth, and sensational packaging; it
saved only four titles and discarded distributions/confidence. Preserve those
lessons, not those limitations.

After inspecting real inventory, use a small sample of channels to compare
bounded schemas. Record the hypothesis, exact state/questions, model version,
probability distributions, latency, token usage, and the owner's independent
labels. Hold some channels out of prompt/threshold tuning. Distinguish model
confidence, evidence completeness, and actual agreement with user preferences.

Metadata can support topic and packaging judgments. It cannot establish actual
video depth or originality. Jev is text-only; the official YouTube caption API
requires video-edit permission. A small, honest experiment is preferable to a
dashboard full of unsupported precision.

YouTube's [developer policies](https://developers.google.com/youtube/terms/developer-policies)
restrict derived data and require metadata refresh/deletion. The
[additional metrics amendment](https://developers.google.com/youtube/terms/derived-metrics-policy)
provides a conditional route for certain analytics uses. Eligibility for this
personal experiment is unresolved; evidence and judgments derived from the API
are kept for at most 30 days and purged automatically (`tidy purge` runs it on
demand). Scraping is not a policy workaround.

Later increments: cached evidence pilot; Jev evaluation comparison; action report;
manual review/calibration; approved mutations with safeguards; local dashboard;
longitudinal drift; discovery. Automatic mutations require separate authorization.

## Sharing the learning

Code and synthetic tests are separate from private account and subscription data.
For a future post, report both successes and failures, compare schemas on the same
evidence, state sample limitations, and avoid claiming universal channel quality.
Nothing has been published. Review tracked files and outputs before sharing;
the CLI report includes private channel IDs.
