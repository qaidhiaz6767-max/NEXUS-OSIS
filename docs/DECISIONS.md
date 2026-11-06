# Architecture decision record (ADR)

## ADR-001 — Python is the core, OpenClaw is optional
**Decision:** Local Python application is the source of truth; no required OpenClaw dependency. **Rationale:** independent database, testable permissions, lower initial operational complexity. **Revisit:** only after v0.4 safety tests.

## ADR-002 — SQLite before remote/cloud database
**Decision:** SQLite for a single local operator. **Rationale:** simple, offline, easy to back up. **Limitation:** not a multi-user, distributed, encrypted data store. **Revisit:** only if multiple trusted accounts are actually needed.

## ADR-003 — Approval boundary belongs in application code
**Decision:** Models can propose allowlisted changes; only the Python policy layer can execute them after approval. **Rationale:** prompt instructions alone do not guarantee safety. **Revisit:** never weaken silently.

## ADR-004 — School data and future business data remain separate
**Decision:** isolated workspaces/data stores and access controls. **Rationale:** privacy, duties, consent, future organizational boundaries.

## ADR-005 — Voice is push-to-talk, not always-listening
**Decision:** explicit user gesture; transcript displayed before sending. **Rationale:** less background collection and simpler privacy model.

## ADR-006 — No automatic outbound messaging initially
**Decision:** draft messages locally; no send capability until a vetted integration with approval, recipient preview and verified delivery outcomes exists.

## ADR-007 — Use a private GitHub repository first
**Decision:** publish code privately, keep all records local. **Rationale:** code review/workflow while minimizing exposure. Private code isn't an excuse to commit secrets.

## ADR-008 — Deploy only to localhost in the current phase
**Decision:** do not expose the HTTP server on LAN/WAN, tunnel publicly or use it as a multi-user school server. **Revisit:** with authentication, security review and hosting design.
