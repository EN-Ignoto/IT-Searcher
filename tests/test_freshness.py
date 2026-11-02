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


def test_update_closes_old_dates_preserved_by_merge(monkeypatch):
    """Fresh feed dates must not reopen expired authoritative stored dates."""
    from intern_engine import health, observe, quality, registry, store

    cfg = config.validate_config({'opportunity_scope': 'it', 'cycles': filters_it.BUCKETS,
                                  'default_cycle': filters_it.BUCKETS[0], 'max_age_days': 14})
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    recent = datetime.now(UTC).isoformat()
    jid = 'greenhouse:acme:1'
    existing = {jid: dict(id=jid, source='greenhouse', company='Acme', company_slug='acme',
                         title='Help Desk Technician', location='Orlando, FL',
                         url='https://example.com/1', season=filters_it.BUCKETS[0],
                         posted_at=old, posted_at_source='exact', first_seen_at=old,
                         last_seen_at=old, is_open=True)}
    job = Job(jid, 'greenhouse', 'Acme', 'acme', 'Help Desk Technician',
              'Orlando, FL', 'https://example.com/1', posted_at=recent,
              season=filters_it.BUCKETS[0], posted_at_source='exact')
    monkeypatch.setattr(config, 'load_config', lambda: cfg)
    monkeypatch.setattr(quality, 'load_blocklist', lambda: {})
    monkeypatch.setattr(pipeline, '_load_companies', lambda: [])
    monkeypatch.setattr(store, 'load', lambda *_: existing)
    monkeypatch.setattr(store, 'save', lambda *_: None)
    monkeypatch.setattr(registry, 'migrate_store_board_keys', lambda *_: None)
    monkeypatch.setattr(health, 'load', lambda: {})
    monkeypatch.setattr(health, 'save', lambda *_: None)
    monkeypatch.setattr(health, 'migrate_legacy_keys', lambda *_: None)
    monkeypatch.setattr(health, 'partition', lambda *_: ([], []))
    monkeypatch.setattr(observe, 'record_run', lambda *_: None)
    monkeypatch.setattr(pipeline, '_append_rejected_titles', lambda *_: None)
    monkeypatch.setattr(pipeline, '_append_history', lambda *_: None)
    monkeypatch.setattr(pipeline, 'write_stats', lambda *_: None)
    monkeypatch.setattr(pipeline, '_build_stats', lambda *args: {'new_this_run': len(args[8])})

    async def fetched(*_):
        # Simulate the accepted, enriched feed row just before the store merge.
        pipeline_kept = [job]
        # _enrich_stage owns the kept closure; exercise it with mocked enrichment.
        company = {'name': 'Acme', 'slug': 'acme', 'ats': 'greenhouse'}
        return [(company, Fetch(pipeline_kept), None)], await _[1](
            [(company, Fetch(pipeline_kept), None)], None, None)

    async def no_enrichment(*_):
        return set(), 0

    monkeypatch.setattr(pipeline.enrich, 'enrich_jobs', no_enrichment)
    monkeypatch.setattr(pipeline, '_fetch_all', fetched)
    _, merged, announced = pipeline.run_update()
    assert merged[jid]['posted_at'] == old
    assert not merged[jid]['is_open']
    assert announced == []


@pytest.mark.parametrize('title', [
    'Vice President, Technology Service Desk/On-Site Support',
    'Landscape Technician - Infrastructure Management',
    'Scheduler / Planner - Data Center Construction',
])
def test_non_entry_and_non_it_false_positives_are_excluded(title):
    assert not filters_it.is_opportunity(title)


@pytest.mark.parametrize('location', [
    'Remote (California, US)', 'US AL Remote', 'US Remote - NY',
    'United States - NC Remote', 'USA - TX (Remote)',
])
def test_state_restricted_remote_roles_are_not_claimed_as_florida(location):
    assert filters_it.location_group(location) is None
