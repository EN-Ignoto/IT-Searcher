"""Paradox career sites — used by the School District of Osceola County.

    POST https://{host}/api/get-jobs?page_number=N&enable_kilometers=false
    body {}

Ten jobs per page with `totalJob` in the response. Each job lists its
locations with a city, state and coordinates. The posting page lives at
`https://{host}/{originalURL}` and embeds schema.org JobPosting JSON-LD with
the description and the publish date.

School districts hire technology support staff under titles such as
"Technology Support Specialist" and "Computer Technician", and none of it is
syndicated to NLx — which is why the district is read directly.
"""

from __future__ import annotations

from ..models import (
    INCOMPLETE_CAPPED,
    INCOMPLETE_MALFORMED,
    INCOMPLETE_STALLED,
    Fetch,
    Job,
    source_board_key,
)
from ..net import Net

HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
_MAX_PAGES = 120
_LIST_KEYS = ("jobs", "data", "results", "jobList", "items")
_TOTAL_KEYS = ("totalJob", "totalJobs", "total", "totalCount")


class ParadoxError(RuntimeError):
    pass


def _listing(data) -> list[dict] | None:
    if not isinstance(data, dict) or data.get("error") or data.get("errors"):
        return None
    for key in _LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list) and all(isinstance(x, dict) for x in value):
            return value
    return None


def _total(data: dict) -> int | None:
    for key in _TOTAL_KEYS:
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _text(item: dict, *names: str) -> str:
    for name in names:
        value = item.get(name)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return ""


def _job(item: dict, company: dict, host: str) -> Job | None:
    title = _text(item, "title", "jobTitle", "name")
    path = _text(item, "originalURL", "originalUrl", "url", "jobUrl").lstrip("/")
    external = _text(item, "jobId", "id", "requisitionID", "reqId", "uniqueID") or path
    if not title or not external:
        return None
    location, latlon = "—", None
    places = item.get("locations")
    if isinstance(places, list) and places and isinstance(places[0], dict):
        place = places[0]
        city = _text(place, "city")
        state = _text(place, "stateAbbr", "state")
        location = ", ".join(x for x in (city, state) if x) or \
            _text(place, "locationName", "name") or "—"
        try:
            lat, lon = float(place.get("latitude")), float(place.get("longitude"))
            if (lat, lon) != (0.0, 0.0) and -90 <= lat <= 90 and -180 <= lon <= 180:
                latlon = (lat, lon)
        except (TypeError, ValueError):
            latlon = None
    if path.startswith(("http://", "https://")):
        url = path
    else:
        url = f"https://{host}/{path}" if path else f"https://{host}/"
    return Job(
        id=f"paradox:{company['slug']}:{external}",
        source="paradox",
        company=company["name"],
        company_slug=company["slug"],
        title=title,
        location=location,
        url=url,
        board_key=source_board_key(company, "paradox"),
        latlon=latlon,
        employment_hint=_text(item, "employmentType", "jobType", "category") or None,
    )


async def fetch(company: dict, net: Net) -> Fetch:
    host = company["host"]
    jobs: dict[str, Job] = {}
    reason: str | None = INCOMPLETE_CAPPED
    previous: tuple[str, ...] = ()
    for page in range(1, _MAX_PAGES + 1):
        data = await net.post_json(
            f"https://{host}/api/get-jobs",
            params={"page_number": str(page), "enable_kilometers": "false"},
            json={}, headers=HEADERS)
        items = _listing(data)
        if items is None:
            if not jobs:
                # Say what came back: the log is the only way to see a shape
                # change on a site this workspace cannot reach.
                keys = sorted(data)[:12] if isinstance(data, dict) else type(data).__name__
                raise ParadoxError(f"unrecognized response; top-level keys: {keys}")
            reason = INCOMPLETE_MALFORMED
            break
        signature = tuple(str(sorted(i.items(), key=str))[:200] for i in items)
        if items and signature == previous:
            reason = INCOMPLETE_STALLED
            break
        previous = signature
        for item in items:
            job = _job(item, company, host)
            if job is not None:
                jobs.setdefault(job.id, job)
        if items and not jobs:
            raise ParadoxError(f"jobs not understood; item keys: {sorted(items[0])[:20]}")
        total = _total(data)
        if not items or len(items) < 10 or (total is not None and len(jobs) >= total):
            reason = None
            break
    return Fetch(list(jobs.values()), complete=reason is None, incomplete_reason=reason)


async def description(job: Job, net: Net) -> str | None:
    from .. import pagetext
    page = await net.get_text(job.url)
    text, posted = pagetext.extract(page)
    if posted and not job.posted_at:
        job.posted_at = posted
    return text
