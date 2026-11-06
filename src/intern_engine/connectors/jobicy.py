"""Jobicy public remote-job feed: a recent independent source of US IT openings.

Jobicy's free API serves postings from the previous seven days. A listing
falling out of that rolling window is not proof it closed, so its snapshot
MUST NEVER be treated as complete for lifecycle deletion.

Source: https://jobicy.com/jobs-rss-feed
Attribution and the Jobicy URL are retained for every posting.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from ..models import Fetch, Job, INCOMPLETE_CAPPED, INCOMPLETE_MALFORMED, clean_listing

_BASE = "https://jobicy.com/api/jobs?count=100&geo=usa&tag="
_TERMS = (
    "help desk", "service desk", "IT support", "desktop support",
    "technical support", "IT technician", "network technician",
    "IT intern", "IT operations",
)
_US = re.compile(r"\b(?:us|usa|united states|america|north america|worldwide|anywhere|global)\b", re.I)
_OTHER_COUNTRY = re.compile(
    r"\b(?:united kingdom|canada only|europe only|australia only|"
    r"latam only|emea only|uk only|canada|europe|germany|france)\b", re.I,
)
_EXPERIENCED = re.compile(r"\b(?:senior|staff|principal|lead|manager|director|executive|mid[ -]?level)\b", re.I)


def _location(geo: str) -> str | None:
    """Admit only listings that explicitly permit US-based remote applicants."""
    if _OTHER_COUNTRY.search(geo) and not re.search(r"\b(?:us|usa|united states)\b", geo, re.I):
        return None
    if not _US.search(geo):
        return None
    return f"Remote - United States (Jobicy: {geo})"


def _convert(row: dict, company: dict) -> Job | None:
    external_id = row.get("id")
    title = str(row.get("jobTitle") or "").strip()
    employer = str(row.get("companyName") or "").strip()
    geo = str(row.get("jobGeo") or "").strip()
    url = str(row.get("url") or "").strip()
    if not external_id or not title or not employer or not geo:
        return None
    if not url.startswith("https://jobicy.com/"):
        return None
    location = _location(geo)
    if location is None:
        return None
    level = str(row.get("jobLevel") or "")
    if _EXPERIENCED.search(level):
        return None
    description = str(row.get("jobDescription") or row.get("jobExcerpt") or "").strip()
    compensation = " ".join(
        str(row.get(field) or "")
        for field in ("salaryMin", "salaryMax", "salaryCurrency", "salaryPeriod")
    )
    # The title is left unchanged; the original public listing provides
    # jobLevel and jobType for users to verify.
    types = row.get("jobType") or []
    type_text = " ".join(map(str, types)) if isinstance(types, list) else str(types)
    details = " ".join((description, "Compensation:", compensation, "Employment type:", type_text))
    date = str(row.get("pubDate") or "").strip() or None
    return Job(
        id=f"jobicy:{company['slug']}:{external_id}",
        source="jobicy",
        company=employer,
        company_slug=company["slug"],
        title=title,
        location=location,
        url=url,
        posted_at=date,
        posted_at_source="exact" if date else None,
        description=details,
    )


async def fetch(company: dict, net) -> Fetch:
    """Get recent US remote support roles, suppressing duplicates across terms.

    A failed keyword query cannot be mistaken for an empty complete board.
    If other keyword searches succeeded, their results are still usable.
    """
    found: dict[str, Job] = {}
    successful = 0
    for term in _TERMS:
        try:
            data = await net.get_json(_BASE + quote(term, safe=""), retries=1)
        except Exception:  # noqa: BLE001 — isolate a broken keyword request
            continue
        if not isinstance(data, dict) or data.get("success") is False:
            continue
        rows = clean_listing(data, "jobs")
        if rows is None:
            continue
        successful += 1
        for row in rows:
            job = _convert(row, company)
            if job is not None:
                found.setdefault(job.id, job)
    if not successful:
        return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
    # Rolling seven-day sources are never complete lifecycle snapshots.
    return Fetch(list(found.values()), complete=False, incomplete_reason=INCOMPLETE_CAPPED)
