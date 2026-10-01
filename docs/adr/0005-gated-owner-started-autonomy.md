# Gated, owner-started autonomy

On 2026-09-19 the owner chose automatic unsubscribe and automatic subscribe of high-quality candidates, superseding per-batch approval. Autonomy is enabled per action type only after the calibration gate holds (≥85% agreement on at least 30 held-out owner labels), runs only in an owner-started run within caps (start: ≤5 unsubscribes, ≤3 subscribes), never acts on one dimension alone, aborts on anomalous proposal counts, logs every action, and keeps unsubscribes reversible. New subscriptions are a 30-day trial. Testing-mode OAuth tokens expire in about 7 days, which fits monthly runs and rules out unattended scheduling until the app is published.

## Note on one dimension (2026-09-20)

Policy-2 lets two independent judges (Jev and a second model) both rating value low authorize an unsubscribe proposal,
which is two opinions on one dimension. The owner chose this strict cascade on 2026-09-19 over the earlier
"two different dimensions" rule. Automatic execution stays behind the calibration gate, and `tidy act --execute`
refuses a closed gate unless `--override-gate` is passed.

## Scope: YouTube actions only (2026-10-01)

This ADR governs unsubscribe and subscribe. Mail triage (`tidy mail-triage`) is outside it: `--apply` auto-applies only
`ARCHIVE` (label-only, reversible), while TRASH and SPAM are proposed and held for an owner-run `mail-act`. The mail
calibration gate cannot open yet (no owner-labeled mail), so a scheduled run needs the owner's `--override-gate`,
which `tidy/mail.py` documents as the owner escape hatch. Running it from cron is therefore an explicit owner choice,
not a breach of "owner-started". Revisit once mail has owner labels.
