"""Source adapter interface and built-in adapters for Radar.

Each adapter collects raw signals from a specific source (notes/wiki, email,
calendar, reminders, repos, etc.) within a given time horizon. Adapters
gracefully handle missing credentials, wrong platforms, and unavailable CLIs
by returning a SourceResult with status='not_checked' or 'error'.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class SourceResult:
    """Result of collecting from a single source."""
    source_id: str
    domain: str
    status: str  # ok | partial | blocked_auth | disabled_by_policy | not_checked | error
    items: list[dict] = field(default_factory=list)
    adapter: str = ""
    checked_at: str = ""
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now(timezone.utc).isoformat()
        if not self.adapter:
            self.adapter = self.source_id


class SourceAdapter(ABC):
    """Base class for Radar source adapters."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def domain(self) -> str:
        ...

    @abstractmethod
    def check_requirements(self) -> bool:
        """Return True if this adapter has everything it needs."""
        ...

    @abstractmethod
    def collect(self, config: dict, horizon: dict) -> SourceResult:
        """Collect raw signals from this source within the given time horizon."""
        ...

    def safe_collect(self, config: dict, horizon: dict) -> SourceResult:
        """Wrapper that catches exceptions and returns error status."""
        try:
            if not self.check_requirements():
                return SourceResult(
                    source_id=self.name(),
                    domain=self.domain(),
                    status="not_checked",
                    error_message="Requirements not met",
                )
            return self.collect(config, horizon)
        except Exception as e:
            return SourceResult(
                source_id=self.name(),
                domain=self.domain(),
                status="error",
                error_message=str(e)[:200],
            )


class BrainAdapter(SourceAdapter):
    """Reads hot/todo/home files from a wiki/notes root."""

    def name(self) -> str:
        return "brain"

    def domain(self) -> str:
        return "notes"

    def check_requirements(self) -> bool:
        return True  # Always checkable; just may find nothing

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        src_cfg = config.get("radar", {}).get("sources", {}).get("brain", {})
        if not src_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        wiki_root = src_cfg.get("wiki_root")
        if not wiki_root:
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="No wiki_root configured")

        wiki_path = Path(os.path.expanduser(wiki_root))
        if not wiki_path.exists():
            return SourceResult(self.name(), self.domain(), "error", error_message=f"Wiki root not found: {wiki_path}")

        items: list[dict] = []
        for fname, label in [("hot.md", "hot"), ("todo.md", "todo"), ("home.md", "home")]:
            fpath = wiki_path / fname
            if fpath.exists():
                content = fpath.read_text(errors="ignore").strip()
                if content:
                    lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
                    items.append({
                        "file": fname,
                        "label": label,
                        "line_count": len(lines),
                        "preview": lines[:5],
                        "path": str(fpath),
                    })

        return SourceResult(self.name(), self.domain(), "ok", items=items)


class EmailAdapter(SourceAdapter):
    """Reads Gmail via google_api.py (requires gmail.readonly scope)."""

    def name(self) -> str:
        return "email"

    def domain(self) -> str:
        return "email"

    def check_requirements(self) -> bool:
        return True  # Will gracefully fail if google_api.py isn't available

    def _find_google_api(self) -> Optional[Path]:
        """Find google_api.py in common locations."""
        candidates = [
            Path.home() / ".hermes" / "profiles" / os.environ.get("HERMES_PROFILE", "") / "skills" / "productivity" / "google-workspace" / "scripts" / "google_api.py",
            Path.home() / ".hermes" / "skills" / "productivity" / "google-workspace" / "scripts" / "google_api.py",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _find_python3(self) -> Optional[str]:
        """Find a Python 3.10+ interpreter."""
        for candidate in [
            "/opt/homebrew/opt/python@3.14/bin/python3.14",
            "/opt/homebrew/bin/python3.13",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3.11",
            "/usr/local/bin/python3.11",
            "python3",
        ]:
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    ver = result.stdout.strip()
                    if "Python 3." in ver:
                        parts = ver.replace("Python ", "").split(".")
                        if len(parts) >= 2:
                            major, minor = int(parts[0]), int(parts[1])
                            if major >= 3 and minor >= 10:
                                return candidate
            except Exception:
                continue
        return None

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        src_cfg = config.get("radar", {}).get("sources", {}).get("email", {})
        if not src_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        google_api = self._find_google_api()
        if not google_api:
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="google_api.py not found")

        python = self._find_python3()
        if not python:
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="Python 3.10+ not found")

        search_window = src_cfg.get("search_window_days", 3)
        max_threads = src_cfg.get("max_threads", 15)

        try:
            result = subprocess.run(
                [python, str(google_api), "gmail", "search",
                 f"newer_than:{search_window}d", f"--max={max_threads}"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                err = result.stderr[:200] if result.stderr else "Unknown error"
                if "403" in err or "scope" in err.lower():
                    return SourceResult(self.name(), self.domain(), "blocked_auth", error_message=err)
                return SourceResult(self.name(), self.domain(), "error", error_message=err)

            # Parse output (format depends on google_api.py)
            threads = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    threads.append({"subject": line[:100]})

            return SourceResult(self.name(), self.domain(), "ok", items=threads[:max_threads])

        except subprocess.TimeoutExpired:
            return SourceResult(self.name(), self.domain(), "error", error_message="Gmail query timed out")


class CalendarAdapter(SourceAdapter):
    """Reads Google Calendar (requires calendar scope)."""

    def name(self) -> str:
        return "calendar"

    def domain(self) -> str:
        return "calendar"

    def check_requirements(self) -> bool:
        return True

    def _find_google_api(self) -> Optional[Path]:
        return EmailAdapter()._find_google_api()

    def _find_python3(self) -> Optional[str]:
        return EmailAdapter()._find_python3()

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        cal_cfg = config.get("radar", {}).get("calendar", {})
        if not cal_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        google_api = self._find_google_api()
        if not google_api:
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="google_api.py not found")

        python = self._find_python3()
        if not python:
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="Python 3.10+ not found")

        lookahead = cal_cfg.get("lookahead_hours", 96)
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=lookahead)

        try:
            result = subprocess.run(
                [python, str(google_api), "calendar", "list",
                 f"--start={now.isoformat()}",
                 f"--end={end.isoformat()}",
                 "--max=20"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                err = result.stderr[:200] if result.stderr else "Unknown error"
                if "403" in err or "scope" in err.lower():
                    return SourceResult(self.name(), self.domain(), "blocked_auth", error_message=err)
                return SourceResult(self.name(), self.domain(), "error", error_message=err)

            events = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    events.append({"summary": line[:100]})

            return SourceResult(self.name(), self.domain(), "ok", items=events)

        except subprocess.TimeoutExpired:
            return SourceResult(self.name(), self.domain(), "error", error_message="Calendar query timed out")


class RemindersAdapter(SourceAdapter):
    """Reads Apple Reminders via remindctl (macOS only)."""

    def name(self) -> str:
        return "reminders"

    def domain(self) -> str:
        return "reminders"

    def check_requirements(self) -> bool:
        return shutil.which("remindctl") is not None

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        src_cfg = config.get("radar", {}).get("sources", {}).get("reminders", {})
        if not src_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        if not self.check_requirements():
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="remindctl not found (macOS only)")

        items: list[dict] = []

        # Get overdue
        try:
            result = subprocess.run(
                ["remindctl", "show", "overdue", "--json", "--no-input"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    for r in data:
                        items.append({"type": "overdue", "title": r.get("title", "")[:100], "due": r.get("dueDate", "")})
        except Exception:
            pass

        # Get this week
        try:
            result = subprocess.run(
                ["remindctl", "show", "week", "--json", "--no-input"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    for r in data:
                        items.append({"type": "week", "title": r.get("title", "")[:100], "due": r.get("dueDate", "")})
        except Exception:
            pass

        return SourceResult(self.name(), self.domain(), "ok", items=items)


class ReposAdapter(SourceAdapter):
    """Reads git/gh status for monitored repos."""

    def name(self) -> str:
        return "repos"

    def domain(self) -> str:
        return "repos"

    def check_requirements(self) -> bool:
        return shutil.which("git") is not None

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        src_cfg = config.get("radar", {}).get("sources", {}).get("repos", {})
        if not src_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        repos = src_cfg.get("monitored_repos", [])
        if not repos:
            return SourceResult(self.name(), self.domain(), "not_checked", error_message="No repos configured")

        items: list[dict] = []
        for repo in repos:
            repo_path = Path(os.path.expanduser(repo))
            if not repo_path.exists():
                # Try ~/repo_name
                repo_path = Path.home() / repo
            if not repo_path.exists():
                items.append({"repo": repo, "status": "not_found"})
                continue

            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-3"],
                    capture_output=True, text=True, timeout=5,
                    cwd=str(repo_path),
                )
                commits = result.stdout.strip().split("\n") if result.returncode == 0 else []
                items.append({
                    "repo": repo,
                    "path": str(repo_path),
                    "recent_commits": commits[:3],
                    "commit_count": len(commits),
                })
            except Exception as e:
                items.append({"repo": repo, "status": "error", "error": str(e)[:100]})

        return SourceResult(self.name(), self.domain(), "ok", items=items)


class FinanceAdapter(SourceAdapter):
    """Reads finance/admin alerts from email."""

    def name(self) -> str:
        return "finance"

    def domain(self) -> str:
        return "finance"

    def check_requirements(self) -> bool:
        return True

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        src_cfg = config.get("radar", {}).get("sources", {}).get("finance", {})
        if not src_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        adapter_type = src_cfg.get("adapter", "email_alerts")
        if adapter_type == "email_alerts":
            # Delegate to EmailAdapter with finance-specific search
            email_adapter = EmailAdapter()
            email_result = email_adapter.safe_collect(config, horizon)
            if email_result.status != "ok":
                return SourceResult(
                    self.name(), self.domain(),
                    email_result.status,
                    error_message=f"Email adapter: {email_result.error_message}",
                )
            # Filter for finance-related items
            keywords = ["billing", "payment", "invoice", "due", "statement",
                       "past due", "failed", "refund", "charge", "subscription"]
            finance_items = [
                item for item in email_result.items
                if any(kw in item.get("subject", "").lower() for kw in keywords)
            ]
            return SourceResult(self.name(), self.domain(), "ok", items=finance_items)

        return SourceResult(self.name(), self.domain(), "not_checked", error_message=f"Unknown adapter: {adapter_type}")


class TravelAdapter(SourceAdapter):
    """Extracts travel/logistics items from email + calendar."""

    def name(self) -> str:
        return "travel"

    def domain(self) -> str:
        return "travel"

    def check_requirements(self) -> bool:
        return True

    def collect(self, config: dict, horizon: dict) -> SourceResult:
        src_cfg = config.get("radar", {}).get("sources", {}).get("travel", {})
        if not src_cfg.get("enabled"):
            return SourceResult(self.name(), self.domain(), "disabled_by_policy")

        # Travel items are typically found via calendar and email
        # This adapter merges results from both
        cal_adapter = CalendarAdapter()
        cal_result = cal_adapter.safe_collect(config, horizon)

        travel_items = []
        if cal_result.status == "ok":
            travel_keywords = ["flight", "hotel", "airport", "travel", "trip", "boarding",
                              "check-in", "reservation", "booking", "itinerary"]
            for item in cal_result.items:
                if any(kw in item.get("summary", "").lower() for kw in travel_keywords):
                    travel_items.append({"source": "calendar", **item})

        return SourceResult(self.name(), self.domain(), "ok" if travel_items else "not_checked", items=travel_items)


# Registry of built-in adapters
ADAPTER_REGISTRY: dict[str, type[SourceAdapter]] = {
    "brain": BrainAdapter,
    "email": EmailAdapter,
    "calendar": CalendarAdapter,
    "reminders": RemindersAdapter,
    "repos": ReposAdapter,
    "finance": FinanceAdapter,
    "travel": TravelAdapter,
}


def get_enabled_adapters(config: dict) -> list[SourceAdapter]:
    """Get instances of all enabled source adapters from config."""
    sources = config.get("radar", {}).get("sources", {})
    adapters: list[SourceAdapter] = []

    for name, adapter_cls in ADAPTER_REGISTRY.items():
        src_cfg = sources.get(name, {})
        if isinstance(src_cfg, dict) and src_cfg.get("enabled"):
            adapters.append(adapter_cls())

    return adapters


def collect_all(config: dict, horizon: dict) -> list[SourceResult]:
    """Collect from all enabled adapters."""
    adapters = get_enabled_adapters(config)
    results: list[SourceResult] = []

    for adapter in adapters:
        result = adapter.safe_collect(config, horizon)
        results.append(result)

    return results
