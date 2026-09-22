"""Jev inbox triage: one bundled call per email, then a pure policy turning the category into a proposal.

No Gmail writes here. This module only reads (via `gmail.Gmail`) and classifies; applying a
proposal (archive, spam, ...) is a separate gated step, same shape as `tidy/mutate.py`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import getaddresses

from typesafe_sdk import Choice, TypeSafeError

from .gmail import APIError

CATEGORIES = {
    "Needs Reply": "A person is personally asking the owner something or waiting on a reply from them.",
    "Updates": "Automated account, service, shipping or informational mail with nothing to answer.",
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
POLICY_VERSION = "mail-policy-2"
ACTION_FOR_CATEGORY = {
    "Needs Reply": "KEEP",
    "Updates": "ARCHIVE",
    "Promos": "TRASH",
    "Sales": "TRASH",
    "Spam": "SPAM",
}
CONFIDENCE_MIN = 0.6  # below this, propose REVIEW instead of trusting the category
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
    action: str  # KEEP, ARCHIVE, SPAM, REVIEW
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


def propose(judgment):
    if judgment.category not in ACTION_FOR_CATEGORY:
        return MailProposal(judgment.message_id, "REVIEW", judgment.category, ["unknown category"])
    if judgment.confidence < CONFIDENCE_MIN:
        return MailProposal(judgment.message_id, "REVIEW", judgment.category,
                            [f"confidence low ({judgment.confidence:.2f})"])
    action = ACTION_FOR_CATEGORY[judgment.category]
    signals = [f"category {judgment.category} ({judgment.confidence:.2f})"]
    if action in AUTO_ACTIONS:
        # Never auto-apply on Jev's category alone (AGENTS.md/ADR 0005): needs an independent, code-owned
        # signal corroborating "this looks automated/bulk", same shape as policy.py's two-dimension rule.
        facts = judgment.facts or {}
        corroborated = facts.get("list_unsubscribe_header") or not facts.get("addressed_directly")
        if not corroborated:
            return MailProposal(judgment.message_id, "REVIEW", judgment.category,
                                signals + ["no independent corroborating signal (personally addressed, no unsubscribe header)"])
    return MailProposal(judgment.message_id, action, judgment.category, signals)


# Label changes for the batch-eligible actions. TRASH has no batch endpoint (see gmail.Gmail.trash);
# KEEP and REVIEW are never applied: no labels touched.
LABELS_FOR_ACTION = {"ARCHIVE": {"remove": ["INBOX"]}, "SPAM": {"add": ["SPAM"], "remove": ["INBOX"]}}
BATCH_MODIFY_LIMIT = 1000  # Gmail's messages.batchModify hard cap


def _chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


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
