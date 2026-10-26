"""`tidy mail-triage` and `tidy mail-act` end to end through `main`, with fake Gmail and Jev. Never real Gmail."""

import contextlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from tidy.__main__ import main
from tidy.gmail import Gmail
from test_gmail import response
from test_mail_triage import CATEGORY, OWNER, SubjectClient, inbox


class FakeGmail:
    """`gmail.connect` stand-in: records which tokens were opened and hands out a read or write fake."""
    def __init__(self):
        self.read = inbox()
        self.write = Mock(calls=0, max_calls=1000)
        self.write.labels.return_value = ["INBOX"]
        self.opened = []

    @contextlib.contextmanager
    def connect(self, token_path, expected_email=None, write=False, max_calls=1200):
        self.opened.append((Path(token_path).name, write, expected_email))
        yield self.write if write else self.read


class MailCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config.json").write_text(json.dumps({"expected_email": OWNER, "mail_email": OWNER}))
        self.gmail = FakeGmail()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        client = contextlib.nullcontext(SubjectClient(CATEGORY))
        with patch("tidy.gmail.connect", self.gmail.connect), \
                patch("tidy.setup_check.typesafe_client", return_value=client), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--data-dir", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def triage(self, *flags):
        return self.run_cli("mail-triage", "--execute", "--json", str(self.root / "run.json"), *flags)


class MailTriageCliTests(MailCliTests):
    def test_without_execute_opens_no_token(self):
        code, out, _ = self.run_cli("mail-triage", "--apply", "--override-gate")

        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out)["executes"])
        self.assertEqual(self.gmail.opened, [])

    def test_without_apply_only_the_read_token_is_opened(self):
        code, out, _ = self.triage("--override-gate")

        self.assertEqual(code, 0)
        self.assertEqual(self.gmail.opened, [("token_mail.json", False, OWNER)])
        self.gmail.write.batch_modify.assert_not_called()
        self.assertEqual(json.loads((self.root / "run.json").read_text())["mode"], "dry")

    def test_apply_without_override_opens_the_write_token_but_changes_nothing(self):
        code, out, _ = self.triage("--apply")

        self.assertEqual(code, 0)
        self.assertIn(("token_mail_write.json", True, OWNER), self.gmail.opened)
        self.gmail.write.batch_modify.assert_not_called()
        self.assertEqual(json.loads(out)["outcome_counts"], {"applied": 0, "held": 4})

    def test_cron_flags_archive_only_and_write_a_private_run_file(self):
        code, out, _ = self.triage("--apply", "--override-gate", "--cap-archive", "100")

        self.assertEqual(code, 0)
        self.gmail.write.batch_modify.assert_called_once_with(["arch1", "arch2"], add=[], remove=["INBOX"])
        self.gmail.write.trash.assert_not_called()
        path = self.root / "run.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        doc = json.loads(path.read_text())
        self.assertEqual(doc["mode"], "apply")
        self.assertEqual({r["id"]: r["outcome"] for r in doc["rows"] if r["action"] in ("TRASH", "SPAM")},
                         {"promo": "held", "spam": "held"})

    def test_cap_archive_flag_is_honoured(self):
        self.triage("--apply", "--override-gate", "--cap-archive", "1")

        self.gmail.write.batch_modify.assert_called_once_with(["arch1"], add=[], remove=["INBOX"])

    def test_missing_config_fails_without_touching_gmail(self):
        (self.root / "config.json").unlink()

        code, _, err = self.triage("--apply", "--override-gate")

        self.assertEqual(code, 1)
        self.assertIn("Not set up yet", err)
        self.assertEqual(self.gmail.opened, [])


class MailActCliTests(MailCliTests):
    def held_run(self):
        self.triage("--apply", "--override-gate", "--cap-archive", "100")
        self.gmail.write.reset_mock()
        self.gmail.opened.clear()
        return self.root / "run.json"

    def test_dry_run_previews_held_trash_and_spam_and_opens_no_token(self):
        run = self.held_run()

        code, out, _ = self.run_cli("mail-act", "--run", str(run))

        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertFalse(result["executes"])
        self.assertEqual(sorted((p["id"], p["action"]) for p in result["preview"]), [("promo", "TRASH"), ("spam", "SPAM")])
        self.assertEqual(self.gmail.opened, [])

    def test_execute_rechecks_applies_and_records_outcomes_so_a_rerun_is_a_no_op(self):
        run = self.held_run()

        code, out, _ = self.run_cli("mail-act", "--run", str(run), "--execute")

        self.assertEqual(code, 0)
        self.assertEqual(self.gmail.opened, [("token_mail_write.json", True, OWNER)])
        self.gmail.write.trash.assert_called_once_with("promo")
        self.gmail.write.batch_modify.assert_called_once_with(["spam"], add=["SPAM"], remove=["INBOX"])
        self.assertEqual(json.loads(out)["applied"], 2)
        rows = {r["id"]: r for r in json.loads(run.read_text())["rows"]}
        self.assertEqual((rows["promo"]["outcome"], rows["spam"]["outcome"]), ("applied", "applied"))
        self.assertEqual(stat.S_IMODE(run.stat().st_mode), 0o600)

        self.gmail.write.reset_mock()
        code, out, _ = self.run_cli("mail-act", "--run", str(run), "--execute")

        self.gmail.write.trash.assert_not_called()
        self.gmail.write.batch_modify.assert_not_called()
        self.assertEqual(json.loads(out)["applied"], 0)

    def test_mail_starred_or_moved_since_the_run_is_skipped_and_recorded(self):
        run = self.held_run()
        self.gmail.write.labels.side_effect = {"promo": ["INBOX", "STARRED"], "spam": ["CATEGORY_UPDATES"]}.get

        code, out, _ = self.run_cli("mail-act", "--run", str(run), "--execute")

        self.assertEqual(code, 0)
        self.gmail.write.trash.assert_not_called()
        self.gmail.write.batch_modify.assert_not_called()
        self.assertEqual(json.loads(out)["skipped"], {"promo": "skipped: starred since the run",
                                                      "spam": "skipped: no longer in inbox"})
        rows = {r["id"]: r["outcome"] for r in json.loads(run.read_text())["rows"]}
        self.assertEqual(rows["promo"], "skipped: starred since the run")

    def test_actions_flag_limits_to_trash(self):
        run = self.held_run()

        self.run_cli("mail-act", "--run", str(run), "--actions", "TRASH", "--execute")

        self.gmail.write.trash.assert_called_once_with("promo")
        self.gmail.write.batch_modify.assert_not_called()

    def test_hand_edited_id_is_refused_before_any_change(self):
        for tampered in ("promo", "spam"):  # first and last held row: the later one is reached after a live read
            with self.subTest(tampered=tampered):
                run = self.held_run()
                doc = json.loads(run.read_text())
                next(r for r in doc["rows"] if r["id"] == tampered)["id"] = "../profile"
                run.write_text(json.dumps(doc))
                session = Mock()
                session.get.return_value = response({"labelIds": ["INBOX"]})
                self.gmail.write = Gmail(session)  # the real client, so the real ID check runs

                code, _, err = self.run_cli("mail-act", "--run", str(run), "--execute")

                self.assertEqual(code, 1)
                self.assertIn("Invalid Gmail message ID", err)
                session.post.assert_not_called()
                self.gmail = FakeGmail()

if __name__ == "__main__":
    unittest.main()
