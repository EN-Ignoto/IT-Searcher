"""Is the searcher healthy? Prints a Markdown report; exit 1 when it is not.

    python tools/health_report.py [--published PATH] [--gate success|failure]

Written after November 2026, when half the runs failed for twelve days and
1,890 Workday boards sat benched, and nothing said so except a stream of
"run failed" emails. This looks at the things that broke then, and the ones
that would break the same way:

  - the published data is old (nothing has been published for hours)
  - the last nationwide sweep is old, or most of its boards failed
  - a local source has failed several runs in a row
  - a large share of one platform's boards is benched
  - the publish gate rejected this run
  - the open count suddenly collapsed

The workflows turn a failing report into one GitHub issue (labelled
`searcher-health`) and close it once a report comes back clean.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from intern_engine import health, registry  # noqa: E402

MAX_PUBLISH_AGE_H = 12
MAX_SWEEP_AGE_H = 24
MIN_SWEEP_SUCCESS = 0.80
LOCAL_FAIL_STREAK = 3
MAX_BENCHED_SHARE = 0.20
MIN_BOARDS_FOR_SHARE = 20
COLLAPSE_SHARE = 0.5


def _ts(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _load(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def check(*, published: dict, current: dict, health_data: dict, local: list[dict],
          registry_boards: list[dict], history: list[dict], gate: str | None,
          now: datetime) -> tuple[list[str], list[str]]:
    """(problems, facts). Problems open the alert; facts are context."""
    problems: list[str] = []
    facts: list[str] = []

    def age_h(value) -> float | None:
        dt = _ts(value)
        return None if dt is None else (now - dt).total_seconds() / 3600

    pub_age = age_h(published.get("fetched_at"))
    facts.append(f"Published data: {published.get('fetched_at')} "
                 f"({'unknown age' if pub_age is None else f'{pub_age:.1f} h old'}), "
                 f"{published.get('open_total')} open roles "
                 f"{published.get('open_by_section') or ''}")
    if pub_age is None or pub_age > MAX_PUBLISH_AGE_H:
        problems.append(f"Nothing published for {pub_age if pub_age is None else round(pub_age)}"
                        f" hours (limit {MAX_PUBLISH_AGE_H}). Either runs are failing or "
                        "GitHub is not starting them; see the Actions tab.")

    if gate == "failure":
        problems.append("This run's publish gate rejected the data, so it was not "
                        "published. The gate's reasons are in the run log.")

    sweep = current.get("last_full") or published.get("last_full") or {}
    sweep_age = age_h(sweep.get("fetched_at"))
    facts.append(f"Last nationwide sweep: {sweep.get('fetched_at')}, "
                 f"{sweep.get('fetched_ok')} of {sweep.get('boards_total')} boards read, "
                 f"success rate {sweep.get('fetch_success_rate')}")
    if sweep_age is None or sweep_age > MAX_SWEEP_AGE_H:
        problems.append(f"No nationwide sweep for over {MAX_SWEEP_AGE_H} hours, so remote "
                        "roles are not being refreshed.")
    rate = sweep.get("fetch_success_rate")
    if isinstance(rate, (int, float)) and rate < MIN_SWEEP_SUCCESS:
        problems.append(f"The last sweep read only {rate:.0%} of the boards it tried "
                        f"(limit {MIN_SWEEP_SUCCESS:.0%}). Failures by platform: "
                        f"{sweep.get('errors_by_source', 'not recorded')}; benched boards are "
                        "not counted as tried.")
    for ats, share in (current.get("provider_outages") or {}).items():
        problems.append(f"{ats}: {share:.0%} of its boards failed in one run. Treated as a "
                        "platform-wide problem (nothing was benched), but if it repeats, "
                        "the connector or our access to it needs a look.")

    failing = []
    for company in local:
        entry = health_data.get(registry.board_key(company)) or {}
        streak = entry.get("consecutive_failures", 0)
        if streak >= LOCAL_FAIL_STREAK:
            failing.append(f"{company['name']} ({streak} runs: {entry.get('last_error', '')[:140]})")
    if failing:
        problems.append("Local sources failing run after run:\n" +
                        "\n".join(f"    - {f}" for f in failing))

    benched: Counter = Counter()
    total: Counter = Counter()
    for company in registry_boards:
        ats = company.get("ats") or "?"
        total[ats] += 1
        if health.is_quarantined(health_data.get(registry.board_key(company)), now):
            benched[ats] += 1
    for ats, n in sorted(total.items()):
        if n >= MIN_BOARDS_FOR_SHARE and benched[ats] / n > MAX_BENCHED_SHARE:
            problems.append(f"{benched[ats]} of {n} {ats} boards ({benched[ats] / n:.0%}) are "
                            "benched by the failure breaker. That many failing at once usually "
                            "means throttling or a changed API, not dead boards.")
    facts.append("Benched boards by platform: " + (", ".join(
        f"{a} {benched[a]}/{total[a]}" for a in sorted(total) if benched[a]) or "none"))

    week_ago = now - timedelta(days=7)
    recent = [h.get("open", 0) for h in history if (_ts(h.get("ts")) or now) >= week_ago]
    peak = max(recent, default=0)
    now_open = current.get("open_total", published.get("open_total")) or 0
    if peak >= 10 and now_open < peak * COLLAPSE_SHARE:
        problems.append(f"Open roles fell from {peak} to {now_open} within a week. "
                        "Check data/rejected.jsonl for a rule that suddenly drops everything.")
    return problems, facts


def render(problems: list[str], facts: list[str], run_url: str | None) -> str:
    head = ("**Something needs attention.**" if problems else
            "**All checks pass.**")
    lines = [head, ""]
    lines += [f"- {p}" for p in problems] + ([""] if problems else [])
    lines += ["<details><summary>Current state</summary>", ""]
    lines += [f"- {f}" for f in facts] + ["", "</details>", ""]
    if run_url:
        lines.append(f"Report from {run_url}")
    lines.append("_Opened and closed automatically by tools/health_report.py._")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--published", default=os.path.join(ROOT, "data", "stats.json"))
    parser.add_argument("--gate", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    history = []
    try:
        with open(os.path.join(ROOT, "data", "history.jsonl"), encoding="utf-8") as f:
            history = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        pass
    local = _load(os.path.join(ROOT, "data", "local_sources.json"), [])
    local_keys = {registry.board_key(c) for c in local}
    boards = [c for c in _load(os.path.join(ROOT, "data", "companies.json"), [])
              if isinstance(c, dict) and registry.board_key(c) not in local_keys]
    problems, facts = check(
        published=_load(args.published, {}),
        current=_load(os.path.join(ROOT, "data", "stats.json"), {}),
        health_data=_load(os.path.join(ROOT, "data", "health.json"), {}),
        local=local, registry_boards=boards, history=history, gate=args.gate,
        now=datetime.now(UTC))
    run_url = None
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/"
                   f"{os.environ['GITHUB_RUN_ID']}")
    text = render(problems, facts, run_url)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
