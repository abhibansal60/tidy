"""Builds the synthetic review page used for docs/assets/review_page.png (no real channels). Run from the repo root:
    python docs/assets/synthetic_report.py   # writes synthetic.html and synthetic_open.html to the current folder
"""
import random
from datetime import datetime, timedelta, timezone
from tidy import report_html
from tidy.collector import EvidenceSample
from tidy.judge import Judgment
from tidy.proposal import Proposal

random.seed(11)
now = datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)
props, judgments, samples, labels = [], [], [], {}
for i in range(1, 61):
    cid = f"UCsynthetic{i:03d}xxxxxxxxxxxx"
    fit = min(3, max(0, random.gauss(1.6, 0.8)))
    val = min(3, max(0, 0.5 * fit + random.gauss(0.9, 0.7)))
    watched = random.random() < fit / 4
    if val < 0.5 and not watched:
        action, signals = "UNSUBSCRIBE", [f"value low, Jev ({val:.1f})", f"value low, second opinion ({max(val - 0.1, 0):.1f})", "watched 0 times in 42 days"]
    elif watched:
        action, signals = "KEEP", [f"watched {random.randint(1, 9)} times in 42 days"]
    elif i % 9 == 0:
        action, signals = "SUBSCRIBE", [f"value {val:.1f}", f"watched {random.randint(3, 12)} times in 42 days, not subscribed"]
    else:
        action, signals = "REVIEW", ["unwatched in 42 days"] + (["quality high: watch it or drop it"] if val >= 2 else [])
    videos = [{"id": f"v{i}{k}", "title": f"Video {k} from Channel {i:02d}", "description": "", "published_at": "2026-09-01T00:00:00Z",
               "duration": "PT9M", "url": f"https://www.youtube.com/watch?v=v{i}{k}"} for k in range(1, 6)]
    samples.append(EvidenceSample(cid, f"Channel {i:02d}", "", videos, now.isoformat(), (now + timedelta(days=30)).isoformat(),
                                  {"requested": 12, "collected": 12, "unavailable": 0}, "2026-09-12T00:00:00Z", f"h{i}"))
    ans = {"relevance": {"score": min(3, max(0, fit * 0.8 + random.gauss(0.3, 0.4))), "confidence": random.uniform(0.4, 0.9)},
           "apparent_value": {"score": val, "confidence": random.uniform(0.4, 0.9)},
           "watch_likelihood": {"score": fit, "confidence": random.uniform(0.4, 0.9)},
           "packaging_risk": {"noul": random.uniform(0.05, 0.7)}, "evidence_sufficiency": {"noul": random.uniform(0.4, 0.95)}}
    judgments.append(Judgment(cid, f"h{i}", "titles-v2", "jev", ans, {}, 1, now.isoformat()))
    props.append(Proposal(cid, action, signals, "policy-2", f"h{i}"))
    if i % 7 == 0:
        labels[cid] = random.choice(["keep", "drop"])
html = report_html.render(props, judgments, samples, labels, {"open": False, "reasons": ["9 labels, need 30"]})
open("synthetic.html", "w").write(html)
# open the first Unsubscribe row for the screenshot
first = html.index('<details class="row UNSUBSCRIBE"')
open("synthetic_open.html", "w").write(html[:first] + html[first:].replace("<details ", "<details open ", 1))
