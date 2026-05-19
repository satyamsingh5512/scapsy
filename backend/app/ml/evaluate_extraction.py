from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def field_f1(expected: dict[str, Any], predicted: dict[str, Any]) -> float:
    expected_items = {(key, str(value).strip().lower()) for key, value in expected.items()}
    predicted_items = {(key, str(value).strip().lower()) for key, value in predicted.items()}
    if not expected_items and not predicted_items:
        return 1.0
    true_positive = len(expected_items & predicted_items)
    precision = true_positive / max(len(predicted_items), 1)
    recall = true_positive / max(len(expected_items), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--target-f1", type=float, default=0.893)
    args = parser.parse_args()

    rows = load_jsonl(args.predictions)
    scores = [field_f1(row["expected"], row["predicted"]) for row in rows]
    score = sum(scores) / max(len(scores), 1)
    print(json.dumps({"f1": round(score, 6), "target": args.target_f1, "passed": score >= args.target_f1}, indent=2))
    return 0 if score >= args.target_f1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
