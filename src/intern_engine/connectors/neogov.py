"""NEOGOV (governmentjobs.com) — city and county governments.

Local governments are steady employers of help desk and IT technician staff
and post nowhere else. Each agency's career page loads its list from

    GET https://www.governmentjobs.com/careers/home/index?agency={slug}&page=N
    header  X-Requested-With: XMLHttpRequest

which answers with an HTML fragment, ten jobs per page:

    <li class="list-item" data-job-id="4821345">
      <a class="item-details-link" href="/careers/osceola/jobs/4821345/...">Title</a>
      <ul class="list-meta"><li>Kissimmee, FL</li><li>Full-Time ...</li></ul>
      <span class="list-published">Posted 1 week ago</span>

An agency with no openings answers with `jobs-not-found-container`; a slug
that does not exist answers with a whole HTML document, which is an error, not
an empty board. These boards are small enough to read in full, so the snapshot
is complete and may close roles.
"""

from __future__ import annotations

import html as _html
import re
from datetime import UTC, datetime, timedelta

from ..models import INCOMPLETE_CAPPED, INCOMPLETE_STALLED, Fetch, Job, source_board_key
from ..net import Net

BASE = "https://www.governmentjobs.com"
HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "text/html, */*; q=0.01",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}
_MAX_PAGES = 30

_ITEM_OPEN_RE = re.compile(
    r"<li\b[^>]*\bclass=\"[^\"]*\blist-item\b[^\"]*\"[^>]*>", re.I)
_ID_RE = re.compile(r"data-job-id=\"(\d+)\"", re.I)
_LINK_RE = re.compile(
    r"<a\b[^>]*\bclass=\"[^\"]*\bitem-details-link\b[^\"]*\"[^>]*>(.*?)</a>", re.I | re.S)
_HREF_RE = re.compile(r"href=\"([^\"]+)\"", re.I)
_META_RE = re.compile(
    r"<ul\b[^>]*\bclass=\"[^\"]*\blist-meta\b[^\"]*\"[^>]*>(.*?)</ul>", re.I | re.S)
_LI_RE = re.compile(r"<li\b[^>]*>(.*?)</li>", re.I | re.S)
_PUBLISHED_RE = re.compile(
    r"class=\"[^\"]*\blist-published\b[^\"]*\"[^>]*>(.*?)</", re.I | re.S)
_AGO_RE = re.compile(r"(\d+|an?)\s+(hour|day|week|month)s?\s+ago", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


class NeogovError(RuntimeError):
    pass


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG_RE.sub(" ", fragment or ""))).strip()


def _posted(text: str, now: datetime | None = None) -> str | None:
    """'Posted 1 week ago' -> an approximate day. More than a month is too vague."""
    low = (text or "").lower()
    now = now or datetime.now(UTC)
    if "today" in low or "hour" in low or "minute" in low:
        return now.strftime("%Y-%m-%dT00:00:00Z")
    if "yesterday" in low:
        return (now - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    m = _AGO_RE.search(low)
    if not m:
        return None
    count = 1 if m.group(1) in ("a", "an") else int(m.group(1))
    unit = m.group(2)
    if unit == "month" or "more than" in low or "over" in low:
        return None
    days = count * (7 if unit == "week" else 1)
    return (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")


def parse(fragment: str, company: dict) -> list[Job]:
    """Every job in one page fragment."""
    agency = company["slug"]
    jobs: list[Job] = []
    opens = [m.start() for m in _ITEM_OPEN_RE.finditer(fragment)]
    for start, end in zip(opens, [*opens[1:], len(fragment)], strict=False):
        whole = fragment[start:end]
        job_id = _ID_RE.search(whole[:whole.find(">") + 1])
        link = _LINK_RE.search(whole)
        if not link:
            continue
        anchor = whole[link.start():link.end()]
        href = _HREF_RE.search(anchor)
        path = _html.unescape(href.group(1)) if href else ""
        if not job_id:
            job_id = re.search(r"/jobs/(\d+)", path)
        if not job_id:
            continue
        jid = job_id.group(1)
        meta = _META_RE.search(whole)
        items = [_clean(x) for x in _LI_RE.findall(meta.group(1))] if meta else []
        items = [x for x in items if x]
        published = _PUBLISHED_RE.search(whole)
        posted = _posted(_clean(published.group(1))) if published else None
        url = (BASE + path.split("?")[0]) if path.startswith("/") else \
            f"{BASE}/careers/{agency}/jobs/{jid}"
        jobs.append(Job(
            id=f"neogov:{agency}:{jid}",
            source="neogov",
            company=company["name"],
            company_slug=agency,
            title=_clean(link.group(1)),
            location=items[0] if items else "—",
            url=url,
            posted_at=posted,
            posted_at_source="relative_derived" if posted else None,
            board_key=source_board_key(company, "neogov"),
            employment_hint=" ".join(items[1:3]) or None,
        ))
    return jobs


async def fetch(company: dict, net: Net) -> Fetch:
    agency = company["slug"]
    jobs: dict[str, Job] = {}
    reason: str | None = INCOMPLETE_CAPPED
    previous: tuple[str, ...] = ()
    for page in range(1, _MAX_PAGES + 1):
        fragment = await net.get_text(
            f"{BASE}/careers/home/index",
            params={"agency": agency, "sort": "PostingDate|Descending", "page": str(page)},
            headers={**HEADERS, "Referer": f"{BASE}/careers/{agency}"})
        if fragment.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
            raise NeogovError(f"agency {agency!r} not found (full page returned)")
        found = parse(fragment, company)
        if not found:
            if "jobs-not-found-container" in fragment or page > 1:
                reason = None
                break
            raise NeogovError(f"agency {agency!r}: unrecognized response shape")
        signature = tuple(j.id for j in found)
        if signature == previous:
            reason = INCOMPLETE_STALLED
            break
        previous = signature
        for job in found:
            jobs.setdefault(job.id, job)
        if len(found) < 10:
            reason = None
            break
    return Fetch(list(jobs.values()), complete=reason is None, incomplete_reason=reason)


async def description(job: Job, net: Net) -> str | None:
    from .. import pagetext
    page = await net.get_text(job.url, headers={"User-Agent": HEADERS["User-Agent"]})
    text, _posted_on = pagetext.extract(page)
    return text
