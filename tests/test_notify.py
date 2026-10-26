import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tidy import notify

NOW = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)


def row(id, sender, action="KEEP", category="Needs Reply", confidence=0.9):
    return {"id": id, "sender": sender, "action": action, "category": category, "confidence": confidence}


def doc(rows, hours_ago=1):
    return {"run_at": (NOW - timedelta(hours=hours_ago)).isoformat(), "rows": rows}


class BuildTests(unittest.TestCase):
    def test_silent_when_nothing_needs_owner(self):
        self.assertIsNone(notify.build(doc([row("a", "Shop <s@x.com>", "TRASH", "Promos"), row("b", "N <n@x.com>", "ARCHIVE")]), NOW))

    def test_pushes_counts_and_top_sender_names_only(self):
        title, body, prio = notify.build(doc([row("a", "HDFC ERGO <h@x.com>", confidence=1.0), row("b", "Google <g@x.com>", confidence=0.9),
                                              row("c", "Google <g@x.com>", confidence=0.8), row("d", "S <s@x.com>", "TRASH", "Promos")]), NOW)
        self.assertEqual(title, "3 mails need you")
        self.assertIn("HDFC ERGO, Google", body)
        self.assertIn("1 noise to clear", body)
        self.assertEqual(prio, "default")

    def test_more_than_three_senders_are_summarised(self):
        rows = [row(str(i), f"Sender{i} <s{i}@x.com>", confidence=1 - i / 100) for i in range(5)]
        self.assertIn("+2 more", notify.build(doc(rows), NOW)[1])

    def test_stale_or_missing_run_is_a_high_priority_push(self):
        self.assertEqual(notify.build(doc([], hours_ago=40), NOW)[2], "high")
        self.assertEqual(notify.build(None, NOW)[0], "Mail run is stale")

    def test_fyi_alone_stays_silent(self):
        self.assertIsNone(notify.build(doc([row("a", "HDFC <alerts@hdfc.in>", "REVIEW", "Updates", 0.95)]), NOW))


class MainTests(unittest.TestCase):
    """`python -m tidy.notify` as the cron runs it: from the checkout, reading .tidy/ntfy_topic and data/mail_triage/runs."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.runs = self.root / "data/mail_triage/runs"
        self.runs.mkdir(parents=True)
        (self.root / ".tidy").mkdir()

    def write_run(self, name, rows, hours_ago=1):
        run_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
        (self.runs / name).write_text(json.dumps({"run_at": run_at, "rows": rows}))

    def main(self):
        with patch.object(notify, "send") as send, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(notify.main(Path(".tidy")), 0)
        return send

    def test_no_topic_sends_nothing(self):
        self.write_run("2026-10-02.json", [row("a", "A <a@x.com>")])
        self.main().assert_not_called()

    def test_newest_run_file_by_date_is_used(self):
        (self.root / ".tidy/ntfy_topic").write_text("topic-123\n")
        self.write_run("2026-10-02.json", [row("b", "New <n@x.com>")])
        self.write_run("2026-10-01.json", [row("a", "Old <o@x.com>")])  # written last: newest by name, not mtime
        self.write_run("notes.json", [row("c", "Ignored <i@x.com>")])

        send = self.main()

        topic, title, body, priority = send.call_args.args
        self.assertEqual(topic, "topic-123")
        self.assertIn("New", body)
        self.assertNotIn("Old", body)

    def test_quiet_run_stays_silent(self):
        (self.root / ".tidy/ntfy_topic").write_text("t")
        self.write_run("2026-10-02.json", [row("a", "S <s@x.com>", "TRASH", "Promos")])
        self.main().assert_not_called()

    def test_no_run_at_all_is_a_high_priority_push(self):
        (self.root / ".tidy/ntfy_topic").write_text("t")
        self.assertEqual(self.main().call_args.args[1:], ("Mail run is stale", unittest.mock.ANY, "high"))


class SendTests(unittest.TestCase):
    def test_posts_to_the_topic_with_title_priority_and_dashboard_link(self):
        with patch("urllib.request.urlopen") as urlopen:
            notify.send("topic-123", "2 mails need you", "2 need you (A, B)", "default")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://ntfy.sh/topic-123")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data, b"2 need you (A, B)")
        self.assertEqual(request.get_header("Title"), "2 mails need you")
        self.assertEqual(request.get_header("Priority"), "default")
        self.assertEqual(request.get_header("Click"), notify.URL)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 15)
