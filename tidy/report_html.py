"""Self-contained HTML review page for the owner: proposals, reasons, videos, labels and the commands to act.

No server, no network, no external assets: one file the owner opens locally. It contains API-derived data, so it
states when that data expires. Every string from YouTube or a model is HTML-escaped.
"""

from datetime import datetime
from html import escape

ORDER = ("UNSUBSCRIBE", "REVIEW", "WATCH", "KEEP", "SUBSCRIBE")
SCALE = {"relevance": 3, "apparent_value": 3, "watch_likelihood": 3, "packaging_risk": 1, "evidence_sufficiency": 1}
NAMES = {"relevance": "Relevance", "apparent_value": "Value", "watch_likelihood": "Watch fit",
         "packaging_risk": "Packaging risk", "evidence_sufficiency": "Evidence"}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#14171c;--dim:#5b6472;--line:#dfe3e8;--accent:#0f8a5f;--bad:#c2372f;--warn:#a86a00}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e6edf3;--dim:#8b94a3;--line:#2a313b;--accent:#3ddc97;--bad:#ff7b72;--warn:#e3b341}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}h1{margin:0 0 4px;font-size:26px}
.meta,.note{color:var(--dim);font-size:13px}.gate{margin:12px 0;padding:10px 14px;border:1px solid var(--line);border-radius:8px;background:var(--card)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.chips button{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);cursor:pointer}
.chips button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}
article{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
article h2{margin:0;font-size:18px}article h2 a{color:inherit}.pill{display:inline-block;margin-left:8px;padding:1px 9px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid var(--line)}
.UNSUBSCRIBE .pill{color:var(--bad);border-color:var(--bad)}.SUBSCRIBE .pill,.KEEP .pill{color:var(--accent);border-color:var(--accent)}.REVIEW .pill{color:var(--warn);border-color:var(--warn)}
ul{margin:6px 0;padding-left:20px}.dims{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0}
.dim span{display:block;font-size:12px;color:var(--dim)}.bar{height:6px;background:var(--line);border-radius:3px;margin-top:3px}.risk .bar i{background:var(--warn)}.bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
details{margin:8px 0}summary{cursor:pointer;color:var(--dim)}code{display:block;margin:4px 0;padding:6px 8px;background:var(--bg);border:1px solid var(--line);border-radius:6px;font:12px ui-monospace,monospace;overflow-x:auto}
.hidden{display:none}
"""

JS = """
const chips=[...document.querySelectorAll('.chips button')];
chips.forEach(b=>b.addEventListener('click',()=>{chips.forEach(c=>c.setAttribute('aria-pressed',c===b));
document.querySelectorAll('article').forEach(a=>a.classList.toggle('hidden',b.dataset.f!=='ALL'&&a.dataset.action!==b.dataset.f));}));
"""


def render(proposals, judgments, samples, labels, gate):
    by_j, by_s = {j.channel_id: j for j in judgments}, {s.channel_id: s for s in samples}
    ordered = sorted(proposals, key=lambda p: (ORDER.index(p.action), p.channel_id))
    counts = {a: sum(p.action == a for p in ordered) for a in ORDER if any(p.action == a for p in ordered)}
    expires = min((s.expires_at for s in samples), default=None)
    chips = "".join(f'<button type="button" data-f="{a}" aria-pressed="false">{a} {n}</button>' for a, n in counts.items())
    gate_text = ("open: automatic actions are allowed within caps" if gate["open"]
                 else "closed: " + "; ".join(gate["reasons"]) + ". Nothing acts automatically.")
    cards = "\n".join(_card(p, by_s[p.channel_id], by_j[p.channel_id], labels.get(p.channel_id)) for p in ordered)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Tidy proposals</title><style>{CSS}</style></head><body><main>
<h1>Tidy proposals</h1>
<p class="meta">{len(ordered)} channels. Read-only page: it changes nothing. Run the commands shown on each card yourself.</p>
<div class="gate"><strong>Calibration gate:</strong> {escape(gate_text)}</div>
<p class="note">This page holds data from the YouTube API{f" that must be deleted or refreshed by {escape(expires[:10])}" if expires else ""}. Keep it under .tidy/ and delete it after that date.</p>
<div class="chips"><button type="button" data-f="ALL" aria-pressed="true">All {len(ordered)}</button>{chips}</div>
{cards}
</main><script>{JS}</script></body></html>
"""


def _card(p, s, j, label):
    dims = "".join(_dim(name, a) for name, a in j.answers.items())
    age = ""
    if s.newest_published_at:
        newest = datetime.fromisoformat(s.newest_published_at.replace("Z", "+00:00"))
        days = (datetime.fromisoformat(s.fetched_at) - newest).days
        age = f", newest upload {days} day{'' if days == 1 else 's'} old"
    videos = "".join(f'<li><a href="{escape(v["url"], quote=True)}">{escape(v["title"])}</a></li>' for v in s.videos)
    signals = "".join(f"<li>{escape(x)}</li>" for x in p.signals) or "<li>none</li>"
    cid = escape(p.channel_id, quote=True)
    approve = f'<code>tidy approve {cid} --note "why"</code>' if p.action == "UNSUBSCRIBE" else ""
    return f"""<article class="{p.action}" data-action="{p.action}" id="{cid}">
<h2><a href="https://www.youtube.com/channel/{cid}">{escape(s.title)}</a><span class="pill">{p.action}</span></h2>
<p class="meta">Evidence: {s.coverage["collected"]} of {s.coverage["requested"]} videos{age}. Owner label: {escape(label or "none")}</p>
<ul>{signals}</ul><div class="dims">{dims}</div>
<details><summary>Recent videos ({len(s.videos)})</summary><ul>{videos}</ul></details>
<details><summary>Commands</summary>{approve}<code>tidy label {cid} keep</code><code>tidy label {cid} drop</code><code>tidy label {cid} unsure</code></details>
</article>"""


def _dim(name, answer):
    value = answer["score"] if "score" in answer else answer["noul"]
    top = SCALE.get(name, 1)
    shown = f"{value:.1f} / {top}" if top == 3 else f"{value:.2f}"
    return (f'<div class="dim{" risk" if name == "packaging_risk" else ""}"><span>{escape(NAMES.get(name, name))}: {shown}</span>'
            f'<div class="bar"><i style="width:{max(0, min(100, value / top * 100)):.0f}%"></i></div></div>')
