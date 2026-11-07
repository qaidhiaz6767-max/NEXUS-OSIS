# NEXUS cognitive Core — Mission 003

Status: working bounded local coordinator, schema 2, backend v0.5. Baseline is
Mission 002 (`0e581df`), which depends on Mission 001 (`e34b677`). The frontend
remains unchanged. Main was not merged. See [implementation report](MISSION_003_REPORT.md).

## Command lifecycle and authority

```text
HTTP/CLI text + trusted workspace registry
  → validate input → persist received/planning + recent conversation
  → deterministic bilingual intent / existing OSIS parser
  → optional replaceable model with scoped bounded context
  → validate all returned tools
      read tools → actual scoped results → report
      local writes → normalized proposal + record fingerprints → await approval
  → human decision → expiry/replay/fingerprint/schema/relationship checks
  → one SQLite transaction → execute → verify commit → audit/result/history
```

`orchestrator.Coordinator` is the sole command coordinator. `Store` owns
persistence and approval execution; `planning` owns state transitions and
optimistic snapshots. The model does not execute operations, choose a database,
grant authority or approve work. There is no shell/filesystem/network tool.
Public methods retain `core.Store`, `core.Coordinator` compatibility.

Authority 0–1 returns information/drafts, 2 prepares explicit changes, 3 is a
single approved local transaction. Host grants (`read,propose,approve,export,ai`)
are checked server-side. Operational command/chat/audit records persist during
normal use without a separate confirmation; business records require approval.
Levels 4–5 remain disabled protocols, not active background services or agents.

Command and plan states are persisted, with timestamped command transitions.
Failed local writes roll back completely and retain a failure record. Rejection
and expiry cancel linked work. Tokens commit once. Snapshots restored from
backup invalidate unfinished approvals. Execution is synchronous; there is no
durable worker, streamed progress, crash-resuming job or unrestricted retry loop.
Crash-interrupted planning can remain unfinished until recovery/manual diagnosis.

## Language and provider boundary

`intents` supports common English/Indonesian/mixed briefings, unfinished work,
owner priorities, previous decisions, task completion references and confirmed
meeting follow-ups. The original slash commands remain the broad deterministic
fallback. Richer novel objectives require an explicitly enabled model; the
offline classifier is intentionally finite. Indonesian prompts can route
correctly while deterministic report labels remain English.

`Provider.respond(...) → ModelReply` is replaceable and tested with injected
fakes. `OpenAIResponsesProvider` uses Responses API, timeout 25 seconds, zero SDK
retries, 3,000 output tokens, store:false, one call per turn and at most five tool
calls. Incomplete output, malformed argument JSON, unknown tools, duplicates and
invalid operations cannot create partial proposals. Missing SDK/key, network
failure or timeout returns a bounded unavailable response and keeps local tools
usable. Live paid calls were not performed. SDK transport and real provider
schema acceptance remain unverified against a live account.

The model receives at most eight previous messages plus the current command and
12,000 characters of selected context. Retrieved strings are capped and whole
JSON objects are retained. The model can request five read-only tools:
read_tasks/search_memory/get_project/review_events/generate_briefing. Read results
are returned directly as verified local evidence; there is no second model call
to synthesize newly fetched tool output. Model prose without tools is marked
draft, not verified fact or a completed action.

Conversation is workspace-local and persisted. Pronouns for task completion
resolve from verified local task changes, or a unique open task. Ambiguous
multi-action task references require clarification. Model prose cannot overwrite
these references. This is narrow reference resolution, not universal discourse
understanding or an arbitrary project planner.

## Structured planning and executive records

Two bounded plan types share the same approval and transaction boundary:

- `execute_plan`: 1–5 allowlisted local actions, with no nested execution plan.
- `create_project_plan`: one explicit project objective, up to five milestones
  and 1–20 task drafts. Internal dependencies use earlier 1-based task positions;
  milestone positions are explicit. The executor creates actual IDs and links
  them atomically. This is the only supported new-record reference mechanism.

Project/task details use sidecar tables so original IDs and table layouts survive.
Dependencies are acyclic, prerequisite completion is enforced, and a project or
milestone cannot be completed with open linked tasks. Historical relationships
are never inferred. Local assignment does not imply notification, acknowledgment
or completion. Completion time is recorded only on a verified status transition;
legacy completed tasks retain unknown timestamps.

Meetings store an agenda, draft minutes and participant labels. They do not
verify attendance or infer decisions from text. Decision drafts require separate
review before approved status. Draft action items require confirmation before
conversion to one linked local task. “Summarize our last meeting” reports actual
stored text and confirmed actions; it does not manufacture minutes or extract
unsupported decisions. See [API contract](API_CONTRACT.md).

## Memory and retrieval

`memories` remains the key/value foundation, supplemented by source/approval
metadata and category/source_ref/valid_until/confirmation. Categories cover
preferences, workspace, project objectives, decisions, meeting outcomes and
operational facts. Historical tasks and meeting outcomes also remain their own
structured records. Searchable chat is distinct from saved facts.

Creation/update/deletion uses proposals. Duplicate same-key values, conflicting
values and same-value alternate keys are exposed for review. Conflicting updates
cannot silently overwrite a fact changed since proposal. This is exact-value
conflict detection, not semantic contradiction detection. Source references are
operator/model-provided labels, not independently verified citations.

Expiry marks a fact stale, retains it for search/review and excludes it from
active model context. There is no automatic deletion or complete retention UI.
Deleting a fact does not erase chat, historical proposal payloads, audit or
archives. Obvious credential key names are rejected, but general private-data
detection is not implemented. Do not enter sensitive information into this
prototype without an appropriate policy and storage protection.

Retrieval uses deterministic token overlap over bounded local pools, with per
category quotas so long facts cannot crowd out tasks. It may miss records beyond
pool limits; use literal search or record IDs when necessary. Search escapes
SQLite LIKE wildcards and uses parameters. No vector store or embedding API.

An in-memory synthetic evaluation of 2,000 facts over 50 runs found SQLite FTS5
available: mean substring query 0.074 ms and FTS5 word MATCH 0.040 ms on this Linux
executor. These query semantics differ and the small result does not establish
application-scale superiority. Keep compatible substring search and bounded
selection; FTS5 is evaluated but not enabled. Measure representative authorized
datasets before adding indexing or semantic retrieval.

## Briefings, voice and future adapters

Briefings read full-table counts and actual IDs, current open work, upcoming
events/deadlines, explicit dependency blockers, target-date project risks and
approved decisions. Recommendations are deterministic priorities and are labeled.
Week reports use recorded completion timestamps in configured local dates;
unknown legacy timestamps are disclosed. No proactive scheduling is running.

`interfaces.py` defines specialist, integration, scheduler-preview, speech-to-text,
text-to-speech, consent and cancellation boundaries. These protocols carry no
execution authority. Registered specialist manifests are inactive. A future
adapter must return to Core for validation and approval, use its own least
privilege account scopes, and expose actual results/errors. Existing browser
push-to-talk submits reviewed text through chat; there is no backend audio API,
always-listening microphone, wake-word or verified Mac voice implementation.

## Security boundaries and recovery

SQLite snapshots, authenticated encryption, preview/confirmation, workspace/schema
checks, advisory runtime locks, encrypted rollback copy and atomic replacement
provide an administrative recovery path. See [DATA_SAFETY.md](DATA_SAFETY.md).
Backups are not model tools. The live database is not encrypted. This remains a
trusted local single-user application, not a sandbox against its host account.
Prompt instructions and retrieved content cannot bypass tool validation or grant
permissions, but a model can still suggest a harmful allowed local mutation;
the operator must review every proposal. See [security review](SECURITY_AND_PRIVACY.md).
