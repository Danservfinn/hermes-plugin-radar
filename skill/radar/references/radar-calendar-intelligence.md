# Radar Calendar Intelligence

## Purpose

Make Calendar and Apple Reminders high-signal, quiet inputs to the Radar Momentum Loop. They should help Radar protect time, prepare meetings/travel/admin handoffs, surface due commitments, and suppress no-op repeats.

A scheduled Radar delivery loop uses the user's calendar as both a source and an autonomous management surface. This replaces ad-hoc "check my calendar" requests with a layered system that sweeps, synthesizes, manages, and alerts.

## Architecture (4 Layers)

| Layer | Mechanism | Schedule | Token cost |
|---|---|---|---|
| **Morning Brief** | Agent cron + pre-run context collector script | 7am daily | ~3-5K/run |
| **Evening Closeout** | Agent cron + pre-run context collector script | 8pm daily | ~2-4K/run |
| **Calendar Creation** | Within Radar runs, autonomous authority | Per run | $0 extra |
| **Interrupt Alerts** | Script-only watchdog | every 30m | **0 tokens** |

### Layer 1+2: Agent crons with pre-run context

**Key pattern:** A script (`radar_context_collector.py`) runs before the agent and collects all source signals (Calendar, Gmail, Reminders, knowledge base, pending Radar events) into compact JSON. The agent prompt says "Pre-run context has already been collected — work from this, don't re-query sources." This keeps agent token consumption to ~3-5K instead of ~15-20K from source-discovery overhead.

Both morning and evening crons use `script: radar_context_collector.py morning|evening` as pre-run context injection.

### Layer 3: Autonomous calendar management

When the user grants autonomous create/delete authority, every Radar-created event must:
1. Include `created_by: radar` in the event description field
2. Be logged to `{artifact_root}/calendar_registry.jsonl`
3. Respect rate caps (5 creates / 3 deletes per run)

### Layer 4: Script-only interrupt alerts

`radar_interrupt_alerts.py` runs every 30m as a `no_agent: true` cron. Checks:
- Meetings starting within 15 min (🔴) or 60 min (🟡)
- Calendar conflicts (overlapping events)
- Travel events within 24h (✈️)
- Overdue reminders >24h (⏰)

**Silent on no-op** (watchdog pattern). Only prints when something needs the user's attention.

## Calendar + Reminders loop details

### Live implementation

- Script: `{HERMES_HOME}/scripts/radar_watch_sources.py`
- Root: `{artifact_root}`
- Enabled state: `{artifact_root}/state.json`
- Schedule: `every 30m`
- Mode: `no_agent=true`, script-only, silent unless a real failure occurs.

The script default/no-arg behavior is cron-safe `--append --cron-mode` across all adapters:

```bash
python3 {HERMES_HOME}/scripts/radar_watch_sources.py --root {artifact_root} --adapter all --append --cron-mode
```

### Adapters

| Adapter | Source | Horizon | Material events |
|---|---|---:|---|
| `source_coverage` | latest Radar run `source-coverage.json` | latest run | blocked/partial/error/disabled source coverage |
| `calendar` | Google Workspace calendar API | next 96h, 30m past grace | meeting prep, travel/logistics, admin/finance deadlines, overlaps/conflicts |
| `reminders` | Apple Reminders CLI | overdue + current week | overdue/today/tomorrow/week reminders, people/admin/finance/travel commitments |

Environment knobs:

- `RADAR_CALENDAR_LOOKAHEAD_HOURS` (default `96`)
- `RADAR_CALENDAR_PREP_WINDOW_HOURS` (default `36`)
- `RADAR_CALENDAR_PAST_GRACE_MINUTES` (default `30`)
- `RADAR_GOOGLE_API` (test/override path)
- `RADAR_REMINDCTL` (test/override path)
- `RADAR_NOW` (deterministic test clock)

## Authority boundary

Allowed by default:

- Read Calendar and Reminders.
- Append normalized local Radar events/status receipts.
- Prepare local notes, agenda/checklist/handoff drafts.
- Mark stale source-coverage rows consumed when a live adapter readback proves the source is restored.

Not allowed without exact explicit approval:

- Calendar create/edit/delete/reschedule/decline/invite.
- Reminders create/edit/delete/complete.
- OAuth credential entry, browser approval clicks, or scope broadening.
- External sends, payments, legal/identity submission, service restarts, deletes, pushes.

## Dedupe and no-noise behavior

- Event IDs are stable hashes over source identity, start/due time, and event kind.
- `event_seen()` suppresses rows already in `events.jsonl` by `event_id`, `payload_hash`, or `dedupe_key`.
- Cron mode writes nothing to stdout for disabled/no-op/duplicate/successful ticks.
- Duplicate ticks must not add duplicate status rows.

## Itinerary extraction from email

When the user says "incorporate my itinerary," mine email for structured booking data:

1. **Search broadly** for travel-related terms (airline names, destination, "itinerary", "confirmation").
2. **Get full bodies** of booking confirmation emails — look for JSON-LD microdata (`FlightReservation` schema with `flightNumber`, `departureAirport`, `departureTime`, `arrivalAirport`, `arrivalTime`).
3. **Hotel confirmations** — search for hotel name, extract confirmation #, check-in/out dates, room type from email body.
4. **Cross-reference** with existing calendar events — outbound flights may already be on calendar; return flights may be missing.
5. **Create missing events** using the calendar API with full details in description.
6. **Create smart reminders:** online check-in (24h before departure), hotel checkout, timezone awareness notes.
7. **Save to knowledge base:** write a trip itinerary page with full itinerary for Radar reference.

### Booking reference extraction

Airline confirmation emails often contain JSON-LD `FlightReservation` blocks with structured flight data. Parse these from the email body:
```python
body = re.sub(r'<[^>]+>', '\n', raw_body)
# Look for: flightNumber, departureAirport.name, departureTime, arrivalAirport.name, arrivalTime
```

## Travel-aware context collector

The `radar_context_collector.py` script detects active trips by scanning calendar event summaries for travel keywords (`flight`, `hotel`, `travel`, `trip`, `vacation`). When found, it adds a `travel_context` object to the pre-run JSON so the Radar agent knows the user may be in a different timezone.

## Files

| File | Purpose |
|---|---|
| `{HERMES_HOME}/scripts/radar_context_collector.py` | Pre-run context collector for morning/evening agent crons |
| `{HERMES_HOME}/scripts/radar_interrupt_alerts.py` | Script-only 30m interrupt watchdog (0 tokens) |
| `{HERMES_HOME}/scripts/radar_watch_sources.py` | 30m calendar/reminders poller (events.jsonl) |
| `{artifact_root}/calendar_registry.jsonl` | Registry of Radar-created calendar events (for safe autonomous deletion) |

## Verification

After creating calendar events from itinerary data, verify with:
1. `py_compile` the context collector
2. Run collector and check `travel_context.active_trips` is populated
3. Calendar API readback of created events (spot-check by date range)
4. `calendar_registry.jsonl` has entries for all created events

Run these after changing the loop:

```bash
python3 -m py_compile {HERMES_HOME}/scripts/radar_event_common.py {HERMES_HOME}/scripts/radar_ingest_event.py {HERMES_HOME}/scripts/radar_scan_event_artifacts.py {HERMES_HOME}/scripts/radar_watch_sources.py {HERMES_HOME}/scripts/radar_summarize_pending_events.py
python3 -m pytest {artifact_root}/tests/test_radar_momentum_loop.py -q
python3 {HERMES_HOME}/scripts/radar_watch_sources.py --root {artifact_root} --status --json
python3 {HERMES_HOME}/scripts/radar_scan_event_artifacts.py --root {artifact_root} --json --fail-on-hit
python3 {HERMES_HOME}/scripts/radar_summarize_pending_events.py --root {artifact_root} --json --dry-run
```

For dry-run counts without exposing private summaries, parse JSON and print only counts/event IDs.

## Failure handling

- If Calendar auth/scopes fail, emit a `calendar:blocked:*` event with `requires_user=true` and `authority_floor=draft_only`; do not attempt OAuth mutation.
- If `remindctl status` shows denied/no access, emit a `reminders:blocked:*` event; do not click privacy prompts.
- If JSON contract changes, emit a blocked adapter event and repair tests before relying on live ranking.

## Critical Pitfall: Token Scope Loss Breaks the Entire Stack

The **#1 operational failure** for Calendar Intelligence is the Google OAuth
token silently losing its `calendar` scope. When this happens:
- `radar_context_collector.py` → calendar source returns `blocked_auth`
- `radar_interrupt_alerts.py` → calendar events not found → silent (misses alerts)
- Calendar API → 403 insufficient scopes
- All calendar event creation fails

**Prevention (build into every Radar run that touches calendar):**
1. Check `token["scopes"]` includes `calendar` before trusting calendar data
2. If missing, flag it as a `blocked_auth` source-coverage issue immediately
3. Do NOT silently skip calendar — report the gap in the brief
4. See the google-workspace skill's token-scope-durability reference for full details

**Pattern:** manual PKCE re-auth can write a Gmail-only token over the
Gmail+Calendar token. The fix is a single re-auth with all needed scopes,
but detection takes too long when the agent doesn't check scopes proactively.

## External API Timeout on Constrained Networks

When the user is traveling, external API calls may SSL-timeout due to network
routing. This can cause `no_agent: true` cron workers to exhaust their time
budget and get killed.

**Generalizable lesson:** When a script-only cron worker fails on a constrained
network, check whether it's hitting external APIs with generous timeouts.
Reduce per-request timeout budget so the script can complete (with reduced data)
rather than hanging and getting killed.
