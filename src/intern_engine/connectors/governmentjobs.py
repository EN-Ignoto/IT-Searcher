"""Monitor local governmental job postings using verifiable public detail pages.

The City of Kissimmee uses the GovernmentJobs portal for public job listings.
Never invent a posting date or requirements. Search pages may be incomplete,
so missing items are NOT grounds for automatically closing past listings.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin

from .. import filters_it
from ..models import INCOMPLETE_CAPPED, INCOMPLETE_MALFORMED, Fetch, Job

_BASE = "https://www.governmentjobs.com"
_CITY_URL = (
    _BASE + "/jobs?distance=25&isPromotional=False&isTransfer=False"
    "&location=Kissimmee%2C+FL&organization%5B0%5D=City+of+Kissimmee&page="
)
_LINK = re.compile(
    r"<a\b(?P<attrs>[^>]*\bclass=[\"'][^\"']*\bjob-details-link\b[^\"']*[\"'][^>]*)>"
    r"(?P<title>.*?)</a>", re.I | re.S,
)
_HREF = re.compile(r"\bhref=[\"'](?P<path>/jobs/\d+-\d+/[\w-]+)[\"']", re.I)
_SCRIPT = re.compile(
    r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.I | re.S,
)
_TAGS = re.compile(r"<[^>]*>")


def _plain(s: str) -> str:
    return " ".join(unescape(_TAGS.sub(" ", s or "")).split())


def city_links(page: str) -> dict[str, str]:
    """Extract result links from the live GovernmentJobs search markup."""
    hits = {}
    for match in _LINK.finditer(page):
        href = _HREF.search(match.group("attrs"))
        if not href:
            continue
        title = _plain(match.group("title"))
        if filters_it.is_opportunity(title):
            hits.setdefault(href.group("path"), title)
    return hits


def city_job(path: str, detail: str) -> Job | None:
    """Accept only City of Kissimmee's own dated, valid JobPosting evidence."""
    for body in _SCRIPT.findall(detail):
        try:
            data = json.loads(unescape(body))
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("@type") != "JobPosting":
            continue
        employer = data.get("hiringOrganization") or {}
        if not isinstance(employer, dict):
            continue
        if str(employer.get("name") or "").strip().casefold() != "city of kissimmee":
            continue
        title = _plain(str(data.get("title") or ""))
        if not filters_it.is_opportunity(title):
            continue
        location = data.get("jobLocation") or {}
        if isinstance(location, list):
            location = next((x for x in location if isinstance(x, dict)), {})
        if not isinstance(location, dict):
            continue
        address = location.get("address") or {}
        if not isinstance(address, dict):
            continue
        city = str(address.get("addressLocality") or "").strip()
        state = str(address.get("addressRegion") or "").strip()
        if city.casefold() != "kissimmee" or state.upper() not in {"FL", "FLORIDA"}:
            continue
        posted = str(data.get("datePosted") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", posted):
            continue
        expiry = str(data.get("validThrough") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry):
            if expiry < datetime.now(UTC).date().isoformat():
                continue
        description = _plain(str(data.get("description") or ""))
        if not description:
            continue
        job_num = path.split("/")[2]
        return Job(
            id=f"localboards:kissimmee-city:{job_num}",
            source="localboards",
            company="City of Kissimmee",
            company_slug="kissimmee-city",
            title=title,
            location="Kissimmee, FL",
            url=urljoin(_BASE, path),
            posted_at=posted,
            posted_at_source="date_only",
            description=description,
        )
    return None


async def fetch(company: dict, net) -> Fetch:
    found: dict[str, Job] = {}
    seen: set[str] = set()
    healthy = 0
    # Usually <15 vacancies. A bounded second page avoids missing postings,
    # without silently treating a truncated search as a full company snapshot.
    for page_num in (1, 2, 3):
        try:
            page = await net.get_text(_CITY_URL + str(page_num), retries=1)
        except Exception:  # noqa: BLE001 — a failed page isn't a closed job
            break
        if "job-item-container" not in page and "Search Results" not in page:
            break
        links = city_links(page)
        if not links:
            healthy += 1
            break
        fresh_paths = [path for path in links if path not in seen]
        if not fresh_paths:
            break
        seen.update(links)
        healthy += 1
        for path in fresh_paths:
            try:
                detail = await net.get_text(urljoin(_BASE, path), retries=1)
            except Exception:  # noqa: BLE001
                continue
            job = city_job(path, detail)
            if job:
                found.setdefault(job.id, job)
    if not healthy:
        return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
    return Fetch(list(found.values()), complete=False, incomplete_reason=INCOMPLETE_CAPPED)
