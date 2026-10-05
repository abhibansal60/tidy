# Changelog

## Unreleased

- **Security:** HTML mail bodies are stripped of style/script blocks in one linear pass. The old regex was
  quadratic on unclosed tags, so one crafted email (200 KB) could stall a run for about 30 seconds per copy.
- **Mail:** auto-archive no longer treats "you aren't the only To recipient" as a bulk signal. Cc'd mail, family
  threads and alias deliveries need an unsubscribe header or a Gmail bulk tab before Jev's category can archive them.
- **Mail:** `mail-triage --max-calls` defaults to 1200, so the documented `--limit 200` run no longer hits the budget.
  Gmail `Retry-After` waits are capped at 120 s; a timed-out second opinion is recorded as an error instead of
  stopping the run; "Open in Gmail" URL-encodes the account.

## 0.2.3 (2026-10-02)

- **Mail dashboard:** grouped by what needs you (Needs you, FYI, Noise, Handled) as tabs and a card grid, with
  per-message and bulk action buttons, undo, and bulk one-click unsubscribe from the Noise tab. The buttons call a
  same-origin `/api/mail/act` endpoint (a hosted app such as tidy-mail); opened as a plain file the page is read-only.
  The page reloads when a Home Screen app resumes, has a Refresh button, and hides messages Gmail has already handled.
- **Mail:** optional push summary after the daily run via ntfy (`python -m tidy.notify`).
- `discover` takes `--window` (latest uploads per channel), like `collect`.
- Internal: Gmail and YouTube share one Google OAuth module; the mail-triage run is a library function
  (`mail.triage`) with its own tests; `gmail.connect()` loads, verifies and saves a token in one step.

## 0.2.2 (2026-09-27)

- **Mail:** new `Action Needed` category (kept in the inbox) for automated mail that asks you to do something or warns
  of a problem: action required, failed payment or build, expiring subscription, security alert. Before, these counted
  as `Updates` and were auto-archived. On the owner's last 5 days of mail (206 messages, 117 auto-archived), 28
  archived messages now stay in the inbox and 10 go to review; routine transaction alerts and one-time codes stay
  `Updates`. Bulk-split archiving now also backs off when Jev puts weight on `Action Needed`. Schema `mail-v2`,
  policy `mail-policy-4` (old cached judgments are not reused).

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
