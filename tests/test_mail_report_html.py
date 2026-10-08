import unittest

from tidy import mail_report_html as m


def row(id="m1", subject="Invoice ready", sender="Billing <b@x.com>", category="Updates",
        confidence=0.9, action="ARCHIVE", signals=None, outcome=None, unsubscribe=None, thread_id=None):
    return {"id": id, "thread_id": thread_id or id, "subject": subject, "sender": sender, "snippet": "snip",
            "category": category, "confidence": confidence, "action": action,
            "signals": signals or [f"category {category} ({confidence:.2f})"], "outcome": outcome,
            "unsubscribe": unsubscribe}


class SectionTabsTests(unittest.TestCase):
    def test_mail_page_has_mail_and_jobs_tabs_with_mail_current(self):
        html = m.render([row()])
        self.assertIn('<a href="/" aria-current="page">Mail</a><a href="/jobs">Jobs</a>', html)


class BucketTests(unittest.TestCase):
    def test_keep_needs_you(self):
        self.assertEqual(m.bucket(row(action="KEEP", category="Needs Reply")), "needs_you")

    def test_automated_confident_update_review_is_fyi(self):
        r = row(action="REVIEW", sender="HDFC <alerts@hdfcbank.bank.in>", confidence=0.92)
        self.assertEqual(m.bucket(r), "fyi")

    def test_review_stays_needs_you_when_low_confidence_or_human_sender(self):
        self.assertEqual(m.bucket(row(action="REVIEW", sender="X <no-reply@x.com>", confidence=0.51)), "needs_you")
        self.assertEqual(m.bucket(row(action="REVIEW", sender="Asha <asha@gmail.com>", confidence=0.95)), "needs_you")
        self.assertEqual(m.bucket(row(action="REVIEW", sender="X <no-reply@x.com>", category="Action Needed")), "needs_you")

    def test_archive_handled_trash_and_spam_are_noise(self):
        self.assertEqual(m.bucket(row(action="ARCHIVE")), "handled")
        self.assertEqual(m.bucket(row(action="TRASH", category="Promos")), "noise")
        self.assertEqual(m.bucket(row(action="SPAM", category="Spam")), "noise")


class RenderTests(unittest.TestCase):
    def test_dry_run_says_so_and_applied_run_counts_archived(self):
        self.assertIn("Manual dry run", m.render([row()], applied=False))
        html = m.render([row(outcome="applied")], applied=True)
        self.assertIn("1 archived for you", html)
        self.assertIn("Archived", html)

    def test_zero_applied_is_not_claimed_as_success(self):
        self.assertIn("Nothing was actually applied", m.render([row(outcome="held")], applied=True))

    def test_needs_you_comes_before_noise_and_counts_are_shown(self):
        html = m.render([row(id="t", subject="TTT", action="TRASH", category="Promos"),
                         row(id="k", subject="KKK", action="KEEP", category="Needs Reply")])
        self.assertLess(html.index("KKK"), html.index("TTT"))
        self.assertIn("<b>1</b> need you", html)
        self.assertIn("<b>1</b> noise", html)

    def test_empty_needs_you_state(self):
        self.assertIn("Nothing needs you right now", m.render([row()]))

    def test_open_in_gmail_link_uses_thread_and_account(self):
        html = m.render([row(action="KEEP", thread_id="abc123")], account="me@gmail.com")
        self.assertIn("https://mail.google.com/mail/?authuser=me%40gmail.com#all/abc123", html)

    def test_unsubscribe_is_honest_and_only_on_noise(self):
        unsub = {"http": "https://x.com/u?id=1", "mailto": "mailto:u@x.com"}
        noise = m.render([row(action="TRASH", category="Promos", unsubscribe=unsub)])
        self.assertIn('href="https://x.com/u?id=1"', noise)
        self.assertIn("you confirm there", noise)
        self.assertIn('href="mailto:u@x.com"', noise)
        self.assertIn("opens your mail app", noise)
        self.assertNotIn("Unsubscribe</a>", m.render([row(action="KEEP", category="Needs Reply", unsubscribe=unsub)]))

    def test_senders_grouped_with_count(self):
        rows = [row(id=f"a{i}", sender="Shop <d@shop.com>", action="TRASH", category="Promos") for i in range(3)]
        html = m.render(rows)
        self.assertIn("3 messages", html)
        self.assertEqual(html.count('<section class="card">'), 1)
        self.assertIn("Show 2 more from Shop", html)

    def test_health_line_carries_run_time_for_staleness_check(self):
        self.assertIn('data-run-at="2026-10-01T16:51:07+00:00"', m.render([row()], run_at="2026-10-01T16:51:07+00:00"))

    def test_escapes_subject_sender_and_attribute_values(self):
        html = m.render([row(subject="<script>alert(1)</script>", sender='a"<b@x.com>', action="KEEP")])
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_error_outcome_shown_verbatim(self):
        self.assertIn("error: quota exceeded", m.render([row(action="TRASH", category="Promos", outcome="error: quota exceeded")], applied=True))

    def test_no_dashes_in_prose(self):
        html = m.render([row(action="TRASH", outcome="held")], applied=True)
        self.assertNotIn("—", html)
        self.assertNotIn("–", html)


    def test_row_buttons_by_bucket(self):
        keep = m.render([row(action="KEEP", category="Needs Reply")])
        for op in ("archive", "keep", "trash"):
            self.assertIn(f'data-op="{op}"', keep)
        noise = m.render([row(action="TRASH", category="Promos")])
        self.assertIn('data-op="trash"', noise)
        self.assertNotIn('data-op="keep"', noise)
        done = m.render([row(action="ARCHIVE", outcome="applied")], applied=True)
        self.assertIn('data-op="inbox"', done)

    def test_bulk_buttons_carry_all_ids_for_sender_group(self):
        rows = [row(id=f"a{i}", sender="Shop <d@shop.com>", action="TRASH", category="Promos") for i in range(3)]
        html = m.render(rows)
        self.assertIn('data-op="trash" data-ids="a0,a1,a2" class=danger>Trash all 3', html)

    def test_one_click_button_only_when_flag_and_https_link(self):
        unsub = {"http": "https://x.com/u", "mailto": None}
        on = m.render([dict(row(action="TRASH", category="Promos", unsubscribe=unsub), unsubscribe_one_click=True)])
        off = m.render([row(action="TRASH", category="Promos", unsubscribe=unsub)])
        self.assertIn('data-op="unsubscribe"', on)
        self.assertNotIn('data-op="unsubscribe"', off)

    def test_csp_allows_only_same_origin_requests(self):
        html = m.render([row()])
        self.assertIn("connect-src 'self'", html)
        self.assertIn("default-src 'none'", html)


    def test_bulk_unsubscribe_bar_one_id_per_one_click_sender(self):
        u = {"http": "https://x.com/u", "mailto": None}
        mk = lambda i, who, oc: dict(row(id=i, sender=f"S <{who}@x.com>", action="TRASH", category="Promos", unsubscribe=u), unsubscribe_one_click=oc)
        html = m.render([mk("a1", "a", True), mk("a2", "a", True), mk("b1", "b", True), mk("c1", "c", False)])
        self.assertIn('data-op="unsub-all" data-ids="a1,b1"', html)
        self.assertIn("Unsubscribe from 2 senders", html)
        self.assertNotIn('data-op="unsub-all"', m.render([mk("c1", "c", False)]))


    def test_page_is_installable_and_csp_allows_its_manifest(self):
        html = m.render([row()])
        self.assertIn('rel="manifest"', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn("manifest-src 'self'", html)


    def test_needs_you_group_with_several_messages_gets_archive_all_and_keep_all(self):
        rows = [row(id=f"k{i}", sender="Google <g@x.com>", action="KEEP", category="Action Needed") for i in range(3)]
        html = m.render(rows)
        self.assertIn('data-op="archive" data-ids="k0,k1,k2">Archive all 3', html)
        self.assertIn('data-op="keep" data-ids="k0,k1,k2">Keep all 3', html)


    def test_page_reloads_itself_when_a_suspended_home_screen_app_returns(self):
        html = m.render([row()])
        self.assertIn("visibilitychange", html)
        self.assertIn('id="refresh"', html)


    def test_page_asks_the_server_which_messages_are_already_handled(self):
        self.assertIn("/api/mail/state", m.render([row()]))
