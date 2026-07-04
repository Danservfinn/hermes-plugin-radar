"""Hermes Radar Plugin: chief-of-staff care layer.

Provides radar_run, radar_config, and radar_event tools for sweeping
configured sources, producing care-first briefs with approval-ready actions,
and tracking outcomes.
"""

from __future__ import annotations

from .schemas import (
    RADAR_RUN_SCHEMA,
    RADAR_CONFIG_SCHEMA,
    RADAR_EVENT_SCHEMA,
)
from .tools import (
    check_radar_available,
    handle_radar_run,
    handle_radar_config,
    handle_radar_event,
)

_TOOLS = (
    ("radar_run", RADAR_RUN_SCHEMA, handle_radar_run, "🛡️"),
    ("radar_config", RADAR_CONFIG_SCHEMA, handle_radar_config, "⚙️"),
    ("radar_event", RADAR_EVENT_SCHEMA, handle_radar_event, "📡"),
)


def register(ctx) -> None:
    """Register Radar tools with the Hermes plugin context."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(name, schema, handler, emoji)
