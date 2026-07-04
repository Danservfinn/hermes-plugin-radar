"""Tool handlers for the Radar Hermes plugin."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    load_config,
    validate_config,
    save_config,
    get_artifact_root,
    get_config_path,
    _deep_copy_default,
    deep_merge,
)
from .adapters import collect_all, get_enabled_adapters


def check_radar_available() -> bool:
    """Check if Radar can run (always true — no external deps required)."""
    return True


# ─── radar_run ──────────────────────────────────────────────────────────


def handle_radar_run(args: dict, **kwargs) -> str:
    """Run a Radar care-layer sweep.

    Collects from configured sources, normalizes into Radar Items, and
    produces a structured result with brief, source coverage, and actions.
    """
    mode = args.get("mode", "morning")
    domains_filter = args.get("domains")
    output_format = args.get("output_format", "brief")

    # Load config
    config = load_config()

    # Define horizon based on mode
    horizons = {
        "morning": {"lookback_hours": 24, "lookahead_hours": 72},
        "evening": {"lookback_hours": 12, "lookahead_hours": 36},
        "weekly": {"lookback_hours": 168, "lookahead_hours": 336},
        "deep_work_shield": {"lookback_hours": 1, "lookahead_hours": 8},
        "travel": {"lookback_hours": 24, "lookahead_hours": 168},
        "shipping": {"lookback_hours": 6, "lookahead_hours": 48},
        "family_relationships": {"lookback_hours": 24, "lookahead_hours": 168},
        "finance_admin": {"lookback_hours": 72, "lookahead_hours": 720},
        "on_demand": {"lookback_hours": 24, "lookahead_hours": 72},
    }
    horizon = horizons.get(mode, horizons["morning"])

    # Generate run ID
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    generated_at = datetime.now(timezone.utc).isoformat()

    # Collect from all enabled adapters
    source_results = collect_all(config, horizon)

    # Build source coverage summary
    source_coverage = {}
    total_items = 0
    for result in source_results:
        source_coverage[result.source_id] = {
            "status": result.status,
            "domain": result.domain,
            "item_count": len(result.items),
            "error": result.error_message,
        }
        total_items += len(result.items)

    # Build authority snapshot
    authority = config["radar"].get("authority", {})

    # Create the packet structure
    packet = {
        "schema": "RADAR_PACKET/v1",
        "run_id": run_id,
        "generated_at": generated_at,
        "run_mode": mode,
        "horizon": horizon,
        "domains": domains_filter or "all_configured",
        "standing_authority_snapshot": authority,
        "max_authority": _max_authority(authority),
        "source_coverage": source_coverage,
        "items": [],
        "actions": [],
        "people_promises": [],
        "meeting_prep": [],
        "travel_concierge": [],
        "finance_admin_sentinel": [],
        "already_handled": [],
        "changes_since_last": [],
        "watching_quietly": [],
        "learning": {},
    }

    # Merge source items into the packet (agent will do the actual synthesis)
    all_raw_items = []
    for result in source_results:
        for item in result.items:
            all_raw_items.append({
                "source": result.source_id,
                "domain": result.domain,
                "status": result.status,
                **item,
            })
    packet["_raw_items"] = all_raw_items
    packet["_raw_item_count"] = len(all_raw_items)

    # Write artifacts
    artifact_root = get_artifact_root(config)
    run_dir = artifact_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write packet
    packet_path = run_dir / "packet.json"
    with open(packet_path, "w") as f:
        json.dump(packet, f, indent=2, default=str)

    # Write source coverage
    coverage_path = run_dir / "source-coverage.json"
    with open(coverage_path, "w") as f:
        json.dump(source_coverage, f, indent=2)

    # Write brief placeholder (agent will fill this in)
    brief_path = run_dir / "brief.md"
    brief_text = _generate_brief_skeleton(packet, source_results)
    with open(brief_path, "w") as f:
        f.write(brief_text)

    # Update latest.json
    latest_path = artifact_root / "latest.json"
    with open(latest_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "generated_at": generated_at,
            "run_mode": mode,
            "packet_path": str(packet_path),
            "brief_path": str(brief_path),
        }, f, indent=2)

    # Build response
    response = {
        "run_id": run_id,
        "mode": mode,
        "generated_at": generated_at,
        "source_coverage": source_coverage,
        "total_raw_items": total_items,
        "artifact_paths": {
            "packet": str(packet_path),
            "brief": str(brief_path),
            "coverage": str(coverage_path),
        },
        "authority": authority,
        "max_authority": packet["max_authority"],
        "message": (
            f"Radar sweep complete ({mode} mode). "
            f"Collected {total_items} raw items from {len(source_results)} sources. "
            f"Packet written to {packet_path}. "
            f"Load the radar skill for full synthesis and care-layer workflow."
        ),
    }

    if output_format in ("packet", "both"):
        response["packet"] = packet

    if output_format in ("brief", "both"):
        response["brief"] = brief_text

    return json.dumps(response, indent=2, default=str)


# ─── radar_config ──────────────────────────────────────────────────────


def handle_radar_config(args: dict, **kwargs) -> str:
    """Read, validate, or initialize Radar configuration."""
    action = args.get("action", "show")

    if action == "show":
        config = load_config()
        config_path = get_config_path()
        is_valid, errors = validate_config(config)

        # Count enabled sources
        sources = config["radar"].get("sources", {})
        enabled_sources = [k for k, v in sources.items() if isinstance(v, dict) and v.get("enabled")]

        return json.dumps({
            "action": "show",
            "config_path": str(config_path),
            "config_exists": config_path.exists(),
            "is_valid": is_valid,
            "validation_errors": errors,
            "artifact_root": config["radar"].get("artifact_root"),
            "default_mode": config["radar"].get("default_mode"),
            "enabled_sources": enabled_sources,
            "authority": config["radar"].get("authority"),
            "calendar": {
                "enabled": config["radar"]["calendar"].get("enabled"),
                "autonomous_create": config["radar"]["calendar"].get("autonomous_create"),
                "autonomous_delete_own": config["radar"]["calendar"].get("autonomous_delete_own"),
            },
            "schedule": config["radar"].get("schedule"),
        }, indent=2)

    elif action == "validate":
        config = load_config()
        is_valid, errors = validate_config(config)
        return json.dumps({
            "action": "validate",
            "is_valid": is_valid,
            "errors": errors,
            "config_path": str(get_config_path()),
        }, indent=2)

    elif action == "init":
        return json.dumps({
            "action": "init",
            "message": (
                "Run the onboarding wizard: "
                "python scripts/radar_init.py "
                f"Or manually create {get_config_path()} — see README.md for config reference."
            ),
        })

    elif action == "reset":
        config_path = get_config_path()
        if config_path.exists():
            backup = config_path.with_suffix(".yaml.bak")
            config_path.rename(backup)
            return json.dumps({
                "action": "reset",
                "message": f"Config backed up to {backup}. Defaults restored.",
            })
        return json.dumps({
            "action": "reset",
            "message": "No config to reset — using defaults.",
        })

    return json.dumps({"error": f"Unknown action: {action}"})


# ─── radar_event ──────────────────────────────────────────────────────


def handle_radar_event(args: dict, **kwargs) -> str:
    """Query or append to the Radar event ledger."""
    action = args.get("action", "recent")
    limit = args.get("limit", 20)
    event = args.get("event")

    config = load_config()
    artifact_root = get_artifact_root(config)
    events_path = artifact_root / "events.jsonl"

    if action == "recent":
        if not events_path.exists():
            return json.dumps({"action": "recent", "events": [], "message": "No events yet."})

        events: list[dict] = []
        with open(events_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Return last N events (reversed = most recent first)
        recent = events[-limit:][::-1]
        return json.dumps({
            "action": "recent",
            "count": len(recent),
            "total": len(events),
            "events": recent,
        }, indent=2)

    elif action == "append":
        if not event:
            return json.dumps({"error": "No event provided for append"})

        events_path.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp if missing
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        with open(events_path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

        return json.dumps({
            "action": "append",
            "status": "ok",
            "event": event,
        })

    elif action == "stats":
        if not events_path.exists():
            return json.dumps({"action": "stats", "total": 0, "by_source": {}, "by_type": {}})

        total = 0
        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}

        with open(events_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    total += 1
                    src = evt.get("source", "unknown")
                    by_source[src] = by_source.get(src, 0) + 1
                    etype = evt.get("type", "unknown")
                    by_type[etype] = by_type.get(etype, 0) + 1
                except json.JSONDecodeError:
                    continue

        return json.dumps({
            "action": "stats",
            "total": total,
            "by_source": by_source,
            "by_type": by_type,
        }, indent=2)

    return json.dumps({"error": f"Unknown action: {action}"})


# ─── Helpers ───────────────────────────────────────────────────────────


def _max_authority(authority: dict) -> str:
    """Determine the maximum authority level."""
    if authority.get("destructive"):
        return "destructive"
    if authority.get("financial_or_legal"):
        return "financial_or_legal"
    if authority.get("runtime_mutation"):
        return "runtime_mutation"
    if authority.get("external_send"):
        return "external_send"
    if authority.get("draft_only"):
        return "draft_only"
    if authority.get("read_only"):
        return "read_only"
    return "none"


def _generate_brief_skeleton(packet: dict, source_results: list) -> str:
    """Generate a brief skeleton from collected data.

    The agent will use this as a starting point and fill in the full
    care-layer synthesis (protect, prepare, propose, close).
    """
    mode = packet["run_mode"]
    run_id = packet["run_id"]

    # Source coverage line
    coverage_parts = []
    for src_id, info in packet["source_coverage"].items():
        icon = {"ok": "✅", "partial": "🟡", "blocked_auth": "🔒",
                "disabled_by_policy": "⚪", "not_checked": "⚪", "error": "❌"}.get(info["status"], "❓")
        coverage_parts.append(f"{icon} {src_id}")

    coverage_line = " · ".join(coverage_parts) if coverage_parts else "⚪ No sources configured"

    # Already handled section
    handled = [
        f"Loaded config from {get_config_path()}",
        f"Collected from {len(source_results)} source adapters",
        f"Found {packet['_raw_item_count']} raw items",
    ]

    lines = [
        f"## Radar — {mode.title()}",
        "",
        f"**Run ID:** {run_id}",
        f"**Mode:** {mode}",
        "",
        "### I already handled",
    ]
    lines.extend(f"- {h}" for h in handled)
    lines.extend([
        "",
        "### Source coverage",
        coverage_line,
        "",
        "### Needs you",
        "_(Agent will synthesize items and propose approval-ready actions — load the radar skill for full workflow.)_",
        "",
        "### Coverage / blind spots",
        coverage_line,
        "",
        "### Learning",
        f"- This is run {run_id}. Previous outcome data will inform future runs.",
    ])

    return "\n".join(lines)
