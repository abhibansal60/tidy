# Changelog

## 0.2.1 (2026-09-26)

- **Fix:** watch history from Google Takeout in day-first locales (India, UK: `22 Sept 2026, 14:49:34 IST`) was read
  as zero watches, so every channel looked unwatched. Both US and day-first formats are now parsed.
- **Fix:** a key-lookup test could read the real `~/.tidy/.env` and print that key in its failure message; it now uses
  an isolated data folder.
- `escalate` defaults to `claude-opus-5-5`.
- Tidy mascot and brand kit (mail and subscriptions costumes, generator script), lockup in README header.
- Builder-angle launch card: AI reads it, code decides.

## 0.2.0 (2026-09-22)

First PyPI release, as `tidy-ai`.

- **Gmail cleanup:** `mail-auth`, `mail-triage` (Jev sorts mail; `--apply` auto-archives corroborated bulk mail),
  `mail-act` (reviewed Trash/Spam, several run files, live recheck). Dashboard with an unsubscribe shortlist per sender.
- **Setup:** `tidy init` (private data folder, config, OAuth client, hidden key prompt) and `tidy doctor` (what is
  missing and what to run next; never prints secrets). Data defaults to `~/.tidy` (or `./.tidy`, or `$TIDY_DATA_DIR`).
- **Safety:** starred mail is never touched; reports and run files are written 0600; no raw tracebacks; message IDs
  validated; `requests>=2.32.4`.
- Python 3.11 to 3.14 (was 3.14 only). `tidy` and `tidy-ai` commands.

## 0.1.0 (2026-09-21)

YouTube subscriptions: inventory, evidence, Jev judgments, review page, owner-approved unsubscribes, gated automation,
watch-history discovery.
