"""Self-contained HTML dashboard for a mail-triage run: one row per message, filterable by action.

No server, no network, no external assets: one file opened locally. Every string from Gmail or a
model is HTML-escaped; the CSP allows only this page's own script and style, by hash. Mirrors the
shape of `report_html.py` for the YouTube side, simplified for a flat category+action list rather
than a scored map.
"""

import base64
from email.utils import parseaddr
from html import escape
import hashlib

ORDER = ("REVIEW", "ARCHIVE", "TRASH", "SPAM", "KEEP")
# What's proposed (verdict badge when not yet applied) vs. what actually happened (when outcome == "applied").
PROPOSED_LABEL = {"REVIEW": "Review", "ARCHIVE": "Archive", "TRASH": "Trash", "SPAM": "Spam", "KEEP": "Keep"}
DONE_LABEL = {"ARCHIVE": "Archived", "TRASH": "Trashed", "SPAM": "Marked spam"}
OUTCOME_LABEL = {"applied": "Applied", "held": "Held for review", None: None}

CSS = """
:root{--ground:#EDF0EE;--paper:#FFFFFF;--ink:#16211D;--muted:#52605A;--line:#D3DAD6;--keep:#1A6650;--archive:#52605A;--trash:#7A4A9E;--spam:#A0342A;--review:#7F5300}
@media (prefers-color-scheme:dark){:root{--ground:#101614;--paper:#171E1B;--ink:#E2E9E5;--muted:#93A39B;--line:#2B3631;--keep:#58C9A0;--archive:#93A39B;--trash:#C79BEB;--spam:#FF8A7A;--review:#E0B04A}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 20px 96px}
h1{margin:0;font:600 32px/1.15 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;letter-spacing:-.01em}
.lede{margin:10px 0 0;max-width:66ch;color:var(--muted)}
.tools{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:24px 0 4px}
.tools button{font:inherit;padding:4px 0;background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);cursor:pointer}
.tools button[aria-pressed=true]{color:var(--ink);border-bottom-color:var(--ink)}
.tools input{font:inherit;padding:6px 10px;border:1px solid var(--line);background:var(--paper);color:var(--ink);min-width:200px;margin-left:auto}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.row{border-top:1px solid var(--line);border-left:4px solid var(--archive)}
.row:last-of-type{border-bottom:1px solid var(--line)}.row[hidden]{display:none}
.row.REVIEW{border-left-color:var(--review)}.row.ARCHIVE{border-left-color:var(--archive)}.row.TRASH{border-left-color:var(--trash)}.row.SPAM{border-left-color:var(--spam)}.row.KEEP{border-left-color:var(--keep)}
summary{display:grid;grid-template-columns:1fr auto auto;gap:4px 20px;align-items:baseline;padding:12px 8px 12px 14px;cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
summary:hover{background:var(--paper)}
.name b{font:600 16px/1.3 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}.name span{display:block;color:var(--muted);font-size:13.5px}
.num{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13.5px;white-space:nowrap}
.verdict{font-weight:600;min-width:7em;text-align:right}
.REVIEW .verdict{color:var(--review)}.ARCHIVE .verdict{color:var(--archive)}.TRASH .verdict{color:var(--trash)}.SPAM .verdict{color:var(--spam)}.KEEP .verdict{color:var(--keep)}
.body{padding:4px 14px 20px;display:grid;gap:10px;max-width:76ch;color:var(--muted);font-size:14px}
.key{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
.senders{margin:28px 0 8px;font-size:14px}.senders h2{font:600 18px/1.3 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;margin:0 0 6px}
.senders ol{margin:0;padding-left:22px;color:var(--muted)}.senders li{margin:2px 0}.senders a{color:var(--ink)}
.k-REVIEW{background:var(--review)}.k-ARCHIVE{background:var(--archive)}.k-TRASH{background:var(--trash)}.k-SPAM{background:var(--spam)}.k-KEEP{background:var(--keep)}
@media (max-width:640px){main{padding:24px 14px 72px}summary{grid-template-columns:1fr auto}.num{grid-column:1}.verdict{grid-row:1;grid-column:2}}
"""

JS = """
const rows=[...document.querySelectorAll('.row')],tabs=[...document.querySelectorAll('.tools button')],q=document.getElementById('q');
let f='ALL';
function apply(){const s=q.value.trim().toLowerCase();rows.forEach(r=>{r.hidden=(f!=='ALL'&&r.dataset.action!==f)||(s&&!r.dataset.title.includes(s))});}
tabs.forEach(b=>b.addEventListener('click',()=>{f=b.dataset.f;tabs.forEach(t=>t.setAttribute('aria-pressed',t===b));apply();}));
q.addEventListener('input',apply);
"""


def _hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def render(rows, applied=False):
    """`rows`: dicts with id, subject, sender, category, confidence, action, signals, outcome (outcome optional).
    `applied`: whether this run attempted --apply at all (distinct from whether any row's outcome=="applied")."""
    ordered = sorted(rows, key=lambda r: (ORDER.index(r["action"]), -r["confidence"]))
    counts = {a: sum(r["action"] == a for r in ordered) for a in ORDER if any(r["action"] == a for r in ordered)}
    tabs = f'<button type="button" data-f="ALL" aria-pressed="true">All {len(ordered)}</button>' + "".join(
        f'<button type="button" data-f="{a}" aria-pressed="false"><i class="key k-{a}"></i>{PROPOSED_LABEL[a]} {n}</button>' for a, n in counts.items())
    lede = f"{len(ordered)} messages classified by Jev." + " " + _lede_tail(ordered, applied)
    body_rows = "\n".join(_row(r) for r in ordered)
    csp = f"default-src 'none'; style-src {_hash(CSS)}; script-src {_hash(JS)}; base-uri 'none'; form-action 'none'"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>Tidy mail triage</title><style>{CSS}</style></head><body><main>
<h1>Tidy mail triage</h1>
<p class="lede">{escape(lede)}</p>
{_senders(ordered)}
<div class="tools">{tabs}<input id="q" type="search" placeholder="Search subject/sender" aria-label="Search subject or sender"></div>
{body_rows}
</main><script>{JS}</script></body></html>
"""


def _lede_tail(ordered, applied):
    if not applied:
        return "Nothing was applied to Gmail; this is a dry run."
    done = sum(r.get("outcome") == "applied" for r in ordered)
    if done == 0:
        return ("Nothing was actually applied this run (closed gate, cap, or a failure), so everything below is "
               "a held proposal. Check the run's `gate`/`action_counts`, then `tidy mail-act --execute` for TRASH/SPAM.")
    return (f"{done} action(s) below were applied to Gmail. The rest are held for your review "
           "(`tidy mail-act --execute`) or were never touched (KEEP/REVIEW).")


SENDERS_SHOWN = 15


def _senders(rows):
    """Unsubscribe shortlist: bulk senders (not KEEP/REVIEW) that carry an unsubscribe link, most messages first.
    One click per sender instead of one per email; still a link the owner clicks, never fetched by Tidy."""
    groups = {}
    for r in rows:
        if r["action"] in ("KEEP", "REVIEW") or not _unsub_links(r):
            continue
        name, addr = parseaddr(r["sender"])
        key = (addr or r["sender"]).casefold()
        entry = groups.setdefault(key, {"name": name or addr or r["sender"], "count": 0, "row": r})
        entry["count"] += 1
    if not groups:
        return ""
    top = sorted(groups.values(), key=lambda g: -g["count"])[:SENDERS_SHOWN]
    items = "".join(f"<li>{escape(g['name'])} ({g['count']}): {_unsub_links(g['row'])}</li>" for g in top)
    return (f'<section class="senders"><h2>Unsubscribe shortlist</h2><p>{len(groups)} bulk senders offer an unsubscribe '
            f"link. Tidy never clicks these for you.</p><ol>{items}</ol></section>")


def _unsub_line(r):
    links = _unsub_links(r)
    return f"<p>{links}</p>" if links else ""


def _unsub_links(r):
    """A link the owner clicks themselves: Tidy never fetches or emails an unsubscribe link on its own."""
    links = r.get("unsubscribe")
    if not links:
        return ""
    parts = []
    if (links.get("http") or "").lower().startswith(("http://", "https://")):
        parts.append(f'<a href="{escape(links["http"], quote=True)}" rel="noopener noreferrer" target="_blank">Unsubscribe link</a>')
    if (links.get("mailto") or "").lower().startswith("mailto:"):
        parts.append(f'<a href="{escape(links["mailto"], quote=True)}">Unsubscribe by email</a>')
    return " / ".join(parts)


def _row(r):
    subject = escape(r["subject"] or "(no subject)")
    sender = escape(r["sender"])
    signals = "".join(f"<li>{escape(s)}</li>" for s in r.get("signals", [])) or "<li>none</li>"
    raw_outcome = r.get("outcome")
    outcome = OUTCOME_LABEL.get(raw_outcome, raw_outcome)  # unrecognized values (e.g. "error: ...") still shown, not hidden
    outcome_line = f"<p>Outcome: {escape(outcome)}</p>" if outcome else ""
    verdict = DONE_LABEL[r["action"]] if raw_outcome == "applied" and r["action"] in DONE_LABEL else PROPOSED_LABEL[r["action"]]
    return f"""<details class="row {r['action']}" data-action="{r['action']}" data-title="{escape((subject + ' ' + sender).lower(), quote=True)}">
<summary><span class="name"><b>{subject}</b><span>{sender}</span></span>
<span class="num">{escape(r['category'])} ({r['confidence']:.2f})</span>
<span class="verdict">{verdict}</span></summary>
<div class="body"><ul>{signals}</ul>{outcome_line}{_unsub_line(r)}</div>
</details>"""
