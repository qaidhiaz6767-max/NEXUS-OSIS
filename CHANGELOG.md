# Changelog

## v0.3 — Universal NEXUS Core (Mission 001)

- Extracted reusable Core modules and kept the OSIS import/schema compatibility facade.
- Added independent workspace databases, capability checks and identity/version guards.
- Added basic projects, memory provenance/search and approved fact update/deletion.
- Added bounded atomic multistep plans with replay protection and rollback.
- Made cloud AI explicitly opt-in and scoped context to the selected workspace.
- Added the navy workspace dashboard, project panel, memory tools and complete approval previews.
- Added temporary offline demo mode, sanitized errors, private-data exclusions and actual CI configuration.
- Fixed JSON record export truncation caused by dashboard pagination limits.
- Added migration, isolation, permission, provider-fake and browser checks; see the Mission 001 report.

## v0.2 — Executive Workspace UI

- Replaced the chat-centric interface with a polished, responsive OSIS leadership dashboard.
- Added dedicated views for overview, assignments, events, notes, memory, approvals and Chief of Staff chat.
- Added safe quick-create forms, task search/status filters, approval controls, task completion and reassignment proposals.
- Retained backward-compatible database schema and existing Python backend commands.
- Added smoke tests for shipped static dashboard assets.
- Added non-destructive UI upgrade instructions for existing installations.


## 0.1.1 — GitHub starter pack (2026-11-06)

- Repackaged existing OSIS v0.1 prototype without real-user data.
- Added private-repo setup instructions, master roadmap, data/security policy and GitHub CI.
- Added an initial reproducible issue backlog and contributor guidelines.
- Added HTTP Host checking, timezone-aware OSIS briefings and HTTP regression tests.
- Clarified that OpenClaw, messaging, Google services and multi-agent execution are future work.

## 0.1.0 — Local OSIS prototype

- Local browser command center + terminal CLI.
- SQLite tasks, events, notes, memories and audit log.
- Explicit approvals for local mutations; basic briefing and exports.
- Optional OpenAI model-powered conversation; browser-dependent speech input/output.
