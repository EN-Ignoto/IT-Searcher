"""Local postings come from official live pages, not hand-seeded vacancies."""
# ruff: noqa: I001 -- exercise local source fixtures alongside existing imports

import asyncio
import json
from datetime import UTC, datetime, timedelta

from intern_engine import filters_it, models, registry
from intern_engine.connectors import localboards


_VALENCIA = """
<div class='job-item job-item-posting'><h3>
<a href="/postings/44244">Specialist, Technical Support</a></h3></div>
<div class='job-item job-item-posting'><h3>
<a href="/postings/99999">Senior IT Support Manager</a></h3></div>
"""
_VALENCIA_DETAIL = """
<table>
<tr><th>Location(s)</th><td>Orlando, FL 32825 - East Campus</td></tr>
<tr><th>Posting Start Date</th><td>11/05/2026</td></tr>
<tr><th>Posting End Date</th><td>12/31/2099</td></tr>
<tr><th>Salary Range</th><td>19.93 per hour</td></tr>
<tr><th>Description of Job Function</th><td>Help faculty troubleshoot
PCs, laptops and printers, plus network connectivity.</td></tr>
<tr><th>Required Minimum Education</th><td>High school diploma.</td></tr>
</table>
"""
_PATH = "/support-staff-computer-technician-i-12-month/job/993441CCDCCE775901861F2193A33B71"
_SCHOOL = f"""
<div class="c-jobs-list">
<a href="{_PATH}">Support Staff-Computer Technician I-12 Month</a>
<a href="/english-teacher/job/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">English Teacher</a>
</div>
"""
_FUTURE = (datetime.now(UTC) + timedelta(days=180)).date().isoformat()
_SCHOOL_DETAIL = "<script type=\"application/ld+json\">" + json.dumps({
    "@type": "JobPosting", "title": "Support Staff-Computer Technician I-12 Month",
    "description": ("The job is responsible for computer networks and equipment. "
                    "One (1) year troubleshooting experience preferred."),
    "datePosted": "2026-10-29",
    "validThrough": _FUTURE,
    "jobLocation": {"address": {"addressLocality": "Kissimmee", "addressRegion": "FL"}},
}) + "</script>"


class MockNet:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get_text(self, url, **_kwargs):
        self.calls.append(url)
        if url not in self.responses:
            raise OSError("not found")
        return self.responses[url]


def test_valencia_real_html_structure_and_fit():
    assert localboards.valencia_links(_VALENCIA) == {"44244": "Specialist, Technical Support"}
    job = localboards.valencia_job("44244", "Specialist, Technical Support", _VALENCIA_DETAIL)
    assert job is not None
    assert job.url == "https://valenciacollege.peopleadmin.com/postings/44244"
    assert job.location.startswith("Orlando, FL")
    assert job.posted_at == "2026-11-05"
    assert job.salary == "$19.93 per hour"
    assert filters_it.assess_fit(job.title, job.description, job.location) == "eligible"


def test_valencia_closed_and_malformed_postings_not_invented():
    old = _VALENCIA_DETAIL.replace("12/31/2099", "09/19/2026")
    assert localboards.valencia_job("44244", "Specialist, Technical Support", old) is None
    assert localboards.valencia_job("44244", "Specialist, Technical Support", "<html></html>") is None


def test_valencia_live_fetch_is_never_complete_for_closure():
    urls = {
        "https://valenciacollege.peopleadmin.com/postings/search": _VALENCIA,
        "https://valenciacollege.peopleadmin.com/postings/44244": _VALENCIA_DETAIL,
    }
    result = asyncio.run(localboards.fetch({"slug": "valencia"}, MockNet(urls)))
    assert len(result.jobs) == 1
    assert not result.complete
    assert result.incomplete_reason == models.INCOMPLETE_CAPPED


def test_school_jsonld_real_job_parsing():
    assert localboards.osceola_links(_SCHOOL) == {
        _PATH: "Support Staff-Computer Technician I-12 Month"
    }
    job = localboards.osceola_job(_PATH, _SCHOOL_DETAIL)
    assert job is not None
    assert job.company == "School District of Osceola County"
    assert job.location == "Kissimmee, FL"
    assert job.posted_at == "2026-10-29"
    assert job.url.endswith(_PATH)
    assert filters_it.assess_fit(job.title, job.description, job.location) == "eligible"


def test_osceola_expiry_prevents_stale_local_listings():
    old = _SCHOOL_DETAIL.replace(_FUTURE, "2025-01-01")
    assert localboards.osceola_job(_PATH, old) is None


def test_school_page_collection_does_not_close_on_incomplete_pagination():
    urls = {
        "https://jobs.osceolaschools.net/jobs": _SCHOOL,
        "https://jobs.osceolaschools.net/jobs/page/2": _SCHOOL,
        "https://jobs.osceolaschools.net" + _PATH: _SCHOOL_DETAIL,
    }
    result = asyncio.run(localboards.fetch({"slug": "osceola-schools"}, MockNet(urls)))
    assert len(result.jobs) == 1
    assert not result.complete
    assert result.incomplete_reason == models.INCOMPLETE_CAPPED


def test_failed_boards_do_not_close_prior_live_postings():
    result = asyncio.run(localboards.fetch({"slug": "valencia"}, MockNet({})))
    assert result.jobs == []
    assert not result.complete
    assert result.incomplete_reason == models.INCOMPLETE_MALFORMED


def test_full_registry_includes_registered_local_sources():
    companies = registry.load()
    local = [x for x in companies if x["ats"] == "localboards"]
    assert {x["slug"] for x in local} >= {"valencia", "osceola-schools"}
