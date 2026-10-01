"""Self-contained HTML page for a mail-triage run, organised by what the owner has to do.

Sections: Needs you (decisions), FYI (alerts that need no decision), Noise to clear (bulk senders, grouped), Handled
(auto-archived or queued). No server, no network, no external assets: one file. Every string from Gmail or a
model is HTML-escaped; the CSP allows only this page's own script and style, by hash. Buttons that change Gmail are
not here: the page links to the thread in Gmail and states honestly what each unsubscribe link does.
"""

import base64
from email.utils import parseaddr
from html import escape
import hashlib
import re

PROPOSED_LABEL = {"REVIEW": "Review", "ARCHIVE": "Archive", "TRASH": "Trash", "SPAM": "Spam", "KEEP": "Keep"}
DONE_LABEL = {"ARCHIVE": "Archived", "TRASH": "Trashed", "SPAM": "Marked spam"}
OUTCOME_LABEL = {"applied": "Applied", "held": "Held for review", None: None}

# Alerts and receipts that carry no decision: code-owned rule, not a Jev verdict. A REVIEW row only lands here when
# Jev is confident it is an update AND the sender is an automated address. Anything else stays in "Needs you".
FYI_SENDER = re.compile(r"^(no-?reply|do-?not-?reply|alerts?|customernotification|notifications?|credit_cards|help|info|updates?)\b", re.I)
FYI_MIN_CONFIDENCE = 0.6
STALE_HOURS = 26

CSS = """
:root{--ground:#F4F5F7;--paper:#FFFFFF;--ink:#14181F;--muted:#5A6472;--line:#DDE1E7;--accent:#1F5FD0;--warn:#9A5B00;--warnbg:#FFF4DC;--bad:#B3261E;--badbg:#FDECEA;--ok:#1B6E4A;--chip:#E9ECF1}
@media (prefers-color-scheme:dark){:root{--ground:#0F1218;--paper:#171B23;--ink:#E7EAF0;--muted:#97A1B0;--line:#262C37;--accent:#7FA8FF;--warn:#F0B54A;--warnbg:#2B2410;--bad:#FF8A80;--badbg:#341716;--ok:#6FD3A6;--chip:#212733}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:20px 14px 88px}
h1{margin:0 0 4px;font-size:22px;font-weight:650;letter-spacing:-.01em}
h2{margin:28px 0 8px;font-size:13px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
h2 b{color:var(--ink);font-size:15px;letter-spacing:0;margin-left:6px}
.health{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;padding:10px 12px;margin:10px 0 0;border:1px solid var(--line);background:var(--paper);border-radius:10px;font-size:14px;color:var(--muted)}
.health.stale,.health.dry{background:var(--warnbg);border-color:var(--warn);color:var(--warn)}
.health.stale{background:var(--badbg);border-color:var(--bad);color:var(--bad)}
.health strong{color:inherit}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.chips a{display:inline-flex;gap:6px;align-items:baseline;padding:6px 12px;border-radius:999px;background:var(--chip);color:var(--ink);text-decoration:none;font-size:14px}
.chips a b{font-variant-numeric:tabular-nums}
.chips a.hot{background:var(--accent);color:#fff}
input[type=search]{width:100%;margin:16px 0 0;padding:10px 12px;font:inherit;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;margin:0 0 10px;overflow:hidden}
.card[hidden],.item[hidden]{display:none}
.card>header{display:flex;gap:10px;align-items:baseline;justify-content:space-between;padding:12px 14px 6px}
.card>header b{font-size:15px}.card>header span{color:var(--muted);font-size:13px}
.item{padding:8px 14px 12px;border-top:1px solid var(--line)}
.item:first-of-type{border-top:0}
.subj{font-weight:600;overflow-wrap:anywhere}
.snip{color:var(--muted);font-size:13.5px;margin:2px 0 6px;overflow-wrap:anywhere}
.why{font-size:12.5px;color:var(--muted)}
.why em{font-style:normal;padding:1px 7px;border-radius:999px;background:var(--chip);margin-right:6px}
.acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.acts a{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:9px;border:1px solid var(--line);background:var(--paper);color:var(--ink);text-decoration:none;font-size:14px;font-weight:550}
.acts a.main{background:var(--accent);border-color:var(--accent);color:#fff}
.acts .note{align-self:center;font-size:12.5px;color:var(--muted)}
details.fold{margin:0 0 10px}
details.fold>summary{cursor:pointer;list-style:none;padding:12px 14px;background:var(--paper);border:1px solid var(--line);border-radius:12px;font-weight:600}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary span{color:var(--muted);font-weight:400;margin-left:8px;font-size:13.5px}
details.fold[open]>summary{border-bottom-left-radius:0;border-bottom-right-radius:0}
details.fold>.inner{border:1px solid var(--line);border-top:0;border-radius:0 0 12px 12px;background:var(--paper)}
.more>summary{cursor:pointer;padding:10px 14px;color:var(--accent);border-top:1px solid var(--line);font-size:14px}
.empty{padding:18px 14px;color:var(--muted);background:var(--paper);border:1px dashed var(--line);border-radius:12px}
@media (max-width:520px){main{padding:14px 12px 72px}.acts a{flex:1 1 auto;justify-content:center}}
"""

JS = """
const h=document.getElementById('health'),t=Date.parse(h.dataset.runAt);
if(t){const hrs=(Date.now()-t)/36e5,when=new Date(t).toLocaleString([],{weekday:'short',hour:'2-digit',minute:'2-digit'});
 h.querySelector('[data-when]').textContent=when;
 if(hrs>%d){h.classList.add('stale');h.querySelector('[data-state]').textContent='STALE: last run was '+Math.round(hrs)+'h ago. The cron may be failing.';}}
const q=document.getElementById('q');
q.addEventListener('input',()=>{const s=q.value.trim().toLowerCase();
 document.querySelectorAll('.item').forEach(i=>{i.hidden=!!s&&!i.dataset.t.includes(s)});
 document.querySelectorAll('.card').forEach(c=>{c.hidden=!!s&&!c.querySelector('.item:not([hidden])')});
 if(s)document.querySelectorAll('details.fold,details.more').forEach(d=>d.open=true);});
""" % STALE_HOURS


def _hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


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
    who = f"?authuser={escape(account, quote=True)}" if account else ""
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


def _item(r, account, unsub=False):
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
    return (f'<div class="item" data-t="{title}"><div class="subj">{subject}</div>'
            f'<div class="snip">{sender}: {snippet}</div>'
            f'<div class="why"><em>{escape(r["category"])} {r["confidence"]:.2f}</em>{escape(done)}{status}'
            f'{(" · " + reason) if reason else ""}</div>'
            f'<div class="acts"><a class="main" href="{_gmail_url(r, account)}" target="_blank" rel="noopener noreferrer">Open in Gmail</a>'
            f'{_unsub(r) if unsub else ""}</div></div>')


GROUP_SHOWN = 2  # a sender with many near-identical mails shows its top few; the rest sit behind one fold


def _groups(rows, account, unsub=False, by_size=True):
    groups = {}
    for r in rows:
        key, name = _sender_key(r)
        groups.setdefault(key, {"name": name, "rows": []})["rows"].append(r)
    ordered = sorted(groups.values(), key=(lambda g: -len(g["rows"])) if by_size else (lambda g: -max(r["confidence"] for r in g["rows"])))
    cards = []
    for g in ordered:
        rs = g["rows"]
        head = "".join(_item(r, account, unsub) for r in rs[:GROUP_SHOWN])
        more = (f'<details class="more"><summary>Show {len(rs) - GROUP_SHOWN} more from {escape(g["name"])}</summary>'
                + "".join(_item(r, account, unsub) for r in rs[GROUP_SHOWN:]) + "</details>") if len(rs) > GROUP_SHOWN else ""
        cards.append(f'<section class="card"><header><b>{escape(g["name"])}</b><span>{len(rs)} message{"s" if len(rs) != 1 else ""}</span></header>{head}{more}</section>')
    return "".join(cards)


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
    mode = ("applied" if applied else "dry")
    state = ("Manual dry run: nothing was changed in Gmail." if not applied else
             f"{done} archived for you. Nothing else was touched." if done else
             "Nothing was actually applied this run (closed gate, cap or a failure).")
    health_cls = "health" + ("" if applied else " dry")
    needs = (_groups(by["needs_you"], account, by_size=False) if by["needs_you"] else
             '<div class="empty">Nothing needs you right now.</div>')
    noise = _groups(by["noise"], account, unsub=True)
    chips = (f'<a class="hot" href="#needs"><b>{len(by["needs_you"])}</b> need you</a>'
             f'<a href="#fyi"><b>{len(by["fyi"])}</b> FYI</a>'
             f'<a href="#noise"><b>{len(by["noise"])}</b> noise</a>'
             f'<a href="#handled"><b>{len(by["handled"])}</b> handled</a>')
    csp = f"default-src 'none'; style-src {_hash(CSS)}; script-src {_hash(JS)}; base-uri 'none'; form-action 'none'"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>Mail</title><style>{CSS}</style></head><body><main>
<h1>Mail</h1>
<div id="health" class="{health_cls}" data-run-at="{escape(run_at or '', quote=True)}"><span>Ran <strong data-when>{escape(run_at or 'unknown time')}</strong></span><span data-state>{escape(state)}</span><span>{len(rows)} messages judged by Jev</span></div>
<div class="chips">{chips}</div>
<input id="q" type="search" placeholder="Search subject or sender" aria-label="Search subject or sender">
<h2 id="needs">Needs you<b>{len(by["needs_you"])}</b></h2>
{needs}
<h2 id="fyi">FYI, no decision needed<b>{len(by["fyi"])}</b></h2>
{_fold("Bank, payment and system alerts", len(by["fyi"]), _groups(by["fyi"], account), "personally addressed, automated sender") or '<div class="empty">No alerts.</div>'}
<h2 id="noise">Noise to clear<b>{len(by["noise"])}</b></h2>
{noise or '<div class="empty">No bulk mail proposed for trash.</div>'}
<h2 id="handled">Handled<b>{len(by["handled"])}</b></h2>
{_fold("Archived or queued to archive", len(by["handled"]), _groups(by["handled"], account)) or '<div class="empty">Nothing archived.</div>'}
</main><script>{JS}</script></body></html>
"""
