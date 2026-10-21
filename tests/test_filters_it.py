"""IT scope regression cases: routine jobs must survive the internship gate."""
import pytest

from intern_engine import filters_it


@pytest.mark.parametrize('title', [
    'Help Desk Technician', 'Desktop Support Specialist', 'IT Support Intern',
    'Information Technology Internship Summer 2027', 'Junior Network Engineer',
    'Systems Administrator I', 'Entry Level Cloud Support Associate',
    'IT Technician', 'Network Operations Center Intern',
])
def test_accept_it_opportunities(title):
    assert filters_it.is_opportunity(title)


@pytest.mark.parametrize('title', [
    'Senior IT Support Specialist', 'Help Desk Manager', 'Network Engineer III',
    'Security Guard', 'Software Engineer Intern',
    'Mechanical Systems Engineering Intern',
    'Cloud Sales Intern', 'Provider Network Intern',
    'Data Science Intern - Infrastructure (Summer 2027)',
])
def test_reject_unrelated_or_experienced_roles(title):
    assert not filters_it.is_opportunity(title)


@pytest.mark.parametrize("location, expected", [
    ("Orlando, FL", "local"), ("Lake Mary, Florida", "local"),
    ("Sanford, NC", None), ("Miami, FL", None),
    ("Remote - United States", "remote"), ("Remote, FL", "remote"),
    ("Remote, CA", None), ("Remote - Canada", None), ("Remote", None),
])
def test_location_scope(location, expected):
    assert filters_it.location_group(location) == expected


def test_broad_network_role_is_labeled_stretch():
    assert filters_it.is_opportunity("Network Engineer")
    assert filters_it.bucket("Network Engineer", "Orlando, FL") == "Stretch — Orlando area"
    assert filters_it.bucket("Help Desk Technician", "Orlando, FL") == "Orlando area"


def test_pipeline_accepts_regular_local_job_without_internship_cycle():
    from intern_engine import config, pipeline
    from intern_engine.models import Fetch, Job

    cfg = config.validate_config({
        "opportunity_scope": "it", "cycles": filters_it.BUCKETS,
        "default_cycle": filters_it.BUCKETS[0], "max_age_days": 0,
    })
    company = {"name": "Acme", "slug": "acme", "ats": "greenhouse"}
    jobs = [Job(f"greenhouse:acme:{i}", "greenhouse", "Acme", "acme", title,
                location, f"https://example.com/{i}")
            for i, (title, location) in enumerate([
                ("Help Desk Technician", "Orlando, FL"),
                ("Network Engineer", "Lake Mary, FL"),
                ("IT Intern Summer 2027", "Remote - United States"),
                ("IT Technician", "Seattle, WA"),
                ("Senior IT Support Specialist", "Orlando, FL"),
            ])]
    kept, *_ = pipeline._keep_matching([(company, Fetch(jobs), None)], cfg, {})
    assert [j.title for j in kept] == [j.title for j in jobs[:3]]
    assert [j.season for j in kept] == [filters_it.BUCKETS[i] for i in (0, 2, 1)]


def test_scope_migrates_local_record_and_closes_nonlocal_record():
    from intern_engine import config, pipeline

    cfg = config.validate_config({
        "opportunity_scope": "it", "cycles": filters_it.BUCKETS,
        "default_cycle": filters_it.BUCKETS[0],
    })
    records = {loc: {"title": "IT Intern Summer 2027", "location": loc,
                     "company": "Acme", "is_open": True, "season": "Summer 2027"}
               for loc in ("Orlando, FL", "Seattle, WA")}
    pipeline._close_out_of_scope(records, cfg)
    assert records["Orlando, FL"]["is_open"]
    assert records["Orlando, FL"]["season"] == filters_it.BUCKETS[0]
    assert not records["Seattle, WA"]["is_open"]
