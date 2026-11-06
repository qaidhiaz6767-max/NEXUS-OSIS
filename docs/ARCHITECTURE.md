# Technical architecture — NEXUS

## 1. Current v0.1 implementation (working)

```text
User on Mac
    |
    +-- Keyboard -------------------------------+
    +-- Microphone (browser recognition) -------+-- web/index.html, app.js, style.css
    +-- Spoken replies (browser TTS) -----------+         |
                                                         | HTTP localhost only
                                                         v
                                              app.py :127.0.0.1:8765
                                                    |           |
                                       /api/chat /api/decide   /api/state, /api/backup
                                                    |           |
                                             Coordinator       |
                                          /      |      \       |
                                   command    optional AI   Store (SQLite)
                                   parser     reasoning      |
                                          \      |          approval proposals
                                            policy checks    |
                                             require approval
                                                    |
                                                SQL transaction
                                                    |
                                              audit + database
```

The app is a small **modular-monolith prototype**. This picture is what exists today, not a claim that future services are implemented.

**Core data entities:** tasks, events, notes, memories, messages, pending_actions, audit. SQLite stores all local data under `data/nexus.sqlite3`, ignored by Git. Optional model calls send relevant bounded context outside the device if configured; voice recognition may also use cloud services depending on browser.

**Trust boundaries:** browser UI is untrusted; submitted JSON is untrusted; model output is untrusted; stored notes and task titles are untrusted content; calls from potential OpenClaw bridge would be untrusted until independently authenticated and authorized. Only `validate_action` and the `Store` transaction may mutate the database.

## 2. Target architecture (PLANNED, not shipped)

```text
User
  |-- Browser dashboard / keyboard
  |-- Push-to-talk voice interface
  |-- Future authorized messaging bridge
  v
[Interface controller]
  - identity / workspaces
  - session protections and input validation
  v
[NEXUS Coordinator]
  |-- intent recognition and clarification
  |-- bounded plan construction
  |-- contextual retrieval from authorized records
  |-- tool registry with typed schemas
  |-- policy engine + permission checks
  |-- approval queue and human review
  |-- result verification + audit
  v
[Domain services]
  |-- Projects and milestones
  |-- Tasks and delegations
  |-- Meetings and decisions
  |-- Communications drafts
  |-- Briefings and reports
  v
[Persistence / adapters]
  |-- SQLite primary records + migrations
  |-- Local files within approved directory only
  |-- Optional read-only calendar adapter
  |-- Optional read-only document adapter
  |-- Future sandboxed OpenClaw bridge
```

Do **not** split these into network microservices on an M2 laptop solely for aesthetics. Interfaces can be separate Python modules while running in one application and one process. Real adapters should be independently testable without real accounts.

## 3. Orchestration contract

A task execution plan consists of `plan_id`, `intent`, `workspace`, `context_refs`, `proposed_actions[]`, `risk_class`, `requires_confirmation`, `status`, `created_at`. All action proposals carry unique IDs and a timeout. Only structured, explicitly supported operations are accepted. Raw tool output cannot be treated as new system instructions.

### Proposed state machine

```text
RECEIVED
  -> CLASSIFIED
  -> CONTEXT_RETRIEVED
  -> DRAFTED_PLAN
  -> WAITING_FOR_APPROVAL
       | reject -> CANCELLED
       | expiry -> EXPIRED
       | approve -> VALIDATED_AGAIN
  -> EXECUTING
  -> VERIFIED
       | verified success -> COMPLETED
       | failure -> FAILED / NEEDS_REVIEW
  -> AUDIT_RECORDED
```

For school communications, extra states must exist: `DRAFTED`, `APPROVED_TO_SEND`, `SENT_BY_PROVIDER`, `DELIVERY_UNKNOWN`, `ACKNOWLEDGED_BY_RECIPIENT`. Never combine `sent` with `seen` or `accepted`.

### High-level examples

- **Read-only:** “What needs to be done?” -> retrieve authorized tasks -> deterministic list -> optional generated summary -> links to records.
- **Local write:** “Assign stage prep to the technical committee.” -> parse task owner -> propose with full details -> approve -> transaction -> verify DB row.
- **Future external write:** “Send reminder to pengurus.” -> verify intended audience -> draft -> preview recipients/body -> approve -> provider send -> confirmed status -> audit.
- **Uncertain:** “Move tomorrow's meeting.” -> search event and time -> ask clarification if ambiguity -> never guess.

## 4. Model provider boundary

For initial AI functionality, the Python OpenAI SDK is optional. Keep an explicit interface (future `ModelProvider`) so changing models does not change database permissions. Model prompts contain short, privacy-safe summaries, never the entire database or raw transcript by default. Function calls are **proposals**, not authoritative actions. Model response or content from documents must not override the tool allowlist.

Recommended later components (do not install just because they are trendy):

- `model_provider.py`: chat completion/response and tool call parsing.
- `policy.py`: fixed access matrix and risk categories.
- `models.py`: typed project/task/meeting contracts.
- `services/`: transactionally safe OSIS operations.
- `storage/`: migrations, queries, backup/restore.
- `adapters/`: external services, off by default.
- `ui/`: front-end and accessibility.

Plan for provider timeouts and partial failure. A model call may time out **after** returning a proposal; safe retries should not duplicate DB writes or external sends. Test this deliberately.

## 5. Data flow and privacy

**Local command:** keyboard -> local browser -> localhost HTTP -> deterministic command parser -> optional approval -> SQLite.

**AI command:** keyboard -> local browser -> server -> small authorized context -> external AI API -> text/proposed function -> local policy -> human approval -> SQLite. Only if optional key configured. User should clearly see this privacy difference.

**Voice input:** mic permission -> browser transcription (may be online) -> editable textbox -> user submits -> above pipeline. Don't secretly send hot mic audio.

**Calendar export:** `events` -> generated ICS file -> user imports manually; export isn't evidence of calendar synchronization.

**Private OSIS content:** not in Git, logs, CI artifacts, examples or shared issues. School records should not be imported unless permission, retention policy and data classification are established.

## 6. Local API conventions (current)

| Endpoint | Method | Purpose | Side effect |
|---|---|---|---|
| `/` | GET | dashboard | None |
| `/api/state` | GET | bounded local state | None |
| `/api/help` | GET | command help | None |
| `/api/chat` | POST | parse command, request answer/proposal | Chat history + possible pending proposal |
| `/api/decide` | POST | approve/reject pending proposal | Controlled mutation |
| `/api/backup` | GET | export local records | Downloads sensitive export to local browser |
| `/api/calendar.ics` | GET | export ICS | Downloads locally |

Note that `/api/chat` writes chat history even for read requests; future privacy controls should allow disabling or deleting this history. The HTTP API is for the **same local operator**, not a deployable multi-user SaaS API.

## 7. Database evolution plan

Current schema stays until a migration framework is available. Target conceptual entities:

| Entity | Key fields | Why it matters |
|---|---|---|
| `workspaces` | id, category, owner_id, retention_policy | Separate OSIS / personal / ATLAS |
| `projects` | id, workspace_id, title, status, lead_role, target_date, charter | Program tracking |
| `milestones` | id, project_id, title, target_date, state | Key gates |
| `tasks` | id, project_id, title, owner_ref, due_at, priority, status, blockers | Operational follow-through |
| `meetings` | id, project_id, when, agenda, minutes | Meeting lifecycle |
| `decisions` | id, meeting_id, summary, decided_at, superseded_by | Governance memory |
| `action_proposals` | id, workspace_id, actor_id, type, args, risk, status, expires | Permission workflow |
| `audit` | id, actor, action, result, timestamp, redaction | Traceable changes |
| `drafts` | id, project_id, audience, content, review_status | Communications |
| `data_sources` | id, workspace_id, origin, permission, refresh_date | Provenance |

**Migration rule:** before any schema change, back up SQLite to a safe local location and test upgrading a copy. Document migration forward and rollback or restore, and never silently overwrite older records.

## 8. Reliability and performance boundaries

- Current single-user local system: tests focus on correctness, SQLite transactions and errors.
- Future read-heavy performance: add indexes and paging before adding cache layers.
- Future online API: treat quotas, cost ceiling, retries and request cancellation as explicit requirements.
- Future integrations: implement circuit breakers and rate limits, not infinite polling.
- No arbitrary code execution as an LLM tool; any developer-use local coding assistant would live in a separate sandbox with explicit review.
- Future agent parallelism should be capped (for example 2–3 specialist subtasks), with a user-configurable budget and no sensitive cross-workspace context.

## 9. OpenClaw integration boundary (later)

OpenClaw must be a separate gateway/adapter, not a path around NEXUS approval checks. First version should be **read-only**: authenticated user asks for `/brief`, adapter invokes read-only method, returns short summary. Next phase may allow proposals, but approval is completed inside NEXUS. Restrict sender allowlist, per-chat/session isolation, filesystem and shell access; log only minimal metadata. Never expose localhost to public internet to make an integration easier.

Official security references:
- https://docs.openclaw.ai/gateway/security
- https://docs.openclaw.ai/gateway/security/tool-permissions
- https://docs.openclaw.ai/gateway/sandboxing

## 10. Core tradeoffs

| Decision | Advantages | Cost / limitation |
|---|---|---|
| Python core | Easy to learn, test and modify | Needs engineering discipline |
| SQLite | Offline, no database server | Not suitable for multi-tenant deployment |
| Local web UI | Works on Mac without app-store packaging | Not secure for remote exposure |
| Optional cloud AI | Flexible language/planning | Cost, privacy and network dependency |
| Approval-first | Reduces silent mistakes | More clicks than unrestricted automation |
| No mandatory OpenClaw | Fewer moving parts | Messaging integrations take more work later |

## 11. Definition of production readiness (far beyond current state)

An OSIS production deployment would require identity/access management, clear school authorization and governance, secure backup/recovery, encryption decisions, robust integration audit, incident response, accessibility testing, supervised privacy review and penetration testing for any network exposure. A personal localhost prototype is **not** automatically a production-safe school information system.
