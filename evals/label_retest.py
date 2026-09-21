"""Test-retest of the owner's keep or drop labels: how much do they agree with themselves, and what does that cap?

A blind sheet ({"channels": [{"n", "verdict"}]}) plus its n->channel_id map is compared with the current labels.
Only keep and drop pairs count. If one label flips with probability q, two passes agree with probability
(1-q)^2 + q^2, so a perfect predictor of the underlying taste would score AUC of about 1 - q against one pass.
Usage: python -m evals.label_retest data/blind_relabel_2.json .tidy/blind_map_2.json
"""

import json
from pathlib import Path
import sys

from tidy import review, store


def retest(current, sheet_path, map_path):
    mapping = json.loads(Path(map_path).read_text())
    pairs, skipped = [], 0
    for row in json.loads(Path(sheet_path).read_text())["channels"]:
        earlier, now = current.get(mapping[str(row["n"])]), row.get("verdict")
        if earlier in ("keep", "drop") and now in ("keep", "drop"):
            pairs.append((earlier, now))
        else:
            skipped += 1
    n = len(pairs)
    agreed = sum(a == b for a, b in pairs)
    rate = agreed / n if n else 0.0
    keep_a, keep_b = sum(a == "keep" for a, _ in pairs) / max(n, 1), sum(b == "keep" for _, b in pairs) / max(n, 1)
    expected = keep_a * keep_b + (1 - keep_a) * (1 - keep_b)
    kappa = (rate - expected) / (1 - expected) if expected < 1 else 1.0
    q = (1 - max(2 * rate - 1, 0) ** 0.5) / 2
    return {"compared": n, "agreed": agreed, "agreement": rate, "kappa": round(kappa, 3), "skipped": skipped,
            "flip_rate": round(q, 3), "ceiling": round(1 - q, 3)}


if __name__ == "__main__":
    db = store.connect(Path(".tidy/inventory.sqlite3"))
    print(json.dumps(retest(review.current_labels(db), sys.argv[1], sys.argv[2]), indent=1))
