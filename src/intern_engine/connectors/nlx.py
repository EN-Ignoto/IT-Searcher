"""NLx / DEJobs — the National Labor Exchange, searched around one place.

NLx is where state workforce agencies and large employers syndicate openings,
so it carries the hospitals, hotels, school contractors and staffing desks
that never appear on a tech-company ATS. One registry entry is one *area*
("within 50 miles of Kissimmee"), read as the union of several phrase
searches: the whole area is ~15,000 jobs, far too many to page through every
half hour, while the phrases below return a few hundred.

    GET https://prod-search-api.jobsyn.org/api/v1/solr/search
        ?q="help desk"&location=Kissimmee, FL&r=50&page=N
    header  x-origin: dejobs.org

Fifteen jobs per page; `pagination.has_more_pages` drives paging. Every job
carries its own coordinates, posting date and full description, so nothing
here needs a detail request.

The snapshot is "complete" when every phrase was paged to its end. A job that
then stops matching all of them on two consecutive runs is treated as gone.
"""

from __future__ import annotations

import asyncio
import re

import httpx

from .. import geo
from ..models import (
    INCOMPLETE_CAPPED,
    INCOMPLETE_MALFORMED,
    INCOMPLETE_STALLED,
    Fetch,
    Job,
    clean_listing,
    source_board_key,
)
from ..net import Net

API = "https://prod-search-api.jobsyn.org/api/v1/solr/search"
HEADERS = {"x-origin": "dejobs.org", "Accept": "application/json"}

# Quoted phrases, because the API treats bare words as OR-ish and drops "it"
# as a stopword. Order is irrelevant; results are unioned by GUID.
QUERIES = (
    '"help desk"', '"service desk"', '"desktop support"', '"IT support"',
    '"technical support"', '"IT technician"', '"IT specialist"',
    '"support technician"', '"support specialist"', '"support analyst"',
    '"computer technician"', '"field technician"', '"information technology"',
    '"network technician"', '"network administrator"', '"network operations"',
    '"systems administrator"', '"system administrator"', '"data center"',
    '"end user"', '"IT intern"', '"technology intern"', '"cybersecurity"',
    '"security analyst"', '"IT analyst"', '"IT associate"', '"IT assistant"',
    '"technology specialist"', '"technology support"', '"PC technician"',
)

# The first live run sent ~300 requests in 15 seconds and the next run was
# refused with HTTP 429. Two at a time with a pause is about four a second.
_CONCURRENCY = 2
_PAUSE_SECONDS = 0.25
INCOMPLETE_RATE_LIMITED = "rate-limited"
_MAX_PAGES = 40   # 600 results per phrase; more than that is a runaway query


class NlxError(RuntimeError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "job"


def _first(doc: dict, *names: str):
    for name in names:
        value = doc.get(name)
        if isinstance(value, list):
            value = value[0] if value else None
        if value not in (None, ""):
            return value
    return None


def _job(doc: dict, company: dict) -> Job | None:
    guid = _first(doc, "guid")
    title = _first(doc, "title_exact", "title")
    if not guid or not title:
        return None
    guid = str(guid).upper()
    employer = str(_first(doc, "company_exact", "company") or "Employer not named")
    location = str(_first(doc, "location_exact", "location", "city") or "—")
    posted = _first(doc, "date_new", "date_added", "date_updated")
    posted = str(posted) if posted else None
    if posted and not re.match(r"\d{4}-\d{2}-\d{2}", posted):
        posted = None
    title_slug = _first(doc, "title_slug") or _slug(str(title))
    return Job(
        id=f"nlx:{company['slug']}:{guid}",
        source="nlx",
        company=employer.strip(),
        company_slug=_slug(employer),
        title=str(title).strip(),
        location=location.strip(),
        # The DEJobs posting page; its Apply button leads to the employer.
        url=f"https://dejobs.org/{_slug(location)}/{title_slug}/{guid}/job/",
        posted_at=posted,
        description=_first(doc, "description", "html_description"),
        board_key=source_board_key(company, "nlx"),
        # One NLx GUID is one requisition wherever else it is syndicated.
        canonical_id=guid,
        latlon=geo.parse_latlon(_first(doc, "GeoLocation", "geo_location")),
    )


async def _one_query(query: str, base: dict, company: dict, net: Net,
                     gate: asyncio.Semaphore):
    jobs: dict[str, Job] = {}
    previous: tuple[str, ...] = ()
    for page in range(1, _MAX_PAGES + 1):
        try:
            async with gate:
                data = await net.get_json(
                    API, params={**base, "q": query, "page": str(page)}, headers=HEADERS)
                await asyncio.sleep(_PAUSE_SECONDS)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                # Asked to slow down. Keep what this phrase already returned;
                # the snapshot is partial, so it closes nothing.
                return jobs, INCOMPLETE_RATE_LIMITED
            raise
        docs = clean_listing(data, "jobs")
        if docs is None:
            if not jobs and page == 1:
                keys = sorted(data)[:12] if isinstance(data, dict) else type(data).__name__
                raise NlxError(f"unrecognized response; top-level keys: {keys}")
            return jobs, INCOMPLETE_MALFORMED
        if docs and page == 1 and not any(_job(d, company) for d in docs):
            raise NlxError(f"jobs not understood; item keys: {sorted(docs[0])[:25]}")
        signature = tuple(str(d.get("guid")) for d in docs)
        if docs and signature == previous:
            return jobs, INCOMPLETE_STALLED   # the API ignored `page`
        previous = signature
        for doc in docs:
            job = _job(doc, company)
            if job is not None:
                jobs.setdefault(job.id, job)
        pagination = data.get("pagination")
        more = isinstance(pagination, dict) and bool(pagination.get("has_more_pages"))
        if not docs or not more:
            return jobs, None
    return jobs, INCOMPLETE_CAPPED


async def fetch(company: dict, net: Net) -> Fetch:
    base = {"location": company.get("location", geo.HOME_NAME),
            "r": str(company.get("radius", 50))}
    queries = company.get("queries") or QUERIES
    gate = asyncio.Semaphore(_CONCURRENCY)
    results = await asyncio.gather(
        *(_one_query(q, base, company, net, gate) for q in queries))
    jobs: dict[str, Job] = {}
    reason: str | None = None
    for found, why in results:
        for jid, job in found.items():
            jobs.setdefault(jid, job)
        if why in (INCOMPLETE_MALFORMED, INCOMPLETE_STALLED):
            reason = why
        elif why and reason is None:
            reason = why
    if not jobs and reason == INCOMPLETE_RATE_LIMITED:
        raise NlxError("rate limited (HTTP 429) before any result was returned")
    return Fetch(list(jobs.values()), complete=reason is None, incomplete_reason=reason)
