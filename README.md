# IT Searcher

Entry-level IT jobs and paid IT internships near **Kissimmee, FL**, plus remote roles open to Florida residents. Rebuilt automatically from employers' own postings; every link goes to the posting itself.

**[Open the live list →](https://en-ignoto.github.io/IT-Searcher/)** · [CSV](https://en-ignoto.github.io/IT-Searcher/jobs.csv) · [JSON](https://en-ignoto.github.io/IT-Searcher/api/jobs.json) · [Feed](https://en-ignoto.github.io/IT-Searcher/feed.xml)

_Data as of Nov 12, 2026 08:04 UTC · 0 open roles: 0 local, 0 nearby, 0 remote._

This project only finds and lists jobs. It never applies, submits forms, or contacts employers on your behalf.

## Who the list is for

Someone starting in IT: Network+ and Security+, customer-service experience, studying computer science, no professional IT experience yet. A role is listed when its title is an entry path into IT (help desk, desktop support, IT technician, junior network/systems/security work, paid IT internships), it is not senior, and the posting's own text does not *require* experience a beginner lacks. "Preferred" experience never excludes a role; it is shown as a note.

- **Beginner-friendly**: nothing in the posting requires IT experience.
- **Stretch**: about a year is required, a requirement may be met by education or certifications, or the title is a level II.
- **Check requirements**: the posting text could not be read; open it before applying.

## Local (0)

_Within 30 miles of Kissimmee._

No open roles right now.

## Nearby (0)

_30 to 50 miles from Kissimmee._

No open roles right now.

## Remote (0)

_Remote, and open to Florida residents._

No open roles right now.

## How it works

- **Local sources, every 30 minutes**: the National Labor Exchange (NLx) within 50 miles of Kissimmee, eleven city and county governments on GovernmentJobs, the School District of Osceola County, UCF and the City of Orlando.
- **Nationwide sweep, every 6 hours**: about 5,400 employer job boards, which is where the remote roles come from.
- Roles that were considered and dropped are logged with the reason in [`data/rejected.jsonl`](data/rejected.jsonl).
- A role is marked closed only after it is missing from two complete readings of its board in a row.

See [METHODOLOGY.md](METHODOLOGY.md) for the rules and [ARCHITECTURE.md](ARCHITECTURE.md) for the code.
