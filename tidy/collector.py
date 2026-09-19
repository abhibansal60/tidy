"""Read-only evidence collection: dated, bounded samples of channel uploads for Jev."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json

from .youtube import APIError

RETENTION = timedelta(days=30)  # YouTube API data refresh/delete window (docs/research/youtube-api-policy.md)


@dataclass
class EvidenceSample:
    channel_id: str
    title: str
    description: str
    videos: list
    fetched_at: str
    expires_at: str
    coverage: dict
    newest_published_at: str | None
    evidence_hash: str


@dataclass
class CollectResult:
    samples: list
    errors: dict  # channel_id -> safe message; a failed channel never yields a partial sample


def collect(api, channel_ids, window=12, now=None):
    now = now or datetime.now(timezone.utc)
    result = CollectResult([], {})
    for cid in channel_ids:
        try:
            result.samples.append(_sample(api, cid, window, now))
        except APIError as error:
            result.errors[cid] = str(error)
        except (KeyError, IndexError, TypeError):
            result.errors[cid] = "Channel missing or response malformed."
    return result


def _sample(api, channel_id, window, now):
    channel = api.get("channels", part="snippet,contentDetails", id=channel_id)["items"][0]
    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < window:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": min(window - len(ids), 50)}
        if token:
            params["pageToken"] = token
        page = api.get("playlistItems", **params)
        ids += [e["contentDetails"]["videoId"] for e in page["items"]]
        token = page.get("nextPageToken")
        if not token:
            break
    ids = ids[:window]
    details = []
    for i in range(0, len(ids), 50):
        details += api.get("videos", part="snippet,contentDetails", id=",".join(ids[i:i + 50]))["items"]
    videos = [{"id": v["id"], "title": v["snippet"]["title"],
               "description": v["snippet"]["description"],
               "published_at": v["snippet"]["publishedAt"],
               "duration": v["contentDetails"]["duration"],
               "url": "https://www.youtube.com/watch?v=" + v["id"]} for v in details]
    content = {"title": channel["snippet"]["title"], "description": channel["snippet"]["description"],
               "videos": videos}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return EvidenceSample(channel_id, content["title"], content["description"], videos,
                          now.isoformat(), (now + RETENTION).isoformat(), {"requested": window, "collected": len(videos), "unavailable": len(ids) - len(videos)},
                          max((v["published_at"] for v in videos), default=None), digest)
