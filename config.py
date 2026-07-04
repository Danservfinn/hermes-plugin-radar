"""Radar configuration loading, validation, and defaults."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


def get_hermes_home() -> Path:
    """Resolve HERMES_HOME, accounting for profile-scoped paths."""
    home = os.environ.get("HERMES_HOME")
    if home:
        return Path(home)
    # Check for profile-scoped path
    profile = os.environ.get("HERMES_PROFILE", "")
    if profile:
        return Path.home() / ".hermes" / "profiles" / profile
    return Path.home() / ".hermes"


def get_config_path() -> Path:
    """Path to radar_config.yaml."""
    return get_hermes_home() / "radar_config.yaml"


DEFAULT_CONFIG: dict[str, Any] = {
    "radar": {
        "artifact_root": None,  # Set during init; defaults to {HERMES_HOME}/radar
        "default_mode": "morning",
        "calendar": {
            "enabled": False,
            "calendar_id": "primary",
            "autonomous_create": False,
            "autonomous_delete_own": False,
            "max_events_per_run": 5,
            "max_deletes_per_run": 3,
            "lookahead_hours": 96,
            "prep_window_hours": 36,
        },
        "sources": {
            "brain": {"enabled": False, "wiki_root": None},
            "email": {"enabled": False, "search_window_days": 3, "max_threads": 15},
            "calendar": {"enabled": False},
            "reminders": {"enabled": False, "horizon": "week"},
            "messages": {"enabled": False, "platforms": []},
            "finance": {"enabled": False, "adapter": "email_alerts"},
            "repos": {"enabled": False, "monitored_repos": []},
            "travel": {"enabled": False},
            "research": {"enabled": False},
            "relationships": {"enabled": False, "important_dates": []},
        },
        "authority": {
            "read_only": True,
            "draft_only": True,
            "external_send": False,
            "runtime_mutation": False,
            "financial_or_legal": False,
            "destructive": False,
        },
        "approval": {
            "grammar": "approve {number}",
            "accepted_forms": [
                "approve N",
                "approve AN",
                "approve N-M",
                "skip N",
                "defer N until {date}",
            ],
        },
        "schedule": {
            "morning": {"enabled": True, "cron": "0 7 * * *", "mode": "morning"},
            "evening": {"enabled": True, "cron": "0 19 * * *", "mode": "evening"},
            "interrupt_checker": {
                "enabled": True,
                "cron": "*/30 * * * *",
                "script": "radar_watch_sources.py",
                "deliver": "local",
            },
        },
        "metrics": {"enabled": True, "feedback_log": True},
    }
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config() -> dict[str, Any]:
    """Load radar_config.yaml, merging with defaults."""
    config_path = get_config_path()
    if not config_path.exists():
        # No config — return defaults with artifact_root set
        cfg = _deep_copy_default()
        if cfg["radar"]["artifact_root"] is None:
            cfg["radar"]["artifact_root"] = str(get_hermes_home() / "radar")
        return cfg

    if yaml is None:
        # Fallback: try json
        try:
            with open(config_path) as f:
                user_cfg = json.load(f)
        except Exception:
            user_cfg = {}
    else:
        try:
            with open(config_path) as f:
                user_cfg = yaml.safe_load(f) or {}
        except Exception:
            user_cfg = {}

    # Merge user config over defaults
    merged = deep_merge(_deep_copy_default(), user_cfg)

    # Ensure artifact_root is set
    if merged["radar"].get("artifact_root") is None:
        merged["radar"]["artifact_root"] = str(get_hermes_home() / "radar")

    # Expand ~ in paths
    ar = merged["radar"].get("artifact_root")
    if ar:
        merged["radar"]["artifact_root"] = os.path.expanduser(ar)

    wr = merged["radar"]["sources"]["brain"].get("wiki_root")
    if wr:
        merged["radar"]["sources"]["brain"]["wiki_root"] = os.path.expanduser(wr)

    return merged


def validate_config(config: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a Radar config. Returns (is_valid, list_of_errors)."""
    errors: list[str] = []

    if "radar" not in config:
        errors.append("Missing top-level 'radar' key")
        return False, errors

    r = config["radar"]

    # artifact_root
    ar = r.get("artifact_root")
    if ar:
        p = Path(ar)
        if not p.parent.exists():
            errors.append(f"artifact_root parent directory does not exist: {p.parent}")

    # authority
    auth = r.get("authority", {})
    if not auth.get("read_only", False):
        errors.append("read_only should be True — Radar needs read access to function")

    # calendar
    cal = r.get("calendar", {})
    if cal.get("enabled") and cal.get("autonomous_create"):
        if not cal.get("calendar_id"):
            errors.append("calendar.calendar_id must be set when calendar is enabled")

    # sources — at least one should be enabled
    sources = r.get("sources", {})
    enabled_count = sum(1 for s in sources.values() if isinstance(s, dict) and s.get("enabled"))
    if enabled_count == 0:
        errors.append("No sources enabled — Radar needs at least one source adapter")

    return len(errors) == 0, errors


def save_config(config: dict[str, Any]) -> Path:
    """Save config to radar_config.yaml."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if yaml is None:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    else:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return config_path


def get_artifact_root(config: dict[str, Any] | None = None) -> Path:
    """Get the artifact root path from config."""
    if config is None:
        config = load_config()
    return Path(config["radar"]["artifact_root"])


def _deep_copy_default() -> dict[str, Any]:
    """Deep copy the default config."""
    return json.loads(json.dumps(DEFAULT_CONFIG))
