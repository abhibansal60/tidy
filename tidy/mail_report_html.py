"""Self-contained HTML page for a mail-triage run, organised by what the owner has to do.

Sections: Needs you (decisions), FYI (alerts that need no decision), Noise to clear (bulk senders, grouped), Handled
(auto-archived or queued). No server, no network, no external assets: one file. Every string from Gmail or a
model is HTML-escaped; the CSP allows only this page's own script and style, by hash. Buttons that change Gmail are
buttons call /api/mail/act on the same origin (the tidy-mail app), which is the only network access the CSP allows.
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
main{max-width:1180px;margin:0 auto;padding:20px 14px 88px}
h1{display:inline-block;margin:0 14px 4px 0;font-size:22px;font-weight:650;letter-spacing:-.01em}
h2{margin:28px 0 8px;font-size:13px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
h2 b{color:var(--ink);font-size:15px;letter-spacing:0;margin-left:6px}
.nav{display:inline-block}.nav a{color:var(--accent);font-size:14px;margin-right:12px}.nav button{font:inherit;font-size:14px;color:var(--accent);background:none;border:0;padding:0;cursor:pointer}
.health{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;padding:10px 12px;margin:10px 0 0;border:1px solid var(--line);background:var(--paper);border-radius:10px;font-size:14px;color:var(--muted)}
.health.stale,.health.dry{background:var(--warnbg);border-color:var(--warn);color:var(--warn)}
.health.stale{background:var(--badbg);border-color:var(--bad);color:var(--bad)}
.health strong{color:inherit}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.chips a{display:inline-flex;gap:6px;align-items:baseline;padding:6px 12px;border-radius:999px;background:var(--chip);color:var(--ink);text-decoration:none;font-size:14px}
.chips a b{font-variant-numeric:tabular-nums}
input[type=search]{width:100%;margin:16px 0 0;padding:10px 12px;font:inherit;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;align-items:start;margin-top:14px}
.tab[hidden]{display:none}
.unsubbar{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;justify-content:space-between;margin-top:14px;padding:10px 14px;border:1px solid var(--line);border-radius:12px;background:var(--paper);font-size:14px;color:var(--muted)}
.unsubbar button{min-height:38px;padding:0 14px;border-radius:9px;border:1px solid var(--accent);background:var(--accent);color:#fff;font:inherit;font-weight:550;cursor:pointer}
.unsubbar button:disabled{opacity:.5;cursor:wait}
.chips a{cursor:pointer}.chips a[aria-selected=true]{background:var(--accent);color:#fff}
.snip{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.card[hidden],.item[hidden]{display:none}
.card>header{display:flex;gap:10px;align-items:baseline;justify-content:space-between;padding:12px 14px 6px}
.card>header b{font-size:15px}.card>header span{color:var(--muted);font-size:13px}
.item{padding:8px 14px 12px;border-top:1px solid var(--line)}
.item:first-of-type{border-top:0}
.subj{font-weight:600;overflow-wrap:anywhere}
.snip{color:var(--muted);font-size:13.5px;margin:2px 0 6px;overflow-wrap:anywhere}
.why{font-size:12.5px;color:var(--muted)}
.why em{font-style:normal;padding:1px 7px;border-radius:999px;background:var(--chip);margin-right:6px}
.acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.acts a{display:inline-flex;align-items:center;min-height:38px;padding:0 11px;border-radius:9px;border:1px solid var(--line);background:var(--paper);color:var(--ink);text-decoration:none;font-size:14px;font-weight:550}
.acts a.main{background:var(--accent);border-color:var(--accent);color:#fff}
.acts .note{align-self:center;font-size:12.5px;color:var(--muted)}
details.fold{margin:0 0 10px}
details.fold>summary{cursor:pointer;list-style:none;padding:12px 14px;background:var(--paper);border:1px solid var(--line);border-radius:12px;font-weight:600}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary span{color:var(--muted);font-weight:400;margin-left:8px;font-size:13.5px}
details.fold[open]>summary{border-bottom-left-radius:0;border-bottom-right-radius:0}
details.fold>.inner{border:1px solid var(--line);border-top:0;border-radius:0 0 12px 12px;background:var(--paper)}
.acts button{display:inline-flex;align-items:center;min-height:38px;padding:0 11px;border-radius:9px;border:1px solid var(--line);background:var(--paper);color:var(--ink);font:inherit;font-size:14px;font-weight:550;cursor:pointer}
.acts button.danger{color:var(--bad)}.acts button:disabled{opacity:.5;cursor:wait}
.bulk{display:flex;flex-wrap:wrap;gap:8px;padding:0 14px 10px}.bulk button{min-height:36px;padding:0 12px;border-radius:9px;border:1px solid var(--line);background:var(--paper);color:var(--ink);font:inherit;font-size:13.5px;cursor:pointer}
.bulk button.danger{color:var(--bad)}
.item.gone{display:none}
#toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:92vw;display:none;gap:12px;align-items:center;padding:10px 14px;border-radius:12px;background:var(--ink);color:var(--ground);font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.25)}
#toast.on{display:flex}#toast.err{background:var(--bad);color:#fff}#toast button{background:none;border:0;color:inherit;text-decoration:underline;font:inherit;cursor:pointer}
.more>summary{cursor:pointer;padding:10px 14px;color:var(--accent);border-top:1px solid var(--line);font-size:14px}
.empty{padding:18px 14px;color:var(--muted);background:var(--paper);border:1px dashed var(--line);border-radius:12px}
@media (max-width:520px){main{padding:14px 12px 72px}.acts a,.acts button{flex:1 1 auto;justify-content:center}}
"""

JS = """
const h=document.getElementById('health'),t=Date.parse(h.dataset.runAt);
if(t){const hrs=(Date.now()-t)/36e5,when=new Date(t).toLocaleString([],{weekday:'short',hour:'2-digit',minute:'2-digit'});
 h.querySelector('[data-when]').textContent=when;
 if(hrs>%d){h.classList.add('stale');h.querySelector('[data-state]').textContent='STALE: last run was '+Math.round(hrs)+'h ago. The cron may be failing.';}}
const tabs=[...document.querySelectorAll('.chips a')],panes=[...document.querySelectorAll('.tab')];
function show(n){panes.forEach(p=>p.hidden=p.dataset.tab!==n);tabs.forEach(a=>a.setAttribute('aria-selected',a.dataset.b===n))}
tabs.forEach(a=>a.addEventListener('click',e=>{e.preventDefault();q.value='';q.dispatchEvent(new Event('input'));show(a.dataset.b);history.replaceState(null,'','#'+a.dataset.b)}));
const born=Date.now();
// A Home Screen app is suspended, not closed: reload when it comes back after a minute, so it never shows an old run.
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-born>60000)location.reload()});
addEventListener('pageshow',e=>{if(e.persisted)location.reload()});
document.getElementById('refresh').addEventListener('click',()=>location.reload());
const q=document.getElementById('q');
q.addEventListener('input',()=>{const s=q.value.trim().toLowerCase();
 document.querySelectorAll('.item').forEach(i=>{i.hidden=!!s&&!i.dataset.t.includes(s)});
 document.querySelectorAll('.card').forEach(c=>{c.hidden=!!s&&!c.querySelector('.item:not([hidden])')});
 if(s){panes.forEach(p=>p.hidden=false);document.querySelectorAll('details.more').forEach(d=>d.open=true)}else show((tabs.find(a=>a.getAttribute('aria-selected')==='true')||tabs[0]).dataset.b)});
show((location.hash.slice(1)&&tabs.some(a=>a.dataset.b===location.hash.slice(1)))?location.hash.slice(1):'needs_you');

const key='tidy:'+h.dataset.runAt,toast=document.getElementById('toast');
let gone=new Set(JSON.parse(localStorage.getItem(key)||'[]')),tt;
const save=()=>{try{localStorage.setItem(key,JSON.stringify([...gone]))}catch(e){}};
function counts(){document.querySelectorAll('.chips a[data-b]').forEach(a=>{a.querySelector('b').textContent=document.querySelectorAll('.item[data-b="'+a.dataset.b+'"]:not(.gone)').length});
 document.querySelectorAll('.card').forEach(c=>{c.hidden=!c.querySelector('.item:not(.gone)')})}
function sync(){document.querySelectorAll('.item').forEach(i=>i.classList.toggle('gone',gone.has(i.dataset.id)));counts()}
function say(msg,undo,err){clearTimeout(tt);toast.className='on'+(err?' err':'');toast.textContent='';const s=document.createElement('span');s.textContent=msg;toast.append(s);
 if(undo){const b=document.createElement('button');b.textContent='Undo';b.onclick=()=>run(undo.op,undo.ids,true);toast.append(b)}
 tt=setTimeout(()=>toast.className='',10000)}
async function post(op,ids){const r=await fetch('/api/mail/act',{method:'POST',headers:{'Content-Type':'application/json','X-Tidy':'1'},body:JSON.stringify({op,ids})});
 const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}
async function run(op,ids,isUndo){document.querySelectorAll('button').forEach(b=>b.disabled=true);
 try{let applied=[],skipped=[],undo=null,last;
  for(let i=0;i<ids.length;i+=50){const j=await post(op,ids.slice(i,i+50));last=j;
   for(const [id,res] of Object.entries(j.results)){(res==='applied'?applied:skipped).push([id,res])}
   if(j.undo)undo=undo?{op:j.undo.op,ids:undo.ids.concat(j.undo.ids)}:j.undo}
  if(op==='unsubscribe'){const res=Object.values(last.results)[0];
   if(res==='requested')markUnsub(ids[0]);say(res==='requested'?'Unsubscribe request sent. The sender accepted it; Tidy will flag it if mail keeps coming.':res==='link_only'?'This sender has no one-click unsubscribe. Use its Unsubscribe link.':res==='failed'?'The sender did not accept the request. Use its Unsubscribe link.':'Blocked: unsafe unsubscribe address.',null,res!=='requested');return}
  const back=op==='inbox'||op==='untrash'||op==='unkeep';
  for(const [id] of applied){back?gone.delete(id):gone.add(id)}
  save();sync();
  const verb={archive:'Archived',inbox:'Moved back',keep:'Kept',unkeep:'Unmarked',trash:'Trashed',untrash:'Restored'}[op];
  say(verb+' '+applied.length+(skipped.length?'. Skipped '+skipped.length+' ('+skipped[0][1].replace('skipped: ','')+')':''),isUndo?null:undo,false)
 }catch(e){say('Failed: '+e.message,null,true)}finally{document.querySelectorAll('button').forEach(b=>b.disabled=false)}}
async function unsubAll(ids){document.querySelectorAll('button').forEach(b=>b.disabled=true);const t={requested:0,link_only:0,failed:0,blocked:0};
 try{for(let i=0;i<ids.length;i++){say('Unsubscribing '+(i+1)+' of '+ids.length+'...',null,false);
   let res;try{const j=await post('unsubscribe',[ids[i]]);res=Object.values(j.results)[0]}catch(e){res='failed'}
   t[res]=(t[res]||0)+1;if(res==='requested')markUnsub(ids[i])}
  say('Requested '+t.requested+' of '+ids.length+(t.link_only+t.failed+t.blocked?'. '+(t.link_only+t.failed+t.blocked)+' need the Unsubscribe link instead.':'.'),null,t.requested===0)
 }finally{document.querySelectorAll('button').forEach(b=>b.disabled=false)}}
function markUnsub(id){const i=document.querySelector('.item[data-id="'+id+'"]');const b=i&&i.querySelector('button[data-op=unsubscribe]');if(b){b.textContent='Requested';b.dataset.op='';b.disabled=true}}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-op]');if(!b)return;
 if(b.dataset.op==='unsub-all'){const ids=b.dataset.ids.split(',');if(confirm('Ask '+ids.length+' senders to unsubscribe you?'))unsubAll(ids);return}
 const ids=b.dataset.ids?b.dataset.ids.split(','):[b.closest('.item').dataset.id];
 if(b.dataset.op==='trash'&&ids.length>5&&!confirm('Trash '+ids.length+' messages?'))return;run(b.dataset.op,ids)});
sync();
// Gmail is the source of truth: what is out of the inbox or kept is hidden on every device, not only the one that clicked.
fetch('/api/mail/state').then(r=>r.ok?r.json():null).then(j=>{if(j){gone=new Set(j.gone);save();sync()}}).catch(()=>{});
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
    return (f'<div class="item" data-id="{escape(r['id'], quote=True)}" data-b="{b}" data-t="{title}"><div class="subj">{subject}</div>'
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
    csp = f"default-src 'none'; style-src {_hash(CSS)}; script-src {_hash(JS)}; base-uri 'none'; form-action 'none'; connect-src 'self'; manifest-src 'self'; img-src 'self'"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Mail">
<meta name="theme-color" content="#1F5FD0">
<title>Mail</title><style>{CSS}</style></head><body><main>
<h1>Mail</h1><nav class="nav"><a href="/jobs">Jobs</a><button type="button" id="refresh" aria-label="Refresh">Refresh</button></nav>
<div id="health" class="{health_cls}" data-run-at="{escape(run_at or '', quote=True)}"><span>Ran <strong data-when>{escape(run_at or 'unknown time')}</strong></span><span data-state>{escape(state)}</span><span>{len(rows)} messages judged by Jev</span></div>
<div class="chips">{chips}</div>
<input id="q" type="search" placeholder="Search subject or sender" aria-label="Search subject or sender">
{body}
</main><div id="toast" role="status" aria-live="polite"></div><script>{JS}</script></body></html>
"""
