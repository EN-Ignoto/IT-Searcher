"""Connectors for the Central Florida sources, against recorded shapes."""

import asyncio

import pytest

from intern_engine import geo, pagetext, registry
from intern_engine.connectors import neogov, nlx, paradox, workday
from intern_engine.models import INCOMPLETE_MALFORMED, Fetch


class ScriptedNet:
    """Answers each request from a function of (method, url, kwargs)."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    async def _do(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.answer(method, url, kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    async def get_json(self, url, **kw):
        return await self._do("GET", url, **kw)

    async def post_json(self, url, **kw):
        return await self._do("POST", url, **kw)

    async def get_text(self, url, **kw):
        return await self._do("TEXT", url, **kw)


def run(coro) -> Fetch:
    return Fetch.of(asyncio.run(coro))


def test_local_registry_is_valid_and_complete():
    boards = registry.load(None if False else __import__(
        "intern_engine.paths", fromlist=["x"]).LOCAL_SOURCES_PATH)
    kinds = {b["ats"] for b in boards}
    assert {"nlx", "neogov", "paradox", "workday"} <= kinds
    assert sum(b["ats"] == "neogov" for b in boards) == 11
    for b in boards:
        if b.get("fallback_place"):
            assert geo.coords(b["fallback_place"]), b["name"]
        if b["ats"] == "workday":
            assert b.get("whole") is True


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(nlx, "_PAUSE_SECONDS", 0)
    monkeypatch.setattr(nlx, "_RATE_LIMIT_WAIT_SECONDS", 0)


# ------------------------------------------------------------------- NLx --
NLX = {"name": "NLx", "slug": "kissimmee-fl", "ats": "nlx", "queries": ['"help desk"']}


def _nlx_doc(guid, title="Help Desk Technician"):
    return {"guid": guid, "title_exact": title, "company_exact": "AdventHealth",
            "location_exact": "Kissimmee, FL", "GeoLocation": "28.30,-81.41",
            "date_new": "2026-11-10T04:12:00Z", "description": "<p>Resets passwords.</p>"}


def test_nlx_pages_until_the_api_says_stop_and_sends_the_origin_header():
    def answer(_m, _url, kw):
        page = int(kw["params"]["page"])
        return {"jobs": [_nlx_doc(f"A{page}{i}") for i in range(15 if page < 3 else 4)],
                "pagination": {"has_more_pages": page < 3}}
    net = ScriptedNet(answer)
    result = run(nlx.fetch(NLX, net))
    assert result.complete and len(result.jobs) == 34
    assert len(net.calls) == 3
    assert net.calls[0][2]["headers"]["x-origin"] == "dejobs.org"
    assert net.calls[0][2]["params"]["location"] == "Kissimmee, FL"
    job = result.jobs[0]
    assert job.latlon == (28.30, -81.41)
    assert job.description and job.posted_at.startswith("2026-11-10")
    assert job.url == "https://dejobs.org/kissimmee-fl/help-desk-technician/A10/job/"
    assert job.company == "AdventHealth"


def test_nlx_unions_queries_by_guid():
    company = {**NLX, "queries": ['"help desk"', '"service desk"']}
    net = ScriptedNet(lambda *_: {"jobs": [_nlx_doc("SAME")],
                                  "pagination": {"has_more_pages": False}})
    assert len(run(nlx.fetch(company, net)).jobs) == 1


def test_nlx_error_payload_is_not_an_empty_area():
    net = ScriptedNet(lambda *_: {"error": "rate limited", "jobs": []})
    with pytest.raises(nlx.NlxError, match="top-level keys"):
        asyncio.run(nlx.fetch(NLX, net))


def test_nlx_error_after_good_pages_leaves_a_partial_snapshot():
    def answer(_m, _u, kw):
        if kw["params"]["page"] == "1":
            return {"jobs": [_nlx_doc("A")], "pagination": {"has_more_pages": True}}
        return {"error": "rate limited"}
    result = run(nlx.fetch(NLX, ScriptedNet(answer)))
    assert len(result.jobs) == 1
    assert not result.complete and result.incomplete_reason == INCOMPLETE_MALFORMED


# ---------------------------------------------------------------- NEOGOV --
def _neogov_item(jid, title, location="Kissimmee, FL", posted="Posted 1 week ago"):
    return f'''
    <li class="list-item" data-job-id="{jid}">
      <h3><a class="item-details-link" href="/careers/osceola/jobs/{jid}/x?pagetype=jobOpportunitiesJobs">{title}</a></h3>
      <ul class="list-meta"><li>{location}</li><li>Full-Time - $21.50 Hourly</li></ul>
      <div class="list-entry">Category: IT</div>
      <span class="list-published">{posted}</span>
    </li>'''


OSCEOLA = {"name": "Osceola County", "slug": "osceola", "ats": "neogov"}


def test_neogov_reads_every_page_of_a_small_agency():
    pages = {
        1: "<ul>" + "".join(_neogov_item(100 + i, f"Clerk {i}") for i in range(10)) + "</ul>",
        2: "<ul>" + _neogov_item(200, "IT Support Technician I &amp; II") + "</ul>",
    }
    net = ScriptedNet(lambda _m, _u, kw: pages[int(kw["params"]["page"])])
    result = run(neogov.fetch(OSCEOLA, net))
    assert result.complete and len(result.jobs) == 11
    assert net.calls[0][2]["headers"]["X-Requested-With"] == "XMLHttpRequest"
    job = result.jobs[-1]
    assert job.title == "IT Support Technician I & II"
    assert job.id == "neogov:osceola:200"
    assert job.url == "https://www.governmentjobs.com/careers/osceola/jobs/200/x"
    assert job.location == "Kissimmee, FL"
    assert job.posted_at_source == "relative_derived"
    assert "Full-Time" in job.employment_hint


def test_neogov_empty_agency_is_a_complete_empty_board():
    net = ScriptedNet(lambda *_: '<div class="jobs-not-found-container">None</div>')
    result = run(neogov.fetch(OSCEOLA, net))
    assert result.complete and result.jobs == []


def test_neogov_unknown_agency_is_an_error_not_an_empty_board():
    net = ScriptedNet(lambda *_: "<!DOCTYPE html><html><body>Careers</body></html>")
    with pytest.raises(neogov.NeogovError):
        asyncio.run(neogov.fetch(OSCEOLA, net))


def test_neogov_relative_dates():
    assert neogov._posted("Posted 3 days ago")
    assert neogov._posted("Posted today")
    assert neogov._posted("Posted more than 30 days ago") is None
    assert neogov._posted("Posted 2 months ago") is None


# --------------------------------------------------------------- Paradox --
SCHOOLS = {"name": "School District of Osceola County", "slug": "osceolaschools",
           "ats": "paradox", "host": "jobs.osceolaschools.net"}


def _paradox_item(i):
    return {"jobId": f"J{i}", "title": f"Technology Support Specialist {i}",
            "originalURL": f"job/J{i}/tech-support",
            "locations": [{"city": "Kissimmee", "stateAbbr": "FL",
                           "latitude": 28.29, "longitude": -81.4}]}


def test_paradox_pages_to_total_job():
    def answer(_m, _u, kw):
        page = int(kw["params"]["page_number"])
        start = (page - 1) * 10
        return {"totalJob": 23,
                "jobs": [_paradox_item(i) for i in range(start, min(start + 10, 23))]}
    net = ScriptedNet(answer)
    result = run(paradox.fetch(SCHOOLS, net))
    assert result.complete and len(result.jobs) == 23 and len(net.calls) == 3
    assert net.calls[0][0] == "POST" and net.calls[0][2]["json"] == {}
    job = result.jobs[0]
    assert job.url == "https://jobs.osceolaschools.net/job/J0/tech-support"
    assert job.location == "Kissimmee, FL" and job.latlon == (28.29, -81.4)


def test_paradox_unknown_shape_is_malformed_not_empty():
    net = ScriptedNet(lambda *_: {"message": "nope"})
    with pytest.raises(paradox.ParadoxError, match="message"):
        asyncio.run(paradox.fetch(SCHOOLS, net))


# ------------------------------------------------------- Workday (whole) --
def test_workday_whole_board_uses_an_empty_search_and_reads_to_the_end():
    company = {"name": "UCF", "slug": "ucf", "ats": "workday", "wd": "wd1",
               "site": "careers", "whole": True}

    def answer(_m, _u, kw):
        offset = kw["json"]["offset"]
        n = 20 if offset < 60 else 19
        return {"total": 79, "jobPostings": [
            {"title": f"Job {offset + i}", "externalPath": f"/job/Orlando/J_{offset + i}",
             "locationsText": "Orlando, FL", "postedOn": "Posted Today"} for i in range(n)]}
    net = ScriptedNet(answer)
    result = run(workday.fetch(company, net))
    assert result.complete and len(result.jobs) == 79
    assert {c[2]["json"]["searchText"] for c in net.calls} == {""}


# -------------------------------------------------------------- pagetext --
def test_pagetext_prefers_json_ld():
    page = ('<html><head><script type="application/ld+json">{"@type":"JobPosting",'
            '"datePosted":"2026-11-01","description":"' + "Supports end users. " * 20 +
            '"}</script></head><body><nav>Menu</nav></body></html>')
    text, posted = pagetext.extract(page)
    assert posted == "2026-11-01" and "Supports end users" in text and "Menu" not in text


def test_pagetext_falls_back_to_the_body_without_scripts():
    page = "<html><body><script>var x=1</script><div>" + "Resets passwords. " * 50 + \
           "</div></body></html>"
    text, posted = pagetext.extract(page)
    assert posted is None and "Resets passwords" in text and "var x" not in text


def test_nlx_rate_limit_keeps_partial_results_and_closes_nothing(monkeypatch):
    import httpx
    monkeypatch.setattr(nlx, "_PAUSE_SECONDS", 0)
    request = httpx.Request("GET", nlx.API)
    limited = httpx.HTTPStatusError("429", request=request,
                                    response=httpx.Response(429, request=request))

    def answer(_m, _u, kw):
        if kw["params"]["page"] == "1":
            return {"jobs": [_nlx_doc("A")], "pagination": {"has_more_pages": True}}
        return limited
    result = run(nlx.fetch(NLX, ScriptedNet(answer)))
    assert len(result.jobs) == 1 and not result.complete
    assert result.incomplete_reason == nlx.INCOMPLETE_RATE_LIMITED
    with pytest.raises(nlx.NlxError, match="rate limited"):
        asyncio.run(nlx.fetch(NLX, ScriptedNet(lambda *_: limited)))
