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

from . import cli, discovery, escalate, experiment, gmail, mail, mail_report_html, mutate, pilot, profile, report_html, review, setup_check, store
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
        derived = review.derive(db, config)[0]
        if args.per_action_gate:
            per = review.action_gates(db, derived, config)
            reasons = [f"{a}: " + "; ".join(per[a]["gate"]["reasons"]) for a, on in gates.items() if on and not per[a]["gate"]["open"]]
        else:
            reasons = review.gate_status(review.agreement(db, derived), config)["reasons"]
        if reasons:
            raise ValueError("Calibration gate closed: " + "; ".join(reasons) + ". Pass --override-gate to act anyway.")
    caps = {"unsubscribe": config["caps"]["unsubscribe"] if args.cap_unsubscribe is None else args.cap_unsubscribe,
            "subscribe": config["caps"]["subscribe"] if args.cap_subscribe is None else args.cap_subscribe}
    return mutate.act(db, api, proposals, gates, caps, email, args.execute)


def main(argv=None):
    args = cli.build_parser().parse_args(argv)
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
            proposals = review.derive(db, config)[0]
            stats = review.agreement(db, proposals)
            output = {**stats, "gate": review.gate_status(stats, config)}
            if args.per_action:
                output["per_action"] = review.action_gates(db, proposals, config)
        elif args.command == "to-label":
            proposals, judgments, samples = review.derive(db, profile.load(args.data_dir / "profile.json"))
            by_p, by_s = {p.channel_id: p for p in proposals}, {s.channel_id: s for s in samples}
            output = {"channels": [{"channel_id": c, "title": by_s[c].title, "proposal": by_p[c].action,
                                    "signals": by_p[c].signals}
                                   for c in review.sample_for_labeling(db, judgments, args.count)]}
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
