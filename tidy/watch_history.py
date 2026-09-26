"""Google Takeout watch history (HTML): the owner's revealed viewing, counted by code, never by Jev.

Takeout is the owner's own data, not YouTube API data. It stays local under data/.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

ENTRY = re.compile(r'Watched\s*<a href="https://www\.youtube\.com/watch\?v=([^"&]+)[^"]*">.*?</a><br>'
                   r'<a href="https://www\.youtube\.com/channel/([^"]+)">(.*?)</a><br>([^<]+)<br>', re.S)
# Takeout follows the account's locale: US "Sep 18, 2026, 9:05:11 PM IST" or India/UK "18 Sept 2026, 21:05:11 IST".
WHEN_US = re.compile(r"([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4}), (\d{1,2}:\d{2}:\d{2})\s*([AP]M)")
WHEN_DAY_FIRST = re.compile(r"(\d{1,2}) ([A-Z][a-z]{2})[a-z]* (\d{4}), (\d{1,2}:\d{2}:\d{2})(?:\s*([AaPp][Mm]))?")


def _when(text):
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    if m := WHEN_US.search(text):
        return datetime.strptime(f"{m[1]} {m[2]} {m[3]} {m[4]} {m[5]}", "%b %d %Y %I:%M:%S %p")
    if m := WHEN_DAY_FIRST.search(text):
        if m[5]:
            return datetime.strptime(f"{m[2]} {m[1]} {m[3]} {m[4]} {m[5].upper()}", "%b %d %Y %I:%M:%S %p")
        return datetime.strptime(f"{m[2]} {m[1]} {m[3]} {m[4]}", "%b %d %Y %H:%M:%S")
    return None


def parse(html):
    """Watched videos that still have a channel link; the timezone label is dropped (day-level use only)."""
    events = []
    for video, channel, title, when in ENTRY.findall(html):
        if at := _when(when):
            events.append({"video_id": video, "channel_id": channel, "channel_title": title, "watched_at": at})
    return events


def watch_counts(path, days, now=None):
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
    counts = {}
    for e in parse(Path(path).read_text(encoding="utf-8")):
        if now - timedelta(days=days) <= e["watched_at"] <= now:
            counts[e["channel_id"]] = counts.get(e["channel_id"], 0) + 1
    return counts
