from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from tidy.watch_history import history_status, parse, watch_counts

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def cell(video, channel, name, when):
    return ('<div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">Watched '
            f'<a href="https://www.youtube.com/watch?v={video}">Title {video}</a><br>'
            f'<a href="https://www.youtube.com/channel/{channel}">{name}</a><br>{when}<br></div>')


HTML = ("<html><body>"
        + cell("v1", "UCaaa", "Alpha", "Sep 18, 2026, 9:05:11 PM IST")
        + cell("v2", "UCaaa", "Alpha", "Aug 1, 2026, 7:30:00 AM IST")
        + cell("v3", "UCbbb", "Beta", "Jan 2, 2026, 12:00:00 AM IST")
        + '<div class="content-cell mdl-cell">Watched a video that has been removed<br>Sep 1, 2026, 1:00:00 PM IST<br></div>'
        + '<div class="content-cell mdl-cell">Viewed <a href="https://www.youtube.com/post/x">A post</a><br>Sep 1, 2026, 1:00:00 PM IST<br></div>'
        + "</body></html>")


class WatchHistoryTests(unittest.TestCase):
    def test_missing_stale_empty_and_future_history_are_distinct_from_recent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history.html"
            self.assertEqual(history_status(p, 42, NOW)["status"], "missing")
            for html, expected in [("<html></html>", "empty_or_unsupported"),
                                   (cell("v", "c", "C", "Jan 1, 2020, 1:00:00 PM IST"), "stale"),
                                   (cell("v", "c", "C", "Jan 1, 2030, 1:00:00 PM IST"), "future_dated"),
                                   (HTML, "recent")]:
                p.write_text(html)
                status = history_status(p, 42, NOW)
                self.assertEqual(status["status"], expected)
                if expected != "recent":
                    self.assertEqual(status["counts"], {})

    def test_parse_keeps_only_watched_videos_that_have_a_channel(self):
        events = parse(HTML)

        self.assertEqual([(e["video_id"], e["channel_id"], e["channel_title"]) for e in events],
                         [("v1", "UCaaa", "Alpha"), ("v2", "UCaaa", "Alpha"), ("v3", "UCbbb", "Beta")])
        self.assertEqual(events[0]["watched_at"], datetime(2026, 9, 18, 15, 35, 11, tzinfo=timezone.utc))

    def test_counts_per_channel_inside_the_window_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "watch-history.html"
            path.write_text(HTML, encoding="utf-8")

            self.assertEqual(watch_counts(path, days=90, now=NOW), {"UCaaa": 2})
            self.assertEqual(watch_counts(path, days=365, now=NOW), {"UCaaa": 2, "UCbbb": 1})

    def test_parse_reads_day_first_takeout_dates(self):
        html = (cell("v1", "UCaaa", "Alpha", "18 Sept 2026, 21:05:11 IST")
                + cell("v2", "UCbbb", "Beta", "2 Jan 2026, 9:00:00 pm GMT"))

        self.assertEqual([e["watched_at"] for e in parse(html)],
                         [datetime(2026, 9, 18, 15, 35, 11, tzinfo=timezone.utc), datetime(2026, 1, 2, 21, 0, 0, tzinfo=timezone.utc)])

    def test_recency_compares_equivalent_ist_utc_and_offset_instants(self):
        now = datetime(2026, 11, 6, 11, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "history.html"
            for stamp in ("Nov 6, 2026, 5:00:00 PM IST", "Nov 6, 2026, 11:30:00 AM UTC",
                          "Nov 6, 2026, 5:00:00 PM +05:30"):
                p.write_text(cell("v", "c", "C", stamp))
                result = history_status(p, 42, now)
                self.assertEqual(result["status"], "recent")
                self.assertEqual(result["counts"], {"c": 1})
            p.write_text(cell("v", "c", "C", "Nov 6, 2026, 5:01:00 PM IST"))
            self.assertEqual(history_status(p, 42, now)["status"], "future_dated")
            p.write_text(cell("v", "c", "C", "Nov 6, 2026, 5:00:00 PM UNKNOWN"))
            self.assertEqual(history_status(p, 42, now)["status"], "empty_or_unsupported")


if __name__ == "__main__":
    unittest.main()
