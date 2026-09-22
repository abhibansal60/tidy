# Changelog

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
