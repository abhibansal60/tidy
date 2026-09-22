"""Schema experiment: judge the same stored evidence samples under several schemas and compare raw answers."""

from datetime import datetime, timezone
from itertools import combinations
import json
import time

from . import judge as jev, store

FLAG = {"score": 0.5, "noul": 0.3}  # absolute difference at which two schemas "disagree"


def plan(db, schema_ids, interests, now=None, habits=""):
    samples = store.latest_samples(db, now=now)
    chars = sum(len(json.dumps(jev._state(s, interests, jev.SCHEMAS[i]["descriptions"], habits, jev.SCHEMAS[i].get("facts", False))))
                for i in schema_ids for s in samples)
    return {"samples": len(samples), "schemas": list(schema_ids), "calls": len(samples) * len(schema_ids),
            "estimated_input_tokens": chars // 4, "executes": False}


def typesafe_client(data_dir=None):
    """Real client; key from TYPESAFE_API_KEY, else <data dir>/.env, ./.env or ../.env. The key is never printed."""
    from typesafe_sdk import TypeSafeClient
    from .setup_check import data_dir as default_dir, typesafe_key
    key, _ = typesafe_key(data_dir or default_dir())
    if not key:
        raise ValueError("TYPESAFE_API_KEY not found. Get one at https://console.typesafe.ai, then: tidy init --email ... --key-stdin")
    return TypeSafeClient(api_key=key)


def _values(answers):
    return {name: ({"score": a["score"], "confidence": a["confidence"]} if "score" in a else {"noul": a["noul"]})
            for name, a in answers.items()}


class _Counting:
    def __init__(self, client):
        self.client, self.calls = client, 0

    def system_one(self, **kw):
        self.calls += 1  # ponytail: unlocked increment; exact under CPython's GIL for this use
        return self.client.system_one(**kw)


def run(db, client, schema_ids, interests, now=None, habits=""):
    started = time.monotonic()
    samples = store.latest_samples(db, now=now or datetime.now(timezone.utc))
    report = {"samples": len(samples), "interests": interests, "schemas": {},
              "channels": {s.channel_id: {"schemas": {}, "disagreements": {}} for s in samples}}
    for schema_id in schema_ids:
        counting = _Counting(client)
        result = jev.judge(counting, samples, schema_id, interests, db=db, now=now, habits=habits)
        paid = [j for j in result.judgments if j.channel_id in result.fresh]  # cached judgments cost nothing now
        times = [j.latency_ms for j in paid]
        report["schemas"][schema_id] = {
            "input_tokens": sum(j.usage["input_tokens"] for j in paid),
            "output_tokens": sum(j.usage["output_tokens"] for j in paid),
            "latency_ms_sum": sum(times), "latency_ms_max": max(times, default=0),
            "calls": counting.calls, "cache_hits": len(samples) - counting.calls, "errors": result.errors}
        for j in result.judgments:
            report["channels"][j.channel_id]["schemas"][schema_id] = {
                **_values(j.answers), "usage": j.usage, "latency_ms": j.latency_ms}
    for channel in report["channels"].values():
        for a, b in combinations(schema_ids, 2):
            if a in channel["schemas"] and b in channel["schemas"]:
                channel["disagreements"][f"{a}|{b}"] = {
                    name: {"diff": diff, "flagged": diff >= FLAG[kind]}
                    for name, x in channel["schemas"][a].items() if name in jev.QUESTIONS
                    for kind in ["score" if "score" in x else "noul"]
                    for diff in [round(abs(x[kind] - channel["schemas"][b][name][kind]), 6)]}
    report["wall_ms"] = round((time.monotonic() - started) * 1000)
    return report
