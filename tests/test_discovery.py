from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from tidy import discovery, profile, store
from test_watch_history import cell

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


class DiscoveryTests(unittest.TestCase):
    def test_candidates_are_unsubscribed_channels_watched_often_most_first(self):
        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "watch-history.html"
            html.write_text("<html>" + "".join(
                [cell(f"a{i}", "UCsubbed", "Subbed", "Sep 10, 2026, 9:00:00 AM IST") for i in range(5)]
                + [cell(f"b{i}", "UCmany", "Many", "Sep 11, 2026, 9:00:00 AM IST") for i in range(4)]
                + [cell(f"c{i}", "UCthree", "Three", "Sep 12, 2026, 9:00:00 AM IST") for i in range(3)]
                + [cell(f"d{i}", "UCfew", "Few", "Sep 13, 2026, 9:00:00 AM IST") for i in range(2)]
                + [cell(f"e{i}", "UCold", "Old", "Jan 13, 2026, 9:00:00 AM IST") for i in range(9)]) + "</html>",
                encoding="utf-8")
            db = store.connect(Path(d) / "inventory.sqlite3")
            db.execute("INSERT INTO subscriptions VALUES ('s1', 'UCsubbed', 'Subbed', NULL, 1, ?)", (NOW.isoformat(),))
            config = {**profile.load(Path(d) / "none.json"), "watch_history_path": str(html)}

            found = discovery.candidates(db, config, now=NOW)
            capped = discovery.candidates(db, config, now=NOW, limit=1)
            db.close()

        self.assertEqual(found, [("UCmany", 4), ("UCthree", 3)])
        self.assertEqual(capped, [("UCmany", 4)])

    def test_no_watch_history_means_no_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            db = store.connect(Path(d) / "inventory.sqlite3")
            self.assertEqual(discovery.candidates(db, profile.load(Path(d) / "none.json")), [])
            db.close()


class DeriveCandidateTests(unittest.TestCase):
    def test_unsubscribed_channels_get_subscribe_proposals_and_subscribed_ones_keep_the_watch_policy(self):
        from test_evidence_store import sample
        from test_policy import judgment
        from tidy.collector import CollectResult
        from tidy.judge import interests_key
        from tidy import review

        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "watch-history.html"
            html.write_text("<html>" + "".join(
                cell(f"{c}{i}", c, c, "Sep 10, 2026, 9:00:00 AM IST") for c in ("UCnew", "UCjunk", "UCsubbed") for i in range(4))
                + "</html>", encoding="utf-8")
            config = {**profile.load(Path(d) / "none.json"), "watch_history_path": str(html), "schema_id": "titles-v1"}
            db = store.connect(Path(d) / "inventory.sqlite3")
            db.execute("INSERT INTO subscriptions VALUES ('s1', 'UCsubbed', 'Subbed', NULL, 1, ?)", (NOW.isoformat(),))
            key = interests_key(config["interests"], config["viewing_habits"])
            for cid, value in [("UCnew", 2.6), ("UCjunk", 0.2), ("UCsubbed", 2.6)]:
                s = sample(channel=cid, evidence_hash="h" + cid, fetched=NOW)
                store.save_samples(db, CollectResult([s], {}), 1, now=NOW)
                j = judgment(val=value, evidence_hash="h" + cid)
                j.channel_id = cid
                store.put_judgment(db, j, key, s.expires_at)

            proposals, judgments, samples = review.derive(db, config, now=NOW)
            db.close()

        self.assertEqual({p.channel_id: p.action for p in proposals}, {"UCnew": "SUBSCRIBE", "UCsubbed": "KEEP"})
        self.assertEqual([j.channel_id for j in judgments], [s.channel_id for s in samples])
        self.assertEqual(len(proposals), len(judgments))


class DiscoverCommandTests(unittest.TestCase):
    def test_discover_is_a_dry_run_by_default_and_needs_no_network(self):
        import contextlib, io, json
        from tidy.__main__ import main

        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "watch-history.html"
            html.write_text("<html>" + "".join(cell(f"v{i}", "UCnew", "New", "Sep 10, 2026, 9:00:00 AM IST")
                                                for i in range(4)) + "</html>", encoding="utf-8")
            (Path(d) / "profile.json").write_text(json.dumps({"watch_history_path": str(html), "watch_window_days": 5000}))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--data-dir", d, "discover"])

        plan = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual((plan["executes"], plan["candidates"], plan["estimated_units"]),
                         (False, [{"channel_id": "UCnew", "watches": 4}], 3))
