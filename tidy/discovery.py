"""Discovery: channels the owner watches repeatedly but is not subscribed to. Counted from Takeout, never searched."""

from pathlib import Path

from . import pilot, watch_history


def candidates(db, profile, now=None, limit=30):
    """(channel_id, watches) pairs, most watched first, for unsubscribed channels at or over the minimum."""
    path = profile["watch_history_path"]
    if not path or not Path(path).is_file():
        return []
    subscribed = {r[0] for r in db.execute("SELECT channel_id FROM subscriptions WHERE active=1")}
    counts = watch_history.watch_counts(path, profile["watch_window_days"], now)
    ranked = sorted(((c, n) for c, n in counts.items() if c not in subscribed and n >= profile["discovery_min_watches"]),
                    key=lambda item: (-item[1], item[0]))
    return ranked[:limit]


def plan(db, profile, limit=30, window=12, now=None):
    found = candidates(db, profile, now, limit)
    return {"candidates": [{"channel_id": c, "watches": n} for c, n in found],
            "estimated_units": len(found) * pilot._units_per_channel(window), "executes": False}


def run(db, api, profile, limit=30, window=12, now=None):
    """Collect evidence for the candidates (read-only API); judge and propose then run as for any sample."""
    return pilot.run(db, api, [c for c, _ in candidates(db, profile, now, limit)], window, now)
