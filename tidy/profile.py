"""Per-user taste: interests, thresholds, caps, gate. Lives in profile.json under the data dir, not in code."""

import json
from pathlib import Path

from .judge import DEFAULT_INTERESTS

# Scores are on Jev's 0-3 scale; packaging_risk and evidence_sufficiency are 0-1 noul values.
DEFAULTS = {
    "interests": DEFAULT_INTERESTS,
    "schema_id": "titles-desc-v1",
    "thresholds": {"relevance_low": 1.0, "value_low": 1.0, "keep_min": 2.0, "packaging_high": 0.7,
                   "sufficiency_min": 0.5, "min_confidence": 0.5, "stale_days": 180},
    "caps": {"unsubscribe": 5, "subscribe": 3},
    "trial_days": 30,
    "gate": {"min_labels": 30, "min_agreement": 0.85},
}


def load(path):
    path = Path(path)
    given = json.loads(path.read_text()) if path.is_file() else {}
    if not isinstance(given, dict) or set(given) - set(DEFAULTS):
        raise ValueError("profile.json must be an object with known keys only.")
    merged = {}
    for key, default in DEFAULTS.items():
        value = given.get(key, default)
        if isinstance(default, dict):
            if not isinstance(value, dict) or set(value) - set(default):
                raise ValueError(f"profile {key} must be an object with known keys only.")
            value = {**default, **value}
            for name, item in value.items():
                _number(item, f"{key}.{name}", type(default[name]))
        elif isinstance(default, int):
            _number(value, key, int)
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(f"profile {key} must be non-empty text.")
        merged[key] = value
    if not 0 <= merged["gate"]["min_agreement"] <= 1:
        raise ValueError("profile gate.min_agreement must be between 0 and 1.")
    return merged


def _number(value, name, kind):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
    if not ok or (kind is int and not isinstance(value, int)):
        raise ValueError(f"profile {name} must be a non-negative {kind.__name__}.")
