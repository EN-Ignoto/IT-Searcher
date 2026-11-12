"""End to end: fake boards in, store and published pages out."""

import json

import pytest

from intern_engine import (
    dashboard,
    filters_it,
    paths,
    pipeline,
    publish,
    readme,
    registry,
    store,
)
from intern_engine.models import Job

BODY = (" Answers tickets, resets passwords, images laptops, supports Windows 11 and "
        "Office 365 for end users and troubleshoots printers and the VPN. ")

NLX = {"name": "NLx", "slug": "kissimmee-fl", "ats": "nlx"}
CITY = {"name": "City of Kissimmee", "slug": "kissimmeefl", "ats": "neogov",
        "fallback_place": "Kissimmee, FL"}
ACME = {"name": "Acme", "slug": "acme", "ats": "greenhouse"}


def job(board, jid, title, location, description=None, **kw):
    return Job(id=f"{board['ats']}:{board['slug']}:{jid}", source=board["ats"],
               company=kw.pop("company", board["name"]), company_slug=board["slug"],
               title=title, location=location, url=f"https://example.com/{jid}",
               description=description, **kw)


@pytest.fixture
def world(monkeypatch, tmp_path):
    """A controllable set of boards; `boards[key]` is what each returns."""
    monkeypatch.setattr(paths, "STATS_PATH", str(tmp_path / "stats.json"))
    boards = {"local": [NLX, CITY], "registry": [ACME], "answers": {}, "details": {},
              "detail_calls": []}

    def load_boards(scope):
        local = boards["local"]
        chosen = local + (boards["registry"] if scope == "full" else [])
        return chosen, {registry.board_key(c) for c in local}

    def connector(company, _net):
        async def fetch():
            answer = boards["answers"].get(company["slug"], [])
            if isinstance(answer, Exception):
                raise answer
            return answer
        return fetch()

    async def describe(j, _net):
        if j.description:
            return j.description, False
        boards["detail_calls"].append(j.id)
        j.description = boards["details"].get(j.id)
        return j.description, True

    monkeypatch.setattr(pipeline, "load_boards", load_boards)
    monkeypatch.setattr(pipeline, "CONNECTORS",
                        {k: connector for k in ("nlx", "neogov", "greenhouse")})
    monkeypatch.setattr(pipeline.enrich, "describe", describe)
    return boards


def open_titles(data):
    return sorted(r["title"] for r in data.values() if r["is_open"])


def test_local_run_keeps_beginner_roles_and_logs_what_it_drops(world):
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL",
            "No experience required." + BODY, latlon=(28.30, -81.41), company="Osceola Regional"),
        job(NLX, "2", "Desktop Support Technician", "Orlando, FL",
            "5 years of desktop support experience required." + BODY),
        job(NLX, "3", "Registered Nurse", "Kissimmee, FL", "Nursing." + BODY),
        job(NLX, "4", "Senior Help Desk Technician", "Kissimmee, FL", BODY),
        job(NLX, "5", "IT Support Specialist", "Tampa, FL", BODY * 2),
        job(NLX, "6", "IT Support Specialist", "Lakeland, FL",
            "1 year of IT support experience required." + BODY),
    ]
    stats, data, new_ids = pipeline.run_update("local")
    assert open_titles(data) == ["Help Desk Technician", "IT Support Specialist"]
    by_title = {r["title"]: r for r in data.values()}
    local = by_title["Help Desk Technician"]
    assert local["section"] == "Local" and local["fit"] == "beginner" and local["miles"] < 2
    assert local["company"] == "Osceola Regional"
    nearby = by_title["IT Support Specialist"]
    assert nearby["section"] == "Nearby" and nearby["fit"] == "stretch"
    assert len(new_ids) == 2
    assert stats["dropped_by_reason"] == {
        "not-it-role": 1, "outside-area": 1, "requires-5-years-experience": 1,
        "senior-title": 1}
    assert stats["local_sources_ok"] == 2 and stats["open_by_section"]["Local"] == 1
    logged = [json.loads(line) for line in open(paths.REJECTED_PATH, encoding="utf-8")]
    reasons = {row["reason"] for row in logged}
    # Audit-worthy drops are written out; nurses and far-away jobs are only counted.
    assert reasons == {"requires-5-years-experience", "senior-title"}
    assert any("5 years" in row.get("evidence", "") for row in logged)


def test_descriptions_are_fetched_once_then_the_verdict_is_cached(world):
    world["answers"]["kissimmeefl"] = [
        job(CITY, "9", "IT Technician I", "City Hall"),
        job(CITY, "10", "Network Technician", "City Hall"),
    ]
    world["details"] = {
        "neogov:kissimmeefl:9": "Entry level position." + BODY,
        "neogov:kissimmeefl:10": "Minimum 4 years of network experience required." + BODY,
    }
    _, data, _ = pipeline.run_update("local")
    assert open_titles(data) == ["IT Technician I"]
    record = next(iter(r for r in data.values() if r["is_open"]))
    # "City Hall" is not a place; the employer's own town stands in for it.
    assert record["section"] == "Local" and record["miles"] == 0.0
    assert len(world["detail_calls"]) == 2
    pipeline.run_update("local")
    assert len(world["detail_calls"]) == 2, "second run must reuse cached verdicts"
    # ...and the rejection is not logged a second time.
    assert sum(1 for _ in open(paths.REJECTED_PATH, encoding="utf-8")) == 1


def test_unreadable_posting_is_listed_as_unverified(world):
    world["answers"]["kissimmeefl"] = [job(CITY, "9", "Help Desk Technician", "Kissimmee, FL")]
    _, data, _ = pipeline.run_update("local")
    record = next(iter(data.values()))
    assert record["is_open"] and record["fit"] == filters_it.FIT_UNVERIFIED


def test_remote_roles_come_from_the_full_sweep_and_survive_local_runs(world):
    world["answers"]["acme"] = [
        job(ACME, "r1", "IT Support Specialist", "Remote, United States",
            "Entry level." + BODY),
        job(ACME, "r2", "IT Support Specialist", "Remote - Texas", "Entry level." + BODY),
        job(ACME, "r3", "IT Support Specialist", "Remote, United States",
            "Entry level. Must reside in one of the following states: Texas, Ohio." + BODY),
    ]
    stats, data, _ = pipeline.run_update("full")
    assert [r["section"] for r in data.values() if r["is_open"]] == ["Remote"]
    assert stats["dropped_by_reason"]["remote-not-open-to-florida"] == 1
    assert stats["last_full"]["boards_total"] == 3
    # Two local runs in a row never read Acme, so they must not close its role.
    for _ in range(2):
        stats, data, _ = pipeline.run_update("local")
    assert sum(r["is_open"] for r in data.values()) == 1
    assert stats["last_full"]["boards_total"] == 3


def test_role_closes_after_two_complete_misses_not_one(world):
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL", "Entry level." + BODY)]
    pipeline.run_update("local")
    world["answers"]["kissimmee-fl"] = []
    _, data, _ = pipeline.run_update("local")
    assert sum(r["is_open"] for r in data.values()) == 1
    _, data, _ = pipeline.run_update("local")
    record = next(iter(data.values()))
    assert not record["is_open"] and record["closed_reason"] == "gone-from-feed"


def test_a_failed_source_closes_nothing_and_is_reported(world):
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL", "Entry level." + BODY)]
    pipeline.run_update("local")
    world["answers"]["kissimmee-fl"] = RuntimeError("503 from NLx")
    for _ in range(3):
        stats, data, _ = pipeline.run_update("local")
    assert sum(r["is_open"] for r in data.values()) == 1
    failed = [b for b in stats["local_sources"] if b["error"]]
    assert len(failed) == 1 and "503" in failed[0]["error"]
    assert stats["local_sources_ok"] == 1


def test_role_that_stops_qualifying_is_closed_at_once(world):
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL", "Entry level." + BODY)]
    pipeline.run_update("local")
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Senior Help Desk Technician", "Kissimmee, FL", BODY)]
    _, data, _ = pipeline.run_update("local")
    record = next(iter(data.values()))
    assert not record["is_open"] and record["closed_reason"] == "out-of-scope"


def test_old_postings_are_dropped(world):
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL", "Entry level." + BODY,
            posted_at="2020-01-01T00:00:00Z")]
    stats, data, _ = pipeline.run_update("local")
    assert not data and stats["dropped_by_reason"] == {"stale-posting": 1}


def test_published_pages_put_local_first_and_agree_with_the_store(world):
    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL", "Entry level." + BODY,
            latlon=(28.30, -81.41), posted_at="2026-11-01T00:00:00Z"),
        job(NLX, "2", "IT Support Specialist <b>", "Lakeland, FL", "Entry level." + BODY),
    ]
    world["answers"]["acme"] = [
        job(ACME, "r1", "Service Desk Analyst", "Remote, United States", "Entry level." + BODY)]
    stats, data, _ = pipeline.run_update("full")
    stats["rendered_at"] = stats["fetched_at"]
    summary = readme.generate(data, data_as_of=stats["fetched_at"])
    dashboard.generate(data, stats)
    publish.write_feed(data, stats["fetched_at"])
    assert publish.write_api(data, stats) == 3
    assert summary == {"open": 3, "Local": 1, "Nearby": 1, "Remote": 1}

    api = json.load(open(paths.API_DIR + "/jobs.json", encoding="utf-8"))
    assert [j["section"] for j in api["jobs"]] == ["Local", "Nearby", "Remote"]
    page = open(paths.DASHBOARD_PATH, encoding="utf-8").read()
    assert page.index("Help Desk Technician") < page.index("Service Desk Analyst")
    assert "IT Support Specialist &lt;b&gt;" in page and "<b>\"" not in page
    assert "never applies" in page
    text = open(paths.README_PATH, encoding="utf-8").read()
    assert text.index("## Local (1)") < text.index("## Nearby (1)") < text.index("## Remote (1)")
    csv_text = open(paths.CSV_PATH, encoding="utf-8").read()
    assert csv_text.count("\n") == 4
    store.load(paths.JOBS_PATH)   # the saved store validates


def test_the_publish_gate_passes_a_real_run_and_catches_a_bad_record(world):
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location(
        "verify_accuracy", os.path.join(paths.ROOT, "tools", "verify_accuracy.py"))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    from intern_engine import config

    world["answers"]["kissimmee-fl"] = [
        job(NLX, "1", "Help Desk Technician", "Kissimmee, FL", "Entry level." + BODY)]
    stats, data, _ = pipeline.run_update("local")
    stats["rendered_at"] = stats["fetched_at"]
    readme.generate(data, data_as_of=stats["fetched_at"])
    dashboard.generate(data, stats)
    publish.write_api(data, stats)
    cfg = config.load_config()
    assert gate.check(data, stats, cfg) == []

    record = next(iter(data.values()))
    record["title"] = "Senior Help Desk Technician"
    record["miles"] = 44.0
    problems = "\n".join(gate.check(data, stats, cfg))
    assert "title-not-entry-it" in problems and "local-distance" in problems

    stats["local_sources_ok"] = 0
    assert "local-sources-down" in "\n".join(gate.check(data, stats, cfg))
