"""Fail closed when a successful collection would erase a populated job feed.

An explicit manual dispatch can override the guard after checking real closures.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def unexpected_collapse(previous: int, current: int) -> bool:
    """Detect disappearance, or a loss of >=75% from a substantial feed."""
    if previous < 0 or current < 0:
        raise ValueError("open job counts must be nonnegative")
    return (previous >= 2 and current == 0) or (
        previous >= 10 and current <= previous // 4
    )


def main() -> None:
    base = os.environ.get("BASE_SHA")
    if not base:
        raise SystemExit("BASE_SHA is required to check the published baseline")
    baseline = subprocess.check_output(
        ["git", "show", f"{base}:data/stats.json"], text=True,
    )
    previous = json.loads(baseline)
    with open("data/stats.json", encoding="utf-8") as source:
        current = json.load(source)
    old = previous["open_total"]
    new = current["open_total"]
    if unexpected_collapse(old, new) and os.environ.get("ALLOW_FEED_COLLAPSE") != "1":
        print(
            f"::error::Open roles unexpectedly dropped from {old} to {new}. "
            "Keeping the previous published list. Review filtering and ATS "
            "health. A manual dispatch may override this after verification."
        )
        sys.exit(1)
    print(f"Feed continuity: {old} -> {new} open roles; passed.")


if __name__ == "__main__":
    main()
