from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from tidy.collector import collect
from tidy.youtube import YouTube


NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def response(payload, status=200):
    result = Mock(status_code=status, headers={})
    result.json.return_value = payload
    return result


class FakeYouTube:
    """Routes GETs by resource. Synthetic channels only: {channel_id: [video ids, newest first]}."""

    def __init__(self, uploads, page_size=50, missing=()):
        self.uploads = uploads
        self.page_size = page_size
        self.missing = set(missing)
        self.session = Mock()
        self.session.get.side_effect = self.get

    def get(self, url, params=None, **kwargs):
        params = params or {}
        resource = url.rsplit("/", 1)[-1]
        return response(getattr(self, resource)(params))

    def channels(self, params):
        cid = params["id"]
        if cid not in self.uploads:
            return {}
        return {"items": [{"id": cid,
                           "snippet": {"title": "Channel " + cid, "description": "About " + cid},
                           "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid}}}]}

    def playlistItems(self, params):
        ids = self.uploads[params["playlistId"][2:]]
        start = int(params.get("pageToken", 0))
        size = min(params["maxResults"], self.page_size)
        page = {"items": [{"contentDetails": {"videoId": v}} for v in ids[start:start + size]]}
        if start + size < len(ids):
            page["nextPageToken"] = str(start + size)
        return page

    def videos(self, params):
        return {"items": [{"id": v,
                           "snippet": {"title": "Title " + v, "description": "Desc " + v,
                                       "publishedAt": "2026-09-01T00:00:00Z"},
                           "contentDetails": {"duration": "PT10M"}}
                          for v in params["id"].split(",") if v not in self.missing]}


class CollectorTests(unittest.TestCase):
    def test_one_channel_yields_sample_with_videos_and_coverage(self):
        fake = FakeYouTube({"chanA": ["v1", "v2"]})

        [sample] = collect(YouTube(fake.session), ["chanA"], now=NOW).samples

        self.assertEqual(sample.channel_id, "chanA")
        self.assertEqual(sample.title, "Channel chanA")
        self.assertEqual(sample.description, "About chanA")
        self.assertEqual([v["id"] for v in sample.videos], ["v1", "v2"])
        first = sample.videos[0]
        self.assertEqual(first["title"], "Title v1")
        self.assertEqual(first["published_at"], "2026-09-01T00:00:00Z")
        self.assertEqual(first["duration"], "PT10M")
        self.assertEqual(first["url"], "https://www.youtube.com/watch?v=v1")
        self.assertEqual(sample.fetched_at, NOW.isoformat())
        self.assertEqual(sample.coverage, {"requested": 12, "collected": 2, "unavailable": 0})
        self.assertTrue(sample.evidence_hash)

    def test_window_limits_uploads_and_stops_paging_early(self):
        fake = FakeYouTube({"chanA": ["v%02d" % i for i in range(30)]}, page_size=5)

        [sample] = collect(YouTube(fake.session), ["chanA"], window=12, now=NOW).samples

        self.assertEqual([v["id"] for v in sample.videos], ["v%02d" % i for i in range(12)])
        self.assertEqual(sample.coverage, {"requested": 12, "collected": 12, "unavailable": 0})
        pages = [c for c in fake.session.get.call_args_list if c.args[0].endswith("playlistItems")]
        self.assertEqual(len(pages), 3)

    def test_video_details_are_batched_by_50(self):
        fake = FakeYouTube({"chanA": ["v%03d" % i for i in range(130)]})

        [sample] = collect(YouTube(fake.session), ["chanA"], window=120, now=NOW).samples

        self.assertEqual(len(sample.videos), 120)
        batches = [len(c.kwargs["params"]["id"].split(",")) for c in fake.session.get.call_args_list
                   if c.args[0].endswith("videos")]
        self.assertEqual(batches, [50, 50, 20])

    def test_deleted_or_private_videos_are_dropped_and_counted(self):
        fake = FakeYouTube({"chanA": ["v1", "v2", "v3"]}, missing=["v2"])

        [sample] = collect(YouTube(fake.session), ["chanA"], now=NOW).samples

        self.assertEqual([v["id"] for v in sample.videos], ["v1", "v3"])
        self.assertEqual(sample.coverage, {"requested": 12, "collected": 2, "unavailable": 1})

    def test_channel_without_uploads_gives_empty_sample_and_no_video_lookup(self):
        fake = FakeYouTube({"chanA": []})

        [sample] = collect(YouTube(fake.session), ["chanA"], now=NOW).samples

        self.assertEqual(sample.videos, [])
        self.assertIsNone(sample.newest_published_at)
        self.assertEqual(sample.coverage, {"requested": 12, "collected": 0, "unavailable": 0})
        self.assertFalse([c for c in fake.session.get.call_args_list if c.args[0].endswith("videos")])

    def test_newest_published_date_lets_callers_see_staleness(self):
        fake = FakeYouTube({"chanA": ["v1", "v2"]})

        [sample] = collect(YouTube(fake.session), ["chanA"], now=NOW).samples

        self.assertEqual(sample.newest_published_at, "2026-09-01T00:00:00Z")

    def test_hash_depends_on_content_not_fetch_time(self):
        later = datetime(2026, 9, 25, tzinfo=timezone.utc)
        same = FakeYouTube({"chanA": ["v1", "v2"]})
        [first] = collect(YouTube(same.session), ["chanA"], now=NOW).samples
        [again] = collect(YouTube(same.session), ["chanA"], now=later).samples
        changed = FakeYouTube({"chanA": ["v1", "v3"]})
        [other] = collect(YouTube(changed.session), ["chanA"], now=NOW).samples

        self.assertEqual(first.evidence_hash, again.evidence_hash)
        self.assertNotEqual(first.evidence_hash, other.evidence_hash)

    def test_sample_expires_30_days_after_fetch(self):
        fake = FakeYouTube({"chanA": ["v1"]})

        [sample] = collect(YouTube(fake.session), ["chanA"], now=NOW).samples

        self.assertEqual(sample.expires_at, "2026-10-20T00:00:00+00:00")

    def test_quota_exhaustion_is_reported_per_channel_without_partial_samples(self):
        fake = FakeYouTube({"chanA": ["v1"], "chanB": ["v2"], "chanC": ["v3"]})

        result = collect(YouTube(fake.session, max_units=4), ["chanA", "chanB", "chanC"], now=NOW)

        self.assertEqual([s.channel_id for s in result.samples], ["chanA"])
        self.assertEqual(sorted(result.errors), ["chanB", "chanC"])
        self.assertIn("quota", result.errors["chanB"].lower())

    def test_unknown_channel_is_an_error_and_others_still_collect(self):
        fake = FakeYouTube({"chanA": ["v1"]})

        result = collect(YouTube(fake.session), ["ghost", "chanA"], now=NOW)

        self.assertEqual([s.channel_id for s in result.samples], ["chanA"])
        self.assertEqual(list(result.errors), ["ghost"])

    def test_collection_is_get_only_and_search_is_refused(self):
        fake = FakeYouTube({"chanA": ["v1"]})
        api = YouTube(fake.session)

        collect(api, ["chanA"], now=NOW)

        fake.session.post.assert_not_called()
        fake.session.delete.assert_not_called()
        fake.session.put.assert_not_called()
        with self.assertRaises(ValueError):
            api.get("search", q="anything")


if __name__ == "__main__":
    unittest.main()
