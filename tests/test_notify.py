import contextlib
from datetime import datetime, timedelta, timezone
import http.client
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

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

    def test_archived_counts_only_applied_archives(self):
        rows = [row("a", "A <a@x.com>"), row("b", "N <n@x.com>", "ARCHIVE", "Updates"),
                {**row("c", "N <n@x.com>", "ARCHIVE", "Updates"), "outcome": "applied"},
                {**row("d", "N <n@x.com>", "ARCHIVE", "Updates"), "outcome": "held"}]
        self.assertIn("1 archived for you", notify.build(doc(rows), NOW)[1])
        self.assertNotIn("archived", notify.build(doc(rows[:2]), NOW)[1])  # dry run or closed gate: nothing archived

    def test_more_than_three_senders_are_summarised(self):
        rows = [row(str(i), f"Sender{i} <s{i}@x.com>", confidence=1 - i / 100) for i in range(5)]
        self.assertIn("+2 more", notify.build(doc(rows), NOW)[1])

    def test_stale_or_missing_run_is_a_high_priority_push(self):
        self.assertEqual(notify.build(doc([], hours_ago=40), NOW)[2], "high")
        self.assertEqual(notify.build(None, NOW)[0], "Mail run is stale")

    def test_fyi_alone_stays_silent(self):
        self.assertIsNone(notify.build(doc([row("a", "HDFC <alerts@hdfc.in>", "REVIEW", "Updates", 0.95)]), NOW))


class OfflineTests(unittest.TestCase):
    def test_failed_push_is_one_line_and_exit_1_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            self.addCleanup(os.chdir, os.getcwd())
            os.chdir(d)
            Path(".tidy").mkdir()
            Path(".tidy/ntfy_topic").write_text("secret-topic")
            err = io.StringIO()
            for error in (urllib.error.URLError("name resolution"), http.client.IncompleteRead(b""),
                          http.client.InvalidURL("https://ntfy.sh/secret-topic x")):
                with patch.object(notify, "send", side_effect=error), \
                        contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(notify.main(Path(".tidy")), 1)
        self.assertEqual(err.getvalue(), "push failed (URLError); not sent: Mail run is stale\n"
                                         "push failed (IncompleteRead); not sent: Mail run is stale\n"
                                         "push failed (InvalidURL); not sent: Mail run is stale\n")
