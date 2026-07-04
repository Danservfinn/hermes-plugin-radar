# Radar Artifact Contract v1.1

This contract is the stable interface between a Radar run, chat approval, scheduled cron jobs, future product UI, execution receipts, and evaluation loops.

Radar is a **care-layer / chief-of-staff** system, not a briefing generator. The contract therefore records not only items and proposed actions, but also what was already handled, what needs the user, what is being watched quietly, how authority was bounded, and how the next run should learn.

## File layout

Recommended local layout for Radar runs:

```text
{artifact_root}/latest.json
{artifact_root}/runs/<run_id>/packet.json
{artifact_root}/runs/<run_id>/brief.md
{artifact_root}/runs/<run_id>/brief.html
{artifact_root}/latest.html
{artifact_root}/runs/<run_id>/receipts.md
{artifact_root}/runs/<run_id>/source-coverage.json
{artifact_root}/runs/<run_id>/feedback.jsonl
```

For a SaaS product, the same concepts become tables/events:

```text
radar_runs
radar_sources
radar_items
radar_actions
radar_approvals
radar_execution_receipts
radar_feedback_labels
radar_metrics
radar_user_authority_profiles
radar_suppression_rules
```

## Packet object

```json
{
  "schema": "RADAR_PACKET/v1",
  "schema_version": "1.1",
  "run_id": "radar-20260701T090000-0400",
  "generated_at": "2026-07-01T09:00:00-04:00",
  "run_mode": "morning",
  "horizon": {"lookback_hours": 24, "lookahead_hours": 72},
  "interrupt_threshold": "P1+ decisions, people loops, deadlines, payment/security/travel risk",
  "operator": "user",
  "profile": "default",
  "max_authority": "draft_only",
  "standing_authority_snapshot": {},
  "care_state": {
    "verdict": "mostly_clear",
    "one_sentence": "Mostly clear; one admin risk and two people loops need the user.",
    "protect": [],
    "prepare": [],
    "propose": [],
    "close_loops": []
  },
  "source_coverage": [],
  "items": [],
  "actions": [],
  "already_handled": [],
  "needs_you": [],
  "people_promises": [],
  "meeting_prep": [],
  "travel_concierge": [],
  "finance_admin_sentinel": [],
  "projects_systems": [],
  "quiet_watch": [],
  "changes_since_last": [],
  "open_questions": [],
  "metrics": {},
  "approval_instructions": {
    "examples": ["approve 1, 2", "approve A3", "approve 2 with edit: ...", "defer 4 until Friday", "skip 5"],
    "scope": "Approvals apply only to the exact action IDs and payloads in this packet."
  }
}
```

## Care state

`care_state` is the top-level UX state for the run.

Allowed `verdict` values:

- `clear` — no user action required; Radar handled or is watching everything.
- `mostly_clear` — a few decisions/actions need the user.
- `needs_attention` — multiple important items need a reply/approval.
- `fire_drill` — urgent risk/incident/deadline; escalate clearly.
- `blocked` — source access, auth, or policy prevents a trustworthy run.

The four arrays mirror the Care Contract:

| Field | Meaning |
|---|---|
| `protect` | risks/deadlines/anomalies Radar caught or is watching |
| `prepare` | drafts/checklists/packets/notes prepared but not externally sent |
| `propose` | decisions/actions queued for approval |
| `close_loops` | resolved/deferred/waiting/stale receipts and next checks |

## Source coverage object

```json
{
  "source_id": "gmail-finance-alerts",
  "domain": "finance",
  "adapter": "google-workspace:gmail",
  "status": "ok",
  "checked_at": "2026-07-01T09:00:00-04:00",
  "horizon": "newer_than:7d plus important/unread finance terms",
  "query_or_scope": "payment OR failed OR due OR statement OR security OR card OR claim",
  "result_count": 8,
  "sample_refs": ["gmail:thread:redacted"],
  "privacy_tier": "private_financial",
  "write_authority": "none",
  "failure_mode": null,
  "notes": "Only compact redacted snippets used in the brief."
}
```

Allowed `status`: `ok`, `partial`, `blocked_auth`, `disabled_by_policy`, `not_checked`, `error`.

## Radar item object

```json
{
  "item_id": "R1",
  "kind": "obligation",
  "domain": "finance",
  "summary": "A business billing alert may require manual review.",
  "why_top_of_mind": "Potential service risk if unresolved.",
  "source_refs": ["gmail:thread:redacted"],
  "freshness": "same-day email",
  "urgency": 5,
  "leverage": 4,
  "risk": 5,
  "tractability": 4,
  "confidence": 5,
  "compounding": 3,
  "priority_score": 27.0,
  "owner": "user",
  "status": "new",
  "next_check": "after billing readback",
  "merged_from": ["gmail-finance-alerts"],
  "care_bucket": "protect",
  "suppression_reason": null
}
```

Allowed `kind`: `obligation`, `opportunity`, `risk`, `waiting_on`, `decision`, `follow_up`, `anomaly`, `relationship`, `metric`, `idea`.

Allowed `status`: `new`, `continuing`, `waiting`, `blocked`, `done`, `stale`, `watching`, `suppressed`.

Common `domain`: `knowledge_base`, `finance`, `projects`, `job_apps`, `email`, `messages`, `calendar`, `repos`, `travel`, `research`, `relationship`, `personal`, `other`.

## Care ledger entries

Use compact objects for the care sections. They can reference an item/action when applicable.

```json
{
  "entry_id": "H1",
  "item_id": "R2",
  "action_id": "A2",
  "domain": "relationship",
  "summary": "Prepared a warm check-in draft; nothing sent.",
  "status": "prepared",
  "source_refs": ["contact:redacted"],
  "next_check": "tomorrow morning"
}
```

Recommended `status` values: `handled`, `prepared`, `needs_approval`, `watching`, `suppressed`, `waiting`, `blocked`, `resolved`, `stale`, `not_checked`.

## People / promise ledger object

```json
{
  "entry_id": "P1",
  "person_or_group_ref": "contact:redacted",
  "relationship_tier": "work | family | friend | community | unknown",
  "direction": "user_owes | waiting_on_other | mutual | check_in",
  "summary": "The user may owe a reply.",
  "source_refs": ["gmail:thread:redacted", "contact:redacted"],
  "due_or_sensitivity": "tomorrow | emotionally-sensitive | low",
  "proposed_action_id": "A4",
  "send_requires_approval": true
}
```

## Meeting prep object

```json
{
  "entry_id": "M1",
  "calendar_ref": "calendar:event:redacted",
  "starts_at": "2026-07-01T14:00:00-04:00",
  "summary": "Meeting prep packet ready.",
  "prep_notes_path": "{artifact_root}/runs/.../meeting-M1.md",
  "open_decisions": ["decision needed"],
  "followup_action_id": "A5"
}
```

## Travel concierge object

```json
{
  "entry_id": "T1",
  "trip_ref": "travel:redacted",
  "summary": "Check-in window opens soon.",
  "risk_level": "low | medium | high",
  "manual_handoff_required": true,
  "checklist": ["User handles passport/payment fields manually"],
  "source_refs": ["gmail:thread:redacted"]
}
```

## Finance/admin sentinel object

```json
{
  "entry_id": "F1",
  "finance_event": "payment_failed",
  "class": "urgent_risk",
  "summary": "Billing alert may require manual payment-method review.",
  "sensitivity": "private_financial",
  "redaction_policy": "no account/card/raw transaction values",
  "requires_user_handoff": true,
  "proposed_action_id": "A1"
}
```

Recommended `finance_event` values: `payment_failed`, `bill_due`, `statement_available`, `autopay_active`, `subscription_renewal`, `subscription_price_change`, `refund_or_claim_update`, `cashflow_warning`, `tax_or_legal_deadline`, `no_action_required`.

Recommended finance classes: `urgent_risk`, `upcoming_obligation`, `routine_noop`, `opportunity`, `manual_only`.

## Action object

```json
{
  "action_id": "A1",
  "number": 1,
  "item_id": "R1",
  "title": "Review billing handoff checklist",
  "type": "finance_review",
  "target": "Google Admin billing",
  "side_effect_class": "financial_or_legal",
  "exact_proposed_output": "Manual handoff checklist; no card data typed by agent.",
  "draft_text": null,
  "approval_phrase": "approve 1",
  "requires_confirmation_before_execute": true,
  "verification": "Billing status readback shows issue resolved or user confirms manual update.",
  "rollback_or_safety": "No financial action performed by default; stop before payment/card submit UI.",
  "metric_hook": {"on_approved": "action_acceptance_rate", "on_verified": "action_completion_rate"},
  "status": "proposed"
}
```

Allowed `type`: `message_draft`, `email_reply`, `calendar_event`, `task`, `research`, `implementation`, `review`, `admin`, `finance_review`, `no_op_monitor`, `question`, `draft`, `meeting_prep`, `travel_handoff`, `promise_followup`.

Allowed `side_effect_class`: `read_only`, `draft_only`, `external_send`, `runtime_mutation`, `financial_or_legal`, `destructive`.

## Approval event

Approvals are typed events. Record the exact user text and resolved action IDs.

```json
{
  "approval_id": "appr-20260701T093012-0400",
  "run_id": "radar-20260701T090000-0400",
  "received_at": "2026-07-01T09:30:12-04:00",
  "raw_text": "approve 1, 3 with edit: make it warmer",
  "resolved_actions": ["A1", "A3"],
  "edits": {"A3": "make it warmer"},
  "not_approved_actions": ["A2", "A4"],
  "authority_interpretation": "Approval applies only to A1 and A3 exact payloads after the requested edit."
}
```

Financial/legal approval should also record:

```json
{
  "financial_or_legal_scope": "billing status review only; no payment submit or card entry",
  "secrets_policy": "agent will not type secrets/payment credentials",
  "handoff_required": true
}
```

## Execution receipt

```json
{
  "receipt_id": "exec-A1-20260701T093500-0400",
  "run_id": "radar-20260701T090000-0400",
  "action_id": "A1",
  "approved_at": "2026-07-01T09:30:12-04:00",
  "started_at": "2026-07-01T09:31:00-04:00",
  "finished_at": "2026-07-01T09:35:00-04:00",
  "executor_skill": "google-workspace",
  "tool_refs": ["gmail:thread:redacted"],
  "outcome_status": "blocked",
  "verification_summary": "Stopped before payment-method UI; user handoff required.",
  "artifact_refs": ["{artifact_root}/runs/.../receipts.md"],
  "next_state": "waiting_on_user"
}
```

Allowed `outcome_status`: `executed_verified`, `executed_unverified`, `blocked`, `cancelled`, `partial`, `deferred`, `failed_safe`.

## Metrics object

```json
{
  "source_coverage": {"available": 10, "checked_ok": 7, "partial": 1, "blocked": 2},
  "top_item_count": 7,
  "proposed_action_count": 5,
  "approved_action_count": 0,
  "verified_action_count": 0,
  "false_positive_count": 0,
  "false_negative_count": 0,
  "stale_item_count": 1,
  "burden_reduced_count": 4,
  "interrupt_precision": null,
  "care_miss_count": 0,
  "prepared_but_unused_count": 0,
  "manual_handoff_success_count": 0,
  "finance_alert_precision": null,
  "blocked_by_auth_or_policy": ["bank-api-auth-missing"],
  "quality_notes": []
}
```

Feedback labels: `useful`, `not_useful`, `false_positive`, `false_negative`, `missed`, `too_noisy`, `wrong_authority`, `good_draft_bad_timing`, `action_completed`, `action_blocked`, `care_miss`, `suppressed_correctly`, `manual_handoff_completed`.

## Product UI implications

- Care state becomes the top hero: clear / mostly clear / needs attention / fire drill / blocked.
- `already_handled` becomes trust-building proof that the assistant did work without creating risk.
- `needs_you` and `actions` become approval cards/buttons.
- `quiet_watch` explains what was intentionally suppressed or deferred.
- `source_coverage` becomes the trust/blind-spots panel.
- Finance/legal actions get gated UI and manual handoff mode.
- Receipts and feedback labels become the supervised improvement loop.
