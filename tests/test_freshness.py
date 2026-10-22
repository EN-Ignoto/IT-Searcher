from datetime import UTC, datetime, timedelta

import pytest

from intern_engine import config, filters_it, freshness, pipeline
from intern_engine.models import Fetch, Job

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


@pytest.mark.parametrize('posted, seen, expected', [
    ('2026-10-21', '2026-10-01', False),
    ('2026-10-08', '2026-10-22', False),
    ('2026-10-07', '2026-10-22', True),
    (None, '2026-10-07', True),
    (None, '2026-10-21', False),
    ('invalid', '2026-10-07', True),
    (None, None, False),
])
def test_expiry_uses_publish_date_then_discovery(posted, seen, expected):
    assert freshness.expired(posted, seen, 14, now=NOW) == expected


def test_zero_disables_expiry():
    assert not freshness.expired('2020-01-01', None, 0, now=NOW)


def test_old_internships_and_undated_discoveries_leave_active_feed():
    cfg = config.validate_config({'opportunity_scope': 'it', 'cycles': filters_it.BUCKETS,
                                  'default_cycle': filters_it.BUCKETS[0], 'max_age_days': 14})
    old = (datetime.now(UTC) - timedelta(days=15)).isoformat()
    new = datetime.now(UTC).isoformat()
    records = {
        'intern': dict(title='IT Intern Summer 2027', posted_at=old, first_seen_at=new),
        'undated': dict(title='Help Desk Technician', posted_at=None, first_seen_at=old),
        'recent': dict(title='IT Intern Summer 2027', posted_at=new, first_seen_at=old),
    }
    for row in records.values():
        row.update(company='Acme', location='Orlando, FL', is_open=True,
                   season=filters_it.BUCKETS[0])
    pipeline._close_out_of_scope(records, cfg)
    assert not records['intern']['is_open']
    assert not records['undated']['is_open']
    assert records['recent']['is_open']
    company = {'name': 'Acme', 'slug': 'acme', 'ats': 'greenhouse'}
    job = Job('greenhouse:acme:1', 'greenhouse', 'Acme', 'acme', 'IT Intern Summer 2027',
              'Orlando, FL', 'https://example.com/1', posted_at=old)
    kept, *_ = pipeline._keep_matching([(company, Fetch([job]), None)], cfg, {})
    assert kept == []
