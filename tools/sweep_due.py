"""Print "yes" when the last nationwide sweep is more than SWEEP_HOURS old.

Used by the workflow so a sweep happens on whichever scheduled run actually
starts, instead of only on a cron slot GitHub may skip.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def due(stats: dict, now: datetime, hours: float = 6.0) -> bool:
    last = (stats.get("last_full") or {}).get("fetched_at")
    try:
        when = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return True   # never swept, or unreadable: sweep
    return now - when > timedelta(hours=hours)


def main() -> None:
    try:
        with open(os.path.join(ROOT, "data", "stats.json"), encoding="utf-8") as f:
            stats = json.load(f)
    except (OSError, ValueError):
        stats = {}
    hours = float(os.environ.get("SWEEP_HOURS", "6"))
    print("yes" if due(stats if isinstance(stats, dict) else {}, datetime.now(UTC), hours)
          else "no")


if __name__ == "__main__":
    sys.exit(main())
