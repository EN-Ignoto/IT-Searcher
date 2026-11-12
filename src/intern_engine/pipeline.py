"""One run: fetch boards, keep what a beginner can apply to, record the rest.

    fetch      every board in scope, concurrently, failures isolated
    title      is this an entry path into IT, and not senior?  (filters_it)
    place      within 50 miles of Kissimmee, or remote and open to Florida?
    read       the posting's own text — fetched only for roles that got this far
    assess     does it REQUIRE experience a beginner lacks?       (filters_it)
    store      first-seen / closed tracking, two-miss closure rule (store)

Two scopes share this code. `local` reads only data/local_sources.json — a
dozen Central Florida boards, cheap enough for every half hour. `full` adds
the nationwide registry (data/companies.json), which is where remote roles
come from, and runs a few times a day.

A board only ever closes roles on the boards that were read this run, so a
local run never touches what the last full sweep found.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import httpx

from . import config, enrich, filters_it, geo, health, models, paths, registry, store
from .connectors import (
    amazon,
    ashby,
    breezy,
    eightfold,
    greenhouse,
    icims,
    lever,
    neogov,
    nlx,
    oracle,
    paradox,
    recruitee,
    rippling,
    smartrecruiters,
    workable,
    workday,
)
from .dedup import dedup
from .net import HostLimiter, Net

CONNECTORS = {
    "greenhouse": greenhouse.fetch,
    "icims": icims.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
    "amazon": amazon.fetch,
    "oracle": oracle.fetch,
    "rippling": rippling.fetch,
    "workable": workable.fetch,
    "breezy": breezy.fetch,
    "recruitee": recruitee.fetch,
    "eightfold": eightfold.fetch,
    "nlx": nlx.fetch,
    "neogov": neogov.fetch,
    "paradox": paradox.fetch,
}

SCOPES = ("local", "full")
GLOBAL_CONCURRENCY = 32
PER_HOST_CONCURRENCY = 8
PER_PROVIDER_CONCURRENCY = GLOBAL_CONCURRENCY
BOARD_TIMEOUT_SECONDS = 180
DETAIL_CONCURRENCY = 8
USER_AGENT = f"it-searcher/1.0 (+https://github.com/{config.repo_slug()})"

# Title-level reasons are counted but not logged line by line: a sweep sees
# tens of thousands of nurses and software engineers, and listing them would
# bury the rejections worth auditing.
_COUNT_ONLY = {"not-it-role", "no-title", "outside-area"}
_REJECTED_KEEP = 4000
_HISTORY_KEEP = 2000
_UNVERIFIED_RETRY_HOURS = 24
_CACHE_KEEP_DAYS = 45
_UNSEEN_CLOSE_DAYS = 14
_LIVENESS_CHECKS = 60


def load_boards(scope: str) -> tuple[list[dict], set[str]]:
    """(boards to read this run, keys of the local ones)."""
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    local = registry.load(paths.LOCAL_SOURCES_PATH, missing_ok=True)
    local_keys = {registry.board_key(c) for c in local}
    boards = list(local)
    if scope == "full":
        taken = {(c["ats"], c["slug"]) for c in local}
        boards += [c for c in registry.load(missing_ok=True)
                   if registry.board_key(c) not in local_keys
                   and (c["ats"], c["slug"]) not in taken]
    return boards, local_keys


# ---------------------------------------------------------------- fetching --
async def _fetch_one(company: dict, net: Net):
    """(company, Fetch, error); never raises. On error the result is an EMPTY,
    INCOMPLETE fetch, so a failed request never reads as "no openings"."""
    fetch = CONNECTORS.get(company.get("ats"))
    if fetch is None:
        return company, models.Fetch(complete=False), f"no connector for {company.get('ats')}"
    try:
        result = models.Fetch.of(await fetch(company, net))
        for job in result.jobs:
            job.board_key = registry.board_key(company)
        if not result.jobs and result.incomplete_reason in {
                models.INCOMPLETE_MALFORMED, models.INCOMPLETE_STALLED}:
            return company, result, result.incomplete_reason
        return company, result, None
    except Exception as exc:  # noqa: BLE001 — one bad endpoint must not stop the run
        return company, models.Fetch(complete=False), f"{type(exc).__name__}: {exc}"[:300]


async def _fetch_bounded(company: dict, net: Net):
    limit = int(company.get("timeout") or BOARD_TIMEOUT_SECONDS)
    try:
        async with asyncio.timeout(limit):
            return await _fetch_one(company, net)
    except TimeoutError:
        return company, models.Fetch(complete=False), f"board deadline exceeded ({limit}s)"


async def _fetch_all(companies: list[dict], after):
    """Fetch every board, then run `after(results, net, workday_net)` on the
    same client so detail requests reuse connections."""
    limiter = HostLimiter(PER_HOST_CONCURRENCY, per_provider=PER_PROVIDER_CONCURRENCY)
    gate = asyncio.Semaphore(GLOBAL_CONCURRENCY)
    proxy = os.environ.get("WORKDAY_PROXY") or None
    common = dict(
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
        timeout=httpx.Timeout(25.0, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )
    async with httpx.AsyncClient(**common) as client:
        default_net = Net(client, limiter)
        workday_client = httpx.AsyncClient(proxy=proxy, **common) if proxy else None
        workday_net = Net(workday_client, limiter) if workday_client else default_net
        completed = 0

        async def worker(company: dict):
            nonlocal completed
            net = workday_net if company.get("ats") in ("workday", "oracle") else default_net
            async with gate:
                result = await _fetch_bounded(company, net)
            completed += 1
            if completed % 250 == 0 or completed == len(companies):
                print(f"Fetched boards: {completed}/{len(companies)}", flush=True)
            return result

        try:
            results = await asyncio.gather(*(worker(c) for c in companies))
            extra = await after(results, default_net, workday_net)
            return results, extra
        finally:
            if workday_client is not None:
                await workday_client.aclose()


# ------------------------------------------------------------- the verdict --
def _coordinates(job, company: dict) -> tuple[float, float] | None:
    """Exact coordinates when the source gave them; else the employer's own
    town for single-site local employers whose location text is a building
    name ("City Hall") rather than a place."""
    if job.latlon:
        return job.latlon
    fallback = company.get("fallback_place")
    if not fallback or geo.local_distance(job.location) is not None:
        return None
    if geo.names_other_state(job.location):
        return None
    if filters_it._REMOTE_WORD_RE.search(job.location or ""):
        return None
    return geo.coords(fallback)


def _too_old(posted_at: str | None, max_age_days: float, now: datetime) -> bool:
    if not max_age_days or not posted_at:
        return False
    try:
        day = datetime.fromisoformat(posted_at[:10]).replace(tzinfo=UTC)
    except ValueError:
        return False
    return day < now - timedelta(days=max_age_days)


def load_cache() -> dict:
    try:
        with open(paths.ASSESSED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}   # a cache: losing it costs detail requests, never data


def _cache_hit(cache: dict, job, now: datetime) -> dict | None:
    entry = cache.get(job.id)
    if not isinstance(entry, dict) or entry.get("v") != filters_it.VERSION:
        return None
    if entry.get("title") != job.title or entry.get("location") != job.location:
        return None   # the employer edited the posting: read it again
    result = entry.get("a")
    if not isinstance(result, dict):
        return None
    if result.get("fit") == filters_it.FIT_UNVERIFIED or result.get("reason") in (
            "unconfirmed-it-role", "level-2-unverifiable"):
        # We never saw the text. Try again, but not every half hour.
        try:
            seen = datetime.fromisoformat(entry["at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, AttributeError):
            return None
        if now - seen > timedelta(hours=_UNVERIFIED_RETRY_HOURS):
            return None
    entry["seen"] = now.strftime("%Y-%m-%d")
    return result


async def classify(results, cfg: dict, cache: dict, net: Net, workday_net: Net,
                   now: datetime | None = None) -> dict:
    """Run every fetched job through title -> place -> text -> assessment."""
    now = now or datetime.now(UTC)
    local_r = float(cfg["local_radius_miles"])
    nearby_r = float(cfg["nearby_radius_miles"])
    out = {
        "kept": [], "succeeded": set(), "complete": set(), "seen_ids": set(),
        "errors": 0, "errors_by_ats": Counter(), "reasons": Counter(),
        "rejected": [], "jobs_seen": 0, "detail_fetches": 0, "per_board": {},
    }
    candidates = []   # (job, company, weak, category, latlon)

    def drop(job, reason: str, evidence: str = "") -> None:
        out["reasons"][reason] += 1
        if reason in _COUNT_ONLY:
            return
        out["rejected"].append({
            "reason": reason, "title": job.title, "company": job.company,
            "location": job.location, "source": job.source, "url": job.url,
            **({"evidence": evidence} if evidence else {}),
        })

    for company, result, error in results:
        key = registry.board_key(company)
        board = out["per_board"].setdefault(key, {
            "name": company.get("name"), "ats": company.get("ats"), "jobs": 0,
            "kept": 0, "complete": bool(result.complete), "error": error,
            "partial_reason": result.incomplete_reason,
        })
        if error is not None:
            out["errors"] += 1
            out["errors_by_ats"][company.get("ats", "?")] += 1
            continue
        out["succeeded"].add(key)
        if result.complete:
            out["complete"].add(key)
        board["jobs"] = len(result.jobs)
        out["jobs_seen"] += len(result.jobs)
        for job in result.jobs:
            out["seen_ids"].add(job.id)
            verdict, detail = filters_it.title_verdict(job.title)
            if verdict == "reject":
                drop(job, detail or "not-it-role")
                continue
            latlon = _coordinates(job, company)
            section, _miles, _remote, _note = filters_it.place(
                job.location, job.title, latlon=latlon,
                local_radius=local_r, nearby_radius=nearby_r)
            if section is None:
                drop(job, "outside-area")
                continue
            if _too_old(job.posted_at, cfg["max_age_days"], now):
                drop(job, "stale-posting", f"posted {job.posted_at[:10]}")
                continue
            candidates.append((job, company, verdict == "weak", detail, latlon))

    gate = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def judge(job, company, weak, category, latlon):
        result = _cache_hit(cache, job, now)
        text = ""
        if result is None:
            use = workday_net if job.source in ("workday", "oracle") else net
            async with gate:
                description, fetched = await enrich.describe(job, use)
            out["detail_fetches"] += int(fetched)
            if _too_old(job.posted_at, cfg["max_age_days"], now):
                return job, company, {"verdict": "reject", "reason": "stale-posting",
                                      "evidence": f"posted {job.posted_at[:10]}"}
            text = filters_it.to_text(description)
            result = filters_it.assess(job.title, description, weak_title=weak,
                                       employment_hint=job.employment_hint)
            section, miles, remote, note = filters_it.place(
                job.location, job.title, text, latlon=latlon,
                local_radius=local_r, nearby_radius=nearby_r)
            if section is None and result["verdict"] == "keep":
                # The description restricted where a remote hire may live.
                result = {**result, "verdict": "reject",
                          "reason": "remote-not-open-to-florida"}
            result = {**result, "section": section, "miles": miles,
                      "remote": bool(remote), "category": category,
                      "posted_at": job.posted_at,
                      "posted_at_source": job.posted_at_source}
            if note and result["verdict"] == "keep":
                result["notes"] = [*result.get("notes", []), note]
            cache[job.id] = {
                "v": filters_it.VERSION, "title": job.title, "location": job.location,
                "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "seen": now.strftime("%Y-%m-%d"), "a": result,
            }
        return job, company, result

    judged = await asyncio.gather(*(judge(*c) for c in candidates))
    for job, company, result in judged:
        if result["verdict"] != "keep":
            drop(job, result.get("reason") or "rejected", result.get("evidence") or "")
            continue
        job.section = result["section"]
        job.miles = result.get("miles")
        job.remote = bool(result.get("remote"))
        job.category = result.get("category") or "IT Support / Technician"
        job.fit = result["fit"]
        job.experience = result.get("experience") or ""
        job.evidence = result.get("evidence") or ""
        job.employment = result.get("employment") or "Not stated"
        job.notes = list(result.get("notes") or [])
        job.rules_v = filters_it.VERSION
        if not job.posted_at and result.get("posted_at"):
            job.posted_at = result["posted_at"]
            job.posted_at_source = result.get("posted_at_source")
        if job.posted_at and not job.posted_at_source:
            job.posted_at_source = models.date_source(job.posted_at)
        out["per_board"][registry.board_key(company)]["kept"] += 1
        out["kept"].append(job)
    return out


def _prune_cache(cache: dict, now: datetime) -> None:
    cutoff = (now - timedelta(days=_CACHE_KEEP_DAYS)).strftime("%Y-%m-%d")
    for jid in [j for j, e in cache.items()
                if not isinstance(e, dict) or (e.get("seen") or "") < cutoff]:
        del cache[jid]


def close_out_of_scope(existing: dict) -> int:
    """Close open records our CURRENT rules would not list.

    Our own verdict needs no evidence from the employer, so it applies to the
    whole store — including roles on boards this run did not read.
    """
    ts = store.now_iso()
    n = 0
    for record in existing.values():
        if not record.get("is_open"):
            continue
        verdict, _ = filters_it.title_verdict(record.get("title") or "")
        if verdict != "reject" and record.get("section") in filters_it.SECTIONS \
                and record.get("rules_v") == filters_it.VERSION:
            continue
        record.update(is_open=False, closed_at=ts, closed_reason="out-of-scope")
        record.pop("missing_streak", None)
        n += 1
    return n


async def _close_removed(existing: dict, seen_ids: set[str], complete: set[str],
                         net: Net, now: datetime) -> int:
    """Close roles on CAPPED boards that we can prove are gone.

    A board whose search results are capped can never close a role by
    omission. So for open roles it did not return, ask the posting page
    itself (Workday), and retire anything unseen for two weeks.
    """
    ts = store.now_iso()
    stale_before = (now - timedelta(days=_UNSEEN_CLOSE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pending = []
    closed = 0
    for jid, record in existing.items():
        if not record.get("is_open") or jid in seen_ids:
            continue
        if (record.get("board_key") or "") in complete:
            continue   # the two-miss rule in store.upsert owns these
        if (record.get("last_seen_at") or ts) < stale_before:
            record.update(is_open=False, closed_at=ts, closed_reason="not-seen-14-days")
            closed += 1
        elif record.get("source") == "workday" and len(pending) < _LIVENESS_CHECKS:
            pending.append(record)
    gone = await asyncio.gather(*(enrich.posting_gone(r, net) for r in pending))
    for record, is_gone in zip(pending, gone, strict=True):
        if not is_gone:
            record.pop("gone_checks", None)
            continue
        checks = int(record.get("gone_checks") or 0) + 1
        if checks < 2:
            record["gone_checks"] = checks   # same two-strike rule as the feed
            continue
        record.pop("gone_checks", None)
        record.update(is_open=False, closed_at=ts, closed_reason="posting-removed")
        closed += 1
    return closed


# ----------------------------------------------------------------- the run --
def run_update(scope: str = "local") -> tuple[dict, dict, list[str]]:
    cfg = config.load_config()
    boards, local_keys = load_boards(scope)
    existing = store.load(paths.JOBS_PATH)
    close_out_of_scope(existing)
    cache = load_cache()
    now = datetime.now(UTC)

    health_data = health.load()
    # Local sources are the point of the list: always retry them. The breaker
    # only benches boards from the big registry.
    registry_boards = [b for b in boards if registry.board_key(b) not in local_keys]
    active, benched = health.partition(registry_boards, health_data)
    active = [b for b in boards if registry.board_key(b) in local_keys] + active

    started = time.monotonic()
    state: dict = {}

    async def after(results, net, workday_net):
        found = await classify(results, cfg, cache, net, workday_net, now)
        found["kept"] = dedup(found["kept"], existing)
        found["removed"] = 0
        if scope == "full":
            found["removed"] = await _close_removed(
                existing, found["seen_ids"], found["complete"], workday_net, now)
        state.update(found)

    results, _ = asyncio.run(_fetch_all(active, after))

    for company, result, error in results:
        failure = error
        if failure is None and result.incomplete_reason in {
                models.INCOMPLETE_MALFORMED, models.INCOMPLETE_STALLED}:
            failure = result.incomplete_reason
        health.record(health_data, company, failure)
    health.save(health_data)

    rows = []
    for job in state["kept"]:
        row = asdict(job)
        for field in models.TRANSIENT_FIELDS:
            row.pop(field, None)
        rows.append(row)
    new_ids = store.upsert(existing, rows, state["complete"], seen_ids=state["seen_ids"])
    purged = store.purge(existing)
    store.save(paths.JOBS_PATH, existing)

    _prune_cache(cache, now)
    _atomic_write(paths.ASSESSED_PATH,
                  json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    _append_rejected(state["rejected"])

    stats = _build_stats(scope, boards, benched, local_keys, state, existing, new_ids,
                         purged, round(time.monotonic() - started, 1))
    write_stats(stats)
    _append_history(stats)
    return stats, existing, new_ids


def _open_counts(existing: dict) -> dict:
    open_records = [r for r in existing.values() if r.get("is_open")]
    dated = sum(1 for r in open_records if r.get("posted_at"))
    return {
        "open_total": len(open_records),
        "open_by_section": dict(Counter(r.get("section") for r in open_records)),
        "open_by_fit": dict(Counter(r.get("fit") for r in open_records)),
        "open_by_category": dict(Counter(r.get("category") for r in open_records)),
        "open_by_employment": dict(Counter(r.get("employment") for r in open_records)),
        "open_by_source": dict(Counter(r.get("source") for r in open_records)),
        "posted_date_coverage": round(dated / max(len(open_records), 1), 3),
    }


def _build_stats(scope, boards, benched, local_keys, state, existing, new_ids,
                 purged, duration) -> dict:
    previous = {}
    try:
        previous = load_stats()
    except StatsCorrupt:
        pass
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempted = len(boards) - len(benched)
    per_board = state["per_board"]
    local = [{"key": key, **per_board[key]} for key in sorted(local_keys) if key in per_board]
    stats = {
        "generated_at": fetched_at,
        "fetched_at": fetched_at,
        "scope": scope,
        "duration_seconds": duration,
        "boards_total": len(boards),
        "boards_by_source": dict(Counter(c["ats"] for c in boards)),
        "quarantined": len(benched),
        "fetched_ok": len(state["succeeded"]),
        "fetch_errors": state["errors"],
        "errors_by_source": dict(state["errors_by_ats"]),
        "fetch_success_rate": round(len(state["succeeded"]) / max(attempted, 1), 3),
        "snapshots_complete": len(state["complete"]),
        "snapshots_partial": len(state["succeeded"]) - len(state["complete"]),
        "jobs_seen": state["jobs_seen"],
        "roles_matched": len(state["kept"]),
        "dropped_by_reason": dict(sorted(state["reasons"].items())),
        "detail_fetches": state["detail_fetches"],
        "closed_by_posting_check": state.get("removed", 0),
        "purged_this_run": purged,
        "new_this_run": len(new_ids),
        "local_sources": local,
        "local_sources_ok": sum(1 for b in local if b["error"] is None),
        "local_sources_total": len(local_keys),
        **_open_counts(existing),
    }
    # A local run must not erase what the last nationwide sweep reported.
    if scope == "full":
        stats["last_full"] = {k: stats[k] for k in (
            "fetched_at", "duration_seconds", "boards_total", "fetched_ok",
            "fetch_errors", "fetch_success_rate", "jobs_seen", "roles_matched")}
    elif isinstance(previous.get("last_full"), dict):
        stats["last_full"] = previous["last_full"]
    return stats


def restat(existing: dict, stats: dict) -> dict:
    """Recompute the store-derived counts; fetch metrics stay the last run's."""
    return {**stats, **_open_counts(existing)}


class StatsCorrupt(RuntimeError):
    """Persisted run metrics cannot support honest publishing."""


def _parse_iso(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def load_stats(path: str | None = None) -> dict:
    path = path or paths.STATS_PATH
    try:
        with open(path, encoding="utf-8") as f:
            stats = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise StatsCorrupt(f"{path} is unreadable: {exc}") from exc
    if not isinstance(stats, dict):
        raise StatsCorrupt(f"{path} must contain an object")
    fetched_at = stats.get("fetched_at") or stats.get("generated_at")
    if _parse_iso(fetched_at) is None:
        raise StatsCorrupt(f"{path} has no valid fetch timestamp")
    stats["fetched_at"] = fetched_at
    stats.setdefault("generated_at", fetched_at)
    return stats


def _atomic_write(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_stats(stats: dict) -> None:
    _atomic_write(paths.STATS_PATH, json.dumps(stats, indent=2, ensure_ascii=False) + "\n")


def _append_lines(path: str, new_lines: list[str], keep: int) -> None:
    lines: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        pass
    lines.extend(new_lines)
    _atomic_write(path, "\n".join(lines[-keep:]) + "\n")


def _append_rejected(rows: list[dict]) -> None:
    """The audit trail: every IT-titled role we dropped, and why.

    A role re-rejected on every run would flood the file, so a role already
    logged with the same reason is not logged again.
    """
    known: set[tuple[str, str]] = set()
    try:
        with open(paths.REJECTED_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    known.add((row.get("url"), row.get("reason")))
                except ValueError:
                    continue
    except OSError:
        pass
    ts = store.now_iso()
    fresh = []
    for row in rows:
        key = (row.get("url"), row.get("reason"))
        if key in known:
            continue
        known.add(key)
        fresh.append(json.dumps({"ts": ts, **row}, ensure_ascii=False))
    if fresh:
        _append_lines(paths.REJECTED_PATH, fresh, _REJECTED_KEEP)


def _append_history(stats: dict) -> None:
    line = json.dumps({
        "ts": stats["generated_at"], "scope": stats["scope"],
        "open": stats["open_total"], "local": stats["open_by_section"].get("Local", 0),
        "new": stats["new_this_run"], "boards": stats["boards_total"],
        "ok_rate": stats["fetch_success_rate"], "secs": stats["duration_seconds"],
    }, ensure_ascii=False)
    _append_lines(paths.HISTORY_PATH, [line], _HISTORY_KEEP)
