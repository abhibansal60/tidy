import unittest
from datetime import datetime, timedelta, timezone

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
