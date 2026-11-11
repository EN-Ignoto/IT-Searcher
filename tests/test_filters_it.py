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
    ("Poinciana, FL", "local"), ("Davenport, Florida", "local"),
    ("Haines City, FL", "local"), ("Hunters Creek, FL", "local"),
    ("Remote - United States", "remote"), ("Remote, FL", "remote"),
    ("Remote, CA", None), ("Remote - Canada", None), ("Remote", None),
])
def test_location_scope(location, expected):
    assert filters_it.location_group(location) == expected


def test_broad_network_role_is_excluded():
    assert not filters_it.is_opportunity("Network Engineer")
    assert filters_it.bucket("Network Engineer", "Orlando, FL") is None
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
                ("Junior Network Engineer", "Lake Mary, FL"),
                ("IT Intern Summer 2027", "Remote - United States"),
                ("IT Technician", "Seattle, WA"),
                ("Senior IT Support Specialist", "Orlando, FL"),
            ])]
    kept, *_ = pipeline._keep_matching([(company, Fetch(jobs), None)], cfg, {})
    assert [j.title for j in kept] == [j.title for j in jobs[:3]]
    assert [j.season for j in kept] == [filters_it.BUCKETS[i] for i in (0, 0, 1)]


def test_scope_migrates_local_record_and_closes_nonlocal_record():
    from intern_engine import config, pipeline

    cfg = config.validate_config({
        "opportunity_scope": "it", "cycles": filters_it.BUCKETS,
        "default_cycle": filters_it.BUCKETS[0],
    })
    records = {loc: {"title": "IT Intern Summer 2027", "location": loc,
                     "company": "Acme", "is_open": True, "season": "Summer 2027",
                     "entry_fit": "eligible", "entry_fit_version": filters_it.FIT_VERSION}
               for loc in ("Orlando, FL", "Seattle, WA")}
    pipeline._close_out_of_scope(records, cfg)
    assert records["Orlando, FL"]["is_open"]
    assert records["Orlando, FL"]["season"] == filters_it.BUCKETS[0]
    assert not records["Seattle, WA"]["is_open"]


@pytest.mark.parametrize('title', [
    'Level 2 NOC Systems Administrator', 'Technical Support Engineer II',
    'Intermediate Technical Support Analyst', 'Cyber Forensic Analyst Journeyman',
    'Cloud - Bare Metal Infrastructure Engineer',
    'Field Service Technician HVAC - Data Center',
    'Network & Wireless Infrastructure Engineer', 'Senior IT Intern',
])
def test_actual_bad_feed_titles_are_rejected(title):
    assert not filters_it.is_opportunity(title)


@pytest.mark.parametrize('text,expected', [
    ('No experience required. Paid internship.', 'eligible'),
    ('Paid internship. Qualifications: 0–2 years of IT support experience.', 'eligible'),
    ('Minimum three years of technical support experience.', 'rejected'),
    ('Requires 5+ years of experience with Linux.', 'rejected'),
    ('<p>3–5 years of related experience</p>', 'rejected'),
    ('This is an unpaid internship.', 'rejected'),
    ('Volunteer IT support opportunity', 'rejected'),
    (None, 'unverified'), ('', 'unverified'),
])
def test_requirements_override_junior_title(text, expected):
    assert filters_it.assess_fit('IT Support Intern', text) == expected


def test_old_unverified_and_rejected_records_cannot_survive_render():
    from intern_engine import config, pipeline
    cfg = config.validate_config({
        'opportunity_scope': 'it', 'cycles': filters_it.BUCKETS,
        'default_cycle': filters_it.BUCKETS[0], 'max_age_days': 0,
    })
    records = {verdict: dict(title='Help Desk Technician', company='Acme',
                            location='Orlando, FL', is_open=True,
                            season=filters_it.BUCKETS[0], entry_fit=verdict,
                            entry_fit_version=filters_it.FIT_VERSION)
               for verdict in ('eligible', 'rejected', None)}
    pipeline._close_out_of_scope(records, cfg)
    assert records['eligible']['is_open']
    assert not records['rejected']['is_open']
    assert not records[None]['is_open']


def test_old_sponsorship_cache_must_not_skip_entry_requirements():
    import asyncio

    from intern_engine import enrich, sponsorship
    from intern_engine.models import Job
    job = Job('greenhouse:acme:9', 'greenhouse', 'Acme', 'acme',
              'Help Desk Technician', 'Orlando, FL', 'https://example.com/9')
    existing = {job.id: dict(sponsorship='unknown', enriched_at='old', skills=[],
                            classifier_v=sponsorship.VERSION)}
    class Net:
        async def get_json(self, url):
            return {'content': '<p>Requires 5 years of IT experience.</p>'}
    asyncio.run(enrich.enrich_jobs([job], existing, Net()))
    assert job.entry_fit == 'rejected'


@pytest.mark.parametrize('title,text,expected', [
    ('Help Desk Technician', 'Requires 2 years of IT experience.', 'rejected'),
    ('Help Desk Technician', '0-2 years of experience. Windows troubleshooting.', 'eligible'),
    ('Diagnostics Technical Support Representative', 'No experience required.', 'rejected'),
    ('IT Intern', 'Learn networking and Windows administration.', 'unverified'),
    ('IT Intern', 'Compensation: $20 per hour. No experience required.', 'eligible'),
])
def test_first_it_job_requirements(title, text, expected):
    assert filters_it.assess_fit(title, text) == expected


def test_focused_collection_requires_exact_known_board_identities():
    from tools.verify_accuracy import valid_collection_scope
    companies = [dict(ats='lever', slug='a'), dict(ats='lever', slug='b')]
    assert valid_collection_scope(['lever:a'], 1, companies)
    assert not valid_collection_scope(['lever:unknown'], 1, companies)
    assert not valid_collection_scope(['lever:a', 'lever:a'], 2, companies)
    assert not valid_collection_scope(['lever:a'], 2, companies)
    assert not valid_collection_scope([], 0, companies)


def test_focused_refresh_does_not_mistake_pagination_caps_for_failure():
    from tools.verify_accuracy import usable_snapshot_rate
    assert usable_snapshot_rate(22, 10, {'result-cap': 10}) == 1
    assert usable_snapshot_rate(22, 10, {'malformed-response': 10}) < 0.70
    assert usable_snapshot_rate(22, 10, {'pagination-stalled': 10}) < 0.70
    assert usable_snapshot_rate(22, 10, {'result-cap': 11}) < 0.70


@pytest.mark.parametrize('text,expected', [
    ('Bachelor or Master Degree in a computer-related field or 1-3 years equivalent work experience required.', 'rejected'),
    ("Bachelor's degree in IT required.", 'rejected'),
    ("Bachelor's degree preferred. No prior experience required.", 'eligible'),
    ("Currently pursuing a bachelor's degree required. Paid internship.", 'eligible'),
])
def test_completed_degree_is_not_the_same_as_current_student(text, expected):
    assert filters_it.assess_fit('IT Support Technician', text) == expected


def test_remote_label_cannot_override_required_california_attendance():
    assert filters_it.assess_fit(
        'Technical Support Specialist',
        'Required Skills: Ability to work on-site in Milpitas, California.',
        'Remote (US), United States') == 'rejected'
    assert filters_it.assess_fit(
        'Technical Support Specialist', 'Troubleshoot PCs and Windows.',
        'Remote (US), United States') == 'eligible'


@pytest.mark.parametrize("description,expected", [
    ("2 years of service desk experience preferred. Troubleshoot Windows PCs.", "eligible"),
    ("Preferred: 2+ years of IT support experience.", "eligible"),
    ("2 years of technical support experience is a plus.", "eligible"),
    ("Minimum 2 years of IT support experience required.", "rejected"),
    ("Must have 2 years of relevant experience.", "rejected"),
    ("3+ years of IT support experience preferred.", "rejected"),
    ("Requires 5+ years of related work experience.", "rejected"),
])
def test_preferences_do_not_become_hard_requirements(description, expected):
    assert filters_it.assess_fit("Help Desk Technician", description) == expected


@pytest.mark.parametrize("description,expected", [
    ("Paid volunteer days and unpaid parental leave are included in benefits.", "eligible"),
    ("This is an unpaid internship.", "rejected"),
    ("Volunteer IT support opportunity", "rejected"),
    ("This position is unpaid.", "rejected"),
])
def test_benefit_words_are_not_unpaid_job_evidence(description, expected):
    assert filters_it.assess_fit("IT Support Intern",
                                 description + " Compensation: $19 per hour.") == expected


@pytest.mark.parametrize("title", [
    "IT Operations Specialist",
    "IT Asset Analyst",
    "IT Asset Coordinator",
    "Computer Support Specialist",
    "Technology Support Technician",
])
def test_first_it_operations_and_asset_jobs_are_eligible_title_scope(title):
    assert filters_it.is_opportunity(title)
    assert filters_it.bucket(title, "Kissimmee, FL") == "Orlando area"
    assert filters_it.assess_fit(title, "Troubleshoot Windows workstations; no experience required.") == "eligible"


@pytest.mark.parametrize("title", [
    "IT Operations Manager",
    "IT Asset Analyst II",
    "Senior Computer Support Specialist",
    "Cloud Infrastructure Engineer",
    "Data Center Project Coordinator",
])
def test_foundation_expansion_does_not_include_senior_or_generic_roles(title):
    assert not filters_it.is_opportunity(title)


@pytest.mark.parametrize("title,description", [
    ("Technical Support Specialist", "2 - 5+ years in Technical Support, Support Engineering, or related role in SaaS required."),
    ("Help Desk Technician", "2–5+ years of help desk experience required."),
    ("IT Support Specialist", "3+ years in IT support required."),
    ("IT Support Technician", "Must have 2+ years of customer support experience."),
])
def test_experienced_jobs_are_not_labeled_first_job_eligible(title, description):
    assert filters_it.assess_fit(title, description) == "rejected"


@pytest.mark.parametrize("title", [
    "Product Management Intern, End User Experience - Winter 2027",
    "Cybersecurity Presales Intern",
    "2027 Summer IT Data Engineering Intern",
    "Cloud ERP Implementation Intern",
    "Technical Support Engineer (SkillBridge: On-the-job training)",
])
def test_non_foundational_internships_and_special_programs_excluded(title):
    assert not filters_it.is_opportunity(title)


@pytest.mark.parametrize("title", [
    "Specialist, Technical Support",
    "Computer Technician I-12 Month",
    "IT Intern, IT Support - Winter 2027",
    "Tier I Help Desk Analyst",
])
def test_credible_first_it_jobs_remain_in_scope(title):
    assert filters_it.is_opportunity(title)


@pytest.mark.parametrize("description", [
    "WHAT WE'RE LOOKING FOR: 2 - 5+ years in Technical Support, Support Engineering, or a related technical role in a SaaS environment. NICE TO HAVE: familiar with Zendesk.",
    "2–5+ years in technical support required. Nice to have: networking fundamentals.",
    "Preferred: 2 to 4 years of customer support experience.",
    "We require 2-6 years of hands-on IT troubleshooting. Benefits include paid volunteer days.",
])
def test_multi_year_range_never_becomes_first_job_preference(description):
    assert filters_it.assess_fit("Technical Support Specialist", description) == "rejected"


def test_two_year_preference_remains_possible_even_with_later_benefit_text():
    description = ("Preferred: 2 years of help desk experience. "
                   "Benefits: paid volunteer days and unpaid leave.")
    assert filters_it.assess_fit("Help Desk Technician", description) == "eligible"


def test_first_job_profile_rejects_required_one_year_but_allows_preference():
    assert filters_it.assess_fit('Help Desk Analyst I',
        'One year of experience as a Helpdesk Technician or technical experience required.') == 'rejected'
    assert filters_it.assess_fit('Computer Technician I',
        'One year of troubleshooting experience preferred. High school diploma required.') == 'eligible'


def test_generic_support_engineer_is_not_assumed_to_be_a_first_it_job():
    assert not filters_it.is_opportunity('Designated Technical Support Engineer - West')
    assert filters_it.is_opportunity('Junior Technical Support Engineer')


def test_osceola_preferred_experience_is_not_a_mandatory_year():
    description = ('High School Diploma or GED required, completion of one (1) course in post secondary '
                   'computer electronics, computer networking, or related computer area. '
                   'One (1) year of experience in computer networking, troubleshooting, or repair of '
                   'computers preferred, ability to teach computer skills to adults and students.')
    assert filters_it.assess_fit('Computer Technician I-12 Month', description) == 'eligible'


@pytest.mark.parametrize('description', [
    'Three to five years of infrastructure engineering, systems administration, cloud engineering, or migration experience required.',
    'Two to four years of IT support experience preferred.',
    '3-5 years of Windows administration, networking, and cloud migration experience.',
])
def test_written_ranges_and_comma_lists_do_not_hide_experience(description):
    assert filters_it.assess_fit('IT Support Technician', description) == 'rejected'


def test_first_job_scope_excludes_specialist_migration_and_advisory_jobs():
    assert not filters_it.is_opportunity('Cloud Migration Engineer I')
    assert not filters_it.is_opportunity('Entry-Level IT Advisory Consultant')
    assert filters_it.is_opportunity('IT Support Intern')
