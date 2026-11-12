"""Pull the posting text (and date) out of an employer's HTML job page.

Several local sources have no JSON detail endpoint. Their job pages do embed
schema.org `JobPosting` JSON-LD — that is what Google for Jobs reads — so we
prefer it: it is the employer's own structured statement of the description
and the publish date. When it is missing we fall back to the page body with
scripts, styles and navigation removed.
"""

from __future__ import annotations

import html as _html
import json
import re

_LD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
_DROP_RE = re.compile(
    r"<(script|style|noscript|svg|nav|header|footer|form|select)\b.*?</\1\s*>", re.I | re.S)
_MAIN_RE = re.compile(r"<(main|article)\b.*?</\1\s*>", re.I | re.S)


def _postings(node):
    if isinstance(node, list):
        for item in node:
            yield from _postings(item)
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            yield node
        yield from _postings(node.get("@graph"))


def job_posting(page: str) -> dict | None:
    """The page's schema.org JobPosting object, if it publishes one."""
    for block in _LD_RE.findall(page or ""):
        try:
            data = json.loads(_html.unescape(block) if "&quot;" in block else block)
        except ValueError:
            continue
        for posting in _postings(data):
            return posting
    return None


def extract(page: str) -> tuple[str | None, str | None]:
    """(description HTML/text, datePosted) from a job page. Either may be None."""
    posting = job_posting(page)
    posted = None
    if posting:
        raw = posting.get("datePosted")
        if isinstance(raw, str) and re.match(r"\d{4}-\d{2}-\d{2}", raw):
            posted = raw
        description = posting.get("description")
        if isinstance(description, str) and len(description) > 200:
            parts = [description]
            for key in ("qualifications", "experienceRequirements",
                        "educationRequirements", "skills", "responsibilities"):
                extra = posting.get(key)
                if isinstance(extra, str):
                    parts.append(extra)
            return "<br>".join(parts), posted
    if not page:
        return None, posted
    body = _DROP_RE.sub(" ", page)
    main = _MAIN_RE.search(body)
    return (main.group(0) if main and len(main.group(0)) > 600 else body), posted
