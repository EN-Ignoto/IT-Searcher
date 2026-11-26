# Architecture

One Python package, no database, no server. GitHub Actions runs it on a
schedule, commits the results, and GitHub Pages serves `docs/`.

```
data/local_sources.json ─┐
                         ├─► connectors ─► title ─► place ─► posting text ─► assess ─► store ─► README, docs/
data/companies.json ─────┘   (fetch)       filters_it + geo  (enrich)       filters_it  jobs.json
        (full sweep only)
```

## Two schedules, one pipeline

| Run | Reads | When |
|---|---|---|
| `python run.py update` | `data/local_sources.json`: NLx within 50 miles of Kissimmee, 11 NEOGOV agencies, Valencia College, UCF, City of Orlando | every 30 minutes |
| `python run.py update --full` | the above plus `data/companies.json` (about 5,400 employer boards) | every 6 hours |

Both are the one workflow in `.github/workflows/update.yml`. A run closes roles
only on boards it actually read, so local runs never touch what the last sweep
found.

## Modules (`src/intern_engine/`)

| Module | Job |
|---|---|
| `connectors/` | One file per source. Each returns `models.Fetch`: normalized `Job`s plus whether the answer was the board's complete list. |
| `connectors/nlx.py` | National Labor Exchange search API, phrase queries around one place. Jobs carry coordinates, date and full text. |
| `connectors/neogov.py` | governmentjobs.com agency listings (HTML fragments). |
| `connectors/paradox.py` | Paradox career sites (Osceola schools; currently refused by the site). |
| `connectors/peopleadmin.py` | PeopleAdmin Atom feed (Valencia College). |
| `connectors/workday.py` | Workday. `"whole": true` reads a small tenant end to end; otherwise keyword searches from `terms.py`. |
| `net.py` | HTTP with retries, backoff and per-host concurrency caps. |
| `filters_it.py` | The profile as code: title rules, experience reading, employment type, remote eligibility. |
| `geo.py` | Distance from Kissimmee; closed table of Central Florida places. |
| `enrich.py` | Fetches posting text for sources whose listings do not include it; asks a posting page whether it still exists. |
| `pagetext.py` | Extracts description and date from a job page (schema.org JSON-LD first). |
| `pipeline.py` | The run: fetch, classify, cache verdicts, merge into the store, write stats. |
| `dedup.py` | Collapses the same posting syndicated to two boards. |
| `store.py` | `data/jobs.json`: first-seen, open/closed, two-miss closure rule, retention. |
| `health.py` | Circuit breaker for registry boards that keep failing. Local sources are always retried. |
| `view.py` | Published order and labels, shared by every output. |
| `readme.py`, `dashboard.py`, `publish.py` | README + CSV, `docs/index.html`, Atom feed + JSON API. |
| `registry.py`, `discover.py`, `harvester.py` | Board registry validation and growth. |

## Data files

| File | Contents |
|---|---|
| `data/jobs.json` | Every role ever listed, open or recently closed |
| `data/assessed.json` | Verdict cache, so each posting's text is fetched once |
| `data/rejected.jsonl` | Dropped IT-titled roles with reasons (audit trail) |
| `data/stats.json` | Last run's metrics, including per-source status |
| `data/health.json`, `data/history.jsonl` | Breaker state; one line per run |

## Health alerts

`tools/health_report.py` runs after every update (failed ones included) and once a
day from `.github/workflows/watchdog.yml`. When something is wrong it opens one
GitHub issue labelled `searcher-health`, which emails the repository owner, and
updates it on later runs; when a report passes again it closes the issue. It checks:

- nothing published for 12 hours, or the publish gate rejected a run
- no nationwide sweep for 24 hours, or a sweep that read under 80% of its boards
- a local source failing 3 runs in a row
- more than 20% of one platform's boards benched by the failure breaker
- the open count halving within a week

## Safety properties

- A failed or truncated fetch is never read as "no openings", and a board that
  was not read this run (failed, throttled or benched) never retires a role.
- Local sources are read before the nationwide sweep starts, so the sweep's load
  cannot starve them.
- Workday and Oracle are limited to 8 requests at a time across all tenants;
  both throttle by caller IP.
- HTTP 429 (throttling) never benches a board, and when a quarter or more of one
  platform's boards fail in the same run, nothing on that platform is benched.
- `tools/verify_accuracy.py` runs before every commit; if any open role breaks
  a rule, nothing is published. A local-source outage does not block publishing
  (it closes nothing); the health report raises it instead.
- Third-party text is HTML-escaped on the page and formula-escaped in the CSV.
- The engine only issues read requests to public job listings.

## Adding a local source

Add an entry to `data/local_sources.json`. For a NEOGOV agency that is one line:

```json
{"name": "City of Example", "slug": "examplefl", "ats": "neogov", "fallback_place": "Orlando, FL"}
```

For a new kind of site, add a connector module exposing
`async fetch(company, net) -> Fetch` and register it in `pipeline.CONNECTORS`.
