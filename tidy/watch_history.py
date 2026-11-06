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


def _local_when(text):
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    if m := WHEN_US.search(text):
        return datetime.strptime(f"{m[1]} {m[2]} {m[3]} {m[4]} {m[5]}", "%b %d %Y %I:%M:%S %p")
    if m := WHEN_DAY_FIRST.search(text):
        if m[5]:
            return datetime.strptime(f"{m[2]} {m[1]} {m[3]} {m[4]} {m[5].upper()}", "%b %d %Y %I:%M:%S %p")
        return datetime.strptime(f"{m[2]} {m[1]} {m[3]} {m[4]}", "%b %d %Y %H:%M:%S")
    return None


def _when(text):
    text = text.replace("\u202f", " ").replace("\xa0", " ").strip()
    local = _local_when(text)
    zone = re.search(r"\s(IST|UTC|GMT|[+-]\d{2}:?\d{2})$", text)
    if local is None or zone is None:
        return None  # Unknown timezone: do not guess from this machine's local clock.
    name = zone[1]
    if name == "IST":  # Takeout's Indian Standard Time exports.
        offset = timedelta(hours=5, minutes=30)
    elif name in ("UTC", "GMT"):
        offset = timedelta()
    else:
        digits = name[1:].replace(":", "")
        hours, minutes = int(digits[:2]), int(digits[2:])
        if hours > 23 or minutes > 59:
            return None
        offset = (1 if name[0] == "+" else -1) * timedelta(hours=hours, minutes=minutes)
    return local.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)


def parse(html):
    """Watched videos that still have a channel link, normalized to UTC with an explicit timezone."""
    events = []
    for video, channel, title, when in ENTRY.findall(html):
        if at := _when(when):
            events.append({"video_id": video, "channel_id": channel, "channel_title": title, "watched_at": at})
    return events


def history_status(path, days, now=None):
    """Recency is necessary, not proof of a complete export. Missing history is unknown, never zero watches."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    result = {"status": "missing", "latest_event": None, "parsed_events": 0, "counts": {}}
    if not path or not Path(path).is_file():
        return result
    try:
        events = parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {**result, "status": "unreadable"}
    if not events:
        return {**result, "status": "empty_or_unsupported"}
    latest = max(e["watched_at"] for e in events)
    result.update(latest_event=latest.isoformat(), parsed_events=len(events))
    if latest > now:
        return {**result, "status": "future_dated"}
    if latest < now - timedelta(days=days):
        return {**result, "status": "stale"}
    counts = {}
    for e in events:
        if now - timedelta(days=days) <= e["watched_at"] <= now:
            counts[e["channel_id"]] = counts.get(e["channel_id"], 0) + 1
    return {**result, "status": "recent", "counts": counts}


def watch_counts(path, days, now=None):
    return history_status(path, days, now)["counts"]
