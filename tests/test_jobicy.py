"""US remote IT feed is normalized safely and never closes old rolling-window jobs."""
import asyncio

from intern_engine.connectors import jobicy
from intern_engine.models import INCOMPLETE_CAPPED, INCOMPLETE_MALFORMED


COMPANY = {"ats": "jobicy", "slug": "us-remote-it", "name": "Jobicy US Remote IT Jobs"}


class FakeNet:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    async def get_json(self, url, **kwargs):
        self.urls.append(url)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_remote_support_feed_is_normalized_and_never_complete():
    data = {"success": True, "jobs": [{
        "id": 101, "jobTitle": "Help Desk Technician",
        "companyName": "Example Employer", "jobGeo": "USA",
        "jobLevel": "Entry-level", "jobType": ["Part-Time"],
        "jobDescription": "Windows and laptop troubleshooting. Paid role.",
        "url": "https://jobicy.com/jobs/help-desk-technician",
        "pubDate": "2026-11-06T12:00:00+00:00",
    }, {
        "id": 102, "jobTitle": "Help Desk Manager",
        "companyName": "Example Employer", "jobGeo": "USA",
        "jobLevel": "Senior", "url": "https://jobicy.com/jobs/manager",
    }, {
        "id": 103, "jobTitle": "IT Support Specialist",
        "companyName": "Example Employer", "jobGeo": "Canada",
        "url": "https://jobicy.com/jobs/canadian-role",
    }]}
    net = FakeNet(data)
    fetched = asyncio.run(jobicy.fetch(COMPANY, net))
    assert not fetched.complete
    assert fetched.incomplete_reason == INCOMPLETE_CAPPED
    assert len(fetched.jobs) == 1
    role = fetched.jobs[0]
    assert role.title == "Help Desk Technician"
    assert role.company == "Example Employer"
    assert role.location.startswith("Remote - United States")
    assert role.description.startswith("Windows and laptop")
    assert role.posted_at == "2026-11-06T12:00:00+00:00"
    assert all("geo=usa" in url for url in net.urls)


def test_malformed_source_does_not_become_complete_empty_board():
    net = FakeNet({"error": "blocked", "jobs": []})
    fetched = asyncio.run(jobicy.fetch(COMPANY, net))
    assert fetched.jobs == []
    assert not fetched.complete
    assert fetched.incomplete_reason == INCOMPLETE_MALFORMED


def test_empty_search_is_not_evidence_that_old_jobs_closed():
    net = FakeNet({"success": True, "jobs": []})
    fetched = asyncio.run(jobicy.fetch(COMPANY, net))
    assert fetched.jobs == []
    assert not fetched.complete
    assert fetched.incomplete_reason == INCOMPLETE_CAPPED


def test_failed_all_queries_stays_incomplete():
    net = FakeNet(RuntimeError("temporary outage"))
    fetched = asyncio.run(jobicy.fetch(COMPANY, net))
    assert fetched.incomplete_reason == INCOMPLETE_MALFORMED
    assert not fetched.complete
