"""Shared contract: what policy produces and what the act step consumes."""

from dataclasses import dataclass, field

ACTIONS = ("KEEP", "WATCH", "REVIEW", "UNSUBSCRIBE", "SUBSCRIBE")


@dataclass
class Proposal:
    channel_id: str
    action: str                 # one of ACTIONS
    signals: list = field(default_factory=list)   # short strings naming what drove it, e.g. "value low (0.4)"
    policy_version: str = ""
    evidence_hash: str = ""     # ties the proposal to the evidence and judgment it came from
