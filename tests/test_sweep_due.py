import importlib.util
import os
from datetime import UTC, datetime

from intern_engine import paths

spec = importlib.util.spec_from_file_location(
    "sweep_due", os.path.join(paths.ROOT, "tools", "sweep_due.py"))
sweep_due = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep_due)

NOW = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)


def test_sweep_is_due_only_when_the_last_one_is_old_or_missing():
    assert sweep_due.due({"last_full": {"fetched_at": "2026-11-12T09:46:35Z"}}, NOW)
    assert not sweep_due.due({"last_full": {"fetched_at": "2026-11-12T15:00:00Z"}}, NOW)
    assert sweep_due.due({}, NOW)
    assert sweep_due.due({"last_full": {"fetched_at": "garbage"}}, NOW)
