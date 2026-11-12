"""PeopleAdmin — the applicant system many colleges use (Valencia College).

Every PeopleAdmin site publishes its open postings as one public Atom feed,
the same one behind the "All Jobs Atom Feed" link on the college's job search
page:

    GET https://{host}/postings/all_jobs.atom

One request returns the whole board, so the snapshot is complete. Each entry
has a title, a link to the posting, a publish date and an HTML summary.

Valencia has campuses on both sides of the 30-mile line (Osceola Campus is in
Kissimmee itself), so the campus named in the entry decides the location.
"""

from __future__ import annotations

import html as _html
import re
from xml.etree import ElementTree

from ..models import Fetch, Job, source_board_key
from ..net import Net

_ATOM = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")

# Campus name as written in a posting -> a place `geo` can measure.
CAMPUSES = (
    (re.compile(r"\bosceola\b", re.I), "Kissimmee, FL (Osceola Campus)"),
    (re.compile(r"\bpoinciana\b", re.I), "Poinciana, FL (Poinciana Campus)"),
    (re.compile(r"\blake\s+nona\b", re.I), "Lake Nona, FL (Lake Nona Campus)"),
    (re.compile(r"\bwinter\s+park\b", re.I), "Winter Park, FL (Winter Park Campus)"),
    (re.compile(r"\bdowntown\b", re.I), "Orlando, FL (Downtown Campus)"),
    (re.compile(r"\bwest\s+campus\b", re.I), "Orlando, FL (West Campus)"),
    (re.compile(r"\beast\s+campus\b", re.I), "Orlando, FL (East Campus)"),
    (re.compile(r"\bschool\s+of\s+public\s+safety\b", re.I),
     "Orlando, FL (School of Public Safety)"),
    (re.compile(r"\bdistrict\s+office\b", re.I), "Orlando, FL (District Office)"),
)


class PeopleAdminError(RuntimeError):
    pass


def _campus(text: str) -> str | None:
    for pattern, place in CAMPUSES:
        if pattern.search(text):
            return place
    return None


def parse(feed: str, company: dict) -> list[Job]:
    try:
        root = ElementTree.fromstring(feed.encode("utf-8"))
    except ElementTree.ParseError as exc:
        raise PeopleAdminError(f"feed is not XML: {exc}; starts {feed[:80]!r}") from exc
    if root.tag != f"{_ATOM}feed":
        raise PeopleAdminError(f"not an Atom feed: root is {root.tag}")
    slug = company["slug"]
    jobs: list[Job] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = (entry.findtext(f"{_ATOM}title") or "").strip()
        url = ""
        for link in entry.findall(f"{_ATOM}link"):
            if link.get("rel") in (None, "alternate") and link.get("href"):
                url = link.get("href")
                break
        match = re.search(r"/postings/(\d+)", url) or re.search(
            r"(\d+)\s*$", entry.findtext(f"{_ATOM}id") or "")
        if not title or not url or not match:
            continue
        body = entry.findtext(f"{_ATOM}content") or entry.findtext(f"{_ATOM}summary") or ""
        plain = _html.unescape(_TAG_RE.sub(" ", _html.unescape(body)))
        posted = entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")
        if posted and not re.match(r"\d{4}-\d{2}-\d{2}", posted):
            posted = None
        jobs.append(Job(
            id=f"peopleadmin:{slug}:{match.group(1)}",
            source="peopleadmin",
            company=company["name"],
            company_slug=slug,
            title=title,
            location=_campus(plain) or _campus(title) or "—",
            url=url,
            posted_at=posted,
            # A two-line summary is not the posting; let the pipeline read the page.
            description=_html.unescape(body) if len(plain) > 800 else None,
            board_key=source_board_key(company, "peopleadmin"),
        ))
    return jobs


async def fetch(company: dict, net: Net) -> Fetch:
    feed = await net.get_text(
        f"https://{company['host']}/postings/all_jobs.atom",
        headers={"Accept": "application/atom+xml, application/xml;q=0.9"})
    return Fetch.board(parse(feed, company), payload_ok=True)


async def description(job: Job, net: Net) -> str | None:
    from .. import pagetext
    page = await net.get_text(job.url)
    text, _posted = pagetext.extract(page)
    if job.location == "—" and text:
        plain = _html.unescape(_TAG_RE.sub(" ", text))
        job.location = _campus(plain) or job.location
    return text
