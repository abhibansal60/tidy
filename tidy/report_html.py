"""Self-contained HTML review page for the owner: a map of the feed, then one row per channel with the evidence.

No server, no network, no external assets: one file opened locally. It holds API-derived data, so it states when that
data expires. Every string from YouTube or a model is HTML-escaped; only https://www.youtube.com links are linked; the
CSP allows only this page's own script and style, by hash.
"""

import base64
from datetime import datetime
import hashlib
from html import escape
import re
import shlex

ORDER = ("UNSUBSCRIBE", "REVIEW", "WATCH", "KEEP", "SUBSCRIBE")
LABEL = {"UNSUBSCRIBE": "Unsubscribe", "REVIEW": "Review", "WATCH": "Watch", "KEEP": "Keep", "SUBSCRIBE": "Subscribe"}
SCALE = {"relevance": 3, "apparent_value": 3, "watch_likelihood": 3, "packaging_risk": 1, "evidence_sufficiency": 1}
NAMES = {"relevance": "Relevance", "apparent_value": "Value", "watch_likelihood": "Watch fit",
         "packaging_risk": "Packaging risk", "evidence_sufficiency": "Evidence"}
YOUTUBE = "https://www.youtube.com/"
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")

CSS = """
:root{--ground:#EDF0EE;--paper:#FFFFFF;--ink:#16211D;--muted:#52605A;--line:#D3DAD6;--keep:#1A6650;--unsub:#A0342A;--review:#7F5300;--subscribe:#2A4FA0;--watch:#52605A}
@media (prefers-color-scheme:dark){:root{--ground:#101614;--paper:#171E1B;--ink:#E2E9E5;--muted:#93A39B;--line:#2B3631;--keep:#58C9A0;--unsub:#FF8A7A;--review:#E0B04A;--subscribe:#8FB0FF;--watch:#93A39B}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 20px 96px}
h1{margin:0;font:600 32px/1.15 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;letter-spacing:-.01em}
.lede{margin:10px 0 0;max-width:62ch;color:var(--muted)}
.notice{margin:18px 0 0;padding:12px 16px;border-left:3px solid var(--review);background:var(--paper);max-width:70ch}
.notice[hidden]{display:none}
h2{margin:44px 0 6px;font:600 20px/1.2 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
.map{width:100%;height:auto;display:block;margin-top:10px;background:var(--paper);border:1px solid var(--line)}
.map text{fill:var(--muted);font:12px system-ui,sans-serif}.map .grid{stroke:var(--line);stroke-width:1}
.map a circle{stroke:var(--paper);stroke-width:1.5}.map a:hover circle,.map a:focus circle{stroke:var(--ink);stroke-width:2}
.k-UNSUBSCRIBE{background:var(--unsub)}.k-REVIEW{background:var(--review)}.k-KEEP{background:var(--keep)}.k-WATCH{background:var(--watch)}.k-SUBSCRIBE{background:var(--subscribe)}
.key{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
.dot-UNSUBSCRIBE{fill:var(--unsub)}.dot-REVIEW{fill:var(--review)}.dot-KEEP{fill:var(--keep)}.dot-WATCH{fill:var(--watch)}.dot-SUBSCRIBE{fill:var(--subscribe)}
.tools{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:16px 0 4px}
.tools button{font:inherit;padding:4px 0;background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);cursor:pointer}
.tools button[aria-pressed=true]{color:var(--ink);border-bottom-color:var(--ink)}
.tools input{font:inherit;padding:6px 10px;border:1px solid var(--line);background:var(--paper);color:var(--ink);min-width:200px;margin-left:auto}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.row{border-top:1px solid var(--line);border-left:4px solid var(--watch)}
.row:last-of-type{border-bottom:1px solid var(--line)}.row[hidden]{display:none}
.row.UNSUBSCRIBE{border-left-color:var(--unsub)}.row.REVIEW{border-left-color:var(--review)}.row.KEEP{border-left-color:var(--keep)}.row.SUBSCRIBE{border-left-color:var(--subscribe)}
summary{display:grid;grid-template-columns:1fr auto auto auto;gap:4px 20px;align-items:baseline;padding:12px 8px 12px 14px;cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
summary:hover{background:var(--paper)}
.name b{font:600 17px/1.3 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}.name span{display:block;color:var(--muted);font-size:13.5px}
.num{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13.5px;white-space:nowrap}.num b{color:var(--ink);font-weight:600}
.verdict{font-weight:600;min-width:6.5em;text-align:right}
.UNSUBSCRIBE .verdict{color:var(--unsub)}.REVIEW .verdict{color:var(--review)}.KEEP .verdict{color:var(--keep)}.SUBSCRIBE .verdict{color:var(--subscribe)}
.body{padding:4px 14px 20px;display:grid;gap:16px;max-width:76ch}
.body h3{margin:0 0 4px;font:600 15px/1.3 system-ui,sans-serif}
.body ul{margin:0;padding-left:1.1em}.body table{border-collapse:collapse;font-variant-numeric:tabular-nums}
.body th{font-weight:400;color:var(--muted);text-align:left;padding:2px 22px 2px 0}.body td{padding:2px 22px 2px 0}
code{display:block;margin:3px 0;padding:6px 10px;background:var(--paper);border:1px solid var(--line);font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;overflow-x:auto;user-select:all}
.hint{color:var(--muted);font-size:13.5px;margin:2px 0 6px}
a{color:inherit}
@media (max-width:640px){main{padding:24px 14px 72px}summary{grid-template-columns:1fr auto}.num{grid-column:1}.verdict{grid-row:1;grid-column:2}}
"""

JS = """
const rows=[...document.querySelectorAll('.row')],tabs=[...document.querySelectorAll('.tools button')],q=document.getElementById('q');
let f='ALL';
function apply(){const s=q.value.trim().toLowerCase();rows.forEach(r=>{r.hidden=(f!=='ALL'&&r.dataset.action!==f)||(s&&!r.dataset.title.includes(s))});}
tabs.forEach(b=>b.addEventListener('click',()=>{f=b.dataset.f;tabs.forEach(t=>t.setAttribute('aria-pressed',t===b));apply();}));
q.addEventListener('input',apply);
const stale=document.getElementById('stale');if(stale&&Date.parse(stale.dataset.expires)<Date.now())stale.hidden=false;
"""


def _hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def _tidy(data_dir):
    return "tidy" if data_dir == ".tidy" else f"tidy --data-dir {shlex.quote(str(data_dir))}"


def _safe_url(url, allow_prefix=YOUTUBE):
    return url if isinstance(url, str) and url.startswith(allow_prefix) else None


def render(proposals, judgments, samples, labels, gate, data_dir=".tidy"):
    by_j, by_s = {j.channel_id: j for j in judgments}, {s.channel_id: s for s in samples}
    ordered = sorted(proposals, key=lambda p: (ORDER.index(p.action), p.channel_id))
    counts = {a: sum(p.action == a for p in ordered) for a in ORDER if any(p.action == a for p in ordered)}
    expires = min((s.expires_at for s in samples), default=None)
    tabs = f'<button type="button" data-f="ALL" aria-pressed="true">All {len(ordered)}</button>' + "".join(
        f'<button type="button" data-f="{a}" aria-pressed="false"><i class="key k-{a}"></i>{LABEL[a]} {n}</button>' for a, n in counts.items())
    if gate["open"]:
        gate_text = ("Calibration gate open for the current labels. Automatic actions still need an owner-started "
                     "run of tidy act and stay within the per-run caps.")
    else:
        gate_text = "Calibration gate closed: " + "; ".join(gate["reasons"]) + ". Nothing acts automatically."
    retention = (f'<p class="lede">Contains data from the YouTube API. Delete or refresh by {escape(expires[:10])}. '
                 f'Keep this file under .tidy/ and delete it yourself; nothing removes it for you.</p>'
                 f'<p class="notice" id="stale" data-expires="{escape(expires, quote=True)}" hidden>This page is past its '
                 f'retention date. Delete it and run tidy propose --html again.</p>') if expires else ""
    rows = "\n".join(_row(p, by_s[p.channel_id], by_j[p.channel_id], labels.get(p.channel_id), data_dir) for p in ordered)
    csp = (f"default-src 'none'; style-src {_hash(CSS)}; script-src {_hash(JS)}; base-uri 'none'; form-action 'none'")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>Tidy proposals</title><style>{CSS}</style></head><body><main>
<h1>Tidy proposals</h1>
<p class="lede">{len(ordered)} channels judged. This page only shows evidence: it changes nothing, and every command below is one you run yourself.</p>
<p class="lede">{escape(gate_text)}</p>
{retention}
<h2>The feed on one page</h2>
{_map(ordered, by_j)}
<h2>Channels</h2>
<div class="tools">{tabs}<input id="q" type="search" placeholder="Search titles" aria-label="Search channel titles"></div>
{rows}
</main><script>{JS}</script></body></html>
"""


def _map(ordered, by_j):
    use_watch = all("watch_likelihood" in by_j[p.channel_id].answers for p in ordered) and bool(ordered)
    xname = "watch_likelihood" if use_watch else "relevance"
    left, top, width, height = 56, 16, 780, 290

    def pos(x, y):
        return left + x / 3 * width, top + (1 - y / 3) * height

    grid = "".join(f'<line class="grid" x1="{left}" x2="{left + width}" y1="{top + (1 - v / 3) * height:.0f}" y2="{top + (1 - v / 3) * height:.0f}"/>'
                   f'<text x="{left - 10}" y="{top + (1 - v / 3) * height + 4:.0f}" text-anchor="end">{v}</text>'
                   f'<text x="{left + v / 3 * width:.0f}" y="{top + height + 22}" text-anchor="middle">{v}</text>' for v in (0, 1, 2, 3))
    dots = ""
    for p in ordered:
        a = by_j[p.channel_id].answers
        if "apparent_value" not in a or xname not in a:
            continue
        x, y = pos(a[xname]["score"], a["apparent_value"]["score"])
        dots += (f'<a href="#{escape(p.channel_id, quote=True)}"><circle class="dot-{p.action}" cx="{x:.1f}" cy="{y:.1f}" r="5">'
                 f'<title>{escape(_title(p, a, xname))}</title></circle></a>')
    xlabel = "Watch fit (Jev's guess that you would watch it)" if use_watch else "Relevance to your interests"
    return (f'<svg class="map" viewBox="0 0 860 350" role="img" aria-label="Each channel by value and {escape(xlabel)}">{grid}{dots}'
            f'<text x="{left + width / 2}" y="344" text-anchor="middle">{escape(xlabel)}</text>'
            f'<text x="14" y="{top + height / 2}" transform="rotate(-90 14 {top + height / 2})" text-anchor="middle">Value (0 to 3)</text></svg>'
            f'<p class="hint">Each dot is a channel, colored by what Tidy proposes. Jev scores content quality and fit; it does not know what you keep, which is why the dots do not sort cleanly. Select a dot to jump to its row.</p>')


def _title(p, a, xname):
    return f"{LABEL[p.action]}: value {a['apparent_value']['score']:.1f}, {NAMES[xname].lower()} {a[xname]['score']:.1f}"


def _row(p, s, j, label, data_dir):
    a = j.answers
    cid = p.channel_id
    link = f"{YOUTUBE}channel/{cid}" if SAFE_ID.fullmatch(cid) else None
    name = escape(s.title)
    opened = f'<p class="hint"><a href="{escape(link, quote=True)}">Open the channel on YouTube</a></p>' if link else ""
    why = escape(p.signals[0]) if p.signals else "no signals"
    value = a.get("apparent_value", {}).get("score")
    fit = a.get("watch_likelihood", {}).get("score")
    days = ""
    if s.newest_published_at:
        newest = datetime.fromisoformat(s.newest_published_at.replace("Z", "+00:00"))
        n = (datetime.fromisoformat(s.fetched_at) - newest).days
        days = f", newest upload {n} day{'' if n == 1 else 's'} old"
    dims = "".join(_dim(name_, a.get(name_)) for name_ in SCALE)
    videos = "".join(_video(v) for v in s.videos) or "<li>none collected</li>"
    signals = "".join(f"<li>{escape(x)}</li>" for x in p.signals) or "<li>none</li>"
    t, sid = _tidy(data_dir), escape(cid, quote=True)
    act = ""
    if p.action == "UNSUBSCRIBE":
        act = (f'<p class="hint">Approving queues the change. Check the dry run before you apply it.</p>'
               f"<code>{t} approve {sid} --note \"why\"</code><code>{t} unsubscribe</code>"
               f"<code>{t} unsubscribe --execute</code>")
    return f"""<details class="row {p.action}" id="{sid}" data-action="{p.action}" data-title="{escape(s.title.lower(), quote=True)}">
<summary><span class="name"><b>{name}</b><span>{why}</span></span>
<span class="num">Value <b>{"n/a" if value is None else f"{value:.1f}"}</b></span><span class="num">Watch fit <b>{"n/a" if fit is None else f"{fit:.1f}"}</b></span>
<span class="verdict">{LABEL[p.action]}</span></summary>
<div class="body">
<div><h3>Why</h3><ul>{signals}</ul>{opened}</div>
<div><h3>Jev's scores</h3><table>{dims}</table>
<p class="hint">Evidence: {s.coverage["collected"]} of {s.coverage["requested"]} videos{days}. Your label: {escape(label or "none")}.</p></div>
<div><h3>Recent videos</h3><ul>{videos}</ul></div>
<div><h3>Record your decision</h3>{act}<code>{t} label {sid} keep</code><code>{t} label {sid} drop</code><code>{t} label {sid} unsure</code></div>
</div>
</details>"""


def _video(v):
    url = _safe_url(v.get("url"))
    title = escape(v["title"])
    return f'<li><a href="{escape(url, quote=True)}">{title}</a></li>' if url else f"<li>{title}</li>"


def _dim(name, answer):
    if answer is None:
        return f"<tr><th>{NAMES[name]}</th><td>not judged</td><td></td></tr>"
    value = answer["score"] if "score" in answer else answer["noul"]
    top = SCALE[name]
    shown = f"{value:.1f} of {top}" if top == 3 else f"{value:.2f}"
    conf = f"confidence {answer['confidence']:.2f}" if "confidence" in answer else ""
    return f"<tr><th>{NAMES[name]}</th><td>{shown}</td><td>{conf}</td></tr>"
