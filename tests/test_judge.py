from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from typesafe_sdk import NoulAnswer, ScoreAnswer, SystemOneResponse, TypeSafeError, Usage

from tidy import store
from tidy.judge import SCHEMAS, judge
from test_evidence_store import NOW, sample


def response(**overrides):
    answers = {
        "relevance": ScoreAnswer(score=2.4, confidence=0.8, legend={0: "a"}, probabilities={2: 0.6, 3: 0.4}),
        "apparent_value": ScoreAnswer(score=1.9, confidence=0.7, legend={0: "a"}, probabilities={2: 0.9}),
        "packaging_risk": NoulAnswer(noul=0.2),
        "evidence_sufficiency": NoulAnswer(noul=0.9),
    }
    return SystemOneResponse(model="jev-test-1", usage=Usage(input_tokens=1200, output_tokens=10),
                             answers={**answers, **overrides})


class FakeClient:
    def __init__(self, reply=None):
        self.system_one = Mock(side_effect=lambda **kw: reply or response())


class JudgeTests(unittest.TestCase):
    def test_judgment_keeps_raw_answers_model_usage_and_evidence_hash(self):
        client = FakeClient()
        original = sample(channel="chanA", evidence_hash="h1")

        [result] = judge(client, [original], "titles-v1").judgments

        self.assertEqual(result.channel_id, "chanA")
        self.assertEqual(result.evidence_hash, "h1")
        self.assertEqual(result.schema_id, "titles-v1")
        self.assertEqual(result.model, "jev-test-1")
        self.assertEqual(result.usage, {"input_tokens": 1200, "output_tokens": 10})
        self.assertEqual(result.answers["packaging_risk"]["noul"], 0.2)
        self.assertEqual(result.answers["relevance"]["probabilities"], {"2": 0.6, "3": 0.4})
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_state_is_compact_with_code_computed_ages_and_owner_interests(self):
        client = FakeClient()

        judge(client, [sample(channel="chanA", title="Channel A")], "titles-v1", interests="compilers, music")

        state = client.system_one.call_args.kwargs["state"]
        self.assertEqual(state, {
            "channel": "Channel A", "owner_interests": "compilers, music",
            "videos": [{"title": "Title v1", "days_ago": 19, "minutes": 10}]})

    def test_one_bundled_call_per_sample_with_every_question(self):
        client = FakeClient()

        results = judge(client, [sample(channel="a"), sample(channel="b"), sample(channel="c")], "titles-v1").judgments

        self.assertEqual(len(results), 3)
        self.assertEqual(client.system_one.call_count, 3)
        for call in client.system_one.call_args_list:
            self.assertEqual(sorted(call.kwargs["questions"]),
                             ["apparent_value", "evidence_sufficiency", "packaging_risk", "relevance"])


class CachedJudgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_unchanged_evidence_costs_no_second_call(self):
        client = FakeClient()
        original = sample(evidence_hash="h1")

        [first] = judge(client, [original], "titles-v1", db=self.db, now=NOW).judgments
        [again] = judge(client, [original], "titles-v1", db=self.db, now=NOW).judgments

        self.assertEqual(client.system_one.call_count, 1)
        self.assertEqual(again, first)

    def test_changed_evidence_interests_or_expiry_trigger_a_new_call(self):
        client = FakeClient()
        judge(client, [sample(evidence_hash="h1")], "titles-v1", db=self.db, now=NOW)

        judge(client, [sample(evidence_hash="h2")], "titles-v1", db=self.db, now=NOW)
        judge(client, [sample(evidence_hash="h1")], "titles-v1", interests="other", db=self.db, now=NOW)
        self.assertEqual(client.system_one.call_count, 3)

        judge(client, [sample(evidence_hash="h1")], "titles-v1", db=self.db, now=NOW + timedelta(days=31))
        self.assertEqual(client.system_one.call_count, 4)


class SchemaComparisonTests(unittest.TestCase):
    def rich_sample(self):
        original = sample(channel="chanA")
        original.videos[0]["description"] = ("Great intro to parsers. https://example.com/sponsor?x=1\n\n"
                                              "Follow me: https://t.co/abc " + "more text " * 60)
        return original

    def state_for(self, schema_id):
        client = FakeClient()
        judge(client, [self.rich_sample()], schema_id)
        return client.system_one.call_args.kwargs["state"]

    def test_same_evidence_yields_different_states_per_schema(self):
        titles, described = self.state_for("titles-v1"), self.state_for("titles-desc-v1")

        self.assertNotIn("description", titles["videos"][0])
        text = described["videos"][0]["description"]
        self.assertTrue(text.startswith("Great intro to parsers."))
        self.assertNotIn("http", text)
        self.assertLessEqual(len(text), 200)
        self.assertEqual(described["channel_description"], "About chanA")
        self.assertNotIn("channel_description", titles)

    def test_schemas_ask_the_same_questions_so_results_compare_directly(self):
        self.assertEqual(sorted(SCHEMAS["titles-v1"]["questions"]), sorted(SCHEMAS["titles-desc-v1"]["questions"]))


class WatchFitTests(unittest.TestCase):
    def three_video_sample(self):
        original = sample(channel="chanA")
        base = original.videos[0]
        original.videos = [
            {**base, "id": "v1", "published_at": "2026-09-01T00:00:00Z", "duration": "PT10M"},
            {**base, "id": "v2", "published_at": "2026-08-22T00:00:00Z", "duration": "PT45S"},
            {**base, "id": "v3", "published_at": "2026-08-12T00:00:00Z", "duration": "PT30M"}]
        return original

    def state_for(self, schema_id, **kwargs):
        client = FakeClient()
        judge(client, [self.three_video_sample()], schema_id, **kwargs)
        return client.system_one.call_args

    def test_v2_adds_code_computed_channel_facts_and_owner_habits(self):
        call = self.state_for("titles-v2", habits="watches short explainers on the commute")

        state = call.kwargs["state"]
        self.assertEqual(state["owner_viewing_habits"], "watches short explainers on the commute")
        self.assertEqual(state["channel_facts"], {"uploads_per_month": 4.5, "days_since_last_upload": 19,
                                                  "short_videos": 1, "recent_videos": 3, "median_minutes": 10.0})
        self.assertIn("watch_likelihood", call.kwargs["questions"])

    def test_v1_state_is_unchanged_by_the_new_schema(self):
        state = self.state_for("titles-v1", habits="ignored").kwargs["state"]

        self.assertNotIn("channel_facts", state)
        self.assertNotIn("owner_viewing_habits", state)
        self.assertNotIn("watch_likelihood", SCHEMAS["titles-v1"]["questions"])


class CachedHabitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name) / "inventory.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_changed_habits_rejudge_but_empty_habits_keep_the_old_cache_key(self):
        client = FakeClient()
        judge(client, [sample()], "titles-v2", habits="a", db=self.db, now=NOW)
        judge(client, [sample()], "titles-v2", habits="a", db=self.db, now=NOW)
        judge(client, [sample()], "titles-v2", habits="b", db=self.db, now=NOW)
        self.assertEqual(client.system_one.call_count, 2)

        from tidy.judge import interests_key
        self.assertEqual(interests_key("x"), interests_key("x", ""))


class FailureAndSpeedTests(unittest.TestCase):
    def test_a_failing_sample_is_reported_and_others_still_judged_in_order(self):
        def reply(**kw):
            if kw["state"]["channel"] == "Channel bad":
                raise TypeSafeError("service down")
            return response()
        client = Mock(system_one=Mock(side_effect=reply))
        samples = [sample(channel=c, title="Channel " + n) for c, n in [("a", "a"), ("b", "bad"), ("c", "c")]]

        result = judge(client, samples, "titles-v1")

        self.assertEqual([j.channel_id for j in result.judgments], ["a", "c"])
        self.assertEqual(list(result.errors), ["b"])


if __name__ == "__main__":
    unittest.main()
