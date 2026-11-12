"""What the published pages show, computed once so they cannot disagree.

README, dashboard, CSV, feed and JSON API all list the same roles in the same
order: Local first, then Nearby, then Remote; newest posting first inside
each. The order is the product — the reader wants the closest jobs first.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from . import filters_it

SECTION_BLURB = {
    filters_it.LOCAL: "Within {local:g} miles of Kissimmee",
    filters_it.NEARBY: "{local:g} to {nearby:g} miles from Kissimmee",
    filters_it.REMOTE: "Remote, and open to Florida residents",
}
FIT_LABEL = {
    filters_it.FIT_BEGINNER: "Beginner-friendly",
    filters_it.FIT_STRETCH: "Stretch",
    filters_it.FIT_UNVERIFIED: "Check requirements",
}
SOURCE_LABEL = {
    "nlx": "NLx / DEJobs", "neogov": "GovernmentJobs", "paradox": "District careers site",
    "workday": "Workday", "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
    "smartrecruiters": "SmartRecruiters", "oracle": "Oracle", "icims": "iCIMS",
    "workable": "Workable", "rippling": "Rippling", "breezy": "Breezy",
    "recruitee": "Recruitee", "amazon": "Amazon Jobs", "eightfold": "Eightfold",
}


def parse_ts(value: str | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _sort_key(record: dict):
    # Newest first by the day it was posted (or, undated, the day we found it).
    day = (record.get("posted_at") or record.get("first_seen_at") or "")[:10]
    miles = record.get("miles")
    # The id breaks ties, so the order never depends on how the store happens
    # to be laid out in memory versus on disk.
    return (day, -(miles if isinstance(miles, (int, float)) else 999.0),
            record.get("first_seen_at") or "", record.get("id") or "")


def open_by_section(store_data: dict) -> dict[str, list[dict]]:
    sections: dict[str, list[dict]] = {name: [] for name in filters_it.SECTIONS}
    for record in store_data.values():
        if record.get("is_open") and record.get("section") in sections:
            sections[record["section"]].append(record)
    for rows in sections.values():
        rows.sort(key=_sort_key, reverse=True)
    return sections


def open_jobs(store_data: dict) -> list[dict]:
    """Every open role in published order."""
    sections = open_by_section(store_data)
    return [r for name in filters_it.SECTIONS for r in sections[name]]


def is_new(record: dict, as_of: datetime, hours: float = 72) -> bool:
    seen = parse_ts(record.get("first_seen_at"))
    return bool(seen and as_of - seen <= timedelta(hours=hours))


def posted_label(record: dict) -> str:
    """'Nov 3' for a real date, '~Nov 3' for an approximate one, else found-on."""
    posted = parse_ts(record.get("posted_at"))
    if posted:
        approx = "~" if record.get("posted_at_source") == "relative_derived" else ""
        return f"{approx}{posted.strftime('%b')} {posted.day}"
    seen = parse_ts(record.get("first_seen_at"))
    return f"found {seen.strftime('%b')} {seen.day}" if seen else "—"


def where(record: dict) -> str:
    location = (record.get("location") or "—").strip()
    miles = record.get("miles")
    if isinstance(miles, (int, float)) and record.get("section") != filters_it.REMOTE:
        location += f" · {miles:.0f} mi"
    if record.get("remote") and record.get("section") != filters_it.REMOTE:
        location += " · remote option"
    return location
