"""Google Takeout watch history (HTML): the owner's revealed viewing, counted by code, never by Jev.

Takeout is the owner's own data, not YouTube API data. It stays local under data/.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

ENTRY = re.compile(r'Watched\s*<a href="https://www\.youtube\.com/watch\?v=([^"&]+)[^"]*">.*?</a><br>'
                   r'<a href="https://www\.youtube\.com/channel/([^"]+)">(.*?)</a><br>([^<]+)<br>', re.S)
WHEN = re.compile(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4}), (\d{1,2}:\d{2}:\d{2})\s*([AP]M)")


def parse(html):
    """Watched videos that still have a channel link; the timezone label is dropped (day-level use only)."""
    events = []
    for video, channel, title, when in ENTRY.findall(html):
        m = WHEN.search(when.replace(" ", " ").replace(" ", " "))
        if m:
            at = datetime.strptime(f"{m[1]} {m[2]} {m[3]} {m[4]} {m[5]}", "%b %d %Y %I:%M:%S %p")
            events.append({"video_id": video, "channel_id": channel, "channel_title": title, "watched_at": at})
    return events


def watch_counts(path, days, now=None):
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    counts = {}
    for e in parse(Path(path).read_text(encoding="utf-8")):
        if now - timedelta(days=days) <= e["watched_at"] <= now:
            counts[e["channel_id"]] = counts.get(e["channel_id"], 0) + 1
    return counts
