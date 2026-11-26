import importlib.util
import os
from datetime import UTC, datetime

from intern_engine import paths

spec = importlib.util.spec_from_file_location(
    "health_report", os.path.join(paths.ROOT, "tools", "health_report.py"))
hr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hr)

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
LOCAL = [{"name": "City of Kissimmee", "slug": "kissimmeefl", "ats": "neogov"}]
WD = [{"name": f"T{i}", "slug": f"t{i}", "ats": "workday", "wd": "wd1", "site": "s"}
      for i in range(40)]
GOOD = {"fetched_at": "2026-11-26T11:00:00Z", "open_total": 50,
        "last_full": {"fetched_at": "2026-11-26T08:00:00Z", "fetch_success_rate": 0.97}}


def run(**over):
    args = dict(published=GOOD, current=GOOD, health_data={}, local=LOCAL,
                registry_boards=WD, history=[], gate="success", now=NOW)
    args.update(over)
    return hr.check(**args)[0]


def test_healthy_state_reports_nothing():
    assert run() == []


def test_each_november_failure_mode_is_caught():
    old = {**GOOD, "fetched_at": "2026-11-25T10:00:00Z"}
    assert any("Nothing published" in p for p in run(published=old))
    assert any("publish gate" in p for p in run(gate="failure"))
    weak = {**GOOD, "last_full": {"fetched_at": "2026-11-26T08:00:00Z",
                                  "fetch_success_rate": 0.6}}
    assert any("60%" in p for p in run(current=weak))
    stale_sweep = {**GOOD, "last_full": {"fetched_at": "2026-11-24T08:00:00Z"}}
    assert any("nationwide sweep" in p for p in run(current=stale_sweep, published=stale_sweep))
    benched = {f"workday:t{i}:s": {"consecutive_failures": 8,
                                   "last_attempt_at": "2026-11-26T10:00:00Z",
                                   "last_error": "429"} for i in range(20)}
    assert any("workday boards" in p for p in run(health_data=benched))
    local_down = {"neogov:kissimmeefl": {"consecutive_failures": 4,
                                         "last_attempt_at": "2026-11-26T10:00:00Z",
                                         "last_error": "ConnectTimeout"}}
    assert any("City of Kissimmee" in p for p in run(health_data=local_down))
    history = [{"ts": "2026-11-24T00:00:00Z", "open": 60}]
    assert any("fell from 60" in p for p in run(history=history,
                                                 current={**GOOD, "open_total": 20}))
