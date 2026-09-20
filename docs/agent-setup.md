# Agent setup runbook

For a coding agent setting up Tidy for a person. Follow the steps in order. Steps marked HUMAN need the person; stop
and ask, do not guess.

## Rules

1. Never print, log, commit or paste secrets: OAuth client JSON, tokens, `TYPESAFE_API_KEY`, `.env`.
2. Never run a command with `--execute` unless the person said to in this conversation. Dry runs are always fine.
3. Never edit `.gitignore` to include `.tidy/`, `data/`, `secrets/` or `.env`, and never commit them.
4. Do not use browser automation on YouTube. All changes go through the API commands below.
5. Report what each step did in one or two lines. If a command fails, show the error line and stop.

## Steps

1. **Check the machine.** Python 3.14 or newer (`python3 -V`), `git`. If Python is older, ask the person to install
   3.14 (or use `uv`/`pyenv`).
2. **Install.** `curl -fsSL https://raw.githubusercontent.com/abhibansal60/tidy/main/install.sh | sh` then `cd tidy`.
   Or clone the repo, `python3 -m venv .venv`, `.venv/bin/pip install -e .`. Confirm `.venv/bin/tidy --help` prints usage
   and `.venv/bin/python -m unittest discover -s tests -q` passes.
3. **HUMAN: Google Cloud.** The person creates a project, enables YouTube Data API v3, configures the OAuth consent
   screen (add themselves as a test user), and creates an OAuth client of type Desktop app. They save the JSON as
   `secrets/client_secret.json`. You never open or print it.
4. **HUMAN: TypeSafe key.** The person creates a key at console.typesafe.ai and puts `TYPESAFE_API_KEY=...` in `.env` in
   the repository folder (or the environment; `../.env` also works). You never read it.
5. **Configure.** `mkdir -p .tidy secrets`, copy `config.example.json` to `.tidy/config.json` and set `expected_email` to the person's Google
   email (ask them for it).
6. **HUMAN: authorize.** Run `.venv/bin/tidy auth`. A browser opens for consent. It binds the database to that
   Google account.
7. **Fetch.** `tidy sync` then `tidy collect --all` (dry run: shows channels and the quota estimate). With the person's
   go-ahead run `tidy collect --all --max-units 400 --execute`.
8. **HUMAN (optional, recommended): watch history.** The person exports YouTube watch history from Google Takeout as
   HTML into `data/takeout/history/`. Then set `watch_history_path` and a one or two sentence `viewing_habits` in
   `.tidy/profile.json` (keys and defaults are in `tidy/profile.py`; see `docs/reference.md`).
9. **Judge.** `tidy judge --schemas titles-desc-v1` (dry run), then with go-ahead `--execute`. If `profile.json` sets a
   different `schema_id`, use that.
10. **Propose.** `tidy propose --html .tidy/proposals.html` (or `tidy propose > .tidy/proposals.md` for Markdown). Summarize counts per action and the top signals. Do not approve
    anything for the person.
11. **Optional: second opinion and discovery.** `tidy escalate` (dry run) and `tidy discover` (dry run) list what they
    would send or fetch.
12. **Changes, only if the person asks.** `tidy auth --write`, `tidy approve CHANNEL_ID... --note "why"`,
    `tidy unsubscribe` (dry run), and only then `tidy unsubscribe --execute --max-units 500`.

## Done when

`tidy report` shows the subscription count, `.tidy/proposals.md` exists, `git status` shows no private files, and the person
knows to rerun about once a month: a fresh Takeout export, then `tidy sync` and `tidy collect --all` (step 7), judge (step 9) and propose (step 10).
