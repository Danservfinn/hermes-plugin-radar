# Radar — Chief-of-Staff Care Layer for Hermes

> A source-backed attention surface that protects, prepares, proposes, and closes loops across your notes, email, calendar, reminders, repos, finance, travel, and relationships.

## Installation

```bash
hermes plugins install Danservfinn/hermes-plugin-radar --enable
```

After installation, run the onboarding wizard:

```bash
python ~/.hermes/plugins/radar/scripts/radar_init.py
```

Or configure manually — see [Configuration](#configuration) below.

## What Radar Does

Radar is **not** a briefing generator or a summary bot. It's a chief-of-staff care layer that:

| Job | What it does | User feeling |
|---|---|---|
| **Protect** | Notices risks, deadlines, failed payments, broken services, neglected people, stale loops | "Nothing important is silently slipping." |
| **Prepare** | Drafts replies, handoff checklists, meeting prep, travel packets, admin notes | "The hard part is already teed up." |
| **Propose** | Presents exact low-friction decisions with stable approval phrases | "I can move things with `approve 1, 3`." |
| **Close loops** | Tracks approved, executed, blocked, deferred, and waiting states with receipts | "I don't have to remember what happened." |

## Quick Start

1. **Install:** `hermes plugins install Danservfinn/hermes-plugin-radar --enable`
2. **Configure:** `python ~/.hermes/plugins/radar/scripts/radar_init.py`
3. **Run:** In Hermes, type `/skill radar` then say "run radar morning"
4. **Approve:** Reply with `approve 1, 3` to approve specific actions

## Configuration

Radar reads `{HERMES_HOME}/radar_config.yaml`. Generate it with the wizard or write it manually.

### Key Settings

```yaml
radar:
  # Where to write artifacts (packets, briefs, receipts)
  artifact_root: ~/brain/status/radar

  # Source adapters
  sources:
    brain:
      enabled: true
      wiki_root: ~/notes          # Your notes/wiki directory
    email:
      enabled: true               # Uses google-workspace skill
    calendar:
      enabled: true               # Uses google-workspace skill
    reminders:
      enabled: true               # macOS only (remindctl)
    repos:
      enabled: true
      monitored_repos: ["~/myproject", "~/another-repo"]
    finance:
      enabled: true               # Scans email for billing/payment alerts
    travel:
      enabled: true               # Extracts travel items from email + calendar

  # Calendar management
  calendar:
    enabled: true
    autonomous_create: true       # Create prep blocks, buffers, reminders
    autonomous_delete_own: true   # Delete events Radar created
    max_events_per_run: 5

  # Authority (what Radar can do without asking)
  authority:
    read_only: true               # Read sources
    draft_only: true              # Write local notes/drafts
    external_send: false           # Send messages — requires approval
    financial_or_legal: false      # Payments — requires approval + manual handoff
    destructive: false             # Deletes — requires approval + rollback

  # Scheduled sweeps
  schedule:
    morning:
      enabled: true
      cron: "0 7 * * *"
    evening:
      enabled: true
      cron: "0 19 * * *"
    interrupt_checker:
      enabled: true
      cron: "*/30 * * * *"
```

### Run Modes

| Mode | Horizon | Use Case |
|---|---|---|
| `morning` | last 24h + next 72h | Daily care sweep, top decisions |
| `evening` | today + tomorrow | Close loops, tee up tomorrow |
| `weekly` | last 7d + next 14d | Strategic review, stale items |
| `deep_work_shield` | now + next 8h | Suppress noise, protect focus |
| `travel` | trip window | Logistics, documents, timing |
| `family_relationships` | next 7d | Promises, birthdays, warm drafts |
| `finance_admin` | next 30d | Payments, fraud, legal/tax |

## Source Adapters

Radar uses pluggable source adapters. Each adapter collects signals from one domain:

| Adapter | Source | Requirements |
|---|---|---|
| `brain` | Wiki/notes directory | A directory path with markdown files |
| `email` | Gmail | `google-workspace` skill + Gmail OAuth scope |
| `calendar` | Google Calendar | `google-workspace` skill + Calendar OAuth scope |
| `reminders` | Apple Reminders | macOS + `remindctl` CLI |
| `repos` | Git repositories | `git` CLI |
| `finance` | Email finance alerts | `email` adapter enabled |
| `travel` | Email + calendar | `email` or `calendar` adapter enabled |

### Writing Custom Adapters

```python
from adapters import SourceAdapter, SourceResult

class MyAdapter(SourceAdapter):
    def name(self) -> str:
        return "my_source"

    def domain(self) -> str:
        return "custom"

    def check_requirements(self) -> bool:
        return True  # Check for CLI, credentials, etc.

    def collect(self, config, horizon) -> SourceResult:
        # Collect your data here
        items = [{"title": "Example item"}]
        return SourceResult(
            source_id=self.name(),
            domain=self.domain(),
            status="ok",
            items=items,
        )
```

Register your adapter in `adapters.py` → `ADAPTER_REGISTRY`.

## Tools Provided

### `radar_run`

Run a Radar sweep across configured sources.

```
radar_run(mode="morning", domains=["calendar", "email"], output_format="brief")
```

### `radar_config`

Read, validate, or reset Radar configuration.

```
radar_config(action="show")     # Show current config
radar_config(action="validate") # Validate config
```

### `radar_event`

Query or append to the Radar event ledger.

```
radar_event(action="recent", limit=20)  # Recent events
radar_event(action="stats")              # Event statistics
```

## Approval Grammar

Radar proposes actions with stable IDs. You approve by number:

```
approve 1, 3          # Approve actions 1 and 3
approve 1-3           # Approve actions 1, 2, and 3
approve 2 with edit: <change>  # Approve with modification
skip 4                # Skip action 4
defer 5 until Friday  # Defer action 5
```

## Autonomous Calendar Management

When enabled in config, Radar can autonomously create and delete calendar events:

- **Creates:** prep blocks (15-30 min before meetings), travel buffers, deadline markers, focus shields, admin blocks
- **Deletes:** only events Radar created (tagged `created_by: radar`)
- **Never touches:** events you or others created (requires explicit approval)
- **Rate-limited:** max 5 creates and 3 deletes per run

All Radar-created events are logged to `{artifact_root}/calendar_registry.jsonl` for safe cleanup.

## Requirements

- **Hermes Agent** — any recent version
- **Python 3.10+** — for Google API calls (uses PEP 604 syntax)
- **google-workspace skill** — for email/calendar adapters (optional but recommended)
- **macOS + remindctl** — for Apple Reminders adapter (optional)
- **git CLI** — for repo monitoring (optional)

## How It Works

```
Source adapters → Normalized evidence → Care-state synthesis → Top decisions → Approval-ready actions → Receipts + learning → Next-run tuning
```

1. **Collect:** Each enabled adapter gathers raw signals within the time horizon
2. **Normalize:** Raw signals are merged and deduplicated into Radar Items
3. **Score:** Items are ranked by urgency, leverage, risk, tractability, and compounding value
4. **Synthesize:** Care ledgers are built (promises, meeting prep, finance sentinel, etc.)
5. **Propose:** 3-7 approval-ready actions are generated with exact payloads
6. **Execute:** On `approve N`, the action is executed and verified
7. **Learn:** Outcomes are tracked for future ranking improvements

## File Structure

```
~/.hermes/plugins/radar/
├── plugin.yaml              # Plugin manifest
├── __init__.py              # Tool registration
├── schemas.py               # JSON schemas for tools
├── tools.py                 # Tool handlers
├── config.py                # Config loading/validation
├── adapters.py              # Source adapter interface + implementations
├── scripts/
│   ├── radar_init.py        # Onboarding wizard
│   ├── radar_watch_sources.py    # Quiet watchdog (cron)
│   └── radar_context_collector.py # Pre-run context gatherer
└── skill/radar/
    ├── SKILL.md             # Full workflow instructions
    ├── templates/           # Brief, modes, authority, packet schema
    └── references/          # Detailed pattern docs
```

## License

MIT

## Author

Danservfinn
