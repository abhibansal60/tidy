import argparse
import json
from pathlib import Path
import sqlite3
import sys

from google.auth.exceptions import GoogleAuthError
from oauthlib.oauth2 import OAuth2Error
import requests

from . import store
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
    parser = argparse.ArgumentParser(description="Read-only YouTube subscription inventory; no mutations.")
    parser.add_argument("--data-dir", type=Path, default=Path(".jev"))
    commands = parser.add_subparsers(dest="command", required=True)
    legacy = commands.add_parser("import-legacy", help="Import local Claude artifacts without network calls")
    legacy.add_argument("--csv", type=Path, default=Path("yt/subscriptions.csv"))
    legacy.add_argument("--results", type=Path, default=Path("results.json"))
    auth = commands.add_parser("auth", help="Authorize read-only YouTube and verify configured Google email")
    auth.add_argument("--client-secrets", type=Path, default=Path("secrets/client_secret.json"))
    auth.add_argument("--no-browser", action="store_true")
    live = commands.add_parser("sync", help="Fetch all live subscriptions, then atomically update inventory")
    live.add_argument("--max-units", type=int, default=100)
    commands.add_parser("report", help="Show baseline/live counts and differences as JSON")
    args = parser.parse_args(argv)
    db = None
    try:
        db = store.connect(args.data_dir / "inventory.sqlite3")
        if args.command == "import-legacy":
            output = store.import_legacy(db, args.csv, args.results)
        elif args.command == "report":
            output = store.report(db)
        else:
            config_file = args.data_dir / "config.json"
            if not config_file.is_file():
                raise ValueError("Create private config.json from config.example.json; see README.")
            config = json.loads(config_file.read_text())
            if not isinstance(config, dict):
                raise ValueError("Private config.json must be an object.")
            email = store.required_text(config.get("expected_email"), "expected_email")
            token_path = args.data_dir / "token.json"
            if args.command == "auth":
                if not args.client_secrets.is_file():
                    raise ValueError("Google Desktop OAuth client JSON missing; see README setup steps.")
                credentials = authorize(args.client_secrets, email, not args.no_browser)
                with session_for(credentials) as session:
                    api = YouTube(session)
                    identity = api.identity(email)
                    store.bind_account(db, identity)
                save_credentials(token_path, credentials)
                output = {"authorized": True, **identity, "estimated_quota_units": api.units}
            else:
                if not token_path.is_file():
                    raise ValueError("No OAuth token. Run auth first; see README.")
                credentials = load_credentials(token_path)
                with session_for(credentials) as session:
                    output = sync(db, YouTube(session, args.max_units), email)
                save_credentials(token_path, credentials)
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
