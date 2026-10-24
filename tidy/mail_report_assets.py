"""Style and script for the mail dashboard (`mail_report_html`). Hash-pinned by its CSP, so edit both together."""


CSS = """
:root{--ground:#F4F5F7;--paper:#FFFFFF;--ink:#14181F;--muted:#5A6472;--line:#DDE1E7;--accent:#1F5FD0;--warn:#9A5B00;--warnbg:#FFF4DC;--bad:#B3261E;--badbg:#FDECEA;--ok:#1B6E4A;--chip:#E9ECF1}
@media (prefers-color-scheme:dark){:root{--ground:#0F1218;--paper:#171B23;--ink:#E7EAF0;--muted:#97A1B0;--line:#262C37;--accent:#7FA8FF;--warn:#F0B54A;--warnbg:#2B2410;--bad:#FF8A80;--badbg:#341716;--ok:#6FD3A6;--chip:#212733}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 14px 88px}
h2{margin:28px 0 8px;font-size:13px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
h2 b{color:var(--ink);font-size:15px;letter-spacing:0;margin-left:6px}
.tabs{position:sticky;top:0;z-index:5;display:flex;align-items:stretch;gap:4px;margin:-20px -14px 0;padding:0 14px;background:var(--ground);border-bottom:1px solid var(--line)}
.tabs a{padding:14px 16px 12px;border-bottom:3px solid transparent;color:var(--muted);font-size:16px;font-weight:600;text-decoration:none}
.tabs a[aria-current=page]{color:var(--ink);border-bottom-color:var(--accent)}
.tabs button{margin-left:auto;font:inherit;font-size:14px;color:var(--accent);background:none;border:0;padding:0 4px;cursor:pointer}
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

# %d: the hours after which the page calls the run stale (mail_report_html.STALE_HOURS).
JS_TEMPLATE = """
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
"""
