import argparse
import json
from pathlib import Path
import sqlite3
import sys

from google.auth.exceptions import GoogleAuthError
from oauthlib.oauth2 import OAuth2Error
import requests

from . import mutate, pilot, store
from .youtube import APIError, YouTube, authorize, load_credentials, save_credentials, session_for


def sync(db, api, expected_email):
    with db:
        run_id = db.execute("INSERT INTO sync_runs(started_at,status) VALUES (?, 'running')",
                            (store.now(),)).lastrowid
    try:
        identity = api.identity(expected_email)
        store.bind_account(db, identity)
        rows = api.subscriptions()
        store.save_inventory(db, identity, rows, run_id, api.units)
    except Exception as error:
        with db:
            db.execute("UPDATE sync_runs SET finished_at=?,status='failed',request_units=?,error=? WHERE id=?",
                       (store.now(), api.units, type(error).__name__, run_id))
        raise
    return {"subscriptions": len(rows), "estimated_quota_units": api.units, "run_id": run_id}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tidy: YouTube subscription manager; unsubscribes only for owner-approved subscriptions.")
    parser.add_argument("--data-dir", type=Path, default=Path(".tidy"))
    commands = parser.add_subparsers(dest="command", required=True)
    legacy = commands.add_parser("import-legacy", help="Import local Claude artifacts without network calls")
    legacy.add_argument("--csv", type=Path, default=Path("yt/subscriptions.csv"))
    legacy.add_argument("--results", type=Path, default=Path("results.json"))
    auth = commands.add_parser("auth", help="Authorize read-only YouTube and verify configured Google email")
    auth.add_argument("--client-secrets", type=Path, default=Path("secrets/client_secret.json"))
    auth.add_argument("--no-browser", action="store_true")
    auth.add_argument("--write", action="store_true", help="Authorize YouTube write access into a separate token")
    live = commands.add_parser("sync", help="Fetch all live subscriptions, then atomically update inventory")
    live.add_argument("--max-units", type=int, default=100)
    collect = commands.add_parser("collect", help="Evidence pilot: dry run by default; --execute fetches and stores samples")
    collect.add_argument("--channels", nargs="*", default=[], help="Channel IDs to include")
    collect.add_argument("--labels", type=Path, default=Path("data/owner_labels.json"),
                         help="Owner labels file; its channels are added by title (skipped if missing)")
    collect.add_argument("--window", type=int, default=12, help="Latest uploads per channel")
    collect.add_argument("--max-units", type=int, default=100)
    collect.add_argument("--execute", action="store_true")
    commands.add_parser("report", help="Show baseline/live counts and differences as JSON")
    approve = commands.add_parser("approve", help="Record owner approval to unsubscribe from active channels")
    approve.add_argument("channel_ids", nargs="+")
    approve.add_argument("--note", required=True, help="Why and on what evidence (proposal version)")
    unsub = commands.add_parser("unsubscribe", help="Dry-run by default; --execute deletes approved subscriptions")
    unsub.add_argument("--execute", action="store_true")
    unsub.add_argument("--max-units", type=int, default=500)
    args = parser.parse_args(argv)
    if args.data_dir == Path(".tidy"):
        store.adopt_old_dir(args.data_dir, Path(".jev"))
    db = None
    try:
        db = store.connect(args.data_dir / "inventory.sqlite3")
        if args.command == "import-legacy":
            output = store.import_legacy(db, args.csv, args.results)
        elif args.command == "report":
            output = store.report(db)
        elif args.command == "approve":
            output = mutate.approve(db, args.channel_ids, args.note)
        elif args.command == "collect" and not args.execute:
            output = {**pilot.plan(db, args.channels, args.labels if args.labels.is_file() else None, args.window),
                      "executes": False}
        elif args.command == "unsubscribe" and not args.execute:
            output = mutate.unsubscribe(db, None, None, False)
        else:
            config_file = args.data_dir / "config.json"
            if not config_file.is_file():
                raise ValueError("Create private config.json from config.example.json; see README.")
            config = json.loads(config_file.read_text())
            if not isinstance(config, dict):
                raise ValueError("Private config.json must be an object.")
            email = store.required_text(config.get("expected_email"), "expected_email")
            write = args.command == "unsubscribe" or getattr(args, "write", False)
            token_path = args.data_dir / ("token_write.json" if write else "token.json")
            if args.command == "auth":
                if not args.client_secrets.is_file():
                    raise ValueError("Google Desktop OAuth client JSON missing; see README setup steps.")
                credentials = authorize(args.client_secrets, email, not args.no_browser, write)
                with session_for(credentials) as session:
                    api = YouTube(session)
                    identity = api.identity(email)
                    store.bind_account(db, identity)
                save_credentials(token_path, credentials, write)
                output = {"authorized": True, **identity, "estimated_quota_units": api.units}
            else:
                if not token_path.is_file():
                    raise ValueError("No OAuth token. Run auth first; see README.")
                credentials = load_credentials(token_path, write)
                with session_for(credentials) as session:
                    if args.command == "collect":
                        chosen = pilot.plan(db, args.channels, args.labels if args.labels.is_file() else None,
                                            args.window)["channels"]
                        output = pilot.run(db, YouTube(session, args.max_units), chosen, args.window)
                    elif args.command == "unsubscribe":
                        output = mutate.unsubscribe(db, YouTube(session, args.max_units), email, True)
                    else:
                        output = sync(db, YouTube(session, args.max_units), email)
                save_credentials(token_path, credentials, write)
        print(json.dumps(output, indent=2))
        return 0
    except (GoogleAuthError, OAuth2Error, requests.RequestException):
        print("Google authorization/network failure. Reauthorize if needed; credentials not logged.", file=sys.stderr)
        return 1
    except (OSError, ValueError, sqlite3.Error, APIError) as error:
        # Avoid traceback/HTTP bodies, which can expose OAuth callbacks or credentials.
        message = str(error) if isinstance(error, (ValueError, APIError)) else type(error).__name__
        print(f"Error: {message}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
