#!/usr/bin/env python3
"""Radar watch sources — quiet watchdog that polls configured sources.

Appends only new/changed material events to {artifact_root}/events.jsonl.
Stays silent for no-op/duplicate cron ticks.

Usage:
    python radar_watch_sources.py [--status --json]
    python radar_watch_sources.py --adapter all
    python radar_watch_sources.py --adapter calendar
    python radar_watch_sources.py --adapter reminders --append --cron-mode
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from config import load_config, get_artifact_root
from adapters import collect_all


def get_hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME")
    if home:
        return Path(home)
    profile = os.environ.get("HERMES_PROFILE", "")
    if profile:
        return Path.home() / ".hermes" / "profiles" / profile
    return Path.home() / ".hermes"


def event_hash(source: str, item: dict) -> str:
    """Stable hash for deduplication."""
    key = f"{source}:{json.dumps(item, sort_keys=True, default=str)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def load_seen_hashes(seen_path: Path) -> set[str]:
    """Load previously seen event hashes."""
    if not seen_path.exists():
        return set()
    seen: set[str] = set()
    with open(seen_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    evt = json.loads(line)
                    if "hash" in evt:
                        seen.add(evt["hash"])
                except json.JSONDecodeError:
                    continue
    return seen


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Radar watch sources")
    parser.add_argument("--status", action="store_true", help="Show adapter status")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--adapter", default="all", help="Which adapter to run (default: all)")
    parser.add_argument("--append", action="store_true", help="Append new events to events.jsonl")
    parser.add_argument("--cron-mode", action="store_true", help="Suppress all output unless interrupt threshold met")
    args = parser.parse_args()

    config = load_config()
    artifact_root = get_artifact_root(config)
    events_path = artifact_root / "events.jsonl"
    seen_path = artifact_root / ".seen_hashes"

    if args.status:
        # Show status of all configured adapters
        horizon = {"lookahead_hours": 96}
        results = collect_all(config, horizon)
        status_data = {
            "artifact_root": str(artifact_root),
            "sources": {},
        }
        for r in results:
            status_data["sources"][r.source_id] = {
                "status": r.status,
                "items": len(r.items),
                "error": r.error_message,
                "checked_at": r.checked_at,
            }

        if args.json:
            print(json.dumps(status_data, indent=2))
        else:
            print(f"Radar Status — {artifact_root}")
            for src, info in status_data["sources"].items():
                icon = {"ok": "✅", "partial": "🟡", "blocked_auth": "🔒",
                        "disabled_by_policy": "⚪", "not_checked": "⚪", "error": "❌"}.get(info["status"], "❓")
                print(f"  {icon} {src}: {info['status']} ({info['items']} items)")
        return

    # Normal collection mode
    horizon = {"lookahead_hours": 96}
    results = collect_all(config, horizon)

    if not args.append:
        # Just print what we found
        for r in results:
            print(f"[{r.status}] {r.source_id} ({r.domain}): {len(r.items)} items")
            for item in r.items[:5]:
                title = item.get("summary", item.get("title", item.get("subject", str(item)[:80])))
                print(f"  - {title}")
        return

    # Append mode — only write new events
    seen = load_seen_hashes(seen_path)
    new_events: list[dict] = []

    for r in results:
        if r.status not in ("ok", "partial"):
            continue
        for item in r.items:
            h = event_hash(r.source_id, item)
            if h not in seen:
                event = {
                    "hash": h,
                    "source": r.source_id,
                    "domain": r.domain,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": item,
                }
                new_events.append(event)
                seen.add(h)

    if new_events:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(events_path, "a") as f:
            for evt in new_events:
                f.write(json.dumps(evt, default=str) + "\n")

    # Cron mode: silent unless there are new interrupt-worthy events
    if args.cron_mode:
        interrupt_count = len([e for e in new_events if e["domain"] in ("finance", "calendar")])
        if interrupt_count == 0:
            return  # Silent — no-op
        print(json.dumps({"new_events": len(new_events), "interrupt_candidates": interrupt_count}))
    else:
        print(f"New events: {len(new_events)}")
        for evt in new_events[:10]:
            print(f"  [{evt['source']}] {evt['data'].get('summary', evt['data'].get('title', '?'))[:80]}")


if __name__ == "__main__":
    main()
