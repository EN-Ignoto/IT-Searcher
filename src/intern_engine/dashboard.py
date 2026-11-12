"""The public page (docs/index.html): one static file, no build step.

Roles are rendered into the HTML on the server side, so the page is complete
without JavaScript; the script only filters what is already there.
"""

from __future__ import annotations

import os
from html import escape

from . import config, filters_it, geo, paths, view

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16202b;--muted:#5b6876;--line:#dde2e8;
--accent:#0b6bcb;--accent-ink:#fff;--good:#11734b;--good-bg:#e2f5ec;--warn:#8a5a00;
--warn-bg:#fdf1d6;--unk:#55606c;--unk-bg:#e9edf1;--new:#b3261e;--chip:#eef1f5}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--card:#19212a;--ink:#e8edf2;
--muted:#9aa7b4;--line:#2b3642;--accent:#6fb3ff;--accent-ink:#0b1622;--good:#7fdcae;
--good-bg:#12382a;--warn:#f2c867;--warn-bg:#40300c;--unk:#b4bfca;--unk-bg:#27313c;
--new:#ff8a80;--chip:#232d38}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.wrap{max-width:980px;margin:0 auto;padding:0 16px}
header{padding:28px 0 8px}
h1{font-size:1.7rem;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0;max-width:62ch}
.asof{color:var(--muted);font-size:.88rem;margin:10px 0 0}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0 12px}
.tab{border:1px solid var(--line);background:var(--card);color:var(--ink);
border-radius:999px;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer}
.tab b{font-variant-numeric:tabular-nums;color:var(--muted);font-weight:600;margin-left:4px}
.tab[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.tab[aria-pressed=true] b{color:inherit}
.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 6px}
.filters input,.filters select{font:inherit;padding:8px 10px;border:1px solid var(--line);
border-radius:8px;background:var(--card);color:var(--ink);min-width:0}
.filters input{flex:1 1 220px}
.count{color:var(--muted);font-size:.9rem;margin:8px 0 0}
h2{font-size:1.15rem;margin:28px 0 2px}
.blurb{color:var(--muted);font-size:.9rem;margin:0 0 12px}
.job{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:14px 16px;margin:0 0 10px}
.job h3{font-size:1.05rem;margin:0 0 2px;line-height:1.3}
.job h3 a{text-decoration:none}
.job h3 a:hover{text-decoration:underline}
.meta{color:var(--muted);font-size:.92rem;margin:0}
.meta strong{color:var(--ink);font-weight:600}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 0;padding:0;list-style:none}
.tags li{font-size:.8rem;padding:3px 9px;border-radius:999px;background:var(--chip);
color:var(--ink)}
.tags .beginner{background:var(--good-bg);color:var(--good);font-weight:600}
.tags .stretch{background:var(--warn-bg);color:var(--warn);font-weight:600}
.tags .unverified{background:var(--unk-bg);color:var(--unk);font-weight:600}
.new{color:var(--new);font-size:.75rem;font-weight:700;letter-spacing:.04em;
text-transform:uppercase;margin-left:8px;white-space:nowrap}
.exp{margin:10px 0 0;font-size:.93rem}
.quote{margin:6px 0 0;padding-left:10px;border-left:3px solid var(--line);
color:var(--muted);font-size:.86rem;overflow-wrap:anywhere}
.empty{color:var(--muted);padding:14px 0}
[hidden]{display:none!important}
footer{color:var(--muted);font-size:.86rem;margin:36px 0 40px;border-top:1px solid var(--line);
padding-top:16px}
details{margin:10px 0}
.srcs{width:100%;border-collapse:collapse;font-size:.84rem;margin-top:8px}
.srcs td,.srcs th{text-align:left;padding:4px 8px 4px 0;border-bottom:1px solid var(--line);
vertical-align:top}
.scroll{overflow-x:auto}
.bad{color:var(--new)}
"""

_JS = """
(function(){
var section='all',q=document.getElementById('q'),fit=document.getElementById('fit'),
kind=document.getElementById('kind'),tabs=document.querySelectorAll('.tab'),
jobs=document.querySelectorAll('.job'),count=document.getElementById('count');
function apply(){
 var text=(q.value||'').toLowerCase().trim(),shown=0,per={};
 jobs.forEach(function(el){
  var ok=(section==='all'||el.dataset.section===section)&&
   (!fit.value||el.dataset.fit===fit.value)&&
   (!kind.value||el.dataset.kind===kind.value)&&
   (!text||el.dataset.text.indexOf(text)>-1);
  el.hidden=!ok;if(ok){shown++;per[el.dataset.section]=(per[el.dataset.section]||0)+1;}
 });
 document.querySelectorAll('section[data-section]').forEach(function(s){
  var name=s.dataset.section;
  s.hidden=section!=='all'&&section!==name;
  s.querySelector('.empty').hidden=!!per[name];
 });
 count.textContent=shown+' of '+jobs.length+' roles shown';
}
tabs.forEach(function(t){t.addEventListener('click',function(){
 section=t.dataset.section;
 tabs.forEach(function(o){o.setAttribute('aria-pressed',o===t?'true':'false');});
 apply();});});
[q,fit,kind].forEach(function(el){el.addEventListener('input',apply);});
apply();
})();
"""


def _job(record: dict, as_of, new_hours: float) -> str:
    fit = record.get("fit") or filters_it.FIT_UNVERIFIED
    employment = record.get("employment") or "Not stated"
    tags = [f'<li class="{escape(fit)}">{escape(view.FIT_LABEL.get(fit, fit))}</li>']
    if employment != "Not stated":
        tags.append(f"<li>{escape(employment)}</li>")
    tags.append(f"<li>{escape(record.get('category') or 'IT')}</li>")
    if record.get("salary"):
        tags.append(f"<li>{escape(record['salary'])}</li>")
    tags += [f"<li>{escape(note)}</li>" for note in record.get("notes") or []]
    new = '<span class="new">New</span>' if view.is_new(record, as_of, new_hours) else ""
    evidence = (record.get("evidence") or "").strip()
    quote = f'<p class="quote">“{escape(evidence)}”</p>' if evidence else ""
    experience = record.get("experience") or ""
    haystack = " ".join(str(record.get(k) or "") for k in
                        ("title", "company", "location", "category")).lower()
    source = view.SOURCE_LABEL.get(record.get("source"), record.get("source") or "")
    return (
        f'<article class="job" data-section="{escape(record.get("section") or "")}" '
        f'data-fit="{escape(fit)}" data-kind="{escape(employment)}" '
        f'data-text="{escape(haystack)}">'
        f'<h3><a href="{escape(record.get("url") or "#")}" rel="noopener noreferrer" '
        f'target="_blank">{escape(record.get("title") or "")}</a>{new}</h3>'
        f'<p class="meta"><strong>{escape(record.get("company") or "")}</strong> · '
        f'{escape(view.where(record))} · {escape(view.posted_label(record))}'
        f'{" · via " + escape(source) if source else ""}</p>'
        f'<ul class="tags">{"".join(tags)}</ul>'
        + (f'<p class="exp">{escape(experience)}</p>' if experience else "")
        + quote + "</article>"
    )


def _sources(stats: dict) -> str:
    rows = []
    for board in stats.get("local_sources") or []:
        error = board.get("error")
        status = f'<span class="bad">failed: {escape(str(error)[:90])}</span>' if error \
            else ("read in full" if board.get("complete") else "read in part")
        rows.append(f"<tr><td>{escape(str(board.get('name')))}</td><td>{status}</td>"
                    f"<td>{board.get('jobs', 0)}</td><td>{board.get('kept', 0)}</td></tr>")
    if not rows:
        return ""
    full = stats.get("last_full") or {}
    sweep = ""
    if full:
        sweep = (f"<p>Last nationwide sweep: {escape(str(full.get('fetched_at', '')))} — "
                 f"{full.get('fetched_ok', 0)} of {full.get('boards_total', 0)} boards read, "
                 f"{full.get('jobs_seen', 0)} postings examined.</p>")
    return ("<details><summary>Sources read on the last run</summary>"
            '<div class="scroll"><table class="srcs"><thead><tr><th>Local source</th>'
            "<th>Status</th><th>Postings</th><th>Listed</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>" + sweep + "</details>")


def generate(store_data: dict, stats: dict) -> None:
    cfg = config.load_config()
    as_of = view.parse_ts(stats.get("fetched_at") or stats.get("generated_at")) \
        or view.parse_ts("1970-01-01T00:00:00Z")
    sections = view.open_by_section(store_data)
    total = sum(len(v) for v in sections.values())
    radii = {"local": cfg["local_radius_miles"], "nearby": cfg["nearby_radius_miles"]}
    kinds = sorted({r.get("employment") or "Not stated"
                    for rows in sections.values() for r in rows})

    tabs = [f'<button class="tab" type="button" data-section="all" aria-pressed="true">'
            f"All<b>{total}</b></button>"]
    body = []
    for name in filters_it.SECTIONS:
        rows = sections[name]
        tabs.append(f'<button class="tab" type="button" data-section="{name}" '
                    f'aria-pressed="false">{name}<b>{len(rows)}</b></button>')
        body.append(
            f'<section data-section="{name}"><h2>{name} ({len(rows)})</h2>'
            f'<p class="blurb">{escape(view.SECTION_BLURB[name].format(**radii))}</p>'
            + "".join(_job(r, as_of, cfg["new_hours"]) for r in rows)
            + f'<p class="empty"{" hidden" if rows else ""}>No open roles here right now.</p>'
            "</section>")

    repo = f"https://github.com/{config.repo_slug()}"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IT Searcher — entry-level IT jobs near {escape(geo.HOME_NAME)}</title>
<meta name="description" content="Entry-level IT jobs and paid IT internships within 50 miles of Kissimmee, FL, plus remote roles open to Florida.">
<link rel="alternate" type="application/atom+xml" href="feed.xml" title="New roles">
<style>{_CSS}</style></head><body><div class="wrap">
<header><h1>Entry-level IT jobs near {escape(geo.HOME_NAME)}</h1>
<p class="sub">Help desk, desktop support, IT technician, junior network and security roles,
and paid IT internships. Local jobs first, then remote roles open to Florida residents.</p>
<p class="asof">Updated {as_of.strftime('%b %d, %Y at %H:%M UTC')} · {total} open roles ·
every link opens the employer's own posting</p></header>
<div class="tabs" role="group" aria-label="Area">{''.join(tabs)}</div>
<div class="filters">
<input id="q" type="search" placeholder="Search title, employer or city" aria-label="Search">
<select id="fit" aria-label="Fit"><option value="">Any fit</option>
<option value="beginner">Beginner-friendly</option><option value="stretch">Stretch</option>
<option value="unverified">Check requirements</option></select>
<select id="kind" aria-label="Job type"><option value="">Any type</option>
{''.join(f'<option value="{escape(k)}">{escape(k)}</option>' for k in kinds)}</select>
</div><p class="count" id="count" aria-live="polite"></p>
<main>{''.join(body)}</main>
<footer>
<p><strong>Beginner-friendly</strong> means nothing in the posting requires IT experience.
<strong>Stretch</strong> means about a year is required, education or certifications may
substitute, or the title is a level II. <strong>Check requirements</strong> means the posting
text could not be read. Preferred experience never hides a role.</p>
<p>This site only lists jobs. It never applies or contacts employers for you.</p>
{_sources(stats)}
<p><a href="jobs.csv">CSV</a> · <a href="api/jobs.json">JSON</a> ·
<a href="feed.xml">Feed</a> · <a href="{escape(repo)}">Source and method</a></p>
</footer></div><script>{_JS}</script></body></html>
"""
    os.makedirs(os.path.dirname(paths.DASHBOARD_PATH), exist_ok=True)
    with open(paths.DASHBOARD_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
