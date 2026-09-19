"""Owner-approved unsubscribes: dry-run by default, bound to account + subscription ID, audited."""

from datetime import datetime, timedelta

from . import store
from .youtube import APIError, DELETE_COST, UnknownOutcome


def audit(db, event, subscription_id=None, detail=None):
    db.execute("INSERT INTO audit_events(at,event,subscription_id,detail) VALUES (?,?,?,?)",
               (store.now(), event, subscription_id, detail))


def approve(db, channel_ids, note):
    """Record the owner's approval against the current live subscription, not a bare channel ID."""
    account = db.execute("SELECT youtube_channel_id FROM account").fetchone()
    if not account:
        raise ValueError("No bound account. Run auth and sync first.")
    rows = []
    for channel_id in channel_ids:
        row = db.execute("SELECT id, title FROM subscriptions WHERE channel_id=? AND active=1",
                         (channel_id,)).fetchone()
        if not row:
            raise ValueError(f"{channel_id} is not an active subscription; sync first.")
        rows.append((row["id"], channel_id, row["title"]))
    with db:
        for subscription_id, channel_id, title in rows:
            added = db.execute("""INSERT OR IGNORE INTO unsubscribes
                (subscription_id, channel_id, title, account_channel, approved_at, note, status, updated_at)
                VALUES (?,?,?,?,?,?, 'approved', ?)""",
                (subscription_id, channel_id, title, account[0], store.now(), note, store.now())).rowcount
            if added:
                audit(db, "approved", subscription_id, note)
    return [{"subscription_id": s, "channel_id": c, "title": t} for s, c, t in rows]


def pending(db):
    return [dict(r) for r in db.execute(
        "SELECT * FROM unsubscribes WHERE status IN ('approved','unknown') ORDER BY title")]


def finish(db, row, status, detail):
    with db:
        db.execute("UPDATE unsubscribes SET status=?, updated_at=?, detail=? WHERE subscription_id=?",
                   (status, store.now(), detail, row["subscription_id"]))
        if status == "done":
            db.execute("UPDATE subscriptions SET active=0 WHERE id=?", (row["subscription_id"],))
        audit(db, status, row["subscription_id"], detail)


def _already(results):
    done = [title for title, outcome in results if outcome == "deleted"]
    return f" Already deleted this run: {', '.join(done)}." if done else ""


def unsubscribe(db, api, expected_email, execute):
    todo = pending(db)
    summary = {"dry_run": not execute,
               "pending": [{"subscription_id": r["subscription_id"], "title": r["title"],
                            "status": r["status"]} for r in todo]}
    if not execute or not todo:
        return summary
    identity = api.identity(expected_email)
    store.bind_account(db, identity)  # refuses a different Google/YouTube identity
    # Recheck live state right before acting; approval is never enough on its own.
    live = {row["id"]: row for row in api.subscriptions()}
    live_channels = {row["channel_id"] for row in live.values()}
    deletes = sum(1 for r in todo if r["subscription_id"] in live)
    left = api.max_units - api.units
    if deletes * DELETE_COST > left:  # fail before the first delete, never half-way through a batch
        raise APIError(f"Local quota budget too small: {deletes} deletes need {deletes * DELETE_COST} units, "
                       f"{left} left; nothing deleted. Rerun with a larger --max-units.")
    results = []
    for row in todo:
        if row["account_channel"] != identity["youtube_channel_id"]:
            raise ValueError("Approval belongs to a different account; refusing.")
        current = live.get(row["subscription_id"])
        if current is None:
            if row["channel_id"] in live_channels:
                finish(db, row, "approved", "skipped: channel re-subscribed under a new ID; re-approve")
                results.append((row["title"], "skipped_resubscribed"))
            else:  # gone already, or an earlier unknown attempt succeeded
                finish(db, row, "done", "reconciled: subscription absent from live list")
                results.append((row["title"], "already_absent"))
            continue
        if current["channel_id"] != row["channel_id"]:
            raise APIError("Live subscription no longer matches approval; refusing.")
        try:
            outcome = api.delete_subscription(row["subscription_id"])
        except UnknownOutcome as error:
            finish(db, row, "unknown", str(error))
            raise UnknownOutcome(str(error) + _already(results)) from None  # next run reconciles before any retry
        except APIError as error:
            finish(db, row, "approved", str(error))
            raise APIError(str(error) + _already(results)) from None
        finish(db, row, "done", outcome)
        results.append((row["title"], outcome))
    summary["results"] = results
    summary["estimated_quota_units"] = api.units
    return summary


def _plan(proposals, gates, caps, subscribed, active_count):
    """Decide per proposal: 'would' or 'skipped: reason'; returns (actions, abort reason)."""
    actions = []
    for p in proposals:
        if p.action not in ("UNSUBSCRIBE", "SUBSCRIBE"):
            continue
        if len(p.signals) < 2:
            reason = "skipped: fewer than two signals"
        elif not gates.get(p.action):
            reason = "skipped: gate closed"
        elif (p.channel_id in subscribed) != (p.action == "UNSUBSCRIBE"):
            reason = "skipped: not subscribed" if p.action == "UNSUBSCRIBE" else "skipped: already subscribed"
        else:
            reason = "would"
        actions.append({"action": p.action, "channel_id": p.channel_id, "result": reason})
    eligible = sum(a["action"] == "UNSUBSCRIBE" and a["result"] == "would" for a in actions)
    limit = max(caps.get("unsubscribe", 0) * 3, 0.2 * active_count)
    if eligible > limit:
        return [], f"anomaly: {eligible} unsubscribe proposals exceed limit {limit:g}; no action taken"
    used = {"UNSUBSCRIBE": 0, "SUBSCRIBE": 0}
    for a in actions:
        if a["result"] == "would":
            used[a["action"]] += 1
            if used[a["action"]] > caps.get(a["action"].lower(), 0):
                a["result"] = "skipped: cap"
    return actions, None


def _set(db, row_id, action, channel_id, status, detail=None, subscription_id=None):
    with db:
        db.execute("UPDATE auto_actions SET status=?, detail=?, subscription_id=COALESCE(?, subscription_id) "
                   "WHERE id=?", (status, detail, subscription_id, row_id))
        audit(db, f"auto_{action.lower()}_{status}", subscription_id, channel_id)


def _trial(db, channel_id, subscription_id, started, trial_days):
    db.execute("INSERT OR REPLACE INTO trials VALUES (?,?,?,?)", (
        channel_id, subscription_id, started, (datetime.fromisoformat(started) + timedelta(days=trial_days)).isoformat()))


def _reconcile(db, live, trial_days):
    """Settle actions left pending/unknown by an earlier run from the live list; never retries."""
    for row in db.execute("SELECT * FROM auto_actions WHERE status IN ('pending','unknown')").fetchall():
        present = row["channel_id"] in live
        if present == (row["action"] == "SUBSCRIBE"):
            _set(db, row["id"], row["action"], row["channel_id"], "done", "reconciled from live list",
                 live.get(row["channel_id"]))
            if row["action"] == "SUBSCRIBE":
                with db:
                    _trial(db, row["channel_id"], live[row["channel_id"]], row["at"], trial_days)
        else:
            _set(db, row["id"], row["action"], row["channel_id"], "failed", "reconciled: change not present")


def act(db, api, proposals, gates, caps, expected_email, execute=False, trial_days=30):
    """Gated automatic actions. Dry run (default) is offline and uses the last synced inventory."""
    if execute:
        store.bind_account(db, api.identity(expected_email))  # refuses a different account
        live = {r["channel_id"]: r["id"] for r in api.subscriptions()}
        _reconcile(db, live, trial_days)
        subscribed = set(live)
    else:
        live = {r["channel_id"]: r["id"] for r in db.execute(
            "SELECT id, channel_id FROM subscriptions WHERE active=1")}
        subscribed = set(live)
    actions, aborted = _plan(proposals, gates, caps, subscribed, len(live))
    summary = {"dry_run": not execute, "aborted": aborted, "actions": actions}
    if execute:
        titles = {r["channel_id"]: r["title"] for r in db.execute("SELECT channel_id, title FROM subscriptions")}
        for a in actions:
            if a["result"] != "would":
                continue
            channel, kind = a["channel_id"], a["action"]
            with db:
                row_id = db.execute("INSERT INTO auto_actions(at,action,channel_id,subscription_id,title,status) "
                                    "VALUES (?,?,?,?,?, 'pending')",
                                    (store.now(), kind, channel, live.get(channel), titles.get(channel))).lastrowid
            try:
                if kind == "UNSUBSCRIBE":
                    outcome, new_id = api.delete_subscription(live[channel]), None
                else:
                    outcome, new_id = api.subscribe(channel)
            except UnknownOutcome as error:
                _set(db, row_id, kind, channel, "unknown", str(error))
                raise  # stop the run; the next run reconciles against the live list
            except APIError as error:
                _set(db, row_id, kind, channel, "failed", str(error))
                raise
            _set(db, row_id, kind, channel, "done", outcome, new_id)
            with db:
                if kind == "UNSUBSCRIBE":
                    db.execute("UPDATE subscriptions SET active=0 WHERE id=?", (live[channel],))
                elif outcome == "subscribed":
                    _trial(db, channel, new_id, store.now(), trial_days)
            a["result"] = outcome
        summary["estimated_quota_units"] = api.units
    return summary


def trials_due(db, now):
    """Trial channels whose trial has ended, for owner review. Graduation or removal is not automatic."""
    return [dict(r) for r in db.execute("SELECT * FROM trials WHERE trial_ends_at <= ? ORDER BY trial_ends_at",
                                        (now.isoformat(),))]


def resubscribe(db, api, channel_ids, execute=False, expected_email=None):
    """Restore channels that act unsubscribed. Dry run by default."""
    rows = {r["channel_id"]: r for r in db.execute(
        "SELECT * FROM auto_actions WHERE action='UNSUBSCRIBE' AND status='done' ORDER BY id")}
    missing = [c for c in channel_ids if c not in rows]
    if missing:
        raise ValueError(f"No restorable automatic unsubscribe for: {', '.join(missing)}")
    chosen = [rows[c] for c in channel_ids]
    if not execute:
        return {"dry_run": True, "would": [{"channel_id": r["channel_id"], "title": r["title"],
                                            "subscription_id": r["subscription_id"]} for r in chosen]}
    store.bind_account(db, api.identity(expected_email))
    live = {r["channel_id"] for r in api.subscriptions()}
    results = []
    for row in chosen:
        channel = row["channel_id"]
        if channel in live:
            outcome = "already_subscribed"
        else:
            try:
                outcome, _ = api.subscribe(channel)
            except APIError as error:  # includes UnknownOutcome; the live list settles it next run
                with db:
                    audit(db, "resubscribe_failed", row["subscription_id"], f"{channel}: {error}")
                raise
        _set(db, row["id"], "UNSUBSCRIBE", channel, "restored", outcome)
        results.append((channel, outcome))
    return {"dry_run": False, "results": results, "estimated_quota_units": api.units}
