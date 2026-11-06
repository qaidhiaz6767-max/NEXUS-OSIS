# GitHub issue backlog — create these as Issues

Use one GitHub issue per item. Each has priority, milestone, effort estimate, dependency and a *testable outcome*. Estimates are rough relative complexity (S = small, M = medium, L = large), not a promise of delivery time.

## Milestone M0 — repo and security baseline

- **NEX-001 [P0/S, shipped]** Publish private starter repository. *Done when:* README, CI, .gitignore and baseline tests visible; no records or secrets committed.
- **NEX-002 [P0/S]** Add HTTP security tests. *Done when:* invalid origin, missing custom header, excessive payload and untrusted Host tests fail closed.
- **NEX-003 [P0/M]** Establish schema migration framework. *Done when:* old v0.1 DB upgrades safely, backup is generated, and repeat migration is idempotent.
- **NEX-004 [P0/M]** Verified backup/restore. *Done when:* simulated corruption/restoration preserves matching task/event counts and protected records.
- **NEX-005 [P1/S]** Add startup warning and privacy-mode disclosure. *Done when:* UI clearly distinguishes offline from API-enabled data transfer.
- **NEX-006 [P1/M]** Audit logging retention controls. *Done when:* user can clear history safely; audit retains only appropriate minimal metadata.

## Milestone M1 — projects, milestones and tasks

- **NEX-007 [P0/M]** Add `projects` table and project model. *Done when:* create/list/detail/archive through approval gates, project IDs stable.
- **NEX-008 [P0/M]** Link existing/new tasks to projects. *Done when:* old records stay unassigned but not lost, tasks filter by project.
- **NEX-009 [P1/M]** Add project milestones. *Done when:* milestones track date, owner, status; invalid dates rejected.
- **NEX-010 [P1/S]** Task detail and due date editing. *Done when:* updates are previewed and audited; invalid IDs cannot mutate records.
- **NEX-011 [P1/M]** Task dependencies/blockers. *Done when:* a blocked task points to a real prerequisite; circular dependencies rejected.
- **NEX-012 [P1/M]** Project overview UI. *Done when:* fictional event shows workstream status, owners and milestones without page reload bugs.
- **NEX-013 [P2/S]** Duplicate detection. *Done when:* duplicate event title/date flagged for user review, not automatically merged.

## Milestone M2 — meetings and decisions

- **NEX-014 [P0/M]** Meeting agenda data model. *Done when:* agenda items with owners and required decisions persist.
- **NEX-015 [P0/M]** Minutes and decision register. *Done when:* a decision has date, approval source/status and link to meeting.
- **NEX-016 [P0/M]** Proposed action extraction. *Done when:* user reviews each generated task with owner/date; no write without approve.
- **NEX-017 [P1/M]** Meeting templates. *Done when:* weekly OSIS, event planning, committee check-in templates render correctly.
- **NEX-018 [P1/S]** End-of-meeting summary export. *Done when:* summary contains agreed actions but no personal transcript by default.
- **NEX-019 [P1/M]** Draft templates. *Done when:* broadcast, proposal, MC script, speech, meeting invitation are editable and never auto-sent.

## Milestone M3 — conversation and voice

- **NEX-020 [P0/M]** Dedicated model provider interface. *Done when:* fake provider tests run offline; AI call errors degrade gracefully.
- **NEX-021 [P0/M]** Project-scoped context retrieval. *Done when:* prompt context limited to selected project and user-authorized data.
- **NEX-022 [P0/M]** Prompt-injection regression suite. *Done when:* malicious note text cannot cause forbidden tool calls or bypass approval.
- **NEX-023 [P1/S]** Voice transcript confirm/edit UX. *Done when:* speech transcript never submits automatically.
- **NEX-024 [P1/M]** Indonesian/English accuracy review. *Done when:* curated sample phrases have clear fallback and error handling.
- **NEX-025 [P2/M]** Evaluate local speech-to-text. *Done when:* document test results for privacy, latency and accuracy on Mac M2 before integration.

## Milestone M4 — chief-of-staff dashboard

- **NEX-026 [P0/M]** Verified briefing engine. *Done when:* overdue and upcoming items reproducibly match database at Asia/Jakarta timezone.
- **NEX-027 [P1/M]** Decision-needed and blocker panels. *Done when:* each item points to a real record; no fabricated state.
- **NEX-028 [P1/M]** Project risk register. *Done when:* risks show owner, likelihood, impact, mitigation and review date.
- **NEX-029 [P1/M]** Search and navigation. *Done when:* project/task/note searches return correct scoped results.
- **NEX-030 [P1/S]** Archive/handover export. *Done when:* user previews/redacts before local export.

## Milestone M5+ — connected services (permission gated)

- **NEX-031 [P0/L]** Authentication & workspace isolation design before external access.
- **NEX-032 [P0/L]** Read-only calendar integration with minimum OAuth scopes and revocation.
- **NEX-033 [P1/L]** Read-only Drive/document adapter with file-level consent.
- **NEX-034 [P0/L]** Outbound draft → preview → approve → provider result → audit pattern, with deduplication.
- **NEX-035 [P1/L]** Optional OpenClaw bridge: sender allowlist, sandboxing, read-only initial scope and separate audit.
- **NEX-036 [P0/L]** Workspace splitting for Personal and ATLAS: no shared secrets or cross-workspace context.

## Suggested first four development sprints

**Sprint 0 — Stabilize:** NEX-002, 003, 004, 005.  
**Sprint 1 — Plan an event:** NEX-007, 008, 009, 012.  
**Sprint 2 — Make meetings useful:** NEX-014, 015, 016, 017.  
**Sprint 3 — Make conversation reliable:** NEX-020, 021, 022, 023.

Work on one small issue at a time. The feature is **done** only when acceptance criteria pass locally, related automated tests exist, security/privacy review is complete, and CI passes.
