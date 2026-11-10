# Mission 001 implementation plan and remaining roadmap

Mission 003's incremental plan and completed milestones are recorded in
[MISSION_003_REPORT.md](MISSION_003_REPORT.md). The sections below retain the
Mission 001 implementation history.

## Completed sequence

1. Audit the existing source and tests; pin upstream commit, preserve imports,
   schema and OSIS commands; create `feat/universal-nexus-core`.
2. Extract validation, commands, storage and orchestration into `nexus/` with a
   compatible `core.py` facade; retain the standard-library offline runtime.
3. Introduce a trusted workspace registry, per-workspace SQLite files, ownership
   checks and capabilities enforced at storage and HTTP entry points.
4. Add transactional additive migrations, projects and memory provenance sidecars.
5. Add literal memory/project/note/history search, approval-gated memory updates
   and deletion, and atomic plans of up to five writes.
6. Make cloud AI explicitly opt-in, centralize the tool manifest, scope model
   context and distinguish model drafts from executed results.
7. Ship the navy executive dashboard, request-scoped workspace switcher, projects,
   memory search/edit/delete, full approval preview and visible plan reporting.
8. Add temporary offline `--demo`, data exclusions, sanitized error categories,
   tests, optional browser smoke and CI configuration.
9. Run regressions and browser checks using invented temporary records. Write
   architecture, upgrade instructions and review report. Commit and prepare PR;
   leave merging and any real-data upgrade to the owner.

## Acceptance gates

- Existing OSIS workflows and import APIs pass regression checks.
- Legacy schema fixture retains IDs, facts and pending approvals after migration.
- HTTP clients cannot choose paths, access ungranted workspaces or decide another
  workspace's action; exports/context/search do not cross workspace boundaries.
- Approvals are explicit, expiring, one-time and serialized under concurrency.
- Plan failure rolls back business records, provenance and approval state together.
- An API key alone triggers no provider request; model calls are mocked in tests.
- Browser project creation requires approval and leaves OSIS records untouched
  when performed in Personal; layout works at desktop and mobile widths.
- No real records, credentials or exports are committed, and no merge/deploy occurs.

## Mission 002 — Recovery and richer projects (recommended next)

Implement and verify private SQLite backup/restore with schema/ownership validation
and a non-destructive restore preview. Add project update/archive, project-linked
tasks and explicit dependencies. Add retention and purge previews for history,
proposals and audit; deleting a saved fact should explain retained copies. Provide
trusted local permission configuration with a clear preview and migration story.

Exit gate: backup/restore and retention drills on invented data, preserved workspace
boundaries, and testable project workflows. No real user data until owner review.

## Later missions

- Provider-neutral planner adapter and citations to retrieved facts; semantic
  search only after privacy, performance and relevance evaluation.
- Local speech evaluation and microphone tests on the owner's actual hardware.
- Specialist planners behind the same tool/approval boundary; no open-ended loops.
- Read-only external adapters with explicit account consent and minimal scopes.
- Authentication/session isolation before any multi-user, LAN or hosted operation.
- Outbound writes only with recipient/content previews, idempotency and provider
  confirmation. OpenClaw remains an optional independently reviewed adapter.

Finance and ATLAS currently share only generic local records. Financial advice,
trading, payments, company systems and organization permissions are not implemented.
