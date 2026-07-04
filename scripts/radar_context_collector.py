#!/usr/bin/env python3
"""Radar context collector — pre-run context gathering for token-efficient crons.

Collects minimal context from configured sources before a Radar agent run,
to reduce token consumption by pre-filtering and summarizing raw source data.

Usage:
    python scripts/radar_context_collector.py [--mode morning] [--json]
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from config import load_config, get_artifact_root
from adapters import collect_all


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Radar context collector")
    parser.add_argument("--mode", default="morning", help="Radar run mode")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    config = load_config()

    horizons = {
        "morning": {"lookback_hours": 24, "lookahead_hours": 72},
        "evening": {"lookback_hours": 12, "lookahead_hours": 36},
        "weekly": {"lookback_hours": 168, "lookahead_hours": 336},
        "deep_work_shield": {"lookback_hours": 1, "lookahead_hours": 8},
    }
    horizon = horizons.get(args.mode, horizons["morning"])

    results = collect_all(config, horizon)

    context = {
        "mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon": horizon,
        "sources": [],
        "total_items": 0,
        "summary_lines": [],
    }

    for r in results:
        src_info = {
            "source": r.source_id,
            "domain": r.domain,
            "status": r.status,
            "item_count": len(r.items),
        }
        if r.error_message:
            src_info["error"] = r.error_message
        context["sources"].append(src_info)
        context["total_items"] += len(r.items)

        # Add summary lines for the agent
        if r.status == "ok" and r.items:
            for item in r.items[:3]:  # Top 3 per source
                title = item.get("summary", item.get("title", item.get("subject", "")))
                if title:
                    context["summary_lines"].append(f"[{r.source_id}] {str(title)[:100]}")

    # Add calendar authority info
    cal_cfg = config["radar"].get("calendar", {})
    context["calendar_autonomy"] = {
        "enabled": cal_cfg.get("enabled", False),
        "autonomous_create": cal_cfg.get("autonomous_create", False),
        "autonomous_delete_own": cal_cfg.get("autonomous_delete_own", False),
    }

    # Add authority info
    context["authority"] = config["radar"].get("authority", {})

    if args.json:
        print(json.dumps(context, indent=2, default=str))
    else:
        print(f"Radar Context — {args.mode} mode")
        print(f"Sources: {len(context['sources'])} checked, {context['total_items']} items found")
        for src in context["sources"]:
            icon = {"ok": "✅", "partial": "🟡", "blocked_auth": "🔒",
                    "disabled_by_policy": "⚪", "not_checked": "⚪", "error": "❌"}.get(src["status"], "❓")
            print(f"  {icon} {src['source']}: {src['status']} ({src['item_count']} items)")
        if context["summary_lines"]:
            print("\nKey items:")
            for line in context["summary_lines"][:15]:
                print(f"  {line}")


if __name__ == "__main__":
    main()
