"""Small priority board set scanned frequently between full registry sweeps.

Fast lane checks only independently verified live sources and a few employers
worth watching for foundational IT jobs near Kissimmee. The full registry
remains covered by the slower broad scheduled workflow.
"""
from __future__ import annotations

FAST_ATS = frozenset({"himalayas", "jobicy"})
PRIORITY_EMPLOYERS = frozenset({
    "university of central florida",
    "the walt disney company",
    "nbcuniversal",
    "leidos",
    "bny",
})


def select(companies: list[dict]) -> list[dict]:
    """Return real registered boards, preserving distinct career-site identities."""
    selected = [
        company for company in companies
        if company.get("ats") in FAST_ATS
        or str(company.get("name") or "").casefold() in PRIORITY_EMPLOYERS
    ]
    if not any(company.get("ats") == "himalayas" for company in selected):
        raise ValueError("Fast scan needs its validated remote IT source")
    return selected
