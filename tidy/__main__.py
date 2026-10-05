import argparse
import contextlib
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import sys

from google.auth.exceptions import GoogleAuthError
from oauthlib.oauth2 import OAuth2Error
import requests

from . import __version__, discovery, escalate, experiment, gmail, judge, mail, mail_report_html, mutate, pilot, profile, report_html, review, setup_check, store
from .proposal import Proposal
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


def run_act(db, api, email, args, config):
    if args.command == "resubscribe":
        return mutate.resubscribe(db, api, args.channel_ids, args.execute, email)
    proposals = [Proposal(**p) for p in json.loads(args.proposals.read_text())]
    gates = {"UNSUBSCRIBE": args.gate_unsubscribe, "SUBSCRIBE": args.gate_subscribe}
    if args.execute and any(gates.values()) and not args.override_gate:
        status = review.gate_status(review.agreement(db, review.derive(db, config)[0]), config)
        if not status["open"]:
            raise ValueError("Calibration gate closed: " + "; ".join(status["reasons"]) + ". Pass --override-gate to act anyway.")
    caps = {"unsubscribe": config["caps"]["unsubscribe"] if args.cap_unsubscribe is None else args.cap_unsubscribe,
            "subscribe": config["caps"]["subscribe"] if args.cap_subscribe is None else args.cap_subscribe}
    return mutate.act(db, api, proposals, gates, caps, email, args.execute)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tidy", description="Tidy: Jev judges your YouTube subscriptions and Gmail inbox; code sets the limits; you approve. "
        "Every command prints JSON. Anything that changes your account is a dry run until you add --execute.",
        epilog="Start here: tidy init --email you@gmail.com --client-secrets PATH, then tidy doctor.")
    parser.add_argument("--version", action="version", version=f"tidy {__version__}")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Private data folder (default: $TIDY_DATA_DIR, else ./.tidy if present, else ~/.tidy)")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    first = commands.add_parser("init", help="First-run setup: private data folder, config, OAuth client, TypeSafe key")
    first.add_argument("--email", required=True, help="The Google account you will sign in with")
    first.add_argument("--client-secrets", type=Path, help="Google Desktop OAuth client JSON to copy in (stored 0600)")
    first.add_argument("--key-stdin", action="store_true", help="Read the TypeSafe API key from stdin (never echoed)")
    first.add_argument("--no-mail", action="store_true", help="Do not set up Gmail (mail_email)")
    check = commands.add_parser("doctor", help="Offline: what is set up, what is missing, and the next command (never prints secrets)")
    check.add_argument("--client-secrets", type=Path, default=None)
    legacy = commands.add_parser("import-legacy", help="Import local Claude artifacts without network calls")
    legacy.add_argument("--csv", type=Path, default=Path("yt/subscriptions.csv"))
    legacy.add_argument("--results", type=Path, default=Path("results.json"))
    auth = commands.add_parser("auth", help="Authorize read-only YouTube and verify configured Google email")
    auth.add_argument("--client-secrets", type=Path, default=None, help="Default: <data dir>/client_secret.json, else secrets/client_secret.json")
    auth.add_argument("--no-browser", action="store_true")
    auth.add_argument("--write", action="store_true", help="Authorize YouTube write access into a separate token")
    live = commands.add_parser("sync", help="Fetch all live subscriptions, then atomically update inventory")
    live.add_argument("--max-units", type=int, default=100)
    collect = commands.add_parser("collect", help="Evidence pilot: dry run by default; --execute fetches and stores samples")
    collect.add_argument("--channels", nargs="*", default=[], help="Channel IDs to include")
    collect.add_argument("--all", action="store_true", help="Every active subscription from the last sync")
    collect.add_argument("--labels", type=Path, default=Path("data/owner_labels.json"),
                         help="Owner labels file; its channels are added by title (skipped if missing)")
    collect.add_argument("--window", type=int, default=12, help="Latest uploads per channel")
    collect.add_argument("--max-units", type=int, default=100)
    collect.add_argument("--execute", action="store_true")
    find = commands.add_parser("discover", help="Unsubscribed channels you watch often: dry run by default; --execute collects evidence")
    find.add_argument("--limit", type=int, default=30)
    find.add_argument("--window", type=int, default=12, help="Latest uploads per channel")
    find.add_argument("--max-units", type=int, default=100)
    find.add_argument("--execute", action="store_true")
    jev = commands.add_parser("judge", help="Schema experiment on stored samples: dry run by default; --execute calls Jev")
    jev.add_argument("--schemas", nargs="+", required=True, choices=sorted(judge.SCHEMAS))
    jev.add_argument("--interests", default=None, help="Defaults to profile.json interests")
    jev.add_argument("--habits", default=None, help="Owner viewing habits; defaults to profile.json viewing_habits")
    jev.add_argument("--execute", action="store_true")
    second = commands.add_parser("escalate", help="Second opinion on channels Jev flags as low quality: dry run by default")
    second.add_argument("--model", default="claude-opus-5-5")
    second.add_argument("--execute", action="store_true")
    proposals = commands.add_parser("propose", help="Offline: Markdown report of proposals from stored samples and judgments")
    proposals.add_argument("--html", type=Path, help="Write a self-contained HTML review page to this path instead of Markdown")
    proposals.add_argument("--json", type=Path, help="Write the proposals as a JSON list that `tidy act --proposals` reads")
    commands.add_parser("gate", help="Offline: agreement with owner labels and calibration gate status")
    mark = commands.add_parser("label", help="Record an owner label")
    mark.add_argument("channel_id")
    mark.add_argument("verdict", choices=review.VERDICTS)
    mark.add_argument("--note", default="")
    bulk = commands.add_parser("labels", help="Import owner labels from a {keep, sloppy} title file")
    bulk.add_argument("action", choices=["import", "sheet"])
    bulk.add_argument("path", type=Path)
    commands.add_parser("report", help="Show baseline/live counts and differences as JSON")
    commands.add_parser("purge", help="Delete API-derived evidence and blank stored titles past the 30-day retention")
    approve = commands.add_parser("approve", help="Record owner approval to unsubscribe from active channels")
    approve.add_argument("channel_ids", nargs="+")
    approve.add_argument("--note", required=True, help="Why and on what evidence (proposal version)")
    unsub = commands.add_parser("unsubscribe", help="Dry-run by default; --execute deletes approved subscriptions")
    unsub.add_argument("--execute", action="store_true")
    unsub.add_argument("--max-units", type=int, default=500)
    act = commands.add_parser("act", help="Gated automatic actions from proposals; dry run unless --execute")
    act.add_argument("--proposals", type=Path, required=True, help="JSON list of Proposal dicts")
    act.add_argument("--gate-unsubscribe", action="store_true", help="Open the UNSUBSCRIBE gate (default closed)")
    act.add_argument("--gate-subscribe", action="store_true", help="Open the SUBSCRIBE gate (default closed)")
    act.add_argument("--cap-unsubscribe", type=int, default=None, help="Per-run cap (default: profile caps, 5)")
    act.add_argument("--cap-subscribe", type=int, default=None, help="Per-run cap (default: profile caps, 3)")
    act.add_argument("--override-gate", action="store_true", help="Act although the calibration gate is closed (owner override)")
    act.add_argument("--execute", action="store_true")
    act.add_argument("--max-units", type=int, default=500)
    mail_auth = commands.add_parser("mail-auth", help="Authorize Gmail and verify configured Google email")
    mail_auth.add_argument("--client-secrets", type=Path, default=None, help="Default: <data dir>/client_secret.json, else secrets/client_secret.json")
    mail_auth.add_argument("--no-browser", action="store_true")
    mail_auth.add_argument("--write", action="store_true", help="Authorize label-write access (archive, spam) into a separate token")
    mail_triage = commands.add_parser("mail-triage", help="Jev classifies recent inbox mail; dry run by default. --apply archives/spams (label-only, never deletes).")
    mail_triage.add_argument("--query", default="in:inbox newer_than:7d")
    mail_triage.add_argument("--limit", type=int, default=20)
    mail_triage.add_argument("--max-calls", type=int, default=1200)
    mail_triage.add_argument("--execute", action="store_true")
    mail_triage.add_argument("--apply", action="store_true", help="Actually archive/spam the proposed messages (requires --execute and a write token)")
    mail_triage.add_argument("--cap-archive", type=int, default=100, help="Per-run safety ceiling on auto-applied ARCHIVE actions (ADR 0005 caps pattern); excess proposals are held, not applied")
    mail_triage.add_argument("--override-gate", action="store_true", help="Auto-archive although the mail calibration gate is closed (no owner labels exist yet); owner override, mirrors `act --override-gate`")
    mail_triage.add_argument("--html", type=Path, help="Write a self-contained HTML dashboard to this path")
    mail_triage.add_argument("--json", type=Path, help="Write the full run (messages, judgments, proposals, outcomes) as JSON")
    mail_act = commands.add_parser("mail-act", help="Apply held TRASH/SPAM proposals from a saved mail-triage run; dry run unless --execute. ARCHIVE already auto-applies from mail-triage, so it is not included here.")
    mail_act.add_argument("--run", type=Path, nargs="+", required=True, help="One or more run files written by `mail-triage --json`")
    mail_act.add_argument("--actions", nargs="+", choices=["TRASH", "SPAM"], default=["TRASH", "SPAM"])
    mail_act.add_argument("--max-calls", type=int, default=1000)
    mail_act.add_argument("--force-reapply", action="store_true", help="Also re-run rows already marked outcome=applied in --run (e.g. after manually restoring a message)")
    mail_act.add_argument("--execute", action="store_true")
    resub = commands.add_parser("resubscribe", help="Restore automatically unsubscribed channels; dry run unless --execute")
    resub.add_argument("channel_ids", nargs="+")
    resub.add_argument("--execute", action="store_true")
    resub.add_argument("--max-units", type=int, default=500)
    args = parser.parse_args(argv)
    args.data_dir = setup_check.data_dir(args.data_dir)
    if args.data_dir == Path(".tidy"):
        store.adopt_old_dir(args.data_dir, Path(".jev"))
    if hasattr(args, "client_secrets") and args.command != "init":
        args.client_secrets = setup_check.client_secrets(args.data_dir, args.client_secrets)
    if args.command in ("init", "doctor"):  # no database, no network
        try:
            output = (setup_check.init(args.data_dir, args.email, args.client_secrets, args.key_stdin, not args.no_mail)
                      if args.command == "init" else setup_check.doctor(args.data_dir, args.client_secrets))
        except (OSError, ValueError) as error:
            print(f"Error: {error if isinstance(error, ValueError) else type(error).__name__}", file=sys.stderr)
            return 1
        print(json.dumps(output, indent=2))
        return 0
    db = None
    try:
        db = store.connect(args.data_dir / "inventory.sqlite3")
        if args.command == "import-legacy":
            output = store.import_legacy(db, args.csv, args.results)
        elif args.command == "report":
            output = store.report(db)
        elif args.command == "purge":
            output = {"purged_evidence_samples": store.purge(db)}
        elif args.command == "escalate":
            config = profile.load(args.data_dir / "profile.json")
            output = escalate.run(db, config, escalate.ask, args.model) if args.execute else escalate.plan(db, config)
        elif args.command == "propose":
            config = profile.load(args.data_dir / "profile.json")
            proposals, judgments, samples = review.derive(db, config)
            if args.json:
                store.private_text(args.json, json.dumps([asdict(p) for p in proposals], indent=1))
                output = {"json": str(args.json), "channels": len(proposals)}
            elif args.html:
                gate = review.gate_status(review.agreement(db, proposals), config)
                store.private_text(args.html, report_html.render(proposals, judgments, samples, review.current_labels(db), gate, str(args.data_dir)))
                output = {"html": str(args.html), "channels": len(proposals)}
            else:
                print(review.render_report(proposals, judgments, samples, review.current_labels(db)))
                return 0
        elif args.command == "gate":
            config = profile.load(args.data_dir / "profile.json")
            stats = review.agreement(db, review.derive(db, config)[0])
            output = {**stats, "gate": review.gate_status(stats, config)}
        elif args.command == "label":
            review.label(db, args.channel_id, args.verdict, args.note)
            output = {"labeled": args.channel_id, "verdict": args.verdict}
        elif args.command == "labels":
            output = (review.import_sheet if args.action == "sheet" else review.import_label_file)(db, args.path)
        elif args.command == "approve":
            output = mutate.approve(db, args.channel_ids, args.note)
        elif args.command == "collect" and not args.execute:
            output = {**pilot.plan(db, args.channels, args.labels if args.labels.is_file() else None, args.window, args.all),
                      "executes": False}
        elif args.command == "discover" and not args.execute:
            output = discovery.plan(db, profile.load(args.data_dir / "profile.json"), args.limit, args.window)
        elif args.command == "judge":
            config = profile.load(args.data_dir / "profile.json")
            habits = args.habits if args.habits is not None else config["viewing_habits"]
            interests = args.interests if args.interests is not None else config["interests"]
            if not args.execute:
                output = experiment.plan(db, args.schemas, interests, habits=habits)
            else:
                with setup_check.typesafe_client(args.data_dir) as client:
                    output = experiment.run(db, client, args.schemas, interests, habits=habits)
        elif args.command == "unsubscribe" and not args.execute:
            output = mutate.unsubscribe(db, None, None, False)
        elif args.command in ("act", "resubscribe") and not args.execute:
            output = run_act(db, None, None, args, profile.load(args.data_dir / "profile.json"))
        elif args.command == "mail-triage" and not args.execute:
            output = {"query": args.query, "limit": args.limit, "executes": False,
                      "hint": "Dry run: nothing read or sent. Add --execute to classify (reads Gmail, calls Jev, changes nothing)."}
        elif args.command == "mail-act":
            # Several run files are allowed (the daily cron writes one per day); see mail.select_held. Files are rewritten in place.
            docs = [(path, json.loads(path.read_text())) for path in args.run]
            eligible = mail.select_held([doc for _, doc in docs], args.actions, args.force_reapply)
            if not args.execute:
                output = {"run": [str(p) for p in args.run], "actions": args.actions, "messages": len(eligible),
                          "executes": False,
                          "preview": [{"id": r["id"], "action": r["action"], "subject": r["subject"],
                                       "sender": r["sender"], "category": r["category"]} for r in eligible]}
            else:
                config_file = args.data_dir / "config.json"
                if not config_file.is_file():
                    raise ValueError("Not set up yet. Run: tidy init --email you@gmail.com (then tidy doctor).")
                config = json.loads(config_file.read_text())
                email = store.required_text(config.get("mail_email"), "mail_email")
                with gmail.connect(args.data_dir / "token_mail_write.json", email, write=True, max_calls=args.max_calls) as api:
                    valid, outcomes = mail.recheck(api, [(r["id"], r["action"]) for r in eligible])
                    outcomes.update(mail.apply(api, valid))
                # Persist outcomes back into the run files: a rerun then skips what already succeeded, so it
                # never re-trashes a message the owner has since manually restored (unless --force-reapply).
                for r in eligible:  # the selected row objects live inside `docs`, so this updates exactly them
                    if r["id"] in outcomes:
                        r["outcome"] = outcomes[r["id"]]
                for path, doc in docs:
                    store.private_text(path, json.dumps(doc, indent=1))
                output = {"run": [str(p) for p in args.run], "actions": args.actions,
                          "applied": sum(v == "applied" for v in outcomes.values()),
                          "skipped": {i: v for i, v in outcomes.items() if v.startswith("skipped")},
                          "errors": {i: v for i, v in outcomes.items() if v.startswith("error")}}
        elif args.command in ("mail-auth", "mail-triage"):
            config_file = args.data_dir / "config.json"
            if not config_file.is_file():
                raise ValueError("Not set up yet. Run: tidy init --email you@gmail.com (then tidy doctor).")
            config = json.loads(config_file.read_text())
            if not isinstance(config, dict):
                raise ValueError("Private config.json must be an object.")
            email = store.required_text(config.get("mail_email"), "mail_email")
            if args.command == "mail-auth":
                token_path = args.data_dir / ("token_mail_write.json" if args.write else "token_mail.json")
                if not args.client_secrets.is_file():
                    raise ValueError(f"Google OAuth client JSON not found at {args.client_secrets}. Run: tidy init --email ... --client-secrets PATH")
                credentials = gmail.authorize(args.client_secrets, email, not args.no_browser, args.write)
                with gmail.session_for(credentials) as session:
                    identity = gmail.Gmail(session).identity(email)
                gmail.save_credentials(token_path, credentials, args.write)
                output = {"authorized": True, "write": args.write, **identity}
            else:
                write = (gmail.connect(args.data_dir / "token_mail_write.json", email, write=True, max_calls=args.max_calls)
                         if args.apply else contextlib.nullcontext())
                with gmail.connect(args.data_dir / "token_mail.json", email, max_calls=args.max_calls) as api, \
                        write as write_api, setup_check.typesafe_client(args.data_dir) as client:
                    output = mail.triage(api, client, email, args.query, args.limit, db=db, write_api=write_api,
                                         cap_archive=args.cap_archive, override_gate=args.override_gate)
                run_at = store.now()
                if args.html:
                    store.private_text(args.html, mail_report_html.render(output["rows"], applied=args.apply, run_at=run_at, account=email))
                if args.json:
                    store.private_text(args.json, json.dumps({"run_at": run_at, "mode": "apply" if args.apply else "dry", "query": args.query, "rows": output["rows"], "errors": output["errors"]}, indent=1))
                output.update({"html": str(args.html) if args.html else None, "json": str(args.json) if args.json else None})
        else:
            config_file = args.data_dir / "config.json"
            if not config_file.is_file():
                raise ValueError("Not set up yet. Run: tidy init --email you@gmail.com (then tidy doctor).")
            config = json.loads(config_file.read_text())
            if not isinstance(config, dict):
                raise ValueError("Private config.json must be an object.")
            email = store.required_text(config.get("expected_email"), "expected_email")
            write = args.command in ("unsubscribe", "act", "resubscribe") or getattr(args, "write", False)
            token_path = args.data_dir / ("token_write.json" if write else "token.json")
            if args.command == "auth":
                if not args.client_secrets.is_file():
                    raise ValueError(f"Google OAuth client JSON not found at {args.client_secrets}. Run: tidy init --email ... --client-secrets PATH")
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
                                            args.window, args.all)["channels"]
                        output = pilot.run(db, YouTube(session, args.max_units), chosen, args.window)
                    elif args.command == "discover":
                        found = discovery.candidates(db, profile.load(args.data_dir / "profile.json"), limit=args.limit)
                        output = pilot.run(db, YouTube(session, args.max_units), [c for c, _ in found], args.window)
                    elif args.command in ("act", "resubscribe"):
                        output = run_act(db, YouTube(session, args.max_units), email, args,
                                         profile.load(args.data_dir / "profile.json"))
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
    except (OSError, ValueError, sqlite3.Error, APIError, gmail.APIError) as error:
        # Avoid traceback/HTTP bodies, which can expose OAuth callbacks or credentials.
        message = str(error) if isinstance(error, (ValueError, APIError, gmail.APIError)) else type(error).__name__
        if isinstance(error, OSError) and error.filename:  # a path the user typed, never file contents
            message = f"{error.strerror or type(error).__name__}: {error.filename}"
        print(f"Error: {message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Anything already applied is recorded; rerun to continue.", file=sys.stderr)
        return 130
    except Exception as error:  # never a raw traceback: it can carry request URLs or token-bearing reprs
        if os.environ.get("TIDY_DEBUG"):
            raise
        print(f"Unexpected error ({type(error).__name__}). Rerun with TIDY_DEBUG=1 for details, and check the "
              "output before sharing it: it may include private data.", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
