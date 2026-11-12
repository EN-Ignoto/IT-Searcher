"""Fetch the posting text for a role whose list payload did not carry it.

Cost model: this runs ONLY on roles that already passed the title and location
checks (a handful per run, not thousands). NLx/Lever/Ashby/Amazon/Recruitee
ship descriptions in their list payloads; Greenhouse/SmartRecruiters/Workday/
Oracle/Workable/NEOGOV/Paradox need one detail request per NEW role, after
which the pipeline caches the verdict and never re-fetches. Workday details
also carry the exact posting date, which corrects "N days ago" approximations.
"""

from __future__ import annotations

import re

from .connectors import neogov, paradox, peopleadmin
from .models import Job
from .net import Net

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}

# Both public Workday URL shapes, mapped back to the CXS detail endpoint.
_WD_SUB_RE = re.compile(
    r"https://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w%-]+)(/job/.+)", re.I
)
_WD_SITE_RE = re.compile(
    r"https://(wd\d+\.myworkdaysite\.com)/recruiting/([\w-]+)/([\w%-]+)(/job/.+)", re.I
)
_ORACLE_RE = re.compile(r"https://([\w.-]+\.oraclecloud\.com)/.+/sites/([\w]+)/job/(\d+)", re.I)


async def _greenhouse(job: Job, net: Net) -> str | None:
    external_id = job.id.rsplit(":", 1)[-1]
    url = f"https://boards-api.greenhouse.io/v1/boards/{job.company_slug}/jobs/{external_id}"
    data = await net.get_json(url)
    return data.get("content")


async def _smartrecruiters(job: Job, net: Net) -> str | None:
    external_id = job.id.rsplit(":", 1)[-1]
    url = f"https://api.smartrecruiters.com/v1/companies/{job.company_slug}/postings/{external_id}"
    data = await net.get_json(url)
    sections = ((data.get("jobAd") or {}).get("sections") or {})
    return " ".join(
        str((sections.get(k) or {}).get("text") or "")
        for k in ("jobDescription", "qualifications", "additionalInformation")
    )


async def _workday(job: Job, net: Net) -> str | None:
    m = _WD_SUB_RE.match(job.url)
    if m:
        tenant, wd, site, path = m.groups()
        host = f"{tenant}.{wd}.myworkdayjobs.com"
    else:
        m = _WD_SITE_RE.match(job.url)
        if not m:
            return None
        host, tenant, site, path = m.groups()
    data = await net.get_json(
        f"https://{host}/wday/cxs/{tenant}/{site}{path}", headers=_BROWSER_HEADERS
    )
    info = data.get("jobPostingInfo") or {}
    # The detail API knows the real go-live date; the list API only said
    # "N days ago". The detail date fills blanks AND corrects approximations —
    # the old `if not job.posted_at` guard meant a derived guess, once present,
    # blocked the true date from ever landing.
    start = info.get("startDate")
    if isinstance(start, str) and len(start) == 10 and (
        not job.posted_at or job.posted_at_source == "relative_derived"
    ):
        job.posted_at = f"{start}T00:00:00Z"
        job.posted_at_source = "date_only"
    return info.get("jobDescription")


async def _oracle(job: Job, net: Net) -> str | None:
    m = _ORACLE_RE.match(job.url)
    if not m:
        return None
    host, site, req_id = m.groups()
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
    params = {
        "onlyData": "true",
        "expand": "all",
        "finder": f'ById;Id="{req_id}",siteNumber={site}',
    }
    data = await net.get_json(url, params=params, headers=_BROWSER_HEADERS)
    items = data.get("items") or []
    if not items:
        return None
    return " ".join(
        str(items[0].get(k) or "")
        for k in ("ExternalDescriptionStr", "ExternalQualificationsStr", "CorporateDescriptionStr")
    )


async def _workable(job: Job, net: Net) -> str | None:
    shortcode = job.id.rsplit(":", 1)[-1]
    url = f"https://apply.workable.com/api/v2/accounts/{job.company_slug}/jobs/{shortcode}"
    data = await net.get_json(url)
    return " ".join(str(data.get(k) or "") for k in ("description", "requirements", "benefits"))


_FETCHERS = {
    "greenhouse": _greenhouse,
    "smartrecruiters": _smartrecruiters,
    "workday": _workday,
    "oracle": _oracle,
    "workable": _workable,
    "neogov": neogov.description,
    "paradox": paradox.description,
    "peopleadmin": peopleadmin.description,
}


async def describe(job: Job, net: Net) -> tuple[str | None, bool]:
    """(posting text or None, whether a detail request was made).

    Never raises: a dead detail page must not kill the run. The caller treats
    missing text as "unverified", which is retried later.
    """
    if job.description:
        return job.description, False
    fetcher = _FETCHERS.get(job.source)
    if fetcher is None:
        return None, False
    try:
        job.description = await fetcher(job, net)
    except Exception:  # noqa: BLE001
        return None, True
    return job.description, True


async def posting_gone(record: dict, net: Net) -> bool:
    """True only on the employer's explicit "this posting no longer exists".

    Used for boards whose search results are capped: absence from a capped
    result proves nothing, so the posting itself is asked. Any other outcome
    (timeout, block page, 5xx) is "don't know" and keeps the role.
    """
    import httpx
    url = record.get("url") or ""
    m = _WD_SUB_RE.match(url)
    if m:
        tenant, wd, site, path = m.groups()
        target = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{path}"
    else:
        m = _WD_SITE_RE.match(url)
        if not m:
            return False
        host, tenant, site, path = m.groups()
        target = f"https://{host}/wday/cxs/{tenant}/{site}{path}"
    try:
        await net.get_json(target, headers=_BROWSER_HEADERS, retries=1)
    except httpx.HTTPStatusError as exc:
        return exc.response.status_code in (404, 410)
    except Exception:  # noqa: BLE001
        return False
    return False
