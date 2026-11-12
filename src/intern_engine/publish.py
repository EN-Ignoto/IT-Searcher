"""Machine-readable outputs served from GitHub Pages (docs/).

  docs/feed.xml       — Atom feed ordered by when WE first saw each role, so
                        any RSS reader becomes a free alert channel.
  docs/api/jobs.json  — every open role, in published order, plus stats.json.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape, quoteattr

from . import config, geo, paths, view

_FEED_LIMIT = 100
_FEED_RETENTION_DAYS = 14
_API_FIELDS = (
    "id", "section", "miles", "remote", "title", "company", "location", "category",
    "employment", "fit", "experience", "evidence", "notes", "url", "posted_at",
    "posted_at_source", "first_seen_at", "salary", "source",
)


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_of(value: str | None) -> str:
    parsed = view.parse_ts(value)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") if parsed else _iso_now()


def _entry(record: dict, base: str, as_of: str) -> str:
    title = f"[{record.get('section') or 'Closed'}] {record.get('title', '')} — " \
            f"{record.get('company', '')}"
    bits = [view.where(record), record.get("employment") or "",
            view.FIT_LABEL.get(record.get("fit"), ""), record.get("experience") or ""]
    bits += list(record.get("notes") or [])
    if not record.get("is_open"):
        bits.append("status: closed")
    updated = max(record.get("first_seen_at") or "", record.get("closed_at") or "") or as_of
    return (
        "  <entry>\n"
        f"    <id>urn:it-searcher:{escape(record.get('id', ''))}</id>\n"
        f"    <title>{escape(title)}</title>\n"
        f"    <link href={quoteattr(record.get('url') or base)}/>\n"
        f"    <updated>{escape(updated)}</updated>\n"
        f"    <category term={quoteattr(record.get('section') or 'Closed')}/>\n"
        f"    <summary>{escape(' · '.join(b for b in bits if b))}</summary>\n"
        "  </entry>\n"
    )


def write_feed(store_data: dict, data_as_of: str | None = None) -> int:
    base = config.pages_base()
    as_of = _as_of(data_as_of)
    cutoff = view.parse_ts(as_of) - timedelta(days=_FEED_RETENTION_DAYS)
    entries = []
    for record in store_data.values():
        seen = view.parse_ts(record.get("first_seen_at"))
        if record.get("is_open") or (seen is not None and seen >= cutoff):
            entries.append(record)
    entries.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)
    entries = entries[:_FEED_LIMIT]
    xml = [
        '<?xml version="1.0" encoding="utf-8"?>\n',
        '<feed xmlns="http://www.w3.org/2005/Atom">\n',
        f"  <id>{escape(base)}/feed.xml</id>\n",
        f"  <title>Entry-level IT jobs near {escape(geo.HOME_NAME)} — new roles</title>\n",
        "  <subtitle>Local first, then remote roles open to Florida. Newest finds first."
        "</subtitle>\n",
        f"  <link href={quoteattr(base + '/feed.xml')} rel=\"self\"/>\n",
        f"  <link href={quoteattr(base + '/')}/>\n",
        f"  <updated>{as_of}</updated>\n",
        "  <author><name>IT Searcher</name>"
        f"<uri>https://github.com/{escape(config.repo_slug())}</uri></author>\n",
    ]
    xml.extend(_entry(r, base, as_of) for r in entries)
    xml.append("</feed>\n")
    os.makedirs(paths.DOCS_DIR, exist_ok=True)
    with open(paths.FEED_PATH, "w", encoding="utf-8") as f:
        f.write("".join(xml))
    return len(entries)


def write_api(store_data: dict, stats: dict) -> int:
    rows = view.open_jobs(store_data)
    as_of = _as_of(stats.get("fetched_at") or stats.get("generated_at"))
    payload = {
        "generated_at": as_of,
        "data_as_of": as_of,
        "rendered_at": stats.get("rendered_at") or _iso_now(),
        "home": geo.HOME_NAME,
        "source": f"https://github.com/{config.repo_slug()}",
        "count": len(rows),
        "jobs": [{k: r.get(k) for k in _API_FIELDS} for r in rows],
    }
    os.makedirs(paths.API_DIR, exist_ok=True)
    with open(os.path.join(paths.API_DIR, "jobs.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    with open(os.path.join(paths.API_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1, ensure_ascii=False)
    return len(rows)
