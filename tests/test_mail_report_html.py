import unittest

from tidy import mail_report_html


def row(id="m1", subject="Invoice ready", sender="Billing <b@x.com>", category="Updates",
       confidence=0.9, action="ARCHIVE", signals=None, outcome=None, unsubscribe=None):
    return {"id": id, "subject": subject, "sender": sender, "category": category, "confidence": confidence,
            "action": action, "signals": signals or [f"category {category} ({confidence:.2f})"], "outcome": outcome,
            "unsubscribe": unsubscribe}


class RenderTests(unittest.TestCase):
    def test_dry_run_shows_no_outcomes_and_says_so(self):
        html = mail_report_html.render([row()], applied=False)

        self.assertIn("dry run", html)
        self.assertNotIn("Outcome:", html)

    def test_applied_run_shows_outcome_per_row(self):
        html = mail_report_html.render([row(outcome="applied")], applied=True)

        self.assertIn("Outcome: Applied", html)
        self.assertIn("were applied to Gmail", html)

    def test_unsubscribe_link_rendered_as_clickable_not_autofetched(self):
        html = mail_report_html.render([row(action="TRASH", category="Promos",
                                            unsubscribe={"http": "https://x.com/unsub?id=1", "mailto": None})])

        self.assertIn('href="https://x.com/unsub?id=1"', html)
        self.assertIn("Unsubscribe link", html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_mailto_only_unsubscribe_shown_as_mail_link(self):
        html = mail_report_html.render([row(unsubscribe={"http": None, "mailto": "mailto:unsub@x.com"})])

        self.assertIn('href="mailto:unsub@x.com"', html)
        self.assertIn("Unsubscribe by email", html)

    def test_no_unsubscribe_info_renders_nothing_extra(self):
        html = mail_report_html.render([row(unsubscribe=None)])

        self.assertNotIn("Unsubscribe", html)

    def test_unsubscribe_shortlist_groups_by_sender_most_first(self):
        unsub = {"http": "https://x.com/u", "mailto": None}
        rows = [row(id=f"a{i}", sender="Shop <deals@shop.com>", action="TRASH", unsubscribe=unsub) for i in range(3)]
        rows += [row(id="b1", sender="News <n@news.com>", unsubscribe=unsub),
                 row(id="c1", sender="Friend <f@x.com>", action="KEEP", unsubscribe=unsub)]  # KEEP never shortlisted

        html = mail_report_html.render(rows)

        self.assertIn("Unsubscribe shortlist", html)
        self.assertIn("2 bulk senders", html)
        self.assertLess(html.index("Shop (3)"), html.index("News (1)"))
        self.assertNotIn("Friend (", html)

    def test_no_dashes_in_lede_prose(self):
        html = mail_report_html.render([row(action="TRASH", outcome="held")], applied=True)
        self.assertNotIn("\u2014", html)
        self.assertNotIn("\u2013", html)

    def test_error_outcome_shown_verbatim_not_hidden(self):
        html = mail_report_html.render([row(action="TRASH", category="Promos", outcome="error: quota exceeded")], applied=True)

        self.assertIn("Outcome: error: quota exceeded", html)

    def test_held_trash_proposal_never_claims_applied(self):
        html = mail_report_html.render([row(action="TRASH", category="Promos", outcome="held")], applied=True)

        self.assertIn("Outcome: Held for review", html)
        self.assertNotIn("Outcome: Applied", html)

    def test_review_sorts_before_archive_trash_and_keep(self):
        html = mail_report_html.render([
            row(id="a", subject="AAA archived", action="ARCHIVE"),
            row(id="t", subject="TTT trashed", action="TRASH", category="Promos"),
            row(id="r", subject="RRR review", action="REVIEW", confidence=0.4),
            row(id="k", subject="KKK keep", action="KEEP", category="Needs Reply"),
        ])

        self.assertLess(html.index("RRR review"), html.index("AAA archived"))
        self.assertLess(html.index("AAA archived"), html.index("TTT trashed"))
        self.assertLess(html.index("TTT trashed"), html.index("KKK keep"))

    def test_html_escapes_subject_and_sender(self):
        html = mail_report_html.render([row(subject="<script>alert(1)</script>", sender="a<b@x.com>")])

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_counts_tab_reflects_action_mix(self):
        html = mail_report_html.render([row(action="ARCHIVE"), row(action="ARCHIVE"), row(action="SPAM", category="Spam")])

        self.assertIn("Archive 2", html)
        self.assertIn("Spam 1", html)

    def test_verdict_badge_is_past_tense_only_when_actually_applied(self):
        applied_html = mail_report_html.render([row(action="ARCHIVE", outcome="applied")], applied=True)
        held_html = mail_report_html.render([row(action="ARCHIVE", outcome="held")], applied=True)
        dry_html = mail_report_html.render([row(action="ARCHIVE")], applied=False)

        self.assertIn('class="verdict">Archived<', applied_html)
        self.assertIn('class="verdict">Archive<', held_html)
        self.assertIn('class="verdict">Archive<', dry_html)

    def test_lede_reflects_actual_applied_count_not_requested_mode(self):
        none_applied = mail_report_html.render([row(action="ARCHIVE", outcome="held")], applied=True)
        some_applied = mail_report_html.render([row(id="a", action="ARCHIVE", outcome="applied"),
                                                 row(id="b", action="TRASH", category="Promos", outcome="held")], applied=True)

        self.assertIn("Nothing was actually applied this run", none_applied)
        self.assertIn("1 action(s) below were applied", some_applied)
