"""The gate between "the run produced output" and "the site shows it".

    python tools/verify_accuracy.py        # exit 0 = clean, 1 = violations

Every OPEN role must still satisfy the rules the list promises:
  1. its title is an entry path into IT and not senior
  2. it sits in Local / Nearby / Remote, and the distance agrees with the section
  3. it carries a fit and an experience label from the CURRENT rules
  4. its link is a real URL
And the run as a whole must be healthy: stats are fresh, at least half of the
local sources answered, and the README, CSV and JSON API agree with the store.

A failing gate stops the workflow before the commit, leaving the previous
good build live.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from intern_engine import config, filters_it, paths, pipeline, store, view  # noqa: E402

_FITS = {filters_it.FIT_BEGINNER, filters_it.FIT_STRETCH, filters_it.FIT_UNVERIFIED}


def check(data: dict, stats: dict, cfg: dict, *, allow_stale: bool = False,
          max_stats_age_hours: float = 2.0, min_open: int = 0) -> list[str]:
    problems: list[str] = []
    open_jobs = [r for r in data.values() if r.get("is_open")]

    def flag(record: dict, rule: str) -> None:
        problems.append(f"  [{rule}] {record.get('company', '?')[:28]} | "
                        f"{(record.get('title') or '?')[:56]} | {record.get('section')} "
                        f"| loc={record.get('location')!r}")

    for r in open_jobs:
        if filters_it.title_verdict(r.get("title") or "")[0] == "reject":
            flag(r, "title-not-entry-it")
        section, miles = r.get("section"), r.get("miles")
        if section not in filters_it.SECTIONS:
            flag(r, "no-section")
        elif section == filters_it.LOCAL and not (
                isinstance(miles, (int, float)) and miles <= cfg["local_radius_miles"]):
            flag(r, "local-distance")
        elif section == filters_it.NEARBY and not (
                isinstance(miles, (int, float))
                and cfg["local_radius_miles"] < miles <= cfg["nearby_radius_miles"]):
            flag(r, "nearby-distance")
        elif section == filters_it.REMOTE and not r.get("remote"):
            flag(r, "remote-not-flagged")
        if r.get("fit") not in _FITS:
            flag(r, "no-fit")
        if not r.get("experience"):
            flag(r, "no-experience-label")
        if r.get("rules_v") != filters_it.VERSION:
            flag(r, "stale-rules")
        if not str(r.get("url") or "").startswith(("https://", "http://")):
            flag(r, "bad-url")

    # --- the run ---
    fetched = view.parse_ts(stats.get("fetched_at"))
    if fetched is None:
        problems.append("  [stats] no fetch timestamp")
    elif not allow_stale:
        age = (datetime.now(UTC) - fetched).total_seconds() / 3600
        if age > max_stats_age_hours:
            problems.append(f"  [stats-stale] last fetch was {age:.1f}h ago")
    total, ok = stats.get("local_sources_total", 0), stats.get("local_sources_ok", 0)
    if total and ok * 2 < total:
        problems.append(f"  [local-sources-down] only {ok} of {total} local sources answered")
    if stats.get("open_total") != len(open_jobs):
        problems.append(f"  [stats-drift] stats say {stats.get('open_total')} open, "
                        f"store has {len(open_jobs)}")
    if len(open_jobs) < min_open:
        problems.append(f"  [volume] only {len(open_jobs)} open roles (floor {min_open})")

    # --- published artifacts agree with the store ---
    ids = [r["id"] for r in view.open_jobs(data)]
    if len(ids) != len(open_jobs):
        problems.append("  [unlisted] an open role has no section and would not be shown")
    try:
        with open(os.path.join(paths.API_DIR, "jobs.json"), encoding="utf-8") as f:
            api = json.load(f)
        if [j["id"] for j in api["jobs"]] != ids:
            problems.append("  [api-drift] docs/api/jobs.json differs from the store")
    except (OSError, ValueError, KeyError):
        problems.append("  [api-missing] docs/api/jobs.json unreadable")
    try:
        with open(paths.CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != len(ids):
            problems.append("  [csv-drift] data/jobs.csv differs from the store")
    except OSError:
        problems.append("  [csv-missing] data/jobs.csv unreadable")
    try:
        with open(paths.DASHBOARD_PATH, encoding="utf-8") as f:
            page = f.read()
        if page.count('<article class="job"') != len(ids):
            problems.append("  [page-drift] docs/index.html differs from the store")
    except OSError:
        problems.append("  [page-missing] docs/index.html unreadable")
    return problems


def main() -> None:
    data = store.load(paths.JOBS_PATH)
    stats = pipeline.load_stats()
    problems = check(
        data, stats, config.load_config(),
        allow_stale=os.environ.get("ALLOW_STALE_STATS") == "1",
        max_stats_age_hours=float(os.environ.get("MAX_STATS_AGE_HOURS", "2")),
        min_open=int(os.environ.get("MIN_OPEN_ROLES", "0")),
    )
    open_total = sum(1 for r in data.values() if r.get("is_open"))
    if problems:
        print(f"FAILED: {len(problems)} problem(s) across {open_total} open roles")
        print("\n".join(problems[:80]))
        sys.exit(1)
    print(f"OK: {open_total} open roles satisfy every rule; "
          f"{stats.get('local_sources_ok')}/{stats.get('local_sources_total')} "
          "local sources answered.")


if __name__ == "__main__":
    main()
