from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from tidy.watch_history import parse, watch_counts

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
    def test_parse_keeps_only_watched_videos_that_have_a_channel(self):
        events = parse(HTML)

        self.assertEqual([(e["video_id"], e["channel_id"], e["channel_title"]) for e in events],
                         [("v1", "UCaaa", "Alpha"), ("v2", "UCaaa", "Alpha"), ("v3", "UCbbb", "Beta")])
        self.assertEqual(events[0]["watched_at"], datetime(2026, 9, 18, 21, 5, 11))

    def test_counts_per_channel_inside_the_window_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "watch-history.html"
            path.write_text(HTML, encoding="utf-8")

            self.assertEqual(watch_counts(path, days=90, now=NOW), {"UCaaa": 2})
            self.assertEqual(watch_counts(path, days=365, now=NOW), {"UCaaa": 2, "UCbbb": 1})


if __name__ == "__main__":
    unittest.main()
