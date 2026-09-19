"""Compare stored Jev experiment output with Claude Code baseline runs. Prints JSON; all inputs are private."""

import json
from pathlib import Path
import statistics
import sys

DIMS = ("relevance", "apparent_value", "packaging_risk", "evidence_sufficiency")


def jev_values(path, schema="titles-v1"):
    d = json.loads(Path(path).read_text())
    out = {}
    for cid, c in d["channels"].items():
        a = c["schemas"][schema]
        out[cid] = {n: a[n].get("score", a[n].get("noul")) for n in DIMS}
    return d, out


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


def summarize(jev_path, claude_paths):
    jev, jv = jev_values(jev_path)
    jt = jev["schemas"]["titles-v1"]
    report = {"jev": {"channels": len(jv), "wall_ms": jev["wall_ms"], "input_tokens": jt["input_tokens"],
                      "output_tokens": jt["output_tokens"], "calls": jt["calls"],
                      "latency_ms_p50_p95": [pct([c["schemas"]["titles-v1"]["latency_ms"] for c in jev["channels"].values()], q) for q in (.5, .95)]}}
    for path in claude_paths:
        c = json.loads(Path(path).read_text())
        ok = {k: v for k, v in c["channels"].items() if "answers" in v}
        cv = {k: v["answers"] for k, v in ok.items()}
        shared = [k for k in cv if k in jv]
        walls = [v["wall_ms"] for v in ok.values()]
        entry = {"channels": len(c["channels"]), "errors": len(c["channels"]) - len(ok), "wall_ms": c["wall_ms"],
                 "workers": c["workers"], "latency_ms_p50_p95": [pct(walls, .5), pct(walls, .95)],
                 "cost_usd_estimate": round(sum(v.get("cost_usd") or 0 for v in ok.values()), 3),
                 "billed_tokens": sum(sum(t or 0 for t in v["tokens"].values()) for v in ok.values()),
                 "speedup_jev_over_claude": round(c["wall_ms"] / jev["wall_ms"], 1),
                 "agreement_with_jev": {d: {"spearman": round(statistics.correlation([jv[k][d] for k in shared], [cv[k][d] for k in shared], method="ranked"), 2),
                                             "mean_abs_diff": round(statistics.mean(abs(jv[k][d] - cv[k][d]) for k in shared), 2)} for d in DIMS}}
        report[f"claude_{c['model']}_{c.get('effort') or 'default'}"] = entry
    return report


if __name__ == "__main__":
    print(json.dumps(summarize(sys.argv[1], sys.argv[2:]), indent=1))
