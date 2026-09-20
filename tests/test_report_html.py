import re
import unittest

from tidy import report_html
from tidy.proposal import Proposal
from test_evidence_store import sample
from test_policy import judgment
from dataclasses import replace


def build(title="Alpha Labs", signals=("value low, Jev (0.4)", "watched 0 times in 42 days"), action="UNSUBSCRIBE", labels=None, gate=None):
    s = replace(sample(channel="chanA", title=title), videos=[
        {"id": "v1", "title": "First <b>video</b>", "description": "", "published_at": "2026-09-01T00:00:00Z",
         "duration": "PT10M", "url": "https://www.youtube.com/watch?v=v1"}])
    j = judgment(val=0.4)
    j.channel_id = "chanA"
    keep = replace(sample(channel="chanB", title="Beta Beats"), evidence_hash="h2")
    jb = judgment(val=2.8)
    jb.channel_id = "chanB"
    props = [Proposal("chanB", "KEEP", ["watched 5 times in 42 days"], "policy-2", "h2"),
             Proposal("chanA", action, list(signals), "policy-2", "h1")]
    return report_html.render(props, [j, jb], [s, keep], labels or {"chanA": "drop"},
                              gate or {"open": False, "reasons": ["9 labels, need 30"]})


class ReportHtmlTests(unittest.TestCase):
    def test_shows_what_the_owner_needs_to_decide(self):
        html = build()

        for needle in ("Alpha Labs", "UNSUBSCRIBE", "value low, Jev (0.4)", "https://www.youtube.com/channel/chanA",
                       "https://www.youtube.com/watch?v=v1", "9 labels, need 30", "tidy approve chanA",
                       "tidy label chanA keep", "Owner label: drop"):
            self.assertIn(needle, html)
        self.assertLess(html.index("Alpha Labs"), html.index("Beta Beats"))  # UNSUBSCRIBE before KEEP

    def test_counts_per_action_and_expiry_are_in_the_summary(self):
        html = build()

        self.assertRegex(html, r"UNSUBSCRIBE\D+1")
        self.assertRegex(html, r"KEEP\D+1")
        self.assertIn("2026-10-", html)  # sample expiry date (30 days after the fixture's fetch)

    def test_hostile_titles_and_signals_are_escaped(self):
        html = build(title="<script>alert(1)</script>", signals=("x", "<img src=x onerror=alert(1)>"))

        self.assertNotIn("<script>alert(1)", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("First &lt;b&gt;video&lt;/b&gt;", html)

    def test_page_is_self_contained_and_locked_down(self):
        html = build()

        self.assertIn("Content-Security-Policy", html)
        self.assertIn("default-src 'none'", html)
        self.assertIsNone(re.search(r"<link|@import|<img|<iframe|src=\"http|url\(http", html))


class ProposeHtmlCommandTests(unittest.TestCase):
    def test_propose_html_writes_the_page_and_reports_where(self):
        import contextlib, io, json, tempfile
        from pathlib import Path
        from tidy.__main__ import main

        with tempfile.TemporaryDirectory() as d:
            out, page = io.StringIO(), Path(d) / "proposals.html"
            with contextlib.redirect_stdout(out):
                code = main(["--data-dir", d, "propose", "--html", str(page)])

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue()), {"html": str(page), "channels": 0})
            self.assertIn("Tidy proposals", page.read_text())


if __name__ == "__main__":
    unittest.main()
