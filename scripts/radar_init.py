#!/usr/bin/env python3
"""Radar onboarding wizard — generates radar_config.yaml interactively.

Usage:
    python scripts/radar_init.py                 # Interactive wizard
    python scripts/radar_init.py --non-interactive  # Safe auto-detect defaults
    python scripts/radar_init.py --draft-only    # Zero sources, zero schedules, draft-only
    python scripts/radar_init.py --draft-only --artifact-root /path/to/Brain/status/radar

The wizard detects available sources (Google Workspace, remindctl, etc.)
and lets you choose which to enable. All configs start read_only + draft_only.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Allow yaml import fallback
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def get_hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME")
    if home:
        return Path(home)
    profile = os.environ.get("HERMES_PROFILE", "")
    if profile:
        return Path.home() / ".hermes" / "profiles" / profile
    return Path.home() / ".hermes"


def get_brain_root() -> Path | None:
    """Detect canonical Brain root. Prefer ~/Brain over ~/brain."""
    home = Path.home()
    candidates = [
        home / "Brain",
        home / "brain",
        Path("/Users") / os.environ.get("USER", "") / "Brain",
    ]
    # Also check BRAIN_ROOT env var
    env_brain = os.environ.get("BRAIN_ROOT")
    if env_brain:
        candidates.insert(0, Path(env_brain))
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


def get_default_artifact_root() -> str:
    """Prefer Brain/status/radar if Brain exists, else HERMES_HOME/radar."""
    brain = get_brain_root()
    if brain:
        return str(brain / "status" / "radar")
    return str(get_hermes_home() / "radar")


def prompt(question: str, default: str = "") -> str:
    """Ask an open question with optional default."""
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def yes_no(question: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    try:
        answer = input(f"{question} [{suffix}]: ").strip().lower()
    except EOFError:
        answer = ""
    if not answer:
        return default
    return answer.startswith("y")


def is_macos() -> bool:
    return platform.system() == "Darwin"


def find_python3() -> str:
    """Find Python 3.10+."""
    for candidate in [
        "/opt/homebrew/opt/python@3.14/bin/python3.14",
        "/opt/homebrew/bin/python3.13",
        "/opt/homebrew/bin/python3.12",
        "/opt/homebrew/bin/python3.11",
        "/usr/local/bin/python3.11",
    ]:
        if Path(candidate).exists():
            return candidate
    return "python3"


def find_google_api() -> Path | None:
    """Find google_api.py in skill directories."""
    hh = get_hermes_home()
    candidates = [
        hh / "skills" / "productivity" / "google-workspace" / "scripts" / "google_api.py",
        Path.home() / ".hermes" / "skills" / "productivity" / "google-workspace" / "scripts" / "google_api.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def test_google_api(api_path: Path, python: str, cmd: str) -> tuple[bool, str]:
    """Test a google_api.py command."""
    try:
        result = subprocess.run(
            [python, str(api_path)] + cmd.split(),
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, result.stdout[:200]
        return False, (result.stderr[:200] if result.stderr else "Unknown error")
    except Exception as e:
        return False, str(e)[:200]


def generate_draft_only_config(artifact_root: str | None = None) -> dict:
    """Generate a minimal draft-only config with zero sources and zero schedules."""
    ar = artifact_root or get_default_artifact_root()
    return {
        "radar": {
            "artifact_root": ar,
            "default_mode": "morning",
            "bootstrap_mode": "draft_only",
            "sources_policy": "disabled_until_authorized",
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
                    "approve N", "approve AN", "approve N-M",
                    "skip N", "defer N until {date}",
                ],
            },
            "schedule": {
                "morning": {"enabled": False, "cron": "0 7 * * *", "mode": "morning"},
                "evening": {"enabled": False, "cron": "0 19 * * *", "mode": "evening"},
                "interrupt_checker": {
                    "enabled": False,
                    "cron": "*/30 * * * *",
                    "script": "radar_watch_sources.py",
                    "deliver": "local",
                },
            },
            "metrics": {"enabled": True, "feedback_log": True},
        }
    }


def generate_config(
    non_interactive: bool = False,
    artifact_root_override: str | None = None,
) -> dict:
    """Generate a Radar configuration interactively or with auto-detected defaults."""

    hh = get_hermes_home()
    is_mac = is_macos()
    python = find_python3()
    google_api = find_google_api()
    brain = get_brain_root()

    # Determine artifact root — prefer Brain, then override, then HERMES_HOME
    default_ar = str(brain / "status" / "radar") if brain else str(hh / "radar")
    artifact_root = artifact_root_override or default_ar

    # Wiki root
    wiki_root = str(brain) if brain else None

    # Source flags — all start False
    enable_email = False
    enable_calendar = False
    enable_reminders = False
    enable_repos = False
    enable_finance = False
    enable_travel = False
    enable_messages = False
    enable_relationships = False
    monitored_repos: list[str] = []
    important_dates: list[dict] = []
    autonomous_calendar = False

    # Schedule flags — all start True (interactive), False (non-interactive)
    schedule_morning = True
    schedule_evening = True
    schedule_interrupts = True

    if not non_interactive:
        print()
        print("🛡️  Radar Setup Wizard")
        print()
        print(f"This will create your Radar configuration at {hh / 'radar_config.yaml'}")
        print()
        if brain:
            print(f"📍 Detected Brain root: {brain}")
        print()

        # 1. Artifact root
        artifact_root = prompt(
            "1. Where should Radar store its artifacts?",
            artifact_root,
        )

        # 2. Wiki/notes
        if yes_no("2. Do you have a notes/wiki directory?"):
            wiki_root = prompt("   Path", wiki_root or str(Path.home() / "notes"))
            if not Path(os.path.expanduser(wiki_root)).exists():
                print(f"   ⚠️  Path does not exist yet: {wiki_root}")

        # 3. Google Workspace
        if google_api:
            print(f"\n3. Found google_api.py at {google_api}")
            if yes_no("   Test Google Workspace access?"):
                ok_email, msg_email = test_google_api(google_api, python, "gmail search newer_than:1d --max=3")
                ok_cal, msg_cal = test_google_api(google_api, python, "calendar list --max=3")

                if ok_email:
                    print(f"   ✅ Gmail: {msg_email[:80]}")
                    enable_email = True
                else:
                    print(f"   ❌ Gmail: {msg_email[:80]}")

                if ok_cal:
                    print(f"   ✅ Calendar: {msg_cal[:80]}")
                    enable_calendar = True
                else:
                    print(f"   ❌ Calendar: {msg_cal[:80]}")
        else:
            print("\n3. google_api.py not found — skipping Google Workspace setup.")
            print("   Install the google-workspace skill to enable email/calendar.")

        # 4. Reminders (macOS only)
        if is_mac:
            if shutil.which("remindctl"):
                print("\n4. ✓ remindctl found")
                enable_reminders = yes_no("   Enable Apple Reminders adapter?")
            else:
                print("\n4. remindctl not found — install it for Reminders support")

        # 5. Repos
        if yes_no("\n5. Monitor any git repos?"):
            repo_input = prompt("   Repo paths (comma-separated)")
            monitored_repos = [r.strip() for r in repo_input.split(",") if r.strip()]
            enable_repos = True

        # 6. Calendar autonomy
        if enable_calendar:
            autonomous_calendar = yes_no(
                "\n6. Should Radar create prep blocks, buffers, and reminders autonomously?",
                default=False,
            )

        # 7. Finance
        if enable_email:
            enable_finance = yes_no("\n7. Enable finance/admin sentinel (scans email for billing alerts)?")

        # 8. Travel
        enable_travel = yes_no("\n8. Enable travel concierge?")

        # 9. Schedule — capture actual answers
        print("\n9. Schedule:")
        schedule_morning = yes_no("   Morning brief at 7am?", default=True)
        schedule_evening = yes_no("   Evening brief at 7pm?", default=True)
        schedule_interrupts = yes_no("   30-min interrupt checker?", default=True)
    else:
        # Non-interactive: auto-detect what's available, no schedules
        if google_api:
            enable_email = True
            enable_calendar = True
        if is_mac and shutil.which("remindctl"):
            enable_reminders = True
        # Non-interactive = safe = no scheduled jobs
        schedule_morning = False
        schedule_evening = False
        schedule_interrupts = False

    # Build config
    config = {
        "radar": {
            "artifact_root": artifact_root,
            "default_mode": "morning",
            "calendar": {
                "enabled": enable_calendar,
                "calendar_id": "primary",
                "autonomous_create": autonomous_calendar,
                "autonomous_delete_own": autonomous_calendar,
                "max_events_per_run": 5,
                "max_deletes_per_run": 3,
                "lookahead_hours": 96,
                "prep_window_hours": 36,
            },
            "sources": {
                "brain": {
                    "enabled": wiki_root is not None,
                    "wiki_root": wiki_root,
                },
                "email": {
                    "enabled": enable_email,
                    "search_window_days": 3,
                    "max_threads": 15,
                },
                "calendar": {
                    "enabled": enable_calendar,
                },
                "reminders": {
                    "enabled": enable_reminders,
                    "horizon": "week",
                },
                "messages": {
                    "enabled": enable_messages,
                    "platforms": [],
                },
                "finance": {
                    "enabled": enable_finance,
                    "adapter": "email_alerts",
                },
                "repos": {
                    "enabled": enable_repos,
                    "monitored_repos": monitored_repos,
                },
                "travel": {
                    "enabled": enable_travel,
                },
                "research": {
                    "enabled": False,
                },
                "relationships": {
                    "enabled": enable_relationships,
                    "important_dates": important_dates,
                },
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
                    "approve N", "approve AN", "approve N-M",
                    "skip N", "defer N until {date}",
                ],
            },
            "schedule": {
                "morning": {
                    "enabled": schedule_morning,
                    "cron": "0 7 * * *",
                    "mode": "morning",
                    "deliver": "telegram",
                },
                "evening": {
                    "enabled": schedule_evening,
                    "cron": "0 19 * * *",
                    "mode": "evening",
                    "deliver": "telegram",
                },
                "interrupt_checker": {
                    "enabled": schedule_interrupts,
                    "cron": "*/30 * * * *",
                    "script": "radar_watch_sources.py",
                    "deliver": "local",
                },
            },
            "metrics": {
                "enabled": True,
                "feedback_log": True,
            },
        }
    }

    return config


def main():
    parser = argparse.ArgumentParser(description="Radar onboarding wizard")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Auto-detect sources, safe defaults, no schedules")
    parser.add_argument("--draft-only", action="store_true",
                        help="Zero sources, zero schedules, draft-only scaffolding")
    parser.add_argument("--artifact-root", type=str, default=None,
                        help="Override artifact root path")
    args = parser.parse_args()

    if args.draft_only:
        config = generate_draft_only_config(artifact_root=args.artifact_root)
    else:
        config = generate_config(
            non_interactive=args.non_interactive,
            artifact_root_override=args.artifact_root,
        )

    config_path = get_hermes_home() / "radar_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if HAS_YAML:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    else:
        # JSON fallback
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    print()
    print(f"✅ Configuration written to {config_path}")

    # Validate
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from config import validate_config
        is_valid, errors = validate_config(config)
        if is_valid:
            print("✅ Configuration is valid")
        else:
            # In draft-only/bootstrap mode, "no sources enabled" is expected
            is_bootstrap = config["radar"].get("bootstrap_mode") == "draft_only" or \
                           config["radar"].get("sources_policy") == "disabled_until_authorized"
            for e in errors:
                if "No sources enabled" in e and is_bootstrap:
                    print(f"ℹ️  {e} (expected in draft-only/bootstrap mode)")
                else:
                    print(f"⚠️  {e}")
    except Exception:
        pass

    enabled_sources = [k for k, v in config["radar"]["sources"].items() if isinstance(v, dict) and v.get("enabled")]
    enabled_schedules = [k for k, v in config["radar"]["schedule"].items() if isinstance(v, dict) and v.get("enabled")]

    print()
    print(f"Enabled sources: {', '.join(enabled_sources) or 'none'}")
    print(f"Enabled schedules: {', '.join(enabled_schedules) or 'none'}")
    print(f"Authority: read_only + draft_only (safe defaults)")
    print(f"Calendar autonomy: {'ON' if config['radar']['calendar']['autonomous_create'] else 'OFF'}")
    if config["radar"].get("bootstrap_mode"):
        print(f"Mode: {config['radar']['bootstrap_mode']}")
    print()
    print("To run your first sweep:")
    print("  /skill radar")
    print("  Then say: 'run radar morning'")
    print()
    print("Or use the tool directly:")
    print("  radar_run mode=morning")


if __name__ == "__main__":
    main()
