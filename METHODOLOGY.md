# Methodology

How every number on this list is produced, and what each one does and doesn't
claim. If something here doesn't match what the code does, that's a bug —
[open an issue](../../issues/new/choose).

## Where roles come from

Every role is read directly from the employer's own applicant tracking system
(ATS) — Greenhouse, Lever, Ashby, Workday, Oracle, SmartRecruiters, Workable,
Breezy, Recruitee, Rippling, Eightfold, and Amazon's jobs API. There are no
aggregator links, no scraped third-party lists, and no roles copied from other
GitHub repos. The **Apply** link is the employer's URL.

The registry of boards to poll (`data/companies.json`) is built by
`run.py discover` + `run.py harvest`, which probe candidate ATS slugs and keep
the ones that respond.

## What counts as a role we list

A posting must pass all of:

1. **It is a beginner IT role or paid IT internship** — help desk, desktop support, IT support, junior networking, systems, infrastructure, or related IT operations. Senior and unrelated titles are excluded.
2. **The requirements fit a first IT job** — readable job descriptions are checked for prior professional IT experience, unpaid work, existing clearances, and other hard barriers. Unknown requirements are held out of the published list.
3. **It is local or eligible remote work** — Orlando-area locations or remote roles available in Florida/the US.
4. **It belongs to a location section** — `Orlando area` or `Remote — Florida / US`. These labels describe location, not a hiring season.

The collector, dashboard, employer registry, discovery, retries, and publication workflow are copied from [ihrtkaii/test-1](https://github.com/ihrtkaii/test-1). The role profile changes which opportunities pass the filters and which search terms adapters submit. Applications remain on the employer's website.

## Dates

`posted_at` is the employer's own publication date wherever the board exposes
one. Each date carries a `posted_at_source` describing how good it is:

| `posted_at_source` | Meaning |
|---|---|
| `exact` | A real timestamp from the source. |
| `date_only` | The source published a calendar day, no clock time. |
| `relative_derived` | Computed from relative text ("Posted 6 Days Ago"). Approximate; superseded automatically when the detail page yields a real date. |

A role's date is frozen the first time we see it, so the list behaves like a
ladder. The **one** exception is precision: a higher-precision date replaces a
lower-precision one for the same role. It never regresses.

**Detection latency** (in Engine health) measures minutes between publication
and our first sight of a role. It counts only roles *published inside the
window* and only those with an `exact` timestamp — a `date_only` date would
invent up to 24 hours of fake latency. Both p50 and p95 are published with the
sample size, because a median alone hides the tail.

## Open vs closed

A role is closed for one of two reasons, recorded in `closed_reason`:

- **`gone-from-feed`** — **two consecutive** complete reads of the employer's
  board no longer return it. One miss only arms the closure (ATS search indexes
  have transient gaps); the second fires it. Strong evidence the posting is
  gone; not the same as the employer telling us so.
- **`out-of-scope`** — it's still posted, but it no longer passes our filters
  (wrong country, off-cycle, not a tech internship). Our verdict, not theirs.

Several ATS cap how many search results they return. A capped response looks
identical to "this company has no more roles", so every connector reports
whether its snapshot was **complete**, and a partial snapshot is never allowed
to close anything. Typically ~90 of ~3,450 boards hit a cap on a given run;
their roles simply carry over.

## Visa sponsorship

Detected from the posting's own text by phrase matching, never inferred from the
company. Four verdicts:

| Verdict | Meaning |
|---|---|
| `citizens-only` 🇺🇸 | Requires US citizenship, a clearance, or ITAR/US-person status. |
| `no-sponsorship` 🛂 | The posting says it won't sponsor a work visa. |
| `offers` | The posting explicitly says sponsorship is available. |
| `unknown` | The text says nothing conclusive. **This is most postings.** |

The dashboard filter names each verdict separately on purpose. An earlier
"F-1 friendly" toggle merely *hid* the explicit negatives, so ~97% of what it
returned was actually `unknown` — presented as if it had been checked. It
hadn't.

The classifier is versioned. When its rules change, every stored verdict from an
older version is re-derived from the posting text, so improvements reach the
whole live list rather than only roles found after the change.

## The ✓ H-1B badge

✓ means USCIS approved a meaningful number of H-1B petitions for that employer
in the published fiscal-year window, matched against the public
[H-1B Employer Data Hub](https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub).

It is **a history, not a promise**. It says nothing about internship
sponsorship, about current policy, or about this specific role. No ✓ only means
we couldn't confidently match the employer.

## Drop Radar

A forecast of when companies usually open, from two sources:

- **🎯 verified** — the engine observed the drop itself from the company's
  careers API. `data/observed.json` records, per company and cycle, the earliest
  date seen *and the distinct role ids behind it*, so the sample count is
  auditable rather than a counter that inflates every run.
- **typical window** — a hand-verified opening *month* for a marquee name.
  A month, not a promise of a day.

"Waiting" means we haven't seen it in *our tracked feeds*, not that it isn't
posted somewhere. Only roles whose cycle the employer stated become
observations; a guess is never projected forward as if it were fact.

## "N openings" on a row

Employers really do open the same job several times. Copart currently has eight
live `Software Engineering Intern` requisitions for Dallas; GDIT filed
RQ225450, RQ225456 and RQ225469 for one Annapolis Junction role in a single
morning. Each one is a separate requisition with its own id and its own
application, so none of them is a duplicate and we delete none of them.

Showing you eight identical rows is still bad reading, so a row that says
**"3 openings"** means: *this employer has three separate live requisitions for
the same title, in the same place, for the same cycle.* Every one of them is
linked from that row (`Apply`, then `#2`, `#3`, …).

What this is **not**: it is not deduplication and it never merges two things
that might be different jobs. A different location, a different work mode
(on-site vs remote), a different cycle, or a closed-vs-open pair are always
separate rows. The only thing folded is an exact repeat.

The counts do not change. "165 open roles" still counts requisitions, so a row
saying "3 openings" contributes 3. The CSV and the JSON API are never grouped —
they always carry one record per requisition, with every id.

Separately, one *genuine* duplicate is removed rather than grouped: when a
company runs more than one career site on the same ATS tenant, the same
requisition can appear on both under different URLs. We collapse those only
when the ATS's own requisition number proves they are one posting.

## Counts you'll see, and what they mean

| Where | Number | Denominator |
|---|---|---|
| Hero / API | open roles | every open role in the store |
| Hero | with a stated cycle | roles whose employer named the cycle |
| README tables | "listed below" | after a per-company display cap |
| Any row | "N openings" | separate live requisitions for the same job (see above) |
| `internships.csv` | every open role | no cap, never grouped — the full export |
| Engine health | fetch success | shown against *both* boards attempted and the full registry |

## Verifying any of this yourself

```bash
python -m pytest              # the full test suite, no network
python tools/verify_accuracy.py   # every open role against every invariant
```

`verify_accuracy.py` runs in CI **before** anything is published. If it fails,
the run stops and the previous good build stays live.

## Known limitations

- Most postings never mention sponsorship, so `unknown` dominates — by design.
- Cycle inference is a heuristic; that's exactly why those roles are separated.
- The H-1B data lags by fiscal years and matches on employer name.
- Skill tags come from keyword matching over posting text and will miss things.
- We only see roles posted to the ATS platforms we support.
- Region detection reads the location string; unusual formats may be missed.
