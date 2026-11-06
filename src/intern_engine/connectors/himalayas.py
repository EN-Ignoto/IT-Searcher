"""Himalayas public remote jobs, for display on our own site only.

API terms: preserve applicationLink, visibly credit Himalayas, and do not
syndicate these rows through RSS, CSV, JSON feeds or JobPosting metadata.
https://himalayas.app/docs/remote-jobs-api
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import urlencode

from ..models import INCOMPLETE_CAPPED, INCOMPLETE_MALFORMED, Fetch, Job, clean_listing

_SEARCH = "https://himalayas.app/jobs/api/search"
_TERMS = ("help desk", "IT support", "desktop support", "network technician",
          "IT technician", "service desk", "IT intern")
_FORBIDDEN_LEVELS = ("mid-level", "senior", "manager", "director", "executive")
_FORBIDDEN_TYPES = ("volunteer",)


def _eligible_location(row: dict) -> bool:
    restrictions = row.get("locationRestrictions") or []
    if not isinstance(restrictions, list):
        return False
    # Empty = worldwide-eligible; nonempty must explicitly include the US.
    if restrictions and not any(
        (isinstance(v, str) and v.strip().casefold() in
         {"us", "usa", "united states", "united states of america"})
        or (isinstance(v, dict) and (
            str(v.get("alpha2", "")).upper() == "US"
            or str(v.get("name", "")).casefold() == "united states"))
        for v in restrictions
    ):
        return False
    types = row.get("employmentType") or []
    if isinstance(types, str):
        types = [types]
    if not isinstance(types, list) or any(
        str(t).lower() in _FORBIDDEN_TYPES for t in types
    ):
        return False
    levels = row.get("seniority") or []
    if isinstance(levels, str):
        levels = [levels]
    if not isinstance(levels, list) or any(
        str(level).casefold() in _FORBIDDEN_LEVELS for level in levels
    ):
        return False
    return True


def _convert(row: dict, company: dict, now: datetime) -> Job | None:
    if not _eligible_location(row):
        return None
    title = str(row.get("title") or "").strip()
    name = str(row.get("companyName") or "").strip()
    guid = str(row.get("guid") or "").strip()
    apply = str(row.get("applicationLink") or "").strip()
    if not (title and name and guid.startswith("https://himalayas.app/")
            and apply.startswith("https://")):
        return None
    try:
        expiry = row.get("expiryDate")
        if expiry is not None and datetime.fromtimestamp(int(expiry), UTC) <= now:
            return None
        published = row.get("pubDate")
        posted = datetime.fromtimestamp(int(published), UTC).isoformat() if published else None
    except (ValueError, OverflowError, TypeError):
        return None
    # Stable bounded primary key, independent of query duplicates.
    jid = hashlib.sha256(guid.encode("utf-8")).hexdigest()[:20]
    description = str(row.get("description") or row.get("excerpt") or "")
    currency = str(row.get("currency") or "USD")
    min_pay, max_pay = row.get("minSalary"), row.get("maxSalary")
    salary = None
    if isinstance(min_pay, (int, float)) and min_pay > 0:
        salary = f"{currency} {min_pay:g}"
        if isinstance(max_pay, (int, float)) and max_pay >= min_pay:
            salary += f"–{max_pay:g}"
        salary += f" {row.get('salaryPeriod') or 'annual'}"
        description += f" Compensation: {salary}."
    # Source attribution is part of the displayed employer label on dashboard.
    return Job(
        id=f"himalayas:{company['slug']}:{jid}",
        source="himalayas",
        company=f"{name} (via Himalayas)",
        company_slug=company["slug"],
        title=title,
        location="Remote - United States",
        url=apply,  # MUST NOT replace with a direct ATS link.
        posted_at=posted,
        posted_at_source="exact" if posted else None,
        description=description,
        salary=salary,
    )


async def fetch(company: dict, net) -> Fetch:
    """Get the first two pages of US-applicable remote roles per search term.

    The API's keyword search is never a whole-board snapshot; missing results
    cannot prove a job closed. Failed individual searches are isolated.
    """
    now = datetime.now(UTC)
    found: dict[str, Job] = {}
    healthy = 0
    for term in _TERMS:
        for page in (1, 2):
            params = urlencode({"q": term, "country": "US", "sort": "recent", "page": page})
            try:
                data = await net.get_json(f"{_SEARCH}?{params}", retries=1)
            except Exception:  # noqa: BLE001
                continue
            jobs = clean_listing(data, "jobs")
            if jobs is None:
                continue
            healthy += 1
            for row in jobs:
                job = _convert(row, company, now)
                if job is not None:
                    found.setdefault(job.id, job)
            if len(jobs) < 20:
                break
    if not healthy:
        return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
    return Fetch(list(found.values()), complete=False, incomplete_reason=INCOMPLETE_CAPPED)
