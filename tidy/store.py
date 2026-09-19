"""Local persistence. Legacy observations never become live subscriptions."""

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(value, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def adopt_old_dir(new, old):
    """One-time move of the pre-rename data directory; never overwrites an existing new one."""
    new, old = Path(new), Path(old)
    if old.is_dir() and not new.exists():
        old.rename(new)


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1, 2):
        db.close()
        raise ValueError("Database schema is newer than this application.")
    if version == 0:
        db.executescript("""
            BEGIN;
            CREATE TABLE legacy_imports (
                id TEXT PRIMARY KEY, imported_at TEXT NOT NULL
            );
            CREATE TABLE legacy_channels (
                import_id TEXT REFERENCES legacy_imports(id),
                channel_id TEXT NOT NULL, title TEXT NOT NULL,
                result_json TEXT, PRIMARY KEY (import_id, channel_id)
            );
            CREATE TABLE account (
                id INTEGER PRIMARY KEY CHECK (id=1),
                google_sub TEXT NOT NULL, email TEXT NOT NULL,
                youtube_channel_id TEXT NOT NULL
            );
            CREATE TABLE sync_runs (
                id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
                finished_at TEXT, status TEXT NOT NULL,
                request_units INTEGER NOT NULL DEFAULT 0,
                subscription_count INTEGER, error TEXT
            );
            CREATE TABLE subscriptions (
                id TEXT PRIMARY KEY, channel_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL, subscribed_at TEXT,
                active INTEGER NOT NULL CHECK (active IN (0,1)),
                last_seen TEXT NOT NULL
            );
            PRAGMA user_version=1;
            COMMIT;
        """)
    if version < 2:
        # Owner-approved unsubscribes: bound to account + subscription ID, with an audit trail.
        db.executescript("""
            BEGIN;
            CREATE TABLE unsubscribes (
                subscription_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL,
                title TEXT NOT NULL, account_channel TEXT NOT NULL,
                approved_at TEXT NOT NULL, note TEXT,
                status TEXT NOT NULL CHECK (status IN ('approved','unknown','done')),
                updated_at TEXT NOT NULL, detail TEXT
            );
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY, at TEXT NOT NULL, event TEXT NOT NULL,
                subscription_id TEXT, detail TEXT
            );
            PRAGMA user_version=2;
            COMMIT;
        """)
    # API metadata is a refreshable cache, not a permanent historical archive.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    with db:
        db.execute("DELETE FROM subscriptions WHERE last_seen < ?", (cutoff,))
    return db


def required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid {field}.")
    return value


def import_legacy(db, csv_path, results_path):
    csv_bytes, result_bytes = Path(csv_path).read_bytes(), Path(results_path).read_bytes()
    digest = hashlib.sha256(csv_bytes + b"\0" + result_bytes).hexdigest()
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    results = json.loads(result_bytes)
    if not isinstance(results, list):
        raise ValueError("Legacy results must be a list.")
    by_id = {}
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Invalid legacy result.")
        channel_id = required_text(result.get("id"), "legacy channel ID")
        if channel_id in by_id:
            raise ValueError("Duplicate legacy result channel ID.")
        by_id[channel_id] = result
    records, seen = [], set()
    for row in rows:
        channel_id = required_text(row.get("Channel ID"), "CSV channel ID")
        title = required_text(row.get("Channel title"), "CSV channel title")
        if channel_id in seen:
            raise ValueError("Duplicate CSV channel ID.")
        seen.add(channel_id)
        result = by_id.get(channel_id)
        records.append((digest, channel_id, title, json.dumps(result) if result else None))
    if set(by_id) - seen:
        raise ValueError("Legacy results contain channels absent from CSV.")
    with db:
        inserted = db.execute("INSERT OR IGNORE INTO legacy_imports VALUES (?, ?)",
                              (digest, now())).rowcount
        if inserted:
            db.executemany("INSERT INTO legacy_channels VALUES (?, ?, ?, ?)", records)
    return {"import_id": digest, "channels": len(rows), "already_imported": not bool(inserted)}


def bind_account(db, identity):
    values = tuple(required_text(identity.get(k), k) for k in
                   ("google_sub", "email", "youtube_channel_id"))
    old = db.execute("SELECT google_sub, email, youtube_channel_id FROM account").fetchone()
    if old and tuple(old) != values:
        raise ValueError("Account differs from database identity. Use a separate data directory.")
    with db:
        db.execute("INSERT OR IGNORE INTO account VALUES (1, ?, ?, ?)", values)


def save_inventory(db, identity, rows, run_id, request_units):
    """Commit a fully fetched snapshot and its success record together."""
    bind_account(db, identity)
    timestamp = now()
    with db:
        # Replace by channel as well as subscription ID: re-subscribe creates a new ID.
        db.execute("UPDATE subscriptions SET active=0")
        for row in rows:
            db.execute("DELETE FROM subscriptions WHERE channel_id=? AND id<>?",
                       (row["channel_id"], row["id"]))
            db.execute("""
                INSERT INTO subscriptions VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(id) DO UPDATE SET channel_id=excluded.channel_id,
                  title=excluded.title, subscribed_at=excluded.subscribed_at,
                  active=1, last_seen=excluded.last_seen
            """, (row["id"], row["channel_id"], row["title"], row.get("subscribed_at"), timestamp))
        db.execute("""UPDATE sync_runs SET finished_at=?, status='complete',
                      request_units=?, subscription_count=? WHERE id=?""",
                   (timestamp, request_units, len(rows), run_id))


def report(db):
    legacy = db.execute("SELECT id FROM legacy_imports ORDER BY imported_at DESC LIMIT 1").fetchone()
    successful = db.execute("SELECT * FROM sync_runs WHERE status='complete' ORDER BY id DESC LIMIT 1").fetchone()
    latest = db.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    fresh = bool(successful and datetime.fromisoformat(successful["finished_at"]) >
                 datetime.now(timezone.utc) - timedelta(days=30))
    baseline = {r["channel_id"] for r in db.execute(
        "SELECT channel_id FROM legacy_channels WHERE import_id=?", (legacy[0],))} if legacy else set()
    live = {r["channel_id"] for r in db.execute("SELECT channel_id FROM subscriptions WHERE active=1")}
    return {
        "legacy_channels": len(baseline),
        "live_inventory": "available" if fresh else "missing_or_expired",
        "active_subscriptions": len(live) if fresh else None,
        "new_since_legacy": sorted(live - baseline) if fresh and legacy else None,
        "absent_since_legacy": sorted(baseline - live) if fresh and legacy else None,
        "last_successful_sync": dict(successful) if successful else None,
        "last_attempt": dict(latest) if latest else None,
    }
