# Radar follow-up execution and closeout hooks

Use this when the user approves multiple Radar actions and the session must turn a brief into executed/verified follow-up work.

## Lessons

### Parse approved actions against the latest visible task list

When the user replies with approvals like `Approve 2, 3, 4, 5, and 6`, immediately map those numbers to the latest Radar packet/brief or preserved task list. If context compression later appends a preserved todo list, treat that as the active execution queue and update the session todo state before continuing.

Good pattern:

1. Mark the current item `in_progress` and previous completed items `completed` in `todo`.
2. Execute only the approved scope for each numbered action.
3. For each action, write/read back receipts or source artifacts before moving on.
4. Keep a final `receipts` item pending until the Radar packet/receipts are actually updated.

### Safe billing/payment arrival monitoring

For user-reported transfers or funding events, Radar may create a **read-only monitor** only when the user asks/approves monitoring.

Safe pattern:

- Watch email/admin-visible billing or payment confirmation signals; do not inspect or mutate bank/card/payment systems.
- Prefer a no-agent cron/watchdog script that stays silent on no-match and emits only success/checkpoint/error messages.
- Add a baseline timestamp after the user says the transfer was initiated.
- Tighten classifiers to avoid false positives such as rewards/points-transfer messages; require both money/billing context and an arrival/success term.
- Report "monitor created" only after the script has run once and the cron job exists.

### Calendar OAuth reauth prep

When Calendar is blocked by missing Google scopes but Gmail still works:

1. Run the Google Workspace setup check and confirm it is `AUTHENTICATED (partial)` or otherwise missing Calendar scope.
2. Inspect only non-secret OAuth client metadata before presenting a URL: client type, project id, redirect URIs, client-id prefix/suffix, secret-present boolean.
3. Generate an auth URL for the narrow service set needed, typically `email,calendar` when preserving existing Gmail capability plus adding Calendar.
4. Tell the user that `localhost:1` / unsafe-port browser failure after approval is expected; they should paste back the entire redirected URL.
5. Do not create/read/mutate external Calendar events until the reauth exchange is complete and verified.

### Profile-scoped Radar closeout hook beats SOUL edits

Do not edit `SOUL.md` for Radar closeout behavior. Use a profile-scoped plugin hook instead:

- Put a general plugin under the active profile, e.g. `{HERMES_HOME}/plugins/radar-closeout/`.
- Register `pre_llm_call` to inject a compact, ephemeral user-message checklist only on Radar-like turns. This preserves system-prompt cache and avoids global persona/root-instruction blast radius.
- Register `post_llm_call` only for sanitized observer logging; do not store raw private content.
- Keep the hook advisory: it should remind the agent to close/update todos, receipts, and approval boundaries, not bypass approvals or execute side effects.
- Verify SOUL files by hash before/after and explicitly report unchanged.

### Enabling profile plugins safely

`hermes config set plugins.enabled '["x-publish","radar-closeout"]'` can write the list as a YAML string in some versions because `config set` performs scalar coercion, not JSON/YAML parsing for lists. Prefer one of:

- `hermes plugins enable radar-closeout` when available; or
- a tiny Python config update using `yaml.safe_load` + Hermes `atomic_yaml_write`, preserving an actual YAML list.

Verification should check the final YAML shape:

```yaml
plugins:
  enabled:
  - x-publish
  - radar-closeout
  disabled: []
```

For runtime hook verification, do not assume `PluginManager.get_loaded_plugins()` exists. Safer probes are:

- `hermes plugins list` / `hermes plugins` status where available;
- `discover_plugins(force=True)` plus `invoke_hook('pre_llm_call', ...)` and `invoke_hook('post_llm_call', ...)` in a temporary Python process;
- if using internals, inspect `get_plugin_manager()._plugins` defensively rather than calling a nonexistent public getter.

### Reporting discipline when interrupted by tool limits

If a turn hits the tool-call cap before receipts are fully updated, be explicit:

- which actions are verified complete;
- which artifacts/commits/cron jobs/URLs exist;
- which verification failed and why;
- which final receipts are still pending.

Do not claim the whole Radar follow-up is complete until the main packet/receipts have been updated/read back.

### Final receipt closure recipe

When resuming after interruption or context compression, close the Radar follow-up by updating all three artifacts, not just chat:

1. Re-read enough of `packet.json`, `receipts.md`, and `source-coverage.json` to preserve schema/shape.
2. Set each approved action to one of the packet schema statuses: `executed_verified`, `partial`, `blocked`, `deferred`, `failed_safe`, etc. Use `partial` for actions that were safely prepared/monitored but still require the user (billing/payment handoff, OAuth browser flow).
3. Add a compact `followup_execution` array or equivalent execution receipts with `action_id`, status, summary, and verification refs.
4. Reduce `needs_you` to only live human/manual gates; do not leave already-executed approvals as pending decisions.
5. Add follow-up source coverage entries for verification paths such as cron list, local artifact readbacks, git/test/build receipts, plugin status, and hash readbacks.
6. Update `receipts.md` with a human-readable status table, remaining manual gates, and boundaries held.
7. Validate `packet.json` parses and conforms to `templates/radar-packet.schema.json`; read back `receipts.md` and any source-coverage mirror before marking the session todo complete.

A good final chat summary reports the schema/readback checks and the remaining live gates only, not the full narrative again.
