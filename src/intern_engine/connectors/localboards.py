"""Live official Orlando-area job boards not served by the big ATS connectors.

Supported: Valencia College (PeopleAdmin) and Osceola County Schools (Paradox).
Links, dates, locations and requirements are read from each actual employer's
open career pages; none of the jobs are manually seeded. These searches are
always lifecycle-incomplete, so an indexing gap can't incorrectly close roles.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin

from .. import filters_it
from ..models import INCOMPLETE_CAPPED, INCOMPLETE_MALFORMED, Fetch, Job

_VALENCIA = "https://valenciacollege.peopleadmin.com"
_OSCEOLA = "https://jobs.osceolaschools.net"
_POSTING = re.compile(r'<a\b[^>]*href=["\']/postings/(\d+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_SCHOOL_JOB = re.compile(
    r'<a\b[^>]*href=["\'](/[^"\']+/job/[A-F0-9]{32})["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)
_SCRIPT = re.compile(
    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
_HTML = re.compile(r"<[^>]*>")


def _plain(value: str) -> str:
    return " ".join(unescape(_HTML.sub(" ", value or "")).split())


def _field(page: str, label: str) -> str:
    match = re.search(
        r"<th\b[^>]*>\s*" + re.escape(label) +
        r"\s*</th>\s*<td\b[^>]*>(.*?)</td>",
        page,
        re.I | re.S,
    )
    return _plain(match.group(1)) if match else ""


def _date(value: str) -> str | None:
    try:
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
            return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
        if re.match(r"\d{4}-\d{2}-\d{2}", value):
            return value[:10]
    except ValueError:
        return None
    return None


def valencia_links(html: str) -> dict[str, str]:
    """Extract actual posting anchors; ignore print previews and bookmark links."""
    found: dict[str, str] = {}
    for number, title_html in _POSTING.findall(html):
        title = _plain(title_html)
        if filters_it.is_opportunity(title):
            found.setdefault(number, title)
    return found


def valencia_job(number: str, title: str, detail: str) -> Job | None:
    """Require authoritative posting fields, never invent a location or date."""
    location = _field(detail, "Location(s)")
    posted = _date(_field(detail, "Posting Start Date"))
    closes = _date(_field(detail, "Posting End Date"))
    if closes and closes < datetime.now(UTC).date().isoformat():
        return None
    if not location or not posted:
        return None
    description = ". ".join(
        value for field in (
            "Description of Job Function", "Required Minimum Education",
            "Required Field of Study", "Other Required Qualifications",
            "Required License/Certification", "Preferred Qualifications",
            "Preferred Type of Experience", "Job Type",
            "Proposed Work Schedule (Please note hours subject to change based on business needs)",
        )
        if (value := _field(detail, field))
    )
    if not description:
        return None
    salary = _field(detail, "Salary Range") or None
    if salary and re.match(r"^\d", salary):
        salary = "$" + salary
    return Job(
        id=f"localboards:valencia:{number}",
        source="localboards",
        company="Valencia College",
        company_slug="valencia",
        title=title,
        location=location,
        url=f"{_VALENCIA}/postings/{number}",
        posted_at=posted,
        posted_at_source="date_only",
        description=description,
        salary=salary,
    )


def _school_title(title: str) -> str:
    """'Support Staff-' denotes school employee classification, not seniority."""
    return re.sub(r"^Support Staff\s*[-–:]\s*", "", title, flags=re.I).strip()


def osceola_links(html: str) -> dict[str, str]:
    """Each live employer results page contains distinct /job/<id> anchors."""
    found: dict[str, str] = {}
    for path, title_html in _SCHOOL_JOB.findall(html):
        title = _plain(title_html)
        if filters_it.is_opportunity(_school_title(title)):
            found.setdefault(path, title)
    return found


def osceola_job(path: str, detail: str) -> Job | None:
    """Use the site's JSON-LD JobPosting instead of guessing from navigation."""
    for script in _SCRIPT.findall(detail):
        try:
            payload = json.loads(script.strip())
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "JobPosting":
            continue
        title = _school_title(str(payload.get("title") or "").strip())
        if not filters_it.is_opportunity(title):
            continue
        raw_location = payload.get("jobLocation") or {}
        if isinstance(raw_location, list):
            raw_location = next((x for x in raw_location if isinstance(x, dict)), {})
        if not isinstance(raw_location, dict):
            raw_location = {}
        address = raw_location.get("address") or {}
        if not isinstance(address, dict):
            address = {}
        city = str(address.get("addressLocality") or "").strip()
        region = str(address.get("addressRegion") or "").strip()
        if not city or not region:
            continue
        posted = _date(str(payload.get("datePosted") or ""))
        expires = _date(str(payload.get("validThrough") or ""))
        if expires and expires < datetime.now(UTC).date().isoformat():
            continue
        description = _plain(str(payload.get("description") or ""))
        if not description:
            continue
        jid = path.rsplit("/", 1)[-1].upper()
        return Job(
            id=f"localboards:osceola:{jid}",
            source="localboards",
            company="School District of Osceola County",
            company_slug="osceola-schools",
            title=title,
            location=f"{city}, {region}",
            url=urljoin(_OSCEOLA, path),
            posted_at=posted,
            posted_at_source="date_only" if posted else None,
            description=description,
        )
    return None


async def _fetch_valencia(company: dict, net) -> Fetch:
    try:
        page = await net.get_text(f"{_VALENCIA}/postings/search", retries=1)
    except Exception:  # noqa: BLE001 - do not mistake network errors for closures
        return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
    if "job-item-posting" not in page and "View Results" not in page:
        return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
    jobs = []
    for number, title in valencia_links(page).items():
        try:
            detail = await net.get_text(f"{_VALENCIA}/postings/{number}", retries=1)
        except Exception:  # noqa: BLE001
            continue
        if job := valencia_job(number, title, detail):
            jobs.append(job)
    # PeopleAdmin's search is paginated, and one page cannot prove old jobs closed.
    return Fetch(jobs, complete=False, incomplete_reason=INCOMPLETE_CAPPED)


async def _fetch_osceola(company: dict, net) -> Fetch:
    jobs: dict[str, Job] = {}
    seen: set[str] = set()
    healthy = 0
    for page_num in range(1, 26):
        page_url = f"{_OSCEOLA}/jobs" if page_num == 1 else f"{_OSCEOLA}/jobs/page/{page_num}"
        try:
            page = await net.get_text(page_url, retries=1)
        except Exception:  # noqa: BLE001
            break
        if "jobs-list" not in page and "/job/" not in page:
            break
        found = {
            path: title for path, title in _SCHOOL_JOB.findall(page)
            if filters_it.is_opportunity(_school_title(_plain(title)))
        }
        # The page can contain zero matching IT titles and still contain many
        # genuine open non-IT postings. Use ALL job links to detect a final page.
        all_links = {path for path, _ in _SCHOOL_JOB.findall(page)}
        if not all_links or all_links.issubset(seen):
            break
        seen.update(all_links)
        healthy += 1
        for path in found:
            if path in jobs:
                continue
            try:
                detail = await net.get_text(urljoin(_OSCEOLA, path), retries=1)
            except Exception:  # noqa: BLE001
                continue
            if job := osceola_job(path, detail):
                jobs.setdefault(job.id, job)
    if not healthy:
        return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
    return Fetch(list(jobs.values()), complete=False, incomplete_reason=INCOMPLETE_CAPPED)


async def fetch(company: dict, net) -> Fetch:
    slug = company.get("slug")
    if slug == "valencia":
        return await _fetch_valencia(company, net)
    if slug == "osceola-schools":
        return await _fetch_osceola(company, net)
    return Fetch([], complete=False, incomplete_reason=INCOMPLETE_MALFORMED)
