"""Generate README.md and the CSV from the store."""

from __future__ import annotations

import csv
import io
import os

from . import config, filters_it, geo, paths, view

_ROW_CAP = 150
_CSV_FIELDS = ("section", "miles", "title", "company", "location", "category",
               "employment", "fit", "experience", "notes", "posted_at",
               "first_seen_at", "source", "url")


def _cell(text) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def _row(record: dict, as_of) -> str:
    new = "🆕 " if view.is_new(record, as_of) else ""
    fit = view.FIT_LABEL.get(record.get("fit"), "")
    experience = record.get("experience") or ""
    notes = "; ".join(record.get("notes") or [])
    detail = experience + (f" · {notes}" if notes else "")
    return (f"| {new}[{_cell(record.get('title'))}]({record.get('url')}) "
            f"| {_cell(record.get('company'))} | {_cell(view.where(record))} "
            f"| {_cell(record.get('employment'))} | {fit} | {_cell(detail)} "
            f"| {view.posted_label(record)} |")


def _csv_safe(value):
    """Neutralize spreadsheet formula injection from third-party text."""
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return "" if value is None else value


def write_csv(rows: list[dict]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_FIELDS)
    for record in rows:
        writer.writerow([_csv_safe(record.get(f)) for f in _CSV_FIELDS])
    for target in (paths.CSV_PATH, os.path.join(paths.DOCS_DIR, "jobs.csv")):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as f:
            f.write(buffer.getvalue())


def generate(store_data: dict, data_as_of: str | None = None) -> dict:
    cfg = config.load_config()
    as_of = view.parse_ts(data_as_of) or view.parse_ts("1970-01-01T00:00:00Z")
    sections = view.open_by_section(store_data)
    total = sum(len(v) for v in sections.values())
    site = config.pages_base()
    radii = {"local": cfg["local_radius_miles"], "nearby": cfg["nearby_radius_miles"]}

    lines = [
        "# IT Searcher",
        "",
        f"Entry-level IT jobs and paid IT internships near **{geo.HOME_NAME}**, plus remote "
        "roles open to Florida residents. Rebuilt automatically from employers' own "
        "postings; every link goes to the posting itself.",
        "",
        f"**[Open the live list →]({site}/)** · [CSV]({site}/jobs.csv) · "
        f"[JSON]({site}/api/jobs.json) · [Feed]({site}/feed.xml)",
        "",
        f"_Data as of {as_of.strftime('%b %d, %Y %H:%M UTC')} · {total} open roles: "
        + ", ".join(f"{len(sections[name])} {name.lower()}" for name in filters_it.SECTIONS)
        + "._",
        "",
        "This project only finds and lists jobs. It never applies, submits forms, or "
        "contacts employers on your behalf.",
        "",
        "## Who the list is for",
        "",
        "Someone starting in IT: Network+ and Security+, customer-service experience, "
        "studying computer science, no professional IT experience yet. A role is listed "
        "when its title is an entry path into IT (help desk, desktop support, IT "
        "technician, junior network/systems/security work, paid IT internships), it is "
        "not senior, and the posting's own text does not *require* experience a beginner "
        "lacks. \"Preferred\" experience never excludes a role; it is shown as a note.",
        "",
        "- **Beginner-friendly**: nothing in the posting requires IT experience.",
        "- **Stretch**: about a year is required, a requirement may be met by education "
        "or certifications, or the title is a level II.",
        "- **Check requirements**: the posting text could not be read; open it before "
        "applying.",
        "",
    ]
    for name in filters_it.SECTIONS:
        rows = sections[name]
        lines += [f"## {name} ({len(rows)})", "",
                  f"_{view.SECTION_BLURB[name].format(**radii)}._", ""]
        if not rows:
            lines += ["No open roles right now.", ""]
            continue
        lines += ["| Role | Employer | Where | Type | Fit | What the posting says | Posted |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_row(r, as_of) for r in rows[:_ROW_CAP]]
        if len(rows) > _ROW_CAP:
            lines.append(f"\n_{len(rows) - _ROW_CAP} more on the [live list]({site}/)._")
        lines.append("")
    lines += [
        "## How it works",
        "",
        "- **Local sources, every 30 minutes**: the National Labor Exchange (NLx) within "
        "50 miles of Kissimmee, eleven city and county governments on GovernmentJobs, the "
        "School District of Osceola County, UCF and the City of Orlando.",
        "- **Nationwide sweep, every 6 hours**: about 5,400 employer job boards, which is "
        "where the remote roles come from.",
        "- Roles that were considered and dropped are logged with the reason in "
        "[`data/rejected.jsonl`](data/rejected.jsonl).",
        "- A role is marked closed only after it is missing from two complete readings "
        "of its board in a row.",
        "",
        "See [METHODOLOGY.md](METHODOLOGY.md) for the rules and "
        "[ARCHITECTURE.md](ARCHITECTURE.md) for the code.",
        "",
    ]
    os.makedirs(os.path.dirname(paths.README_PATH), exist_ok=True)
    with open(paths.README_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    write_csv(view.open_jobs(store_data))
    return {"open": total, **{name: len(sections[name]) for name in filters_it.SECTIONS}}
