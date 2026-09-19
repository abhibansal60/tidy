"""Jev judgments: one bundled call per evidence sample; code keeps everything Jev should not do."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
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
# A schema is data: same questions, different evidence rendering, so runs on one sample compare directly.
SCHEMAS = {"titles-v1": {"questions": QUESTIONS, "descriptions": False},
           "titles-desc-v1": {"questions": QUESTIONS, "descriptions": True}}
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


def _minutes(iso_duration):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    return int(m[1] or 0) * 60 + int(m[2] or 0) if m else None


def _clean(text, limit):
    text = re.sub(r"https?://\S+", "", text or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _state(sample, interests, descriptions):
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
    if descriptions:
        state["channel_description"] = _clean(sample.description, CHANNEL_DESCRIPTION_CHARS)
    return state


@dataclass
class JudgeResult:
    judgments: list  # input order, failed samples omitted
    errors: dict     # channel_id -> safe message


def judge(client, samples, schema_id, interests=DEFAULT_INTERESTS, db=None, now=None, workers=6):
    schema = SCHEMAS[schema_id]
    key = hashlib.sha256(interests.encode()).hexdigest()[:16]
    found = {s.channel_id: db and store.get_judgment(db, s.evidence_hash, schema_id, key, now) for s in samples}
    todo = [s for s in samples if not found[s.channel_id]]

    def call(s):
        try:
            return _judge_one(client, s, schema_id, schema, interests)
        except TypeSafeError as error:
            return str(error) or type(error).__name__

    with ThreadPoolExecutor(workers) as pool:  # ponytail: threads suit ~100 channels; batch/async if it grows
        fresh = dict(zip((s.channel_id for s in todo), pool.map(call, todo)))
    result = JudgeResult([], {})
    for s in samples:
        outcome = found[s.channel_id] or fresh[s.channel_id]
        if isinstance(outcome, str):
            result.errors[s.channel_id] = outcome
            continue
        if db and s.channel_id in fresh:
            store.put_judgment(db, outcome, key, s.expires_at)
        result.judgments.append(outcome)
    return result


def _judge_one(client, sample, schema_id, schema, interests):
    started = time.monotonic()
    reply = client.system_one(state=_state(sample, interests, schema["descriptions"]), questions=schema["questions"])
    return Judgment(sample.channel_id, sample.evidence_hash, schema_id, reply.model,
                    {name: answer.model_dump(mode="json") for name, answer in reply.answers.items()},
                    {"input_tokens": reply.usage.input_tokens, "output_tokens": reply.usage.output_tokens},
                    round((time.monotonic() - started) * 1000), datetime.now(timezone.utc).isoformat())
