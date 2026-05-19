from __future__ import annotations

import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


API_BASE_URL = "http://localhost:8000"


def fetch_json(path: str) -> dict:
    with urlopen(f"{API_BASE_URL}{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    checks: list[dict[str, str | None]] = []
    try:
        health = fetch_json("/health")
        checks.append({"name": "api", "status": health.get("status", "down"), "detail": "Root health endpoint responded."})
    except (OSError, URLError) as exc:
        checks.append({"name": "api", "status": "down", "detail": str(exc)})

    try:
        readiness = fetch_json("/api/v1/system/readiness")
        checks.extend(readiness.get("checks", []))
    except (OSError, URLError) as exc:
        checks.append({"name": "readiness_endpoint", "status": "down", "detail": str(exc)})

    print("\nWebIntel AI system check")
    print("========================")
    for check in checks:
        status = str(check.get("status", "unknown")).upper()
        name = str(check.get("name", "unknown"))
        detail = str(check.get("detail", ""))
        print(f"{status:9} {name:24} {detail}")

    broken = [check for check in checks if check.get("status") in {"down", "broken"}]
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
