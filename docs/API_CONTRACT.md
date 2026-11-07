# NEXUS Core HTTP contract — v0.5 / Mission 003

This describes implemented routes in `app.py` and `nexus/backend_api.py`.
The Mission 002 frontend is unchanged. The backend is a trusted, single-user
localhost application, without authentication. Never expose it to a network.

## Transport and workspace

Default base URL: `http://127.0.0.1:8765`. JSON uses UTF-8. Responses have
`Cache-Control: no-store`. Every data route accepts `?workspace=osis` (or `&workspace=`
with other parameters). IDs, history, tools and approval tokens are local to that
workspace. Omitting the query uses the server's startup workspace, normally OSIS.
Allowed workspace IDs are `osis`, `personal`, `academic`, `research`, `coding`,
`finance`, `atlas`; discover actual grants through `/api/workspaces`.

Every POST requires `Content-Type: application/json` and `X-NEXUS-Local: 1`.
Host must be `127.0.0.1:<actual-port>` or `localhost:<actual-port>`. If Origin is
present it must match either local origin at that port. There is no CORS support
for a separately hosted frontend: serve Claude's UI through this same server.
Workspace grants come from trusted Python configuration, never request bodies.

JSON errors are `{"error":"description"}`. Codes: 400 invalid input or rejected
approval execution, 403 grant/Host/Origin/header failure, 404 missing resource or
route, 500 unexpected POST failure with sanitized message. A valid chat request
may return HTTP 200 with `status:"error"` and a failed lifecycle when command or
provider validation fails. A completed command means the response was produced;
only a completed, verified approval result proves a mutation happened.

## Existing routes retained

| Method | Route | Actual response / behavior |
|---|---|---|
| GET | `/api/workspaces` | `{workspaces:[{id,label,domain,capabilities}]}`; readable workspaces only |
| GET | `/api/state` | Snapshot with `workspace,summary,projects,tasks,events,notes,memories,pending,audit,messages,timezone,demo,capabilities,system,mode`; additive `meetings,decisions,milestones,task_dependencies` |
| GET | `/api/search?q=...` | `{facts,projects,history,notes}`; literal substring search, 50 per category |
| GET | `/api/help` | `{message}` with supported slash commands |
| GET | `/api/backup` | Downloadable **plaintext JSON record export**, requiring `export`; not a restorable full database |
| GET | `/api/calendar.ics` | Manual event ICS download, requiring `export`; not Google sync |
| POST | `/api/chat` | `{message:"..."}` → synchronous command result below |
| POST | `/api/propose` | `{name:"create_task",args:{title:"Sample task"}}` → result with normalized pending action; no business writes |
| POST | `/api/decide` | `{id:"approval-id",approve:true}` → `{message,outcome,workspace}`; `false` cancels |

POST JSON size: 16,000 bytes, except `/api/propose` allows 64,000. Chat message:
3,000 characters. Chat/proposals require `propose`; decisions require `approve`;
all Store access requires `read`. Chat and proposal/audit history persist as
operational records before approval; task/project/memory changes do not.

State limits: projects 100, tasks/events 250 each, notes/memories/meetings/
decisions/milestones 100 each, dependency edges 1,000, pending 30, audit 30,
messages 35. `summary` counts use full tables. State `pending[].args_json` is a
JSON **string**; proposal responses use `pending.args` as an object. Expired
proposals may remain listed until decided; compare `expires_at` in the UI.

The JSON export keeps its original `format` (`nexus-osis-v1` or `nexus-core-v1`)
and adds `schema_version:2`, `project_details,task_details,milestones,
task_dependencies,meetings,decisions,meeting_actions`. It includes audit and
memory provenance, excludes chat/pending/command history, and has no JSON import.

## Command result and lifecycle

`POST /api/commands` is an additive alias of `/api/chat`, with the same body.
Example response shape for a proposed task (IDs/timestamps are generated):

```json
{
  "message": "Review the proposed change.",
  "pending": {
    "id": "opaque-approval-id", "name": "create_task",
    "description": "Create task: Sample task (owner: Unassigned, due: not set)",
    "args": {"title":"Sample task","owner":"Unassigned","due_date":"","priority":"medium","description":"","project_id":null,"milestone_id":null},
    "expires_at": "2026-11-07T12:00:00+00:00", "diagnostics": {}
  },
  "plan": {"workspace":"osis","id":"opaque-approval-id","status":"awaiting_approval","steps":[{"tool":"create_task","arguments":{},"status":"awaiting_approval","approval_id":"opaque-approval-id"}]},
  "provider_status": "not_verified", "kind": "pending_approval",
  "authority_level": 2, "command_id": "opaque-command-id",
  "lifecycle": {"id":"opaque-command-id","workspace":"osis","status":"awaiting_approval","history":[]}
}
```

This example abbreviates `plan.steps[].arguments` and lifecycle history; real
responses contain normalized arguments and transition records. `pending` is
absent for read responses. `plan.steps` contains a completed `respond` step for
simple replies; this is not a database mutation. Optional `evidence` contains
`[{tool,workspace,result}]` from actual read tools.

`kind`: `verified_information`, `recommendation`, `draft`, `pending_approval`,
`clarification`, `unavailable`. Model prose is always a draft. Provider status
(`not_verified`, `verified`, `error`) describes the provider observation, not the
truth of prose or action completion. `authority_level` is 0 for grounded reads,
1 for model drafts, 2 for proposals. Level 3 occurs only through explicit decide.

| Method | Route | Response |
|---|---|---|
| GET | `/api/commands/<command-id>` | `id,workspace,command,intent,status,action_id,created_at,updated_at,error_code,result,history:[{from_status,to_status,at}]`; `result` may be absent while unfinished |
| GET | `/api/plans` | `{workspace,plans:[...]}`; newest 50 |
| GET | `/api/plans/<approval-id>` | `id,workspace,objective,status,name,arguments,approval_status,expires_at,created_at,updated_at,result,error_code` |

Command path: `received → planning → completed` for a response, or `planning →
awaiting_approval → executing → completed` for approved mutations. Failures are
`failed`; rejection, attempted expiry and restored unfinished work become
`cancelled`. A failed, rolled-back local proposal can be explicitly retried
before expiry; its linked command can transition `failed → executing`. No
background worker, streaming, unrestricted loop or remote cancellation exists.
Reject the pending approval to cancel it. Synchronous `executing` becomes visible
in persisted history after the transaction, not as a live progress stream.

## Approval rules

Tokens expire one hour after proposal and can commit once. `/api/decide` outcome
is `approved`, `rejected` or `expired` on successful HTTP responses. Replay is
400. Restored pending tokens become `invalidated` and cannot execute. A failure
returns 400, rolls back **all** business writes, retains the pending token, and
records `status:failed` with `result:{verified:false,rolled_back:true,message:...}`
on its plan. Success records `result:{verified:true,atomic:true,message:...}`.

Referenced rows are fingerprinted when proposed and checked at execution.
If a row changed, request a fresh proposal. Legacy proposals predating this
migration have no fingerprints; they retain their existing expiry/validation.
Dependencies and all schemas are revalidated inside the write transaction.
Approval previews must display every normalized argument, not just description.

## Additive read routes

| GET route | Response / parameters |
|---|---|
| `/api/capabilities` | `workspace,authority,read_tools,proposal_tools,features,external_accounts_connected,voice,backup`; includes actual tool schemas and disabled future capabilities |
| `/api/briefing?period=today` | Grounded report: `workspace,period,completion_period,task_filter,sources,counts,priorities,upcoming_events,project_risks,blockers,completed_last_7_days,completion_time_unknown,approved_decisions,recommendations,message,authority_level` |
| `/api/context?q=...` | Bounded selected `facts,projects,tasks,events,notes,meetings,approved_decisions` plus workspace/date/retrieval/provenance labels; query required |
| `/api/projects` | `{workspace,projects}`; latest 100 |
| `/api/projects/<id>` | `{workspace,project,milestones,tasks,meetings,decisions}`; explicit links; approved decisions only |
| `/api/tasks` | `{workspace,tasks}`; same bounded list as state |
| `/api/tasks/<id>` | `{workspace,task,dependencies,blocked,assignment:"recorded",notification:"not_sent",acknowledgment:"not_tracked"}` |
| `/api/meetings` | `{workspace,meetings}`; latest 100 by held_on/id; raw `participants_json` retained here |
| `/api/meetings/<id>` | `{workspace,meeting,decisions,action_items,minutes_status:"draft",attendance_verified:false}`; `meeting.participant_labels` parsed array |
| `/api/decisions?status=approved` | `{workspace,decisions}`; approved default, `draft` or `all` supported; latest 100 |
| `/api/memory?category=preference` | `{workspace,facts,confirmation_meaning}`; same 100-fact bound as state; optional category |

Briefing periods are `today`, `week`, `unfinished`. Each reports current open
work and the next seven days; `week` also highlights verified completions in
the prior seven local calendar days including today. `owner` filters tasks,
not projects/events/approval totals. Sources identify actual record IDs;
recommendations are deterministic ordering, not completed operations.

## Proposal action arguments

These actions all use `/api/propose` and `/api/decide`. There are no direct
project/task/memory PATCH/DELETE routes. Unknown action names are rejected.
Unrecognized write argument keys are ignored, never interpreted as permissions.
For the model, schemas use `strict:true` and `additionalProperties:false`.

| Action | Arguments (optional/defaults in parentheses) |
|---|---|
| `create_task` | `title,owner(Unassigned),due_date(""),priority(medium),description(""),project_id(null),milestone_id(null)` |
| `set_task_status` | `task_id,status` = todo/doing/done |
| `assign_task` | `task_id,owner`; records local owner only |
| `update_task` | `task_id,title,owner(Unassigned),due_date(""),priority(medium),description(""),project_id(null),milestone_id(null),follow_up_context("")`; full replacement of editable details, not PATCH |
| `create_project` | `title,goal,status(active),owner(Unassigned),target_date("")` |
| `update_project` | `project_id,title,goal,status(active),owner(Unassigned),target_date("")`; full replacement; archive via status |
| `create_milestone` | `project_id,title,target_date("")` |
| `set_milestone_status` | `milestone_id,status` = planned/done |
| `add_dependency` | `task_id,depends_on`; existing tasks, self/cycles rejected |
| `create_project_plan` | `title,goal,owner(Unassigned),target_date(""),milestones([]),tasks`; structure below |
| `create_meeting` | `title,held_on(""),project_id(null),agenda(""),draft_minutes(""),participants([])` |
| `record_decision` | `title,body,meeting_id(null),project_id(null),source_ref("")`; saves draft |
| `approve_decision` | `decision_id`; draft must already exist when proposed |
| `record_meeting_action` | `meeting_id,title,owner(Unassigned),due_date(""),priority(medium)`; saves draft |
| `confirm_meeting_action` | `action_item_id`; existing draft → confirmed |
| `create_followup_task` | `action_item_id`; confirmed and unconverted item only |
| `remember` | `key,value,category(operational_fact),source_ref(""),valid_until("")` |
| `forget` | `key`; approved deletion, not secure erasure of history/copies |
| `create_event` | `title,day,time(""),location(""),details("")` |
| `create_note` | `title,body` |
| `execute_plan` | `steps:[{name,args}]`; 1–5 operations; nested execute_plan rejected; `arguments_json` accepted instead of args for model compatibility |

Project status: planned/active/on_hold/completed/archived. Priority: low/medium/high.
Dates: real `YYYY-MM-DD` or empty string when optional; time `HH:MM` or empty.
IDs: positive integers; nullable links may be null. Milestone must belong to the
explicit project. Doing/done requires completed prerequisites. Completing a
project or milestone requires all its linked tasks done. No inferred links.

`create_project_plan`: at most five milestones `{title,target_date}` and 1–20
tasks `{title,description,owner,due_date,priority,milestone_number,depends_on}`.
`milestone_number` is a nullable **1-based array position**, and `depends_on` is
an array of distinct **earlier 1-based task positions**, not database IDs.
This explicit template creates/link records atomically. General execute_plan
cannot guess newly generated IDs. No notifications are sent.

Memory categories: preference/workspace/project_objective/decision/
meeting_outcome/operational_fact. `confirmation:"confirmed"` means the local
operator approved saving the fact, not independent truth. `stale:true` when
valid_until is before today; stale entries remain searchable but are excluded
from selected model context. `pending.diagnostics` on remember contains
`duplicate`, `conflict:{existing_value,updated_at}|null`, `same_value_keys`.
History is not automatically promoted to facts. Credential-name filtering is
only a heuristic; the application has no general sensitive-data detector.

## Voice and unsupported operations

Review a browser transcript, then POST text to `/api/chat` using the same
workspace and approval flow. There is no audio upload, streaming transcription,
server TTS, wake-word, scheduler, specialist execution, Google OAuth, email or
notification API. `/api/capabilities` reports these limits. Encrypted full
backup/restore is an administrative CLI only: see [data safety](DATA_SAFETY.md).
