"""The profile rules: which titles are entry IT, and what a posting requires."""

import pytest

from intern_engine import filters_it as f

LONG = (" The technician answers tickets, resets passwords, images laptops, supports "
        "Windows 11 and Office 365 for end users, and troubleshoots printers and the VPN.")


@pytest.mark.parametrize("title", [
    "Help Desk Technician", "IT Support Specialist I", "Service Desk Analyst",
    "Desktop Support Technician", "Network Technician", "Junior Systems Administrator",
    "SOC Analyst", "IT Intern", "Information Technology Internship - Summer 2099",
    "Computer Technician", "Technology Support Specialist", "NOC Technician I",
    "Cybersecurity Intern", "Data Center Technician", "IT Technician I/II/III",
    "Geek Squad Agent",
])
def test_entry_it_titles_are_kept(title):
    assert f.title_verdict(title)[0] == "keep", title


@pytest.mark.parametrize("title,reason", [
    ("Senior Help Desk Technician", "senior-title"),
    ("IT Support Manager", "senior-title"),
    ("Desktop Support Technician III", "senior-title"),
    ("Network Engineer Lead", "senior-title"),
    ("Registered Nurse", "not-it-role"),
    ("Software Engineer Intern", "not-it-role"),
    ("Sales Associate", "not-it-role"),
    ("Security Officer", "not-it-role"),
    ("Maintenance Technician", "not-it-role"),
    ("IT Project Manager", "not-it-role"),
    ("IT Intern - Summer 2020", "past-term"),
    ("", "no-title"),
    # From the first live run: kept, and should not have been.
    ("Bi-lingual Pharmacy Tech Support/Call Center", "not-it-role"),
    ("Linux Systems Administrator 2/3 - Top Secret", "active-clearance-required"),
    ("Building Automation Systems Specialist", "not-it-role"),
])
def test_other_titles_are_rejected_with_a_reason(title, reason):
    assert f.title_verdict(title) == ("reject", reason)


def test_ambiguous_support_titles_need_confirmation_from_the_text():
    assert f.title_verdict("Support Technician")[0] == "weak"
    plain = "We fix lawn mowers and small engines for customers across the county. " * 3
    assert f.assess("Support Technician", plain, weak_title=True)["reason"] == "not-it-role"
    assert f.assess("Support Technician", "Entry level." + LONG,
                    weak_title=True)["verdict"] == "keep"


def test_title_levels():
    assert f.title_level("Technician I") == 1
    assert f.title_level("Technician II") == 2
    assert f.title_level("Technician I/II/III") == 1
    assert f.title_level("Senior Technician") == 3


class TestExperience:
    def test_required_years_reject(self):
        r = f.assess("Help Desk Technician",
                     "Requirements:\n3 years of help desk experience required." + LONG)
        assert r["verdict"] == "reject" and r["reason"] == "requires-3-years-experience"

    def test_preferred_years_do_not_reject(self):
        r = f.assess("Help Desk Technician",
                     "Preferred Qualifications:\n3 years of help desk experience." + LONG)
        assert r["verdict"] == "keep" and r["fit"] == f.FIT_BEGINNER
        assert "preferred" in r["experience"]

    def test_inline_preferred_beats_a_required_section(self):
        r = f.assess("Help Desk Technician",
                     "Requirements:\n2 years of IT support experience preferred." + LONG)
        assert r["verdict"] == "keep" and r["fit"] == f.FIT_BEGINNER

    def test_two_years_required_rejects_unless_substitutable(self):
        hard = f.assess("IT Technician",
                        "Minimum 2 years of desktop support experience required." + LONG)
        soft = f.assess("IT Technician",
                        "2 years of desktop support experience or equivalent "
                        "education and certifications." + LONG)
        assert hard["verdict"] == "reject"
        assert soft["verdict"] == "keep" and soft["fit"] == f.FIT_STRETCH

    def test_one_year_is_a_stretch(self):
        r = f.assess("IT Technician", "1 year of IT support experience required." + LONG)
        assert r["verdict"] == "keep" and r["fit"] == f.FIT_STRETCH

    def test_months_are_converted(self):
        r = f.assess("IT Technician",
                     "Six months of IT support experience required." + LONG)
        assert r["verdict"] == "keep" and "6 months" in r["experience"]

    def test_customer_service_years_are_a_note_not_a_barrier(self):
        r = f.assess("Help Desk Technician",
                     "Must have 3 years of customer service experience." + LONG)
        assert r["verdict"] == "keep"
        assert any("customer-service" in n for n in r["notes"])

    def test_company_history_is_not_an_experience_requirement(self):
        r = f.assess("Help Desk Technician",
                     "We have been serving Central Florida for over 25 years of experience."
                     + LONG)
        assert r["verdict"] == "keep" and r["fit"] == f.FIT_BEGINNER

    def test_explicit_entry_level(self):
        r = f.assess("Help Desk Technician", "No experience required; we will train." + LONG)
        assert r["experience"].startswith("Entry-level")


class TestOtherGates:
    def test_unpaid_internship_is_rejected(self):
        r = f.assess("IT Intern", "This is an unpaid internship for academic credit." + LONG)
        assert r["reason"] == "unpaid"

    def test_active_clearance_rejects_but_obtainable_is_a_note(self):
        have = f.assess("IT Technician", "Must have an active Secret clearance." + LONG)
        get = f.assess("IT Technician",
                       "Must have the ability to obtain a Secret clearance." + LONG)
        assert have["reason"] == "active-clearance-required"
        assert get["verdict"] == "keep" and "Clearance must be obtainable" in get["notes"]

    def test_required_bachelors_rejects_for_jobs_not_internships(self):
        text = "Bachelor's degree in Computer Science required." + LONG
        assert f.assess("IT Technician", text)["reason"] == "bachelors-degree-required"
        assert f.assess("IT Intern", text)["verdict"] == "keep"

    def test_degree_or_equivalent_is_fine(self):
        r = f.assess("IT Technician",
                     "Bachelor's degree or equivalent experience required." + LONG)
        assert r["verdict"] == "keep"

    def test_missing_text_is_unverified_for_entry_titles_only(self):
        assert f.assess("Help Desk Technician", None)["fit"] == f.FIT_UNVERIFIED
        assert f.assess("Help Desk Technician II", None)["reason"] == "level-2-unverifiable"
        assert f.assess("Support Technician", None,
                        weak_title=True)["reason"] == "unconfirmed-it-role"

    def test_employment_type(self):
        assert f.assess("IT Intern", "x" * 200)["employment"] == "Internship"
        assert f.assess("Help Desk Technician (Part-Time)", "x" * 200)["employment"] == "Part-time"
        assert f.employment_type("Help Desk", "", "Full-Time Regular") == "Full-time"

    def test_structure_survives_html(self):
        html = ("<h3>Minimum Qualifications</h3><ul><li>High school diploma</li></ul>"
                "<h3>Preferred Qualifications</h3><ul><li>5 years of help desk "
                "experience</li></ul><p>" + LONG + "</p>")
        assert f.assess("Help Desk Technician", html)["verdict"] == "keep"


class TestPlace:
    def test_sections_by_distance(self):
        assert f.place("Kissimmee, FL")[0] == f.LOCAL
        assert f.place("Orlando, FL")[0] == f.LOCAL
        assert f.place("Lakeland, FL")[0] == f.NEARBY
        assert f.place("Tampa, FL")[0] is None
        assert f.place("Miami, FL")[0] is None

    def test_exact_coordinates_win(self):
        section, miles, _, _ = f.place("Somewhere unlisted", latlon=(28.30, -81.41))
        assert section == f.LOCAL and miles < 2

    def test_remote_must_be_open_to_florida(self):
        assert f.place("Remote, United States")[0] == f.REMOTE
        assert f.place("Remote - Florida")[0] == f.REMOTE
        assert f.place("Remote - Texas")[0] is None
        assert f.place("Remote, Canada")[0] is None

    def test_residency_list_without_florida_blocks_remote(self):
        text = "Must reside in one of the following states: Texas, Ohio, Georgia."
        assert f.place("Remote, United States", "", text)[0] is None
        ok = "Must reside in one of the following states: Texas, Florida, Georgia."
        assert f.place("Remote, United States", "", ok)[0] == f.REMOTE

    def test_local_beats_remote(self):
        section, _, remote, _ = f.place("Orlando, FL (Remote)")
        assert section == f.LOCAL and remote
