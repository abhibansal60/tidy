"""Jev inbox triage: one bundled call per email, then a pure policy turning the category into a proposal.

No Gmail writes here. This module only reads (via `gmail.Gmail`) and classifies; applying a
proposal (archive, spam, ...) is a separate gated step, same shape as `tidy/mutate.py`.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
import hashlib
import json

from typesafe_sdk import Choice, TypeSafeError

from . import store
from .gmail import APIError, parse_list_unsubscribe, parse_message

SCHEMA_ID = "mail-v2"  # bump if QUESTIONS/_state change, so stale cached judgments never get reused
RETENTION_DAYS = 30  # same API-derived-data retention as the YouTube side (AGENTS.md)

CATEGORIES = {
    "Needs Reply": "A person is personally asking the owner something or waiting on a reply from them.",
    "Action Needed": ("Automated or official mail asking the owner to do something, or warning of a problem: action "
                      "required, a deadline, a failed payment or build, an expiring subscription or policy, a legal or "
                      "government notice, or an unexpected security alert. Not routine transaction alerts, receipts, "
                      "statements, one-time codes or bot status reports."),
    "Updates": ("Automated account, service, shipping or informational mail with nothing to answer or act on, "
                "including routine transaction alerts, receipts, statements and one-time codes."),
    "Promos": "Marketing, offers or newsletters, not addressed to the owner personally.",
    "Sales": "A person (not automated marketing) trying to sell the owner something.",
    "Spam": "Unwanted or suspicious mail.",
}

QUESTIONS = {
    "category": Choice(
        instructions="Classify this email into exactly one category, judging from the subject, sender, snippet and the precomputed facts.",
        criteria=CATEGORIES,
    ),
}

# Category -> proposed action. Never auto-executed here; a later gated step applies it.
POLICY_VERSION = "mail-policy-4"
ACTION_FOR_CATEGORY = {
    "Needs Reply": "KEEP",
    "Action Needed": "KEEP",
    "Updates": "ARCHIVE",
    "Promos": "TRASH",
    "Sales": "TRASH",
    "Spam": "SPAM",
}
CONFIDENCE_MIN = 0.6  # below this, propose REVIEW instead of trusting the category
# Jev often splits clearly-bulk mail between Updates and Promos (e.g. 0.55/0.45). Neither alone clears
# CONFIDENCE_MIN, but together they say "bulk, nothing to answer". Code-owned arithmetic over Jev's own
# probabilities: that case gets the mildest bulk action (ARCHIVE, reversible), never TRASH.
BULK_SPLIT = ("Updates", "Promos")
BULK_SPLIT_MIN = 0.9
BULK_NEEDS_REPLY_MAX = 0.05  # combined mass of the KEEP categories (Needs Reply, Action Needed)
EXECUTABLE_ACTIONS = {"ARCHIVE", "TRASH", "SPAM"}
AUTO_ACTIONS = {"ARCHIVE"}  # everything else (TRASH, SPAM) is proposed but held for a separate gated mail-act step


def gate_status():
    """Calibration gate for auto-apply, same shape as `review.gate_status`. There is no owner-labeled mail
    dataset yet (no `tidy propose`-style labeling flow for mail), so this can never report open on its own;
    per AGENTS.md/ADR 0005, until a gate holds, code should propose only. `--override-gate` is the documented
    owner escape hatch, same as `tidy act --override-gate`, not a silent bypass of this rule."""
    return {"open": False, "reasons": ["no owner-labeled mail yet; calibration gate cannot open"]}


@dataclass
class MailJudgment:
    message_id: str
    thread_id: str
    model: str
    category: str
    confidence: float
    probabilities: dict
    usage: dict
    judged_at: str
    facts: dict = None  # code-owned facts sent alongside; used by propose() as the independent corroborating signal


@dataclass
class MailProposal:
    message_id: str
    action: str  # KEEP, ARCHIVE, TRASH, SPAM, REVIEW
    category: str
    signals: list
    policy_version: str = POLICY_VERSION


def classify(client, message, owner_email):
    """One bundled call for one parsed message (see `gmail.parse_message`)."""
    state = _state(message, owner_email)
    try:
        reply = client.system_one(state=state, questions=QUESTIONS)
    except TypeSafeError as error:
        return str(error) or type(error).__name__
    answer = reply.answers["category"]
    return MailJudgment(message["id"], message["thread_id"], reply.model, answer.choice, answer.confidence,
                        dict(answer.probabilities),
                        {"input_tokens": reply.usage.input_tokens, "output_tokens": reply.usage.output_tokens},
                        datetime.now(timezone.utc).isoformat(), state["facts"])


def evidence_hash(message, owner_email):
    """Hash of the exact state sent to Jev: changes if the message content, code-owned facts, or owner
    changes, so a cached judgment never survives evidence it wasn't actually judged from (ADR 0004)."""
    return hashlib.sha256(json.dumps(_state(message, owner_email), sort_keys=True).encode()).hexdigest()


def classify_batch(client, messages, owner_email, db=None, now=None):
    """`classify()` for each message, reusing a cached judgment for identical evidence instead of a fresh
    Jev call. Returns {message_id: MailJudgment | error string}, same shape as calling `classify()` per message."""
    now = now or datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=RETENTION_DAYS)).isoformat()
    results = {}
    for message in messages:
        h = evidence_hash(message, owner_email)
        cached = db and store.get_mail_judgment(db, message["id"], h, SCHEMA_ID, now)
        if cached:
            results[message["id"]] = cached
            continue
        outcome = classify(client, message, owner_email)
        if db and not isinstance(outcome, str):
            store.put_mail_judgment(db, outcome, h, SCHEMA_ID, expires_at)
        results[message["id"]] = outcome
    return results


def _state(message, owner_email):
    return {
        "subject": message["subject"],
        "sender": message["sender"],
        "snippet": message["snippet"],
        "facts": {
            "list_unsubscribe_header": message["list_unsubscribe"],
            "addressed_directly": _addressed_directly(message, owner_email),
        },
    }


def _addressed_directly(message, owner_email):
    """Code-owned fact: is the owner the sole, personal To recipient (not Cc, not one of several, not a list)."""
    to_addrs = [addr.casefold() for _, addr in getaddresses([message["to"]])] if message["to"] else []
    return len(to_addrs) == 1 and to_addrs[0] == owner_email.casefold()


# Gmail's own tab classifier: an independent, non-Jev signal that a message is bulk (Primary has no label).
BULK_LABELS = {"CATEGORY_UPDATES", "CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}
PROTECTED_LABELS = {"STARRED"}  # the owner's own "keep this" signal: never proposed for any action


def propose(judgment, labels=()):
    """`labels`: the message's current Gmail label IDs (from `gmail.parse_message`), code-owned state Jev never sees."""
    protected = PROTECTED_LABELS & set(labels)
    if protected:
        return MailProposal(judgment.message_id, "KEEP", judgment.category, [f"owner-protected ({', '.join(sorted(protected))})"])
    if judgment.category not in ACTION_FOR_CATEGORY:
        return MailProposal(judgment.message_id, "REVIEW", judgment.category, ["unknown category"])
    probs = judgment.probabilities or {}
    bulk = sum(probs.get(c, 0) for c in BULK_SPLIT)
    keep = sum(probs.get(c, 0) for c, a in ACTION_FOR_CATEGORY.items() if a == "KEEP")
    if judgment.confidence >= CONFIDENCE_MIN:
        action = ACTION_FOR_CATEGORY[judgment.category]
        signals = [f"category {judgment.category} ({judgment.confidence:.2f})"]
    elif (judgment.category in BULK_SPLIT and bulk >= BULK_SPLIT_MIN
          and keep <= BULK_NEEDS_REPLY_MAX):
        action = "ARCHIVE"
        signals = [f"bulk split: Updates+Promos {bulk:.2f}, Needs Reply/Action Needed {keep:.2f}"]
    else:
        return MailProposal(judgment.message_id, "REVIEW", judgment.category,
                            [f"confidence low ({judgment.confidence:.2f})"])
    if action in AUTO_ACTIONS:
        # Never auto-apply on Jev's category alone (AGENTS.md/ADR 0005): needs an independent, code-owned
        # signal corroborating "this looks automated/bulk", same shape as policy.py's two-dimension rule.
        facts = judgment.facts or {}
        gmail_tab = sorted(BULK_LABELS & set(labels))
        # Not being the sole To recipient is no bulk signal: Cc, family threads and aliases are personal mail.
        corroborated = facts.get("list_unsubscribe_header") or gmail_tab
        if not corroborated:
            return MailProposal(judgment.message_id, "REVIEW", judgment.category,
                                signals + ["no independent corroborating signal (no unsubscribe header, Gmail Primary tab)"])
        if gmail_tab and not facts.get("list_unsubscribe_header"):
            signals.append(f"corroborated by Gmail tab ({gmail_tab[0]})")
    return MailProposal(judgment.message_id, action, judgment.category, signals)


# Label changes for the batch-eligible actions. TRASH has no batch endpoint (see gmail.Gmail.trash);
# KEEP and REVIEW are never applied: no labels touched.
LABELS_FOR_ACTION = {"ARCHIVE": {"remove": ["INBOX"]}, "SPAM": {"add": ["SPAM"], "remove": ["INBOX"]}}
BATCH_MODIFY_LIMIT = 1000  # Gmail's messages.batchModify hard cap


def _chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def select_held(docs, actions, force_reapply=False):
    """Rows to apply from one or more `mail-triage --json` run docs. The newest run (by its recorded `run_at`,
    not argument or glob order) decides each message's action; a message already applied in ANY run is
    skipped unless `force_reapply`, so a message the owner restored is never re-trashed by an older file.
    Returns the row dicts themselves (not copies), so callers can record outcomes in place."""
    latest, applied = {}, set()
    for doc in sorted(docs, key=lambda d: d.get("run_at", "")):
        for r in doc["rows"]:
            latest[r["id"]] = r
            if r.get("outcome") == "applied":
                applied.add(r["id"])
    return [r for r in latest.values() if r["action"] in actions and (force_reapply or r["id"] not in applied)]


def recheck(api, pairs):
    """Re-read each message's live labels right before a held (TRASH/SPAM) proposal is applied, same rule as
    ADR 0002's live-list recheck: a run file can be days old, and the owner may have since moved, starred or
    already cleaned a message. Returns (still_valid_pairs, {message_id: "skipped: ..."})."""
    valid, skipped = [], {}
    for message_id, action in pairs:
        if action not in EXECUTABLE_ACTIONS:
            continue
        try:
            labels = set(api.labels(message_id))
        except APIError as error:
            skipped[message_id] = f"skipped: could not recheck ({error})"
            continue
        if "INBOX" not in labels:
            skipped[message_id] = "skipped: no longer in inbox"
        elif PROTECTED_LABELS & labels:
            skipped[message_id] = "skipped: starred since the run"
        else:
            valid.append((message_id, action))
    return valid, skipped


def apply(api, pairs):
    """`pairs`: iterable of (message_id, action). Only ARCHIVE/TRASH/SPAM do anything. Returns {message_id: outcome}.

    Preflights the call budget so a run either fully applies or applies nothing: partway through a
    large batch is the wrong place to discover the budget was too small (see gmail.Gmail.max_calls)."""
    by_action = {}
    for message_id, action in pairs:
        if action in EXECUTABLE_ACTIONS:
            by_action.setdefault(action, []).append(message_id)
    required_calls = (sum(len(_chunks(by_action[a], BATCH_MODIFY_LIMIT)) for a in ("ARCHIVE", "SPAM") if by_action.get(a))
                      + len(by_action.get("TRASH", [])))
    if api.calls + required_calls > api.max_calls:
        raise ValueError(f"This run needs {required_calls} Gmail calls but only {api.max_calls - api.calls} remain "
                         f"in the call budget; rerun with a higher --max-calls. Nothing was applied.")
    # Below this point, every mutation is idempotent and independent, so one failure must not lose the
    # record of ones that already succeeded: catch per unit and keep going rather than raise and discard.
    outcomes = {}
    for action in ("ARCHIVE", "SPAM"):
        ids = by_action.get(action)
        if ids:
            labels = LABELS_FOR_ACTION[action]
            for chunk in _chunks(ids, BATCH_MODIFY_LIMIT):
                try:
                    api.batch_modify(chunk, add=labels.get("add", []), remove=labels.get("remove", []))
                    outcomes.update({i: "applied" for i in chunk})
                except APIError as error:
                    outcomes.update({i: f"error: {error}" for i in chunk})
    for message_id in by_action.get("TRASH", []):
        try:
            api.trash(message_id)
            outcomes[message_id] = "applied"
        except APIError as error:
            outcomes[message_id] = f"error: {error}"
    return outcomes


def triage(api, client, owner_email, query, limit, db=None, write_api=None, cap_archive=0, override_gate=False):
    """One mail-triage run: fetch `query` (up to `limit`), classify, propose, and with `write_api` auto-apply
    the archive-only proposals. Returns the report rows plus a summary; never trashes or spams on its own.

    Auto-apply is archive-only by design: TRASH/SPAM always wait for a reviewed `mail-act` run. Per AGENTS.md/ADR
    0005 it also needs the calibration gate open; with no owner labels for mail yet it never is, so
    `override_gate` is required (an explicit owner decision, not a silent bypass). Capped by `cap_archive` even
    when overridden."""
    if cap_archive < 0:
        raise ValueError("--cap-archive must not be negative.")
    messages = [parse_message(api.message(i)) for i in api.message_ids(query, limit)]
    judgments = classify_batch(client, messages, owner_email, db=db)
    errors = {i: j for i, j in judgments.items() if isinstance(j, str)}
    by_id = {m["id"]: m for m in messages}
    proposals = {i: propose(j, by_id[i]["label_ids"]) for i, j in judgments.items() if i not in errors}
    gate = gate_status()
    outcomes = {}
    if write_api is not None and (gate["open"] or override_gate):
        auto = [(i, p.action) for i, p in proposals.items() if p.action in AUTO_ACTIONS][:cap_archive]
        outcomes = apply(write_api, auto)
    applied = write_api is not None
    rows = []
    for i, p in proposals.items():
        m, j = by_id[i], judgments[i]
        rows.append({
            "id": i, "thread_id": j.thread_id, "subject": m["subject"], "sender": m["sender"], "snippet": m["snippet"],
            "labels": m["label_ids"], "facts": j.facts, "category": p.category, "confidence": j.confidence,
            "probabilities": j.probabilities, "model": j.model, "judged_at": j.judged_at, "usage": j.usage,
            "action": p.action, "policy_version": p.policy_version, "signals": p.signals,
            "outcome": outcomes.get(i, "held" if p.action in EXECUTABLE_ACTIONS else None) if applied else None,
            "unsubscribe": parse_list_unsubscribe(m["list_unsubscribe_value"]) if m["list_unsubscribe"] else None,
            "unsubscribe_one_click": m["list_unsubscribe_one_click"]})
    mutation_errors = {i: v for i, v in outcomes.items() if v != "applied"}
    return {"messages": len(messages), "errors": errors, "applied": applied, "gate": gate,
            "gate_overridden": applied and not gate["open"] and override_gate,
            "action_counts": {a: sum(r["action"] == a for r in rows) for a in set(r["action"] for r in rows)},
            "outcome_counts": {o: sum(r.get("outcome") == o for r in rows) for o in ("applied", "held")} if applied else None,
            "mutation_errors": mutation_errors or None, "rows": rows}
