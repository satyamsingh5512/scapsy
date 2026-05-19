from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_record_hash(record: dict[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def diff_records(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return {"type": "created", "changed_fields": sorted(current), "hash": stable_record_hash(current)}

    changed_fields = sorted(
        key for key in set(previous) | set(current) if previous.get(key) != current.get(key)
    )
    return {
        "type": "changed" if changed_fields else "unchanged",
        "changed_fields": changed_fields,
        "previous_hash": stable_record_hash(previous),
        "current_hash": stable_record_hash(current),
    }
