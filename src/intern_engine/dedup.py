"""Collapse duplicate postings — only where identity is actually proven.

Lifted unchanged from the original engine's pipeline; see `dedup()`.
"""

from __future__ import annotations

import re

from . import models


def _norm_location(location: str) -> str:
    """A location reduced to its comparable core, for dedup only.

    Punctuation and casing are noise. Work mode is NOT: an employer that posts
    "Austin, TX" and "Austin, TX (Remote)" is offering two different jobs, and
    stripping the remote/hybrid marker merged them. Keeping the mode in the key
    means two postings only match when they really describe the same place on
    the same terms.
    """
    low = (location or "").lower()
    mode = ""
    if re.search(r"\bremote\b", low):
        mode = " remote"
    elif re.search(r"\bhybrid\b", low):
        mode = " hybrid"
    low = re.sub(r"\(remote\)|\bremote\b|\bhybrid\b|\bon[\s-]?site\b", " ", low)
    return re.sub(r"[^a-z0-9]+", " ", low).strip() + mode


def _job_rank(job) -> tuple[int, int, int, int, str]:
    """Prefer the copy carrying the strongest useful posting evidence."""
    precision = models.DATE_PRECISION.get(
        job.posted_at_source or models.date_source(job.posted_at), 0,
    )
    return (
        precision,
        int(bool(job.posted_at)),
        int(bool(job.location and job.location != "—")),
        int(bool(job.url and str(job.url).startswith(("https://", "http://")))),
        job.id,
    )


def _existing_owner(existing: dict, ids: set[str]) -> str | None:
    """Return the oldest stored record that owns any id/alias in ``ids``."""
    candidates = []
    for jid, record in existing.items():
        owned = {jid, *(record.get("aliases") or [])}
        if owned.intersection(ids):
            candidates.append(jid)
    if not candidates:
        return None
    return min(candidates, key=lambda jid: (
        existing[jid].get("first_seen_at") or "9999",
        jid,
    ))


def _merge_exact_alias_records(existing: dict, survivor_id: str,
                               duplicate_ids: set[str]) -> None:
    """Consolidate stored records whose shared canonical id proves identity."""
    target = existing.get(survivor_id)
    if target is None:
        return
    aliases = set(target.get("aliases") or [])
    for duplicate_id in sorted(duplicate_ids - {survivor_id}):
        duplicate = existing.pop(duplicate_id, None)
        if duplicate is None:
            continue
        aliases.add(duplicate_id)
        aliases.update(duplicate.get("aliases") or [])
        target["first_seen_at"] = min(
            target.get("first_seen_at") or "9999",
            duplicate.get("first_seen_at") or "9999",
        )
        target["last_seen_at"] = max(
            target.get("last_seen_at") or "",
            duplicate.get("last_seen_at") or "",
        )
        old_rank = models.DATE_PRECISION.get(target.get("posted_at_source"), 0)
        new_rank = models.DATE_PRECISION.get(duplicate.get("posted_at_source"), 0)
        if duplicate.get("posted_at") and (
            not target.get("posted_at") or new_rank > old_rank
        ):
            target["posted_at"] = duplicate["posted_at"]
            target["posted_at_source"] = duplicate.get("posted_at_source")
        for field in ("salary", "skills", "requisition_id"):
            if not target.get(field) and duplicate.get(field):
                target[field] = duplicate[field]
        if (
            target.get("sponsorship", "unknown") == "unknown"
            and duplicate.get("sponsorship", "unknown") != "unknown"
        ):
            target["sponsorship"] = duplicate["sponsorship"]
        if duplicate.get("is_open"):
            # Consolidating aliases must preserve a continuously-open copy.
            # Otherwise choosing an older closed id manufactures a reopening
            # and sends a duplicate alert for a role that never disappeared.
            target["is_open"] = True
            target.pop("closed_at", None)
            target.pop("closed_reason", None)
    aliases.discard(survivor_id)
    if aliases:
        target["aliases"] = sorted(aliases)


def dedup(jobs: list, existing: dict | None = None) -> list:
    """Collapse only identities supported by canonical or syndication evidence.

    The only duplicate we can actually prove is one posting syndicated to two
    ATS: same company, same title, same place, two boards. That collapses, and
    the copy carrying a real posted date wins.

    A connector-supplied canonical id is stronger than the presentation id.
    It lets us merge the same Greenhouse/SmartRecruiters requisition across
    board aliases while retaining every old posting id in ``aliases``.  When a
    canonical role already exists, its oldest store id survives so a slug or
    posting-id change cannot reset first-seen time or trigger a duplicate alert.

    Two requisitions on the SAME board are otherwise never merged, even when title and
    location match. Copart really did open JR109672 and JR109673 — "Software
    Engineering Intern, Dallas" twice — and an employer that opens two reqs is
    offering two jobs. The board already told us they're distinct by giving
    them distinct ids; second-guessing that deletes a real opening.
    """
    existing = existing if existing is not None else {}

    # First collapse exact canonical identities. This may safely merge records
    # that already exist in the store; presentation-only dedup below may not.
    canonical_groups: dict[tuple[str, str], list] = {}
    without_canonical = []
    for job in jobs:
        if job.canonical_id:
            canonical_groups.setdefault(
                (job.source, str(job.canonical_id)), [],
            ).append(job)
        else:
            without_canonical.append(job)

    exact = list(without_canonical)
    for (source, canonical_id), group in canonical_groups.items():
        stored_ids = {
            jid for jid, record in existing.items()
            if record.get("source") == source
            and str(record.get("canonical_id") or "") == canonical_id
        }
        current_ids = {job.id for job in group}
        # On the first deployment, legacy records do not yet carry
        # canonical_id. Current presentation ids (or their stored aliases)
        # still identify those records, and the connector's shared canonical
        # id proves that they can now be consolidated.
        current_owners = {
            owner
            for current_id in current_ids
            if (owner := _existing_owner(existing, {current_id})) is not None
        }
        merge_ids = stored_ids | current_owners
        survivor_id = _existing_owner(existing, merge_ids | current_ids)
        metadata = max(group, key=_job_rank)
        original_id = metadata.id
        if survivor_id is None:
            survivor_id = metadata.id
        metadata.id = survivor_id
        survivor_aliases = set(
            (existing.get(survivor_id) or {}).get("aliases") or [],
        )
        aliases = (
            set(metadata.aliases or []) | survivor_aliases
            | merge_ids | current_ids | {original_id}
        )
        for stored_id in merge_ids:
            aliases.update((existing.get(stored_id) or {}).get("aliases") or [])
        aliases.discard(survivor_id)
        metadata.aliases = sorted(aliases) or None
        _merge_exact_alias_records(existing, survivor_id, merge_ids)
        exact.append(metadata)

    def key_of(job):
        return (
            job.company.lower().strip(),
            re.sub(r"[^a-z0-9]+", "", job.title.lower()),
            _norm_location(job.location),
        )

    # Group first, then decide. Only ONE pattern is provably a duplicate:
    # every source holds exactly one requisition for the key — the classic
    # single posting syndicated across boards. That collapses to the best copy
    # (a real posting date wins). The moment ANY source lists two or more reqs
    # under the key, identity is ambiguous — we can't tell which copy on the
    # other board mirrors which req — and deleting a real opening is worse
    # than showing a possible duplicate, so everything is kept.
    groups: dict[tuple[str, str, str], dict[str, list]] = {}
    for job in exact:
        groups.setdefault(key_of(job), {}).setdefault(job.source, []).append(job)

    unique = []
    for by_source in groups.values():
        if len(by_source) > 1 and all(len(g) == 1 for g in by_source.values()):
            candidates = [group[0] for group in by_source.values()]
            ids = {
                identity
                for job in candidates
                for identity in ({job.id} | set(job.aliases or []))
            }
            survivor_id = _existing_owner(existing, ids)
            best = max(candidates, key=_job_rank)
            original_id = best.id
            if survivor_id is not None:
                best.id = survivor_id
            survivor_aliases = set(
                (existing.get(best.id) or {}).get("aliases") or [],
            )
            aliases = set(best.aliases or []) | survivor_aliases | ids | {original_id}
            aliases.discard(best.id)
            best.aliases = sorted(aliases) or None
            unique.append(best)
        else:
            for group in by_source.values():
                unique.extend(group)
    return unique
