# Contributing

## Add a local employer

Local sources live in [`data/local_sources.json`](data/local_sources.json) and are
read every 30 minutes. See "Adding a local source" in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Change what counts as a beginner role

All rules are in [`src/intern_engine/filters_it.py`](src/intern_engine/filters_it.py).
Bump `VERSION` when a change should re-read every stored posting, and add a test
in `tests/test_filters_it.py` using a real title or posting sentence that used to
be judged wrong. [`data/rejected.jsonl`](data/rejected.jsonl) shows what the
current rules drop.

## Before opening a pull request

```bash
pip install -r requirements-dev.txt
python -m pytest -q
ruff check src tests tools run.py
```
