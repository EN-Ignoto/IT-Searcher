# How IT Searcher finds opportunities

IT Searcher collects employer career feeds and selected remote job feeds. It
is a partial search of the market, not a copy of LinkedIn, Handshake, Indeed,
or ZipRecruiter. Those boards can contain additional employers and postings.

## Coverage

`data/companies.json` is the employer-board registry. Every scheduled collection
scans the complete registry using the full collection and publication workflow
from `ihrtkaii/test-1`. There is no separate priority workflow competing with it.
The configured upstream schedule is at minutes 7 and 37 of every third hour
(UTC); GitHub may delay runs. The latest collection size, success rate, and
publication timestamp are shown in the dashboard. See `UPSTREAM.md` for the
pinned upstream commit and the personal scope adaptations.

Workday, Oracle and SmartRecruiters use internship/co-op queries plus IT queries
including help desk, service desk, desktop support, technical support, computer
technician, network technician, information technology, systems administrator,
IT operations, junior and entry level. Search results are unioned by posting ID.
Other supported employer feeds return their listings through their connectors.

## Which roles appear

The tracker seeks first-job IT support, operations, networking, systems, cloud,
and security opportunities, plus paid IT internships. Title matching excludes
senior titles and unrelated fields. Requirements are read before publication:
required professional IT experience, completed degrees explicitly required
without student wording, unpaid roles and unreadable requirements are excluded.
Two years preferred can remain a possible stretch. These rules are heuristics;
read the employer's requirements and confirm schedule before applying.

Local matching uses named cities around Orlando and Kissimmee. It is not a
measured commute radius. Remote roles need US or Florida location evidence;
confirm that the employer hires Florida residents. Local opportunities appear
first in the default sort, with newest postings first within each group.

## Dates and removal

The feed uses a 270-day window. A posting does not become closed merely because
it is older than 30 days. The 48-hour and other age filters let users focus on
recently posted roles. Undated postings use first discovery for windowing.
Dates come from the source where available; first detection is separate.

Two consecutive complete employer-feed snapshots that omit a posting can close
it as `gone-from-feed`. Capped or incomplete responses cannot establish closure.
A role that fails the scope or age rules is marked `out-of-scope`; this does not
mean the employer closed it. Always confirm availability on the apply page.

## Source restrictions and duplicates

All active source adapters read employer boards. Third-party remote aggregator
feeds have been removed.
Separate requisitions remain separate. The same proven requisition can be
collapsed across career-site aliases, while identical titles at different
locations are preserved. Cross-provider duplicates may still appear.

## Other labels

Salary and skill tags are extracted from posting text. Sponsorship verdicts are
phrase matches, and unknown means no conclusive statement was found. The H-1B
badge reflects historical employer petition approvals, not eligibility for the
particular posting. Employer text remains authoritative for every application.
