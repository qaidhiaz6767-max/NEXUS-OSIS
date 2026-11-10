# SQLite schema 2 and compatibility

Mission 003 uses additive schema version **2**. OSIS keeps its configured path
(`data/nexus.sqlite3`, NEXUS_DB or --db); other workspace files remain separate.
`core.py` imports and the original tasks/events/notes/memories/projects/messages/
pending_actions/audit column layouts and IDs remain unchanged.

## Upgrade behavior

Opening a Store checks workspace ownership and rejects future schema versions
before changing data. Schema creation, sidecar backfill, identity and version
stamp occur under one BEGIN IMMEDIATE transaction, with a second ownership/
future-version check under the lock. An exception rolls back the migration.
Repeated startup is idempotent. Foreign keys are enabled for Store connections.

| Additive table | Purpose / relationship |
|---|---|
| project_details | One per project: owner, target_date, updated_at |
| milestones | Project ID, title, target date, planned/done, timestamps |
| task_details | One per task: description, optional project/milestone, completed_at, follow_up_context |
| task_dependencies | Unique directed task prerequisite edges; both IDs foreign keyed |
| meetings | Optional project, agenda, draft_minutes, participant labels, dates |
| decisions | Optional meeting/project, draft/approved, body/source, approval provenance |
| meeting_actions | Meeting, proposed owner/deadline/priority, draft/confirmed, optional converted task |
| memory_details | One per fact: category, source_ref, valid_until, confirmation; cascades on fact deletion |
| plan_records | One per pending action: objective, state, verified result/failure |
| pending_context | Fingerprints of referenced rows at proposal time |
| command_runs | Command, intent, lifecycle, linked approval and outcome |
| command_transitions | Ordered observable state changes |
| conversation_references | Workspace-local verified task/project/meeting reference IDs |

Indexes support task project/completion lookup, meetings by project and commands
by linked action. Relation consistency and cycle checks also run in the executor;
raw SQL outside the application is not constrained by all business rules.

Backfill creates empty task/project sidecars and default memory details. It does
not guess project/task relationships, attendance or historical completion times.
Existing facts preserve legacy provenance and receive operational_fact category;
“confirmed” records approval-to-save semantics, not independent fact checking.
Existing pending actions receive plan records; they keep original expirations.
Legacy proposals do not acquire invented proposal-time fingerprints.

## Safe operator procedure

1. Stop the app and keep a private full SQLite backup outside Git. For schema 1
   databases from Mission 001/002, the new backup CLI can snapshot read-only before
   opening the new Store. For older unversioned installations, keep a private
   SQLite-supported snapshot before migration; the encrypted CLI requires a
   workspace identity and supported version.
2. Test the new app against a private copy first. Never upload the database or
   exports to a PR. This development mission migrated only synthetic databases.
3. Confirm IDs/records on the copy, then perform any actual local upgrade yourself.
   No MacBook data or installation is modified by this branch.
4. Use controlled restore for recovery. Downgrading code is not a database
   rollback: older schema-1 code rejects schema 2. Restore an appropriate private
   snapshot with matching software if a downgrade is required.

The legacy JSON download is a record export, not a full database restore format.
The encrypted SQLite archive preserves schema, relationships, operational history
and approvals; restoration invalidates unfinished approval tokens. See
[DATA_SAFETY.md](DATA_SAFETY.md) for the implemented CLI and limitations.
