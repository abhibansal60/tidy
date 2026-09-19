"""Evidence pilot: choose channels, estimate quota, collect and store samples."""

import json
from math import ceil

from . import collector, store


def _units_per_channel(window):
    # channels.list + playlistItems pages + videos.list batches, one unit each (lower bound)
    return 1 + 2 * ceil(window / 50)


def plan(db, channel_ids, labels_path, window):
    """Offline: the channels a run would fetch (explicit ones, then owner-labeled by title) and its cost."""
    channels, unresolved = list(channel_ids), []
    if labels_path:
        labels = json.loads(open(labels_path).read())
        by_title = {r["title"].casefold(): r["channel_id"] for r in
                    db.execute("SELECT title, channel_id FROM subscriptions WHERE active=1")}
        for title in labels.get("keep", []) + labels.get("sloppy", []):
            cid = by_title.get(title.casefold())
            if cid is None:
                unresolved.append(title)
            elif cid not in channels:
                channels.append(cid)
    return {"channels": channels, "unresolved_labels": unresolved, "window": window,
            "estimated_units": len(channels) * _units_per_channel(window)}


def run(db, api, channel_ids, window, now=None):
    result = collector.collect(api, channel_ids, window, now)
    store.save_samples(db, result, api.units, now)
    return {"collected": len(result.samples), "errors": result.errors, "request_units": api.units,
            "coverage": {s.channel_id: s.coverage for s in result.samples},
            "expires_at": min((s.expires_at for s in result.samples), default=None)}
