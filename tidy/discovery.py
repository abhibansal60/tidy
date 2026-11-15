"""Discovery: channels the owner watches repeatedly but is not subscribed to. Counted from Takeout, never searched."""

from . import pilot, watch_history


def candidates(db, profile, now=None, limit=30):
    """(channel_id, watches) pairs, most watched first, for unsubscribed channels at or over the minimum."""
    history = watch_history.history_status(profile["watch_history_path"], profile["watch_window_days"], now)
    if history["status"] != "recent":
        return []
    subscribed = {r[0] for r in db.execute("SELECT channel_id FROM subscriptions WHERE active=1")}
    counts = history["counts"]
    ranked = sorted(((c, n) for c, n in counts.items() if c not in subscribed and n >= profile["discovery_min_watches"]),
                    key=lambda item: (-item[1], item[0]))
    return ranked[:limit]


def plan(db, profile, limit=30, window=12, now=None):
    found = candidates(db, profile, now, limit)
    return {"candidates": [{"channel_id": c, "watches": n} for c, n in found],
            "watch_history": {k: v for k, v in watch_history.history_status(
                profile["watch_history_path"], profile["watch_window_days"], now).items() if k != "counts"},
            "estimated_units": len(found) * pilot.units_per_channel(window), "executes": False}

