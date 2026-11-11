"""The personal scope must not reintroduce a competing partial collector."""
from pathlib import Path


def test_one_scheduled_full_registry_collector():
    root = Path(__file__).resolve().parents[1]
    update = (root / '.github/workflows/update.yml').read_text()
    assert 'run: python run.py update' in update
    assert not (root / '.github/workflows/bootstrap-it.yml').exists()
    assert 'fastlane.select' not in update
    assert 'pipeline._load_companies =' not in update


def test_profile_verdict_survives_refresh_and_render():
    from dataclasses import asdict

    from intern_engine import config, filters_it, pipeline, store
    from intern_engine.models import Job
    job = Job('greenhouse:local:1', 'greenhouse', 'Local', 'local',
              'Help Desk Technician', 'Orlando, FL', 'https://example.com/1',
              season='Orlando area', entry_fit='eligible',
              entry_fit_version=filters_it.FIT_VERSION)
    prior = {job.id: {**asdict(job), 'is_open': True, 'entry_fit_version': 5}}
    store.upsert(prior, [asdict(job)], {'greenhouse:local'})
    cfg = config.validate_config(dict(opportunity_scope='it', cycles=filters_it.BUCKETS,
                                    default_cycle='Orlando area', max_age_days=0))
    pipeline._close_out_of_scope(prior, cfg)
    assert prior[job.id]['is_open']
    assert prior[job.id]['entry_fit_version'] == filters_it.FIT_VERSION
