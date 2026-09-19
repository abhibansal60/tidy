"""Jev judgments: one bundled call per evidence sample; code keeps everything Jev should not do."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import statistics
import re
import time

from typesafe_sdk import Noul, Score, TypeSafeError

from . import store

QUESTIONS = {
    "relevance": Score(
        instructions="How closely does this channel's content match the owner's interests in `owner_interests`?",
        criteria=[
            "Unrelated to the owner's interests",
            "Loosely related or only occasionally on topic",
            "Mostly on topic",
            "Squarely on topic and a strong fit",
        ],
    ),
    "apparent_value": Score(
        instructions=("How substantive does this channel's content appear to be, judging only from the evidence "
                      "shown? Judge information content and craft, not topic and not title style."),
        criteria=[
            "Empty: hype, drama or filler with no apparent information or craft",
            "Shallow: recaps, listicles or surface-level overviews",
            "Solid: teaches or documents something concrete, with visible effort",
            "Exceptional: deep, original or expert work, or outstanding storytelling craft",
        ],
    ),
    "packaging_risk": Noul(
        instructions=("Are the titles sensational packaging: clickbait, outrage, breathless hype or shock "
                      "framing? This is about presentation only, not whether the content is good.")),
    "evidence_sufficiency": Noul(
        instructions=("Is the evidence shown enough to judge this channel's relevance and value? "
                      "Answer no if there are few videos, empty descriptions or stale uploads.")),
}
# Personal watch value is separate from content quality: an exceptional channel can still be one the owner never watches.
QUESTIONS_V2 = {**QUESTIONS, "watch_likelihood": Score(
    instructions=("How likely is the owner to actually watch this channel's new uploads regularly? Consider "
                  "`owner_viewing_habits`, and whether the language, format, length and posting rhythm in "
                  "`channel_facts` and `videos` suit those habits. This is personal fit, not content quality."),
    criteria=[
        "Almost certainly never watched: wrong language, format or length for the owner, or the channel is dormant",
        "Unlikely: only an occasional upload would get watched",
        "Likely: fits the owner's habits and posts often enough to be worth following",
        "Very likely a regular watch: fits the habits closely and posts regularly",
    ])}
# A schema is data: same questions, different evidence rendering, so runs on one sample compare directly.
SCHEMAS = {"titles-v1": {"questions": QUESTIONS, "descriptions": False},
           "titles-desc-v1": {"questions": QUESTIONS, "descriptions": True},
           "titles-v2": {"questions": QUESTIONS_V2, "descriptions": False, "facts": True}}
DESCRIPTION_CHARS = 200
CHANNEL_DESCRIPTION_CHARS = 300


@dataclass
class Judgment:
    channel_id: str
    evidence_hash: str
    schema_id: str
    model: str
    answers: dict
    usage: dict
    latency_ms: int
    judged_at: str


DEFAULT_INTERESTS = "AI, software engineering and technical explainers; some music and comedy are welcome"


def interests_key(interests, habits=""):
    return hashlib.sha256((interests + "\n\0" + habits if habits else interests).encode()).hexdigest()[:16]


def _minutes(iso_duration):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    return int(m[1] or 0) * 60 + int(m[2] or 0) if m else None


def _seconds(iso_duration):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0) if m else 0


def _facts(sample):
    """Rates and counts Jev must not compute itself."""
    fetched = datetime.fromisoformat(sample.fetched_at)
    when = sorted(datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) for v in sample.videos)
    secs = [_seconds(v["duration"]) for v in sample.videos]
    return {"uploads_per_month": round(len(when) / max((when[-1] - when[0]).days, 1) * 30, 1) if len(when) > 1 else None,
            "days_since_last_upload": (fetched - when[-1]).days if when else None,
            "short_videos": sum(x <= 60 for x in secs), "recent_videos": len(secs),
            "median_minutes": round(statistics.median(secs) / 60, 1) if secs else None}


def _clean(text, limit):
    text = re.sub(r"https?://\S+", "", text or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _state(sample, interests, descriptions, habits="", facts=False):
    fetched = datetime.fromisoformat(sample.fetched_at)
    videos = []
    for v in sample.videos:
        video = {"title": v["title"],
                 "days_ago": (fetched - datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))).days,
                 "minutes": _minutes(v["duration"])}
        if descriptions:
            video["description"] = _clean(v["description"], DESCRIPTION_CHARS)
        videos.append(video)
    state = {"channel": sample.title, "owner_interests": interests, "videos": videos}
    if facts:
        state["owner_viewing_habits"] = habits
        state["channel_facts"] = _facts(sample)
    if descriptions:
        state["channel_description"] = _clean(sample.description, CHANNEL_DESCRIPTION_CHARS)
    return state


@dataclass
class JudgeResult:
    judgments: list  # input order, failed samples omitted
    errors: dict     # channel_id -> safe message
    fresh: set = None  # channel_ids actually sent to Jev this run (the rest came from cache)


def judge(client, samples, schema_id, interests=DEFAULT_INTERESTS, db=None, now=None, workers=6, habits=""):
    schema = SCHEMAS[schema_id]
    key = interests_key(interests, habits)
    found = {s.channel_id: db and store.get_judgment(db, s.evidence_hash, schema_id, key, now) for s in samples}
    todo = [s for s in samples if not found[s.channel_id]]

    def call(s):
        try:
            return _judge_one(client, s, schema_id, schema, interests, habits)
        except TypeSafeError as error:
            return str(error) or type(error).__name__

    with ThreadPoolExecutor(workers) as pool:  # ponytail: threads suit ~100 channels; batch/async if it grows
        fresh = dict(zip((s.channel_id for s in todo), pool.map(call, todo)))
    result = JudgeResult([], {}, set(fresh))
    for s in samples:
        outcome = found[s.channel_id] or fresh[s.channel_id]
        if isinstance(outcome, str):
            result.errors[s.channel_id] = outcome
            continue
        if db and s.channel_id in fresh:
            store.put_judgment(db, outcome, key, s.expires_at)
        result.judgments.append(outcome)
    return result


def _judge_one(client, sample, schema_id, schema, interests, habits=""):
    started = time.monotonic()
    reply = client.system_one(state=_state(sample, interests, schema["descriptions"], habits, schema.get("facts", False)),
                          questions=schema["questions"])
    return Judgment(sample.channel_id, sample.evidence_hash, schema_id, reply.model,
                    {name: answer.model_dump(mode="json") for name, answer in reply.answers.items()},
                    {"input_tokens": reply.usage.input_tokens, "output_tokens": reply.usage.output_tokens},
                    round((time.monotonic() - started) * 1000), datetime.now(timezone.utc).isoformat())
