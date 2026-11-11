"""Old cached requirements must not certify today's first-job eligibility."""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from intern_engine import enrich, filters_it, sponsorship
from intern_engine.models import Job


@pytest.mark.parametrize('stamp', [
    'invalid', None, (datetime.now(UTC) - timedelta(days=2)).isoformat(),
])
def test_expired_evidence_is_fetched_and_reclassified(stamp):
    job = Job('greenhouse:acme:1', 'greenhouse', 'Acme', 'acme',
              'Help Desk Technician', 'Orlando, FL', 'https://example.com/1')
    existing = {job.id: dict(enriched_at=stamp, skills=[],
                            classifier_v=sponsorship.VERSION, sponsorship='unknown',
                            entry_fit='eligible', entry_fit_version=filters_it.FIT_VERSION)}

    class Net:
        async def get_json(self, url):
            return {'content': 'Requires 3 years of IT experience.'}

    ids, fetched = asyncio.run(enrich.enrich_jobs([job], existing, Net()))
    assert fetched == 1 and ids == {job.id}
    assert job.entry_fit == 'rejected'


def test_failed_refresh_does_not_claim_expired_evidence_is_current():
    job = Job('greenhouse:acme:1', 'greenhouse', 'Acme', 'acme',
              'Help Desk Technician', 'Orlando, FL', 'https://example.com/1')
    existing = {job.id: dict(enriched_at='2026-01-01T00:00:00Z', skills=[],
                            classifier_v=sponsorship.VERSION, sponsorship='unknown',
                            entry_fit='eligible', entry_fit_version=filters_it.FIT_VERSION)}

    class Net:
        async def get_json(self, url):
            raise RuntimeError('Employer temporarily unavailable')

    ids, _ = asyncio.run(enrich.enrich_jobs([job], existing, Net()))
    assert not ids
    assert job.entry_fit != 'eligible'


def test_it_dashboard_counts_and_labels_are_assigned_honestly():
    from intern_engine.dashboard import _hero
    html = _hero({}, [dict(title='IT Intern', season='Orlando area', location='Orlando, FL')],
                 0, it_scope=True)
    assert 'internships' in html and 'Orlando area' in html
    assert 'confirm your commute' in html
    assert 'with a stated cycle' not in html
