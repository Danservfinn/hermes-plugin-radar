# Radar Momentum Loop

Use this reference when the user asks to make Radar more continuous, event-driven, webhook-backed, or constantly moving tracked work forward.

## Core lesson

Do **not** turn Radar into an instant-forwarding bot. The stronger design is:

> Instantly capture important changes, quietly prepare safe next actions, and interrupt the user only when Radar can name a concrete decision, approval, urgent risk, blocked source, stale promise, or no-progress state.

## Loop name

**Radar Momentum Loop**

One unified Radar loop that turns fresh signals into source-backed Radar items, prepares safe next actions, interrupts only when action is genuinely needed, and keeps tracked work moving through receipts instead of repeated reminders.

Short loop prompt:

> Watch approved Radar sources and webhook events. Normalize fresh signals into Radar items, merge them with the latest packet, prepare the smallest safe next action, and verify whether anything changed. Quietly record clean no-ops and drafts; interrupt the user only for approval-needed decisions, urgent risk, blocked progress, or stale promises. Stop when each item is closed, watching, waiting, blocked, or approval-gated.

## Recommended architecture

```text
webhooks / watcher scripts
        ↓
radar events.jsonl
        ↓
dedupe + classify + merge with latest Radar packet
        ↓
prepare safe next action or quiet watch
        ↓
interrupt only if threshold crossed
        ↓
approval → execution → readback → receipt
```

## State and artifacts

Keep Radar's existing packet/receipt contract and add one compact intake ledger:

```text
{artifact_root}/latest.json
{artifact_root}/runs/<run_id>/packet.json
{artifact_root}/runs/<run_id>/brief.md
{artifact_root}/runs/<run_id>/receipts.md
{artifact_root}/runs/<run_id>/source-coverage.json
{artifact_root}/events.jsonl
```

Suggested event shape:

```json
{
  "event_id": "source:type:stable-id",
  "observed_at": "ISO timestamp",
  "source": "github|gmail|calendar|reminders|knowledge_base|stripe|cron|imessage|custom",
  "domain": "repos|finance|people|travel|research|systems|admin|knowledge_base",
  "summary": "short redacted summary",
  "source_ref": "redacted pointer/path/url/thread id",
  "urgency_hint": 0,
  "requires_user": false,
  "privacy_tier": "normal|private|financial|relationship",
  "raw_payload_path": null
}
```

## Webhook vs polling guidance

Use webhooks for sources that can push meaningful events:

- GitHub/repos: PR opened, review requested, CI failed, issue assigned.
- Stripe/billing systems: payment failed, subscription changed, dispute/refund event.
- Monitoring/uptime: service down, cron failed, queue backed up.
- iMessage/Signal adapters: important tracked person/group events.
- Linear/project tools: issue blocked, due soon, mention/comment events.
- Custom task management systems: task state changed, receipt missing, source ingest finished.

Use small watcher scripts for sources without reliable webhooks:

- Knowledge base status pages: changed hot items, stale promises, blocked projects.
- Gmail/Calendar: deadlines, travel/admin/finance messages, meeting prep.
- Apple Reminders: overdue/today/week commitments, people calls, manual handoffs, checklist prep.
- RSS/arXiv/Readwise: tracked research signals.
- Local cron/jobs: failures, missing receipts, repeated no-output states.
- File-based project receipts: prepared-but-never-closed work.

Watcher scripts should usually be quiet: append normalized events or emit nothing unless an interrupt threshold is crossed.

## Minimal implementation pattern

One automation + one state file + one hard gate:

1. `radar_ingest_event.py` validates/redacts/idempotently appends events to `events.jsonl` and optionally wakes a Radar run.
2. `radar_watch_sources.py` checks approved non-webhook sources and emits normalized events only when something materially changed. Its quiet default polls `source_coverage`, Google Calendar, and Apple Reminders; no-arg cron mode must remain silent for no-op/duplicate/successful ticks.
3. A webhook/cron/manual synthesis run loads `radar`, reads latest packet + new events, and writes the updated packet/brief/receipts.
4. The hard gate remains: no external sends, payments/legal submissions, destructive actions, production/runtime mutations, or secret entry without explicit scoped approval.

Example reasoning-backed webhook route:

```bash
hermes webhook subscribe radar-events \
  --events "radar.event" \
  --skills "radar" \
  --prompt "A Radar event arrived. Normalize it against the latest Radar packet, prepare only safe draft/read-only next actions, and interrupt only if the Radar threshold is crossed. Payload:\n{__raw__}" \
  --deliver origin
```

Use `--deliver-only` only for simple emergency forwarding. For Radar, the valuable step is usually not forwarding; it is merging, deduping, ranking, preparing, and deciding whether the user should be interrupted.

## Promotion ladder

1. Manual trial from current Radar state.
2. Event intake only: webhooks/scripts write normalized events, actions remain draft-only.
3. Interrupt threshold tuning with false-positive/false-negative feedback.
4. Closeout receipts: approved actions get original-source readback.
5. Promote only narrow, easy-verifier sources to cron/watchdog behavior.

Readiness default: assisted/manual trial is appropriate; broad unattended action is not.

## Background implementation pattern

Use this pattern when the user approves implementation of a Radar plan but the approval is bounded to a narrow slice and should run in the background.

### Trigger

The user asks to implement a Radar/Radar Momentum Loop plan after a readiness review, especially with language like "Implement in the background".

### Steps

1. Preserve the approved boundary in a self-contained prompt file under the active profile, e.g.:
   - `{HERMES_HOME}/tmp/<topic>-implementation-prompt.md`
2. Make the prompt explicit about non-authorized work:
   - no Phase 2+ activation;
   - no webhook subscribe;
   - no cron creation/update;
   - no gateway restart;
   - no provider/profile/runtime config mutation;
   - no external sends;
   - no finance/admin mutation;
   - no deploys;
   - no Kanban dispatch;
   - no cross-profile Hermes writes.
3. Include the exact plan path, active knowledge base/profile paths, required skills, and verification/reporting requirements.
4. Require temp-root-first TDD and replay gates before any live Radar state mutation.
5. Launch a separate Hermes background process with `notify_on_complete=true` and preload the relevant skills:
   - `radar`
   - `test-driven-development`
   - `shell-command-hygiene`
6. Poll once immediately to confirm the process started, then report the process id/session id and scope boundary. Do not claim implementation is complete until the background process exits and its receipts are read back.

### Example launch shape

```bash
hermes \
  -s radar,test-driven-development,shell-command-hygiene \
  chat -q "$(< {HERMES_HOME}/tmp/radar-momentum-loop-implementation-prompt.md)"
```

Run this via the terminal tool with `background=true`, `notify_on_complete=true`.

### Required final report from the background worker

The worker final response should state:

- completed vs safely stopped;
- files changed/created;
- exact commands run and real results;
- live Radar state touched vs not touched;
- explicit non-actions: no Phase 2+, webhook, cron, gateway/config mutation, external send, finance/admin, deploy, or Kanban action.

## Pitfalls

- Do not let "background" imply durable scheduler/cron creation. Use a tracked background process, not a new cron job.
- Do not let broad implementation authority leak into Radar money/runtime/social gates.
- Do not write prompt files or scripts under default Hermes home; keep them profile-scoped under `{HERMES_HOME}/`.
- Do not report success from process start alone. Starting the background worker is only a handoff receipt.
