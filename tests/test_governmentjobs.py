"""Realistic public municipal search and full posting evidence."""
import asyncio
from datetime import UTC, datetime

from intern_engine import fastlane, filters_it, models, registry
from intern_engine.connectors import governmentjobs


_PATH = "/jobs/152968-1/it-specialist"
_CITY_SEARCH = """
<html><h2>Search Results (12)</h2><div class="job-item-container">
<h3><a aria-label="IT Specialist Link will be opened in a new window."
class="job-details-link" href="/jobs/152968-1/it-specialist">IT Specialist</a></h3>
</div><div class="job-item-container">
<h3><a class="job-details-link" href="/jobs/111111-1/police-officer">Police Officer</a></h3>
</div></html>
"""
_CITY_DETAIL = """
<script type="application/ld+json">
{"@type":"JobPosting","title":"IT Specialist",
"description":"Troubleshoot all computers and peripherals. Requires an Associate's Degree in computer technology supplemented by two (2) years of network operations and support experience. Prefer CompTIA Network+.",
"datePosted":"2026-10-30","validThrough":"2099-11-13",
"hiringOrganization":{"@type":"Organization","name":"City of Kissimmee"},
"jobLocation":{"@type":"Place","address":{"addressLocality":"Kissimmee","addressRegion":"FL"}}}
</script>
"""


class FakeNet:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get_text(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.responses:
            raise OSError("not in fixture")
        return self.responses[url]


def test_city_search_anchors_and_real_date_location():
    assert governmentjobs.city_links(_CITY_SEARCH) == {_PATH: "IT Specialist"}
    job = governmentjobs.city_job(_PATH, _CITY_DETAIL)
    assert job is not None
    assert job.title == "IT Specialist"
    assert job.location == "Kissimmee, FL"
    assert job.posted_at == "2026-10-30"
    assert job.url == "https://www.governmentjobs.com" + _PATH
    assert job.company == "City of Kissimmee"
    # Do NOT label an employer's mandatory two-year requirement entry-level.
    assert filters_it.assess_fit(job.title, job.description, job.location) == "rejected"


def test_city_skips_expired_and_other_employers():
    assert governmentjobs.city_job(_PATH, _CITY_DETAIL.replace("2099-11-13", "2025-01-01")) is None
    assert governmentjobs.city_job(_PATH, _CITY_DETAIL.replace("City of Kissimmee", "Another Employer")) is None
    assert governmentjobs.city_job(_PATH, "<html></html>") is None


def test_city_fetch_is_partial_and_requires_readable_employer_evidence():
    prefix = governmentjobs._CITY_URL
    responses = {
        prefix + "1": _CITY_SEARCH,
        prefix + "2": _CITY_SEARCH,
        "https://www.governmentjobs.com" + _PATH: _CITY_DETAIL,
    }
    result = asyncio.run(governmentjobs.fetch({}, FakeNet(responses)))
    assert len(result.jobs) == 1
    assert not result.complete
    assert result.incomplete_reason == models.INCOMPLETE_CAPPED
    assert result.jobs[0].posted_at == "2026-10-30"


def test_nonresponsive_government_board_never_closes_old_jobs():
    result = asyncio.run(governmentjobs.fetch({}, FakeNet({})))
    assert result.jobs == []
    assert not result.complete
    assert result.incomplete_reason == models.INCOMPLETE_MALFORMED


def test_priority_scan_contains_city_of_kissimmee_source():
    entries = fastlane.select(registry.load())
    assert any(e.get("ats") == "governmentjobs" and e.get("slug") == "kissimmee-city" for e in entries)


def test_written_number_and_numeric_years_are_equivalent():
    for phrase in ("two (2) years", "two years", "2 years"):
        desc = "Associate's Degree supplemented by " + phrase + " of network operations and support experience."
        assert filters_it.assess_fit("IT Specialist", desc, "Kissimmee, FL") == "rejected"
    assert datetime.now(UTC).year >= 2026
