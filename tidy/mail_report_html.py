"""Self-contained HTML page for a mail-triage run, organised by what the owner has to do.

Sections: Needs you (decisions), FYI (alerts that need no decision), Noise to clear (bulk senders, grouped), Handled
(auto-archived or queued). No server, no network, no external assets: one file. Every string from Gmail or a
model is HTML-escaped; the CSP allows only this page's own script and style, by hash. Buttons that change Gmail are
buttons call /api/mail/act on the same origin (the tidy-mail app), which is the only network access the CSP allows.
"""

from email.utils import parseaddr
from html import escape
import re
from urllib.parse import quote

from .mail_report_assets import CSS, JS_TEMPLATE
from .report_html import csp_hash

PROPOSED_LABEL = {"REVIEW": "Review", "ARCHIVE": "Archive", "TRASH": "Trash", "SPAM": "Spam", "KEEP": "Keep"}
DONE_LABEL = {"ARCHIVE": "Archived", "TRASH": "Trashed", "SPAM": "Marked spam"}
OUTCOME_LABEL = {"applied": "Applied", "held": "Held for review", None: None}

# Alerts and receipts that carry no decision: code-owned rule, not a Jev verdict. A REVIEW row only lands here when
# Jev is confident it is an update AND the sender is an automated address. Anything else stays in "Needs you".
FYI_SENDER = re.compile(r"^(no-?reply|do-?not-?reply|alerts?|customernotification|notifications?|credit_cards|help|info|updates?)\b", re.I)
FYI_MIN_CONFIDENCE = 0.6
STALE_HOURS = 50  # page viewed any time: must outlast the gap between runs (daily, or every other day on cron)

JS = JS_TEMPLATE % STALE_HOURS


def bucket(r):
    """needs_you | fyi | noise | handled. Pure and code-owned: Jev only supplies category and confidence."""
    action = r["action"]
    if action == "KEEP":
        return "needs_you"
    if action == "REVIEW":
        local = parseaddr(r["sender"])[1].split("@")[0]
        if r.get("category") == "Updates" and r["confidence"] >= FYI_MIN_CONFIDENCE and FYI_SENDER.match(local):
            return "fyi"
        return "needs_you"
    if action == "ARCHIVE":
        return "handled"
    return "noise"  # TRASH, SPAM: proposed only, never auto-applied


def _gmail_url(r, account):
    thread = r.get("thread_id") or r["id"]
    who = f"?authuser={escape(quote(account), quote=True)}" if account else ""
    return f"https://mail.google.com/mail/{who}#all/{escape(thread, quote=True)}"


def _sender_key(r):
    name, addr = parseaddr(r["sender"])
    return (addr or r["sender"]).casefold(), name or addr or r["sender"]


def _unsub(r):
    """What each unsubscribe link really does. Tidy never fetches these itself, so it cannot say they worked."""
    links = r.get("unsubscribe")
    if not links:
        return ""
    parts = []
    if (links.get("http") or "").lower().startswith(("http://", "https://")):
        parts.append(f'<a href="{escape(links["http"], quote=True)}" rel="noopener noreferrer" target="_blank">Unsubscribe</a>'
                     '<span class="note">opens the sender\'s page; you confirm there</span>')
    if (links.get("mailto") or "").lower().startswith("mailto:"):
        parts.append(f'<a href="{escape(links["mailto"], quote=True)}">Unsubscribe by email</a>'
                     '<span class="note">opens your mail app with a draft to send</span>')
    return "".join(parts)


def _buttons(r, b):
    if b == "handled":
        return _btn("inbox", "Back to inbox") if r.get("outcome") == "applied" else _btn("archive", "Archive")
    if b == "needs_you":
        return _btn("archive", "Archive") + _btn("keep", "Keep") + _btn("trash", "Trash", True)
    if b == "fyi":
        return _btn("archive", "Archive")
    one = _btn("unsubscribe", "One-click unsubscribe") if r.get("unsubscribe_one_click") and (r.get("unsubscribe") or {}).get("http") else ""
    return _btn("archive", "Archive") + _btn("trash", "Trash", True) + one


def _btn(op, label, danger=False, ids=None):
    attr = f' data-ids="{escape(",".join(ids), quote=True)}"' if ids else ""
    return f'<button type="button" data-op="{op}"{attr}{" class=danger" if danger else ""}>{escape(label)}</button>'


def _item(r, account, unsub=False, b="needs_you"):
    subject = escape(r["subject"] or "(no subject)")
    sender = escape(parseaddr(r["sender"])[0] or r["sender"])
    snippet = escape((r.get("snippet") or "")[:150])
    reason = (r.get("signals") or [""])[0]
    reason = "" if reason.startswith("category ") else escape(reason)  # the category chip already says this
    raw_outcome = r.get("outcome")
    outcome = OUTCOME_LABEL.get(raw_outcome, raw_outcome)  # unrecognised values (e.g. "error: ...") stay visible
    done = DONE_LABEL[r["action"]] if raw_outcome == "applied" and r["action"] in DONE_LABEL else PROPOSED_LABEL[r["action"]]
    status = f" <em>{escape(outcome)}</em>" if outcome else ""
    title = escape((r["subject"] + " " + r["sender"]).lower(), quote=True)
    return (f'<div class="item" data-id="{escape(r["id"], quote=True)}" data-b="{b}" data-t="{title}"><div class="subj">{subject}</div>'
            f'<div class="snip">{sender}: {snippet}</div>'
            f'<div class="why"><em>{escape(r["category"])} {r["confidence"]:.2f}</em>{escape(done)}{status}'
            f'{(" · " + reason) if reason else ""}</div>'
            f'<div class="acts"><a class="main" href="{_gmail_url(r, account)}" target="_blank" rel="noopener noreferrer">Open in Gmail</a>'
            f'{_buttons(r, b)}{_unsub(r) if unsub else ""}</div></div>')


def _bulk(rows, ops):
    if len(rows) < 2 or not ops:
        return ""
    ids = [r["id"] for r in rows]
    names = {"archive": "Archive all", "keep": "Keep all", "trash": "Trash all"}
    return '<div class="bulk">' + "".join(_btn(op, f"{names[op]} {len(ids)}", op == "trash", ids) for op in ops) + "</div>"


GROUP_SHOWN = 1  # a sender with many near-identical mails shows its top few; the rest sit behind one fold


def _groups(rows, account, b, unsub=False, by_size=True, bulk=()):
    groups = {}
    for r in rows:
        key, name = _sender_key(r)
        groups.setdefault(key, {"name": name, "rows": []})["rows"].append(r)
    ordered = sorted(groups.values(), key=(lambda g: -len(g["rows"])) if by_size else (lambda g: -max(r["confidence"] for r in g["rows"])))
    cards = []
    for g in ordered:
        rs = g["rows"]
        head = "".join(_item(r, account, unsub, b) for r in rs[:GROUP_SHOWN])
        more = (f'<details class="more"><summary>Show {len(rs) - GROUP_SHOWN} more from {escape(g["name"])}</summary>'
                + "".join(_item(r, account, unsub, b) for r in rs[GROUP_SHOWN:]) + "</details>") if len(rs) > GROUP_SHOWN else ""
        cards.append(f'<section class="card"><header><b>{escape(g["name"])}</b><span>{len(rs)} message{"s" if len(rs) != 1 else ""}</span></header>{_bulk(rs, bulk)}{head}{more}</section>')
    return "".join(cards)


BULK_UNSUB_MAX = 25


def _unsub_bar(rows):
    """One-click unsubscribe for every sender in the Noise tab that supports it: one message id per sender."""
    seen, ids = set(), []
    for r in rows:
        key, _ = _sender_key(r)
        if key not in seen and r.get("unsubscribe_one_click") and (r.get("unsubscribe") or {}).get("http"):
            seen.add(key)
            ids.append(r["id"])
    if not ids:
        return ""
    n = len(ids[:BULK_UNSUB_MAX])
    more = f" (first {BULK_UNSUB_MAX} of {len(ids)})" if len(ids) > BULK_UNSUB_MAX else ""
    return ('<div class="unsubbar"><span>Senders that accept one-click unsubscribe: '
            f'<b>{len(ids)}</b>. Tidy asks each one to stop; it cannot confirm they will.</span>'
            + _btn("unsub-all", f"Unsubscribe from {n} senders{more}", False, ids[:BULK_UNSUB_MAX]) + "</div>")


def _fold(title, count, inner, note=""):
    if not count:
        return ""
    return (f'<details class="fold"><summary>{escape(title)}<span>{count}{(" · " + escape(note)) if note else ""}</span></summary>'
            f'<div class="inner">{inner}</div></details>')


def render(rows, applied=False, run_at=None, account=None):
    """`rows`: dicts with id, thread_id, subject, sender, snippet, category, confidence, action, signals, outcome,
    unsubscribe. `applied`: whether the run attempted --apply at all. `run_at`: ISO time of the run (for the health line)."""
    by = {"needs_you": [], "fyi": [], "noise": [], "handled": []}
    for r in sorted(rows, key=lambda r: -r["confidence"]):
        by[bucket(r)].append(r)
    done = sum(r.get("outcome") == "applied" for r in rows)
    state = ("Manual dry run: nothing was changed in Gmail." if not applied else
             f"{done} archived for you. Nothing else was touched." if done else
             "Nothing was actually applied this run (closed gate, cap or a failure).")
    health_cls = "health" + ("" if applied else " dry")
    panes = [
        ("needs_you", "need you", _groups(by["needs_you"], account, "needs_you", by_size=False, bulk=("archive", "keep")), "Nothing needs you right now."),
        ("fyi", "FYI", _groups(by["fyi"], account, "fyi", bulk=("archive",)), "No alerts. These are automated bank, payment and system mails that need no decision."),
        ("noise", "noise", _groups(by["noise"], account, "noise", unsub=True, bulk=("archive", "trash")), "No bulk mail proposed for trash."),
        ("handled", "handled", _groups(by["handled"], account, "handled"), "Nothing archived."),
    ]
    chips = "".join(f'<a href="#{k}" data-b="{k}" aria-selected="false"><b>{len(by[k])}</b> {label}</a>' for k, label, _, _ in panes)
    body = "\n".join(f'<section class="tab" data-tab="{k}" hidden>' + (_unsub_bar(by["noise"]) if k == "noise" else "") + (f'<div class="grid">{cards}</div>' if cards else f'<div class="empty">{escape(empty)}</div>') + "</section>"
                     for k, _, cards, empty in panes)
    csp = f"default-src 'none'; style-src {csp_hash(CSS)}; script-src {csp_hash(JS)}; base-uri 'none'; form-action 'none'; connect-src 'self'; manifest-src 'self'; img-src 'self'"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Mail">
<meta name="theme-color" content="#1F5FD0">
<title>Mail</title><style>{CSS}</style></head><body><main>
<nav class="tabs" aria-label="Sections"><a href="/" aria-current="page">Mail</a><a href="/jobs">Jobs</a><button type="button" id="refresh" aria-label="Refresh">Refresh</button></nav>
<div id="health" class="{health_cls}" data-run-at="{escape(run_at or '', quote=True)}"><span>Ran <strong data-when>{escape(run_at or 'unknown time')}</strong></span><span data-state>{escape(state)}</span><span>{len(rows)} messages judged by Jev</span></div>
<div class="chips">{chips}</div>
<input id="q" type="search" placeholder="Search subject or sender" aria-label="Search subject or sender">
{body}
</main><div id="toast" role="status" aria-live="polite"></div><script>{JS}</script></body></html>
"""
