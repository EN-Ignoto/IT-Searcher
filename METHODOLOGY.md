# How IT Searcher finds opportunities

IT Searcher collects employer career feeds and selected remote job feeds. It
is a partial search of the market, not a copy of LinkedIn, Handshake, Indeed,
or ZipRecruiter. Those boards can contain additional employers and postings.

## Coverage

`data/companies.json` is the board registry. The full workflow scans that
registry every four hours. The frequent workflow checks a smaller priority set
of Orlando-area employers and remote sources between full sweeps. GitHub can
delay scheduled runs. The dashboard reports the size of the latest collection
separately from the registry size; a small priority scan does not mean that the
full registry contains only that many boards.

Workday, Oracle and SmartRecruiters use internship/co-op queries plus IT queries
including help desk, service desk, desktop support, technical support, computer
technician, network technician, information technology, systems administrator,
IT operations, junior and entry level. Search results are unioned by posting ID.
Other supported employer feeds return their listings through their connectors.

## Which roles appear

The tracker seeks first-job IT support, operations, networking, systems, cloud,
and security opportunities, plus paid IT internships. Title matching excludes
senior titles and unrelated fields. Requirements are read before publication:
mandatory experience of two or more years, completed degrees explicitly required
without student wording, unpaid roles and unreadable requirements are excluded.
Two years preferred can remain a possible stretch. These rules are heuristics;
read the employer's requirements and confirm schedule before applying.

Local matching uses named cities around Orlando and Kissimmee. It is not a
measured commute radius. Remote roles need US or Florida location evidence;
confirm that the employer hires Florida residents. Local opportunities appear
first in the default sort, with newest postings first within each group.

## Dates and removal

The feed uses a 120-day window. A posting does not become closed merely because
it is older than 30 days. The 48-hour and other age filters let users focus on
recently posted roles. Undated postings use first discovery for windowing.
Dates come from the source where available; first detection is separate.

Two consecutive complete employer-feed snapshots that omit a posting can close
it as `gone-from-feed`. Capped or incomplete responses cannot establish closure.
A role that fails the scope or age rules is marked `out-of-scope`; this does not
mean the employer closed it. Always confirm availability on the apply page.

## Source restrictions and duplicates

Some remote roles come from Himalayas and Jobicy. Himalayas roles are displayed
on the dashboard and omitted from redistributed CSV, RSS and JSON exports.
Separate requisitions remain separate. The same proven requisition can be
collapsed across career-site aliases, while identical titles at different
locations are preserved. Cross-provider duplicates may still appear.

## Other labels

Salary and skill tags are extracted from posting text. Sponsorship verdicts are
phrase matches, and unknown means no conclusive statement was found. The H-1B
badge reflects historical employer petition approvals, not eligibility for the
particular posting. Employer text remains authoritative for every application.
