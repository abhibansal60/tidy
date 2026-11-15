"""Policy: pure, versioned rules turning a Jev judgment and evidence into a proposal. No I/O, no Jev calls."""

from datetime import datetime

from .proposal import Proposal

POLICY_VERSION = "policy-1"


def _age_days(sample):
    newest = datetime.fromisoformat(sample.newest_published_at.replace("Z", "+00:00"))
    return (datetime.fromisoformat(sample.fetched_at) - newest).days


def propose(judgment, sample, profile, status="active"):
    t, a = profile["thresholds"], judgment.answers
    rel, rel_conf = a["relevance"]["score"], a["relevance"].get("confidence", 1)
    val, val_conf = a["apparent_value"]["score"], a["apparent_value"].get("confidence", 1)
    pack, suff = a["packaging_risk"]["noul"], a["evidence_sufficiency"]["noul"]
    signals = ["on trial"] if status == "trial" else []
    review = False

    if not sample.coverage["collected"]:
        signals.append("no recent uploads")
        review = True
    elif _age_days(sample) > t["stale_days"]:
        signals.append(f"stale: newest upload {_age_days(sample)} days old")  # flagged, never negative
    thin = suff < t["sufficiency_min"]
    if thin:
        signals.append(f"evidence thin ({suff:.1f})")

    rel_low, val_low, pack_high = rel < t["relevance_low"], val < t["value_low"], pack >= t["packaging_high"]
    if rel_low:
        signals.append(f"relevance low ({rel:.1f})")
    if val_low:
        signals.append(f"value low ({val:.1f})")
    if pack_high:
        signals.append(f"packaging high ({pack:.1f})")
    # A low score only counts toward unsubscribing if Jev's distribution behind it is concentrated.
    unsure = [(n, c) for n, c, low in (("relevance", rel_conf, rel_low), ("value", val_conf, val_low))
              if low and c < t["min_confidence"]]
    signals += [f"{n} confidence low ({c:.1f})" for n, c in unsure]

    # Unsubscribe needs two independent dimensions agreeing (relevance and value), sufficient evidence, firm answers.
    if rel_low and val_low and not (thin or review or unsure):
        action = "UNSUBSCRIBE"
    elif thin or review or unsure or val_low or pack_high:
        action = "REVIEW"
    elif rel >= t["keep_min"] and val >= t["keep_min"]:
        action = "KEEP"
    else:
        action = "WATCH"
    return Proposal(judgment.channel_id, action, signals, POLICY_VERSION, judgment.evidence_hash)


POLICY_VERSION_WATCH = "policy-2-evidence-v1"


def _meets_floor(value, floor):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and floor <= value <= 1


def _evidence_issues(judgment, sample, profile):
    """These checks can only veto actions; model confidence is not calibrated approval."""
    issues = []
    if not sample.videos or not sample.coverage.get("collected", 0):
        issues.append("no recent uploads")
    suff = judgment.answers.get("evidence_sufficiency", {}).get("noul")
    if not _meets_floor(suff, profile["thresholds"]["sufficiency_min"]):
        issues.append("evidence insufficient or missing")
    confidence = judgment.answers.get("apparent_value", {}).get("confidence")
    if not _meets_floor(confidence, profile["thresholds"]["min_confidence"]):
        issues.append("value confidence low or missing")
    return issues


def propose_watch(judgment, sample, profile, watched, second=None, status="active"):
    """Revealed watching plus a strict cascade: low quality needs Jev AND a second opinion below the threshold."""
    days, low = profile["watch_window_days"], profile["low_quality_value"]
    val = judgment.answers["apparent_value"]["score"]
    signals = ["on trial"] if status == "trial" else []
    issues = _evidence_issues(judgment, sample, profile)
    if issues:
        return Proposal(judgment.channel_id, "REVIEW", signals + issues, POLICY_VERSION_WATCH, judgment.evidence_hash)
    if val < low:
        signals.append(f"value low, Jev ({val:.1f})")
        if second is None:
            action = "REVIEW"
            signals.append("needs second opinion")
        elif not _meets_floor(second.get("evidence_sufficiency"), profile["thresholds"]["sufficiency_min"]):
            action = "REVIEW"
            signals.append("second opinion evidence insufficient")
        elif 0 <= second["apparent_value"] < low:
            action = "UNSUBSCRIBE"
            signals += [f"value low, second opinion ({second['apparent_value']:.1f})",
                        f"watched {watched} times in {days} days"]  # shown so the owner can veto
        else:
            action = "REVIEW"
            signals.append(f"second opinion disagrees ({second['apparent_value']:.1f})")
        return Proposal(judgment.channel_id, action, signals, POLICY_VERSION_WATCH, judgment.evidence_hash)
    if watched:
        return Proposal(judgment.channel_id, "KEEP", signals + [f"watched {watched} times in {days} days"],
                        POLICY_VERSION_WATCH, judgment.evidence_hash)
    signals.append(f"unwatched in {days} days")
    if val >= profile["thresholds"]["keep_min"]:
        signals.append("quality high: watch it or drop it")
    return Proposal(judgment.channel_id, "REVIEW", signals, POLICY_VERSION_WATCH, judgment.evidence_hash)


def propose_subscribe(judgment, watched, profile, sample):
    """A channel the owner is not subscribed to: SUBSCRIBE when watching repeats and quality clears a low floor."""
    val = judgment.answers["apparent_value"]["score"]
    if _evidence_issues(judgment, sample, profile) or val < profile["discovery_min_value"] or watched < profile["discovery_min_watches"]:
        return None
    return Proposal(judgment.channel_id, "SUBSCRIBE",
                    [f"value {val:.1f}", f"watched {watched} times in {profile['watch_window_days']} days, not subscribed"],
                    POLICY_VERSION_WATCH, judgment.evidence_hash)
