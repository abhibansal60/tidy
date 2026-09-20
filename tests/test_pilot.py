import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tidy import pilot, store
from tidy.__main__ import main
from tidy.youtube import YouTube
from test_collector import FakeYouTube, NOW


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = store.connect(self.root / "inventory.sqlite3")
        with self.db:
            for cid, title in [("chanA", "Alpha Channel"), ("chanB", "Beta Channel"), ("chanC", "Gamma")]:
                self.db.execute("INSERT INTO subscriptions VALUES (?, ?, ?, NULL, 1, ?)",
                                ("sub-" + cid, cid, title, NOW.isoformat()))
        self.labels = self.root / "labels.json"
        self.labels.write_text(json.dumps({"keep": ["alpha channel"], "sloppy": ["Beta Channel", "Nobody"]}))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_plan_adds_labeled_channels_by_title_and_estimates_quota(self):
        plan = pilot.plan(self.db, ["chanC"], self.labels, window=12)

        self.assertEqual(plan["channels"], ["chanC", "chanA", "chanB"])
        self.assertEqual(plan["unresolved_labels"], ["Nobody"])
        self.assertEqual(plan["estimated_units"], 9)
        self.assertEqual(plan["window"], 12)

    def test_plan_all_takes_every_active_subscription(self):
        plan = pilot.plan(self.db, [], None, window=12, all_active=True)

        self.assertEqual(plan["channels"], ["chanA", "chanB", "chanC"])
        self.assertEqual(plan["estimated_units"], 9)

    def test_run_saves_samples_and_reports_coverage_and_quota(self):
        fake = FakeYouTube({"chanA": ["v1", "v2"], "chanB": []})
        api = YouTube(fake.session)

        report = pilot.run(self.db, api, ["chanA", "chanB", "ghost"], window=12, now=NOW)

        self.assertEqual(report["collected"], 2)
        self.assertEqual(sorted(report["errors"]), ["ghost"])
        self.assertEqual(report["request_units"], api.units)
        self.assertEqual(report["coverage"]["chanA"], {"requested": 12, "collected": 2, "unavailable": 0})
        self.assertEqual(report["expires_at"], "2026-10-20T00:00:00+00:00")
        self.assertEqual([s.channel_id for s in store.latest_samples(self.db, now=NOW)], ["chanA", "chanB"])

    def test_collect_command_is_a_dry_run_by_default_and_needs_no_network(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--data-dir", str(self.root), "collect", "--channels", "chanC",
                         "--labels", str(self.labels)])

        self.assertEqual(code, 0)
        plan = json.loads(out.getvalue())
        self.assertEqual(plan["executes"], False)
        self.assertEqual(plan["channels"], ["chanC", "chanA", "chanB"])


if __name__ == "__main__":
    unittest.main()
