"""Push a short summary of the newest mail-triage run to the owner's phone via ntfy, only when something needs them.

Run after the daily mail deploy:  python -m tidy.notify
Sends when there are "Needs you" messages, or when the run is missing or stale (a failing cron is actionable too).
Silent otherwise. The body carries counts and up to three sender names, never subjects or message text.
The topic is a private random string in <data dir>/ntfy_topic; anyone who knows it can read these pushes.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from . import mail_report_html

URL = "https://mail.abhibansal.dev"
STALE_HOURS = mail_report_html.STALE_HOURS
NAMES_SHOWN = 3


def build(doc, now=None):
    """Return a (title, body, priority) tuple, or None when there is nothing to look at."""
    now = now or datetime.now(timezone.utc)
    run_at = (doc or {}).get("run_at")
    age = None
    if run_at:
        age = (now - datetime.fromisoformat(run_at)).total_seconds() / 3600
    if age is None or age > STALE_HOURS:
        when = f"{age:.0f}h ago" if age is not None else "never"
        return "Mail run is stale", f"The last mail triage run was {when}. Check the cron log; you may need to reauthorize Google.", "high"
    by = {"needs_you": [], "fyi": [], "noise": [], "handled": []}
    for r in doc["rows"]:
        by[mail_report_html.bucket(r)].append(r)
    if not by["needs_you"]:
        return None
    names = []
    for r in sorted(by["needs_you"], key=lambda r: -r["confidence"]):
        name = parseaddr(r["sender"])[0] or parseaddr(r["sender"])[1]
        if name and name not in names:
            names.append(name)
    shown = ", ".join(names[:NAMES_SHOWN]) + (f" +{len(names) - NAMES_SHOWN} more" if len(names) > NAMES_SHOWN else "")
    parts = [f"{len(by['needs_you'])} need you ({shown})"]
    if by["noise"]:
        parts.append(f"{len(by['noise'])} noise to clear")
    if by["handled"]:
        parts.append(f"{len(by['handled'])} archived for you")
    return f"{len(by['needs_you'])} mails need you", "; ".join(parts), "default"


def send(topic, title, body, priority):
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST",
                                 headers={"Title": title, "Priority": priority, "Click": URL, "Tags": "envelope"})
    urllib.request.urlopen(req, timeout=15).close()


def main(data_dir=Path(".tidy")):
    topic_file = data_dir / "ntfy_topic"
    if not topic_file.is_file():
        print("no ntfy_topic file; nothing sent", file=sys.stderr)
        return 0
    runs = sorted((Path("data/mail_triage/runs")).glob("20??-??-??.json"))
    doc = json.loads(runs[-1].read_text()) if runs else None
    message = build(doc)
    if message is None:
        print("nothing needs the owner; silent")
        return 0
    send(topic_file.read_text().strip(), *message)
    print(f"sent: {message[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
