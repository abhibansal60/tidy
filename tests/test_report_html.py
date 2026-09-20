import base64
import hashlib
import html
import re
import unittest

from tidy import report_html
from tidy.proposal import Proposal
from test_evidence_store import sample
from test_policy import judgment
from dataclasses import replace


def build(title="Alpha Labs", signals=("value low, Jev (0.4)", "watched 0 times in 42 days"), action="UNSUBSCRIBE", labels=None, gate=None,
          video_url="https://www.youtube.com/watch?v=v1", data_dir=".tidy"):
    s = replace(sample(channel="chanA", title=title), videos=[
        {"id": "v1", "title": "First <b>video</b>", "description": "", "published_at": "2026-09-01T00:00:00Z",
         "duration": "PT10M", "url": video_url}])
    j = judgment(val=0.4)
    j.channel_id = "chanA"
    keep = replace(sample(channel="chanB", title="Beta Beats"), evidence_hash="h2")
    jb = judgment(val=2.8)
    jb.channel_id = "chanB"
    props = [Proposal("chanB", "KEEP", ["watched 5 times in 42 days"], "policy-2", "h2"),
             Proposal("chanA", action, list(signals), "policy-2", "h1")]
    return report_html.render(props, [j, jb], [s, keep], labels or {"chanA": "drop"},
                              gate or {"open": False, "reasons": ["9 labels, need 30"]}, data_dir)


class ReportHtmlTests(unittest.TestCase):
    def test_shows_what_the_owner_needs_to_decide(self):
        html = build()

        for needle in ("Alpha Labs", "UNSUBSCRIBE", "value low, Jev (0.4)", "https://www.youtube.com/channel/chanA",
                       "https://www.youtube.com/watch?v=v1", "9 labels, need 30", "tidy approve chanA",
                       "tidy label chanA keep", "Your label: drop"):
            self.assertIn(needle, html)
        self.assertLess(html.index("Alpha Labs"), html.index("Beta Beats"))  # UNSUBSCRIBE before KEEP

    def test_counts_per_action_and_expiry_are_in_the_summary(self):
        html = build()

        self.assertRegex(html, r"(?i)unsubscribe\D+1")
        self.assertRegex(html, r"(?i)keep\D+1")
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
        self.assertNotIn("unsafe-inline", html)  # scripts and styles are allowed only by hash
        for tag, directive in (("script", "script-src"), ("style", "style-src")):
            body = re.search(rf"<{tag}>(.*?)</{tag}>", html, re.S)[1]
            digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            self.assertIn(f"{directive} 'sha256-{digest}'", html)

    def test_only_youtube_https_urls_become_links(self):
        for bad in ("javascript:alert(1)", "data:text/html,x", "http://www.youtube.com/watch?v=v1", "https://evil.example/x"):
            with self.subTest(bad):
                html = build(video_url=bad)
                self.assertNotIn(f'href="{bad}', html)
                self.assertIn("First &lt;b&gt;video&lt;/b&gt;", html)  # the title still shows, as text

    def test_commands_target_the_data_directory_the_page_was_made_from(self):
        default = build()
        custom = build(data_dir="/tmp/my data")

        self.assertIn("tidy approve chanA", default)
        self.assertNotIn("--data-dir", default)
        self.assertIn("tidy --data-dir '/tmp/my data' approve chanA", html.unescape(custom))  # what the browser shows

    def test_a_hostile_data_directory_cannot_inject_markup(self):
        html = build(data_dir="/tmp/<b>mine</b>")

        self.assertNotIn("<b>mine</b>", html)
        self.assertIn("&lt;b&gt;mine&lt;/b&gt;", html)

    def test_map_dots_name_their_channel_and_selecting_one_reveals_its_row(self):
        html = build()

        self.assertRegex(html, r"<title>Alpha Labs: ")
        self.assertIn("r.open=true", html)  # the script opens the target row and clears filters first

    def test_scores_state_their_scale_and_direction_and_the_batch_scope(self):
        html = build()

        self.assertIn("of 1", html)
        self.assertIn("higher is riskier", html)
        self.assertIn("every approved channel", html)
        self.assertIn("apparent value", html)
        self.assertNotIn("scores content quality", html)

    def test_gate_wording_never_promises_automatic_action(self):
        opened = build(gate={"open": True, "reasons": []})

        self.assertIn("owner-started", opened)
        self.assertIn("caps", opened)

    def test_page_explains_the_dry_run_step_and_the_retention_deadline(self):
        html = build()

        self.assertIn("tidy unsubscribe --execute", html)
        self.assertIn("dry run", html)
        self.assertIn("Delete or refresh by 2026-10-", html)


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
