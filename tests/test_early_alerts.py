"""Real posting timestamps, not first-seen backfills, control early alerts."""
from datetime import UTC, datetime

from run import _fresh_alert_ids


_NOW = datetime(2026, 11, 6, 23, 0, tzinfo=UTC)


def _job(source, posted, open_role=True):
    return {"source": source, "posted_at": posted, "is_open": open_role}


def test_announces_only_recent_employer_postings_not_old_backfills():
    rows = {
        "fresh": _job("workday", "2026-11-06T21:00:00Z"),
        "yesterday": _job("workday", "2026-11-05T21:00:00Z"),
        "old": _job("workday", "2026-10-08T13:00:00Z"),
        "unknown": _job("workday", None),
        "closed": _job("workday", "2026-11-06T22:00:00Z", False),
        "future": _job("workday", "2026-11-07T03:00:00Z"),
        "onsite_only": _job("himalayas", "2026-11-06T22:00:00Z"),
    }
    assert _fresh_alert_ids(list(rows), rows, _NOW) == ["fresh", "yesterday"]


def test_date_only_posting_and_invalid_timestamps():
    jobs = {
        "today": _job("greenhouse", "2026-11-06"),
        "malformed": _job("greenhouse", "a minute ago"),
        "missing": _job("greenhouse", ""),
    }
    assert _fresh_alert_ids(list(jobs), jobs, _NOW) == ["today"]
