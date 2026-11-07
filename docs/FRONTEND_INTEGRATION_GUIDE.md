# Claude frontend handoff — Mission 003

The entire `web/` tree remains byte-for-byte unchanged from Mission 002. This
branch adds backend functionality and documentation. Use [API_CONTRACT.md](API_CONTRACT.md)
as the source for routes and payloads; no frontend endpoint is implied by a
Python interface or a roadmap item.

## Start with a safe local session

```bash
python3 app.py --demo
```

Demo uses disposable synthetic records, disables model calls and leaves ordinary
databases untouched. Run your frontend from this server at `127.0.0.1:8765`.
All fetches must retain workspace query parameters; POSTs require JSON and
`X-NEXUS-Local: 1`. Existing `web/api.js` already implements these conventions.
There is no cross-origin development API or authentication layer.

## Recommended integration sequence

1. Load readable workspaces and `/api/capabilities` for the selected workspace.
   Treat unsupported features as unavailable, not simulated successes.
2. Keep existing `/api/state`, `/api/chat`, `/api/propose`, `/api/decide`, search
   and exports. Existing fields and IDs retain their meaning; ignore unfamiliar
   additive fields until the UI supports them.
3. Render `kind` separately from message text: verified records, recommendations,
   model drafts, pending approval, clarification or unavailable. A provider
   connection indicator does not verify a model's statements.
4. Render the complete normalized `pending.args`, including nested project tasks,
   milestones, owners, dates and dependency positions. Show expiry and memory
   conflict diagnostics. Never infer approval from prose or approve automatically.
5. Submit the displayed token once to decide. Use actual `outcome`, refresh state,
   and fetch `/api/plans/<id>` for the verified result. On 400/500 refresh before
   offering another decision; show the recorded failure, not a success toast.
6. Use new project/task/meeting/detail routes for relationship views and the
   briefing route for executive summaries. List endpoints are bounded; dashboard
   counts must use `summary` or report counts, not visible array lengths.

Chat returns synchronously, including `command_id` and lifecycle/history. There
is no streaming or background completion to poll. Fetch `/api/commands/<id>`
after a decision/reload for persisted progress. `completed` on a read command
means an answer was produced. Plan `result.verified:true` after approval means
the local transaction committed. Cancel pending work with approve:false.

## New UI data distinctions

- Projects retain title/goal/status/id and add owner/target_date/updated_at.
  Task details add description/project_id/milestone_id/completed_at/
  follow_up_context. Old completed tasks may have unknown completion times.
- Task ownership is a local label. Delivery is `not_sent`, acknowledgment
  `not_tracked`. Do not display “Selma notified” from an assignment response.
- Meetings contain agendas and **draft** minutes; participant labels are not
  verified attendance. Existing event and note records remain separate records.
- Recording a decision creates a draft, even after approving the write. An
  existing decision requires a new approve_decision proposal and explicit review
  before its business status becomes approved. Meeting action items similarly
  require confirmation before conversion to tasks. Do not guess future IDs.
- Memory confirmation means approval to save. Show source/source_ref/time,
  category and stale label. A decision-category memory is not a decision-register
  entry. Meeting decisions must use the structured decision workflow.
- Updates replace their documented editable fields. Prefill full values from
  the actual record before submitting update_task/update_project, so defaults
  cannot silently clear optional links or dates.

The unchanged Mission 002 interface still describes milestones/structured
meetings as future functionality and provides basic project forms. Claude can
now replace those panels using the capabilities and real routes in this branch.
No visual redesign or UI activation is included here.

## Minimal request example

```javascript
const workspace = 'osis'; // Capture the selected workspace for this operation.
const response = await fetch(`/api/propose?workspace=${encodeURIComponent(workspace)}`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-NEXUS-Local': '1'},
  body: JSON.stringify({name: 'create_task', args: {title: 'Review sample agenda'}})
});
const proposal = await response.json();
if (!response.ok) throw new Error(proposal.error);
// Display proposal.pending.args. Only the user's explicit approval sends /api/decide.
```

Preserve the captured workspace through request/decision/refresh and discard
stale responses after switching. Render untrusted text as text, never innerHTML.
No memory or model content may choose permissions, workspace paths or tools.

## Voice contract

Retain push-to-talk, visible recording state, stop/cancel, transcript editing
and a separate send operation. Browser recognition may send audio to platform
services independently of NEXUS's model opt-in. Obtain permission before use;
do not enable continuous listening. Send reviewed text through chat and speak
only displayed responses when the user enables output. Cancellation of speech
does not undo a committed task; approvals still use the standard flow.

Independent Python speech and cancellation protocols exist for future adapters.
No backend speech provider, audio retention, streaming, paid speech call or Mac
microphone behavior was verified. Text remains fully functional.

## Validation performed

Synthetic HTTP contract tests cover old fields, new routes, workspace denial,
approval lifecycle, malformed inputs and actual project/meeting/memory results.
Existing frontend tests and Chromium journeys pass. Live model calls, external
accounts, Claude's future UI and MacBook audio remain unverified. This branch
does not change the owner's installed application or deploy a site.
