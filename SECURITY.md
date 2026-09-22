# Security

Tidy runs on your machine with OAuth access to your own Gmail and YouTube accounts. This page says what it can and
cannot do, and how to report a problem.

## Reporting a vulnerability

Please use [GitHub private vulnerability reporting](https://github.com/abhibansal60/tidy/security/advisories/new).
Do not open a public issue, and never include tokens, `.env`, `client_secret.json`, dashboards or run files.
Expect a first reply within a week. Fixes ship as a new PyPI release and a GitHub advisory.

## What Tidy can do to your accounts

| Token | Scope | Can | Cannot |
|---|---|---|---|
| `token_mail.json` | `gmail.readonly` | read mail | change anything |
| `token_mail_write.json` | `gmail.modify` | archive, trash, mark spam | permanently delete, send, or change settings (the code also only allows the INBOX and SPAM labels) |
| `token.json` | `youtube.readonly` | read subscriptions | change anything |
| `token_write.json` | `youtube` | unsubscribe, subscribe | (code allows only those two calls) |

Write tokens are only created when you run `mail-auth --write` or `auth --write`. Every change needs `--execute`
(or `--apply --override-gate` for auto-archive). Revoke everything at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions) and by deleting `~/.tidy`.

## Design choices that limit damage

- Untrusted content (email text, channel text) only ever reaches Jev as data and comes back as a typed choice or
  score; it cannot name an action, a message ID or a URL. A crafted email can at most change its own category.
- AI output alone never triggers an automatic change: auto-archive needs an independent code-owned signal, starred mail
  is never touched, and held changes are rechecked against the live account right before they are applied.
- API endpoints, HTTP methods and label IDs are fixed in code; message IDs from run files are validated before use;
  redirects are not followed.
- Dashboards are single self-contained HTML files: every string is escaped, a Content-Security-Policy allows only the
  page's own script and style by hash, and unsubscribe links are shown for you to click, never fetched by Tidy.
- Tokens, config, database, dashboards and run files are written atomically with owner-only permissions (0600,
  folder 0700). `tidy doctor` flags anything readable by others.
- Errors print one line, never a traceback (set `TIDY_DEBUG=1` to see one). Secrets are never accepted as command-line
  arguments, so they do not land in shell history or process lists.
- Releases are built and published from GitHub Actions with PyPI Trusted Publishing (no stored token) and signed
  attestations; workflow actions are pinned by commit SHA.

## Data sent to third parties

See [What leaves your machine](README.md#what-leaves-your-machine). TypeSafe's handling of the data you send to Jev is
governed by their terms, not by this project.
