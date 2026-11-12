"""Command-line entrypoint.

    python run.py update            # local sources only (every 30 minutes)
    python run.py update --full     # local sources + the nationwide registry
    python run.py render            # rebuild published pages from the store
    python run.py harvest           # probe curated candidates -> data/companies.json
    python run.py discover          # mine public datasets for company tokens

Nothing here applies to jobs or contacts employers: the engine reads public
postings and publishes a list.
"""

import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from intern_engine import (  # noqa: E402
    dashboard,
    paths,
    pipeline,
    publish,
    readme,
    store,
)


def _render(store_data: dict, stats: dict):
    data_as_of = stats.get("fetched_at") or stats.get("generated_at")
    if pipeline._parse_iso(data_as_of) is None:
        raise pipeline.StatsCorrupt("cannot render without a valid fetch timestamp")
    stats["rendered_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = readme.generate(store_data, data_as_of=data_as_of)
    dashboard.generate(store_data, stats)
    feed_entries = publish.write_feed(store_data, data_as_of=data_as_of)
    publish.write_api(store_data, stats)
    pipeline.write_stats(stats)
    return summary, feed_entries


def cmd_render() -> None:
    store_data = store.load(paths.JOBS_PATH)
    stats = pipeline.restat(store_data, pipeline.load_stats())
    summary, feed_entries = _render(store_data, stats)
    print(f"Rendered from the existing store: {summary}, feed entries {feed_entries}")


def cmd_update(scope: str) -> None:
    stats, store_data, new_ids = pipeline.run_update(scope)
    summary, feed_entries = _render(store_data, stats)
    print(f"Update complete ({scope}):")
    for key, value in stats.items():
        if key == "local_sources":
            continue
        print(f"  {key:<24} {value}")
    print("  local sources:")
    for board in stats["local_sources"]:
        state = f"ERROR {board['error']}" if board["error"] else (
            "complete" if board["complete"] else "partial")
        print(f"    {board['name'][:44]:<44} jobs={board['jobs']:<5} "
              f"kept={board['kept']:<3} {state}")
    print(f"  listed                   {summary}")
    print(f"  feed entries             {feed_entries}")
    print(f"  new this run             {len(new_ids)}")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "update"
    if cmd == "update":
        cmd_update("full" if "--full" in args else "local")
    elif cmd == "render":
        cmd_render()
    elif cmd in ("harvest", "discover"):
        from intern_engine import discover, harvester
        if cmd == "harvest":
            found, candidates = harvester.harvest()
            print(f"Harvested {len(found)}/{len(candidates)} candidates")
        else:
            companies, n_found = discover.discover()
            print(f"Discovered {n_found} tokens; registry has {len(companies)} boards")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
