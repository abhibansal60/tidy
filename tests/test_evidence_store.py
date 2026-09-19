from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from tidy import store
from tidy.collector import CollectResult, EvidenceSample


NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def sample(channel="chanA", title="Channel A", fetched=NOW, evidence_hash="h1"):
    return EvidenceSample(
        channel_id=channel, title=title, description="About " + channel,
        videos=[{"id": "v1", "title": "Title v1", "description": "d", "published_at": "2026-09-01T00:00:00Z",
                 "duration": "PT10M", "url": "https://www.youtube.com/watch?v=v1"}],
        fetched_at=fetched.isoformat(), expires_at=(fetched + timedelta(days=30)).isoformat(),
        coverage={"requested": 12, "collected": 1, "unavailable": 0},
        newest_published_at="2026-09-01T00:00:00Z", evidence_hash=evidence_hash)


class EvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_saved_sample_reads_back_identical(self):
        original = sample()

        store.save_samples(self.db, CollectResult([original], {}), request_units=3, now=NOW)

        self.assertEqual(store.latest_samples(self.db, now=NOW), [original])
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 3)

    def test_new_sample_replaces_old_for_same_channel(self):
        store.save_samples(self.db, CollectResult([sample(title="Old", evidence_hash="h1")], {}), 3, now=NOW)
        later = NOW + timedelta(days=1)
        fresh = sample(title="New", fetched=later, evidence_hash="h2")

        store.save_samples(self.db, CollectResult([fresh], {}), 3, now=later)

        self.assertEqual(store.latest_samples(self.db, now=later), [fresh])

    def test_failed_channel_keeps_previous_sample_and_run_records_error(self):
        original = sample(channel="chanA")
        store.save_samples(self.db, CollectResult([original], {}), 3, now=NOW)
        later = NOW + timedelta(days=1)

        store.save_samples(self.db, CollectResult([sample(channel="chanB", fetched=later)],
                                                  {"chanA": "Local quota budget reached."}), 7, now=later)

        self.assertIn(original, store.latest_samples(self.db, ["chanA"], now=later))
        self.assertEqual(store.last_run(self.db), {"at": later.isoformat(), "request_units": 7, "collected": 1,
                                                   "failed": 1, "errors": {"chanA": "Local quota budget reached."}})

    def test_expired_samples_are_never_returned(self):
        store.save_samples(self.db, CollectResult([sample()], {}), 3, now=NOW)

        self.assertEqual(len(store.latest_samples(self.db, now=NOW + timedelta(days=29))), 1)
        self.assertEqual(store.latest_samples(self.db, now=NOW + timedelta(days=31)), [])

    def test_purge_removes_only_expired_samples_and_reports_count(self):
        store.save_samples(self.db, CollectResult([sample(channel="old")], {}), 3, now=NOW)
        later = NOW + timedelta(days=40)
        store.save_samples(self.db, CollectResult([sample(channel="new", fetched=later)], {}), 3, now=later)

        self.assertEqual(store.purge(self.db, now=later), 1)
        self.assertEqual([s.channel_id for s in store.latest_samples(self.db, now=later)], ["new"])
        self.assertEqual(store.purge(self.db, now=later), 0)

    def test_opening_the_database_purges_expired_samples(self):
        path = Path(self.temp.name) / "reopen.sqlite3"
        first = store.connect(path)
        stale = datetime.now(timezone.utc) - timedelta(days=60)
        store.save_samples(first, CollectResult([sample(fetched=stale)], {}), 3, now=stale)
        first.close()

        reopened = store.connect(path)

        self.assertEqual(store.purge(reopened), 0)
        reopened.close()

    def test_newer_schema_is_refused(self):
        path = Path(self.temp.name) / "future.sqlite3"
        future = store.connect(path)
        future.execute("PRAGMA user_version=99")
        future.close()

        with self.assertRaises(ValueError):
            store.connect(path)


if __name__ == "__main__":
    unittest.main()
