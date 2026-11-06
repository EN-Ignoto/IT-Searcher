"""Guard against accidentally publishing an empty or collapsed feed."""
import pytest

from tools.check_feed_collapse import unexpected_collapse


@pytest.mark.parametrize("before,after,blocked", [
    (0, 0, False),
    (1, 0, False),
    (2, 0, True),
    (2, 1, False),
    (10, 2, True),
    (10, 3, False),
    (24, 0, True),
    (24, 6, True),
    (24, 7, False),
    (100, 90, False),
])
def test_collapse_guard(before, after, blocked):
    assert unexpected_collapse(before, after) is blocked


def test_bad_counts_are_invalid():
    with pytest.raises(ValueError):
        unexpected_collapse(-1, 0)
