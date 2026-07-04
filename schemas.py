"""Tool schemas for the Radar Hermes plugin."""

from __future__ import annotations


RADAR_RUN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "radar_run",
        "description": (
            "Run a Radar care-layer sweep across configured sources. Collects signals "
            "from notes/wiki, email, calendar, reminders, repos, finance, travel, and "
            "more, normalizes them into ranked Radar Items, and produces a care-first "
            "brief with approval-ready actions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": [
                        "morning", "evening", "weekly", "deep_work_shield",
                        "travel", "shipping", "family_relationships",
                        "finance_admin", "on_demand",
                    ],
                    "default": "morning",
                    "description": "Radar run mode controlling horizon, interrupt threshold, and emphasis.",
                },
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional domain filter (e.g. ['calendar', 'email', 'finance']). If omitted, all configured domains are swept.",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["brief", "packet", "both"],
                    "default": "brief",
                    "description": "Output format: human-readable brief, structured machine packet, or both.",
                },
            },
        },
    },
}


RADAR_CONFIG_SCHEMA = {
    "type": "function",
    "function": {
        "name": "radar_config",
        "description": (
            "Read, validate, or initialize Radar configuration. Shows current source "
            "adapters, authority profile, paths, and run settings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["show", "validate", "init", "reset"],
                    "default": "show",
                    "description": "Action to perform on Radar configuration.",
                },
            },
        },
    },
}


RADAR_EVENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "radar_event",
        "description": (
            "Query the Radar event ledger for recent events, or append a new event "
            "(used by watcher scripts and webhook integrations)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["recent", "append", "stats"],
                    "default": "recent",
                    "description": "Action to perform on the event ledger.",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum number of events to return (for action=recent).",
                },
                "event": {
                    "type": "object",
                    "description": "Event to append (for action=append). Must contain 'source' and 'type' fields.",
                },
            },
        },
    },
}
