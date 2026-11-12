"""Tunable settings, loaded from data/config.json (with safe defaults).

  - local_radius_miles  : "Local" means this close to Kissimmee (default 30)
  - nearby_radius_miles : "Nearby" reaches this far (default 50)
  - max_age_days        : drop postings published longer ago than this
  - new_hours           : how long a role keeps its "new" marker
"""

from __future__ import annotations

import json
import os
import re

from . import paths

DEFAULTS = {
    "local_radius_miles": 30,
    "nearby_radius_miles": 50,
    "max_age_days": 120,
    "new_hours": 72,
}

_FALLBACK_REPO = "EN-Ignoto/IT-Searcher"


class ConfigError(RuntimeError):
    """Configuration exists but has the wrong shape. Deliberately fatal: a bad
    radius silently replaced by a default would publish the wrong area."""


def repo_slug() -> str:
    """"owner/name" for this repo: from Actions env, else the git remote."""
    env = os.environ.get("GITHUB_REPOSITORY")
    if env and "/" in env:
        return env
    try:
        with open(os.path.join(paths.ROOT, ".git", "config"), encoding="utf-8") as f:
            m = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?\s", f.read())
            if m:
                return m.group(1)
    except OSError:
        pass
    return _FALLBACK_REPO


def pages_base() -> str:
    """The GitHub Pages base URL serving docs/."""
    owner, _, name = repo_slug().partition("/")
    return f"https://{owner.lower()}.github.io/{name}"


def validate_config(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError(f"config must be an object, got {type(raw).__name__}")
    cfg = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}
    for field, low, high in (("local_radius_miles", 1, 100),
                             ("nearby_radius_miles", 1, 150),
                             ("max_age_days", 0, 3650), ("new_hours", 1, 720)):
        value = cfg[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{field} must be a number")
        if not low <= value <= high:
            raise ConfigError(f"{field} must be between {low} and {high}")
    if cfg["nearby_radius_miles"] < cfg["local_radius_miles"]:
        raise ConfigError("nearby_radius_miles must be at least local_radius_miles")
    return cfg


def load_config() -> dict:
    if not os.path.exists(paths.CONFIG_PATH):
        return validate_config(DEFAULTS)
    try:
        with open(paths.CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"{paths.CONFIG_PATH} is unreadable: {exc}") from exc
    return validate_config(raw)
