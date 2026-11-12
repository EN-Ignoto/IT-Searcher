# Methodology

What each thing on the list claims, and how it is decided. Every rule lives in
[`src/intern_engine/filters_it.py`](src/intern_engine/filters_it.py) and
[`src/intern_engine/geo.py`](src/intern_engine/geo.py).

## Who the list is for

A reader with Network+ and Security+, retail and customer-service experience,
studying computer science, with no professional IT experience. Home is
Kissimmee, Florida.

## The four questions every posting is asked

1. **Is the title an entry path into IT?** Help desk / service desk, desktop and
   end-user support, IT technician and IT support, junior network, NOC, systems
   and data-center work, entry security (SOC analyst, security intern), IT
   operations, and IT internships. Titles that name a support job without saying
   it is an IT one ("Support Technician") are kept only when the posting text
   uses at least four distinct IT-support terms.
2. **Is it senior?** Senior, lead, manager, architect, principal and level III+
   titles are dropped. A title offering several levels ("Technician I/II/III")
   counts at its lowest.
3. **Can the reader work there?** See *Sections* below.
4. **Does the posting require something the reader lacks?** Judged from the
   posting's own text, never from the title. See *Fit*.

## Sections

| Section | Meaning |
|---|---|
| **Local** | 30 miles or less from Kissimmee City Hall, straight-line distance |
| **Nearby** | more than 30 and up to 50 miles |
| **Remote** | the posting is remote and open to Florida residents |

Distance uses the coordinates the source publishes when it has them (NLx, the
school district). Otherwise the location text is matched against a closed table
of about 110 Central Florida places. A place that is not in the table is *not
placed*, which is different from far away, and the role is treated as not local
instead of guessed. Single-site local employers whose location is a building
name ("City Hall") are placed at the employer's own town.

A remote role is kept when its location says United States, nationwide,
Florida, or just "Remote". "Remote - Texas" is not listed. If the posting text
restricts residence to a list of states that leaves Florida out, it is dropped.
A role that is both local and remote is listed under Local with a
"remote option" marker. Local always outranks Remote.

## Fit

Only **required** years of **IT** experience can exclude a role. The posting is
read line by line, tracking whether a line sits under a "Required" or a
"Preferred" heading; wording inside the line ("preferred", "a plus", "must
have") overrides the heading.

| What the posting requires | Result |
|---|---|
| Nothing, or experience is only preferred | **Beginner-friendly**; preferred years shown as a note |
| Under 2 years | **Stretch** |
| 2 years, with "or equivalent education / certifications" | **Stretch** |
| 2 years, no substitute | not listed |
| 3 years or more | not listed |
| Years of customer-service, retail or call-center experience | listed; shown as a note |

Also not listed: unpaid internships, internships for graduate students only,
roles that need an **active** security clearance (the ability to obtain one is
only a note), and non-internship roles that require a bachelor's degree with no
"or equivalent" wording. A level II title with nothing stated is a Stretch.

**Check requirements** means the posting text could not be read. Those roles
are listed only when the title is plainly entry level, and they are re-read
once a day.

## What gets logged

Every IT-titled role that was considered and dropped is written to
[`data/rejected.jsonl`](data/rejected.jsonl) with the reason and the posting's
own sentence. Titles that are simply not IT, and jobs outside the area, are
counted in `data/stats.json` but not listed line by line.

## Open and closed

A role is marked closed only after it is missing from **two consecutive
complete readings** of its board. A failed request, or a search that was cut
off by a result cap, closes nothing. For capped boards the posting page itself
is asked (Workday), and anything not seen for 14 days is retired. A role our
own rules stop accepting is closed immediately.

## Dates

"Nov 3" is the date the employer published. "~Nov 3" is derived from text such
as "Posted 1 week ago". "found Nov 3" means the source gave no date and that is
when the engine first saw it. Postings older than 120 days are dropped.

## What this project does not do

It does not apply to jobs, fill in forms, create accounts or contact employers.
It reads public postings and publishes a list of links.
