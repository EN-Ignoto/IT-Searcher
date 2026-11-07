"""Priority scans use real registered sources, not an invented local feed."""
import pytest

from intern_engine import fastlane


def test_select_fast_lane_keeps_relevant_board_records():
    rows = [
        {"name": "Himalayas US Remote Jobs", "ats": "himalayas", "slug": "remote"},
        {"name": "University of Central Florida", "ats": "workday", "slug": "ucf"},
        {"name": "The Walt Disney Company", "ats": "workday", "slug": "disney"},
        {"name": "BNY", "ats": "oracle", "slug": "bny"},
        {"name": "Generic unrelated firm", "ats": "workday", "slug": "other"},
    ]
    selected = fastlane.select(rows)
    assert selected == rows[:4]


def test_requires_real_remote_source():
    with pytest.raises(ValueError, match="validated remote IT source"):
        fastlane.select([{"name": "University of Central Florida", "ats": "workday"}])
