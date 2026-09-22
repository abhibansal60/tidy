# Agent setup runbook

For a coding agent setting up Tidy for a person. Follow the steps in order. Steps marked HUMAN need the person; stop
and ask, do not guess. Every Tidy command prints JSON; read it instead of guessing.

## Rules

1. Never print, log, commit or paste secrets: the OAuth client JSON, tokens, the TypeSafe key, `.env`. Do not open
   those files. `tidy doctor` output is safe to show.
2. Never run a command with `--execute` or `--apply` unless the person said to in this conversation. Dry runs are fine.
3. Never pass a secret as a command-line argument. The TypeSafe key goes in through `tidy init --key-stdin`, typed or
   pasted by the person.
4. Do not use browser automation on Gmail or YouTube. All changes go through Tidy's commands.
5. Report what each step did in one or two lines. If a command fails, show the `Error:` line and stop.

## Steps

1. **Install.** Python 3.11+ (`python3 -V`). Then `pipx install tidy-ai` (or `uv tool install tidy-ai`; before the first
   PyPI release, `pipx install git+https://github.com/abhibansal60/tidy`). Check `tidy --version` (if another `tidy`
   answers, use `tidy-ai` everywhere below). Run `tidy doctor` and read `next`.
2. **Ask** which parts the person wants: Gmail cleanup, YouTube subscriptions, or both, and their Google email.
3. **HUMAN: Google Cloud** (about 5 minutes, in their browser):
   1. At https://console.cloud.google.com/ create a project (any name).
   2. APIs and Services, Library: enable **Gmail API** and/or **YouTube Data API v3**.
   3. OAuth consent screen: External, Testing mode, add their own Google address as a **test user**. Under Data
      Access add the scopes `gmail.readonly` and `gmail.modify` (Gmail) and/or `youtube.readonly` and `youtube`.
   4. Credentials, Create credentials, OAuth client ID, type **Desktop app**. Download the JSON.
   Google will later say the app is unverified: that is expected for a personal Testing-mode app; they click Continue.
4. **HUMAN: TypeSafe key.** They create a key at https://console.typesafe.ai.
5. **Init.** Ask for the downloaded JSON's path, then have the person run (so they paste the key, not you):
   `tidy init --email THEIR_EMAIL --client-secrets PATH --key-stdin`. Add `--no-mail` if they only want YouTube.
   Then `tidy doctor` must show `"ready": true`.

### Gmail

6. **HUMAN: sign in.** `tidy mail-auth` (browser consent, read-only).
7. **Look, change nothing.** `tidy mail-triage --execute --limit 200 --html ~/.tidy/inbox.html --json ~/.tidy/runs/first.json`.
   Summarize `action_counts` and tell them to open the HTML page.
8. **Only if they want changes:** `tidy mail-auth --write` (HUMAN consent), then with their go-ahead
   `tidy mail-triage --execute --apply --override-gate --limit 200 --json ~/.tidy/runs/first.json` (archives only),
   then `tidy mail-act --run ~/.tidy/runs/first.json` (dry run: show them `preview`), and only on their yes add `--execute`.
9. **Optional daily run:** offer the cron line from the README with the full path from `command -v tidy`.

### YouTube

10. **HUMAN: sign in.** `tidy auth`. Then `tidy sync`, and `tidy collect --all` (dry run: channels and quota estimate).
    With their go-ahead `tidy collect --all --max-units 400 --execute`.
11. **Optional, recommended: watch history.** They export YouTube watch history from Google Takeout as HTML. Set
    `watch_history_path` and a one or two sentence `viewing_habits` in `~/.tidy/profile.json` (keys: `docs/reference.md`).
12. **Judge and propose.** `tidy judge --schemas titles-desc-v1` (dry run), then `--execute` with go-ahead, then
    `tidy propose --html ~/.tidy/review.html`. Summarize counts per action. Do not approve anything for them.
13. **Changes, only if asked.** `tidy auth --write`, `tidy approve CHANNEL_ID... --note "why"`, `tidy unsubscribe`
    (dry run), then `tidy unsubscribe --execute`.

## Done when

`tidy doctor` shows `"ready": true` with no `loose_permissions`, the person has opened their dashboard, and they know
that nothing changes without `--execute`. For YouTube, rerun about once a month (sync, collect, judge, propose).
