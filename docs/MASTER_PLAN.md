# NEXUS MASTER PLAN — OSIS Chief of Staff to Executive AI Platform

> Historical design/roadmap. The implemented v0.3 baseline and current limits are documented in [NEXUS Core architecture](NEXUS_CORE_ARCHITECTURE.md) and [Mission 001 plan](IMPLEMENTATION_PLAN.md).

**Planning baseline:** 2026-11-06  
**Project:** NEXUS — Neural Executive Coordination & Unified System  
**Audience:** solo student developer, potential future contributors and reviewers  
**Status:** architecture and roadmap; only features labeled SHIPPED are implemented.  
**Primary deployment:** one operator's MacBook Air M2, localhost, Python 3.10+  
**Operating principle:** reliable coordination, verified memory, clear approval, data minimization, and simple ownership.

## 0. Executive direction

NEXUS is a **personal command-and-coordination brain**, not a general-purpose autonomous computer controller. It helps the student council president understand obligations, plan programs, delegate tasks, prepare documents, and learn from prior decisions. Future versions may serve personal and ATLAS workspaces, but each workspace has distinct data, authorization, and retention rules. The user's command is a request for assistance, **not** permission for every conceivable action: permissions still matter, especially when school information or other people's communications are involved.

**North star:** On opening NEXUS before a school leadership meeting, the user can request a truthful status report, identify blocked work, propose a meeting agenda, draft announcements, and queue next actions for explicit confirmation. The system must distinguish **drafted**, **proposed**, **approved**, **executed**, **delivered**, and **acknowledged**.

**First practical win:** reliably track the next OSIS event across tasks, owners, deadlines, decisions, and follow-ups. Don't start by adding dozens of agents or browser-automation powers.

### Success measures (not promises)

- Zero unauthorized data mutations in the automated test suite.
- Zero automatic outbound messages or third-party writes in v0.1–v0.3.
- Every local write shows a reviewable proposal and audit event.
- 100% of demo tasks retain their content after stop/restart.
- All dated tasks use consistent local Asia/Jakarta interpretation; timezone documented.
- Each event has a status, owner, milestone, risk and review meeting by v0.4.
- Two-minute morning briefing possible without manual reading of every note by v0.5.
- No names, private contact details, transcripts, credentials, or backup files in Git.
- An upgrade can run with the previous database after tested migrations and backup.
- Production-level claims require security and usability testing on an actual Mac, not only unit tests.

## 1. User and operating model

**Initial user:** one student council president (Ketua OSIS); other pengurus are task owners in a coordination database, **not automatically users of NEXUS**. A name/role in a task doesn't imply that person consented to system access or received a notification.

**Audience served:** school leadership, OSIS executive team, committees, and the student body as a whole. NEXUS drafts for these audiences; it is not authorized to impersonate the school, teachers, or student council.

**Roles for future multi-user mode:**

| Role | Allowed purpose | Not automatically allowed |
|---|---|---|
| Owner / president | Manage own private OSIS workspace, approve edits | Access someone else's private accounts |
| Deputy | View shared project state if invited, suggest updates | Override owner or school policy |
| Secretary | Maintain approved minutes and proposal drafts | Export student records to outside services |
| Treasurer | Track approved budget estimates | Perform money transfers or access bank accounts |
| Committee lead | Update assigned project tasks | View unrelated confidential planning |
| Teacher adviser | Review materials if school explicitly authorizes | Blanket access to personal NEXUS history |

V0.1 is single-user, so **none** of these future roles are implemented as login accounts.

## 2. Product pillars

### Pillar A — Conversational command center

- Text first: instruct, search, ask for briefings, and review proposed changes.
- Push-to-talk voice: transcribe into editable input and read replies aloud.
- User-selectable Indonesian/English tone, with separate formal-broadcast style.
- Understand references to current projects only when the data supports them; ask about missing owners/dates.
- Show source records for status reports where practical, rather than pretending the AI remembered everything.
- Never claim an API call, action, or message succeeded without confirmation from the underlying tool.

### Pillar B — Executive coordination

- Projects: event/program records, milestones, owner, priority, state, committee.
- Tasks: actionable verbs, one accountable owner, optional collaborators, due date and status.
- Dependencies and blockers: why an item cannot move, who can unblock it.
- Meeting system: agenda, attendees by role, minutes, decisions, action items and follow-up dates.
- Communications: draft broadcasts, speeches, event briefs, permission requests and proposals.
- Reviews: daily briefing, weekly check-in, upcoming deadline watch and handover summary.

### Pillar C — Institutional memory

Store approved and relevant information only:

1. Explicit decisions: what was decided, when, where it was approved, and whether superseded.
2. Projects: scope, constraints, dates, stakeholders by role, decisions and progress.
3. Tasks: accountable owner, status transitions and result.
4. Preferences: language/tone and preferred working style.
5. Source references: links or local approved document identifiers; never scrape files indiscriminately.

**Not memory:** private details on classmates, grades, disciplinary situations, addresses, raw private chats, medical information, passwords or payment credentials. Do not infer other people's personal attributes.

### Pillar D — Trust and governance

Every action gets a risk classification:

- **R0 read only:** list local tasks; prepare summaries; no approval required.
- **R1 local reversible:** create/update tasks, notes, calendar drafts; approval required in early versions.
- **R2 external draft:** prepare a message for an identified audience, but don't send it; preview required.
- **R3 external effect:** send an email, edit a shared document, add calendar invite; separate explicit confirmation after showing recipients/content/changes.
- **R4 high impact:** delete bulk records, publish publicly, spend money, change permissions; disabled until stronger authentication, rollback and manual review.

**Autonomy means planning and proposing, not invisible control.** The system should be predictable even when model output is wrong.

## 3. Typical OSIS workflows

### Workflow 1 — Event preparation (EPHORIA / Teachers' Day / future programs)

1. User: "Open a project for our upcoming event, target date X."
2. NEXUS reads existing projects and flags potential duplicates.
3. NEXUS produces a draft project charter: objective, scope, target audience, adviser approval assumptions, budget placeholder, dependencies and risks.
4. User reviews the charter and approves storage.
5. NEXUS proposes task breakdown: concept, permits, sponsorship, stage/venue, equipment, publicity, rehearsal, run-of-show, documentation, debrief.
6. User accepts, revises or rejects **each batch** before records are saved.
7. Dashboard shows owner, target date, status, dependency, and risk for each task.
8. Upcoming events/meetings drive a non-invasive briefing (no unsanctioned reminders to classmates).
9. After completion, NEXUS assists in a post-event debrief and keeps an approved handover packet.

**Definition of success:** no task silently assigned to another person in real life; no school-wide broadcast without separate permission.

### Workflow 2 — OSIS weekly meeting

**Before:** read active projects, identify overdue items, draft agenda ordered by decision needed, prepare three questions for committee leads.  
**During:** accept typed notes entered by the user; optional voice capture only with participants' consent and school approval.  
**After:** show a proposed decision log and list of tasks with explicit owners and due dates.  
**Follow-through:** each proposed action is reviewed, saved and tracked; if an owner hasn't acknowledged, NEXUS labels the communication state `not confirmed`.

**Output:** Agenda, concise minutes, decision register, assignment list, next checkpoint.

### Workflow 3 — Broadcast drafting

User: "Draft a 70% Indonesian / 30% English reminder about our upcoming volunteer briefing; warm, energetic and professional."  
NEXUS asks for missing verified details or uses authorized event records, drafts a text for review, and does **not** send it. The user edits as needed. Future integrations can require explicit audience, exact recipient list, final preview and approval before sending.

### Workflow 4 — Morning chief-of-staff briefing

The brief should show: today's date and timezone, top three priorities, overdue tasks, items due within seven days, events in the next 14 days, unresolved decisions, unacknowledged delegations (future), and suggestions for the next best action. Each recommendation is distinguishable from a recorded fact.

### Workflow 5 — School leadership handover

When the term ends, create a **school-approved** handover package with program structure, outcomes, generic timelines, lessons learned and public reference documents. Omit personal chat history, private notes, data with no permission to disclose and API credentials. Export is deliberate and auditable.

## 4. What the current prototype actually ships

**SHIPPED (v0.1):** localhost dashboard; optional terminal CLI; SQLite for tasks/events/notes/remembered key-values/messages/audit; explicit allowlisted approval proposals and one-time decisions; list/brief/commands; calendar (.ics) and JSON export; optional model reasoning; browser speech capture/output when available; unit tests.

**NOT SHIPPED:** project table; dependencies; role login; real meetings workflow; document integrations; Telegram/WhatsApp/Google sending; full-text search; cross-platform sync; encrypted database; app installer; OpenClaw adapter; automated multi-agent delegation; voice wake word; production-grade security.

## 5. Architecture principles

1. **Modular monolith first**: separate responsibilities without microservices.
2. **Local-first**: data on the user's Mac; optional AI model/API is an explicit opt-in.
3. **Provider-agnostic boundary**: model client behind an interface; prompts may change, not records.
4. **Structured tools**: strongly typed operations; no arbitrary commands or filesystem paths from a model.
5. **A transaction-based approval boundary**: propose → user review → authorize → execute → verify → audit.
6. **Single source of truth**: SQLite is authoritative for internal records, not model chat history.
7. **Evidence-aware state**: a user's command does not certify delivery/completion by others.
8. **Small, tested releases**: no new integration without failure tests, data migration/backup and rollback.
9. **Privacy by design**: minimum context, selective retention, explicit external data transfers.
10. **Portable workspaces**: OSIS and ATLAS data stay logically and physically separate.

## 6. Engineering workstreams

### A. Data and migrations

- Add `schema_version` and numbered migration scripts before changing tables.
- Add projects, milestones, project_tasks, meetings, decisions and communication drafts.
- Use stable UUID identifiers for future distributed sync; preserve old integer IDs while migrating.
- Define soft delete and restore for ordinary records; audit deletions without storing private data indefinitely.
- Backup before migrations; test restore; record local timezone and UTC timestamps.
- Optional future encryption at rest for personal archives; use platform key storage rather than hard-coded keys.

### B. AI orchestration

- V0.1: direct command parse or one function-call proposal, never execute without approval.
- V0.3: intent classify, retrieve scoped project context, prepare a plan, queue multiple proposed steps, execute after approval, verify each result.
- V0.5: specialized `briefing`, `meeting`, `projects`, `writing`, `research` modules; **not** free-ranging agent autonomy.
- V1+: optional specialist services with budgets, timeouts, audit IDs, explicit tool manifests and per-workspace permissions.
- Add anti-hallucination checks: truthful dates, unknown facts left as unknown, confidence/uncertainty visible.

### C. Voice and UX

- Browser speech is optional, push-to-talk; show transcript before submitting.
- Maintain keyboard support, accessible contrast, focus indicators and screen-reader labels.
- Distinct sections: **Inbox**, **Today**, **Projects**, **Tasks**, **Meetings**, **Drafts**, **Memory**, **Settings**.
- Provide a first-run tutorial and a safe Demo Mode with fictional data.
- Do not record raw audio by default; explain any cloud transcription service.
- Later: compare local speech engines for Mac M2; measure privacy, latency, resource usage, accuracy for Bahasa Indonesia and English.

### D. External connectors

- No connectors in early prototype.
- Phase 1 connector: read-only Google Calendar or manually imported `.ics` from authorized account.
- Phase 2 connector: read-only Drive file summaries with explicit file scopes and school permission.
- Phase 3 connector: drafts in selected app; write/send only with final human confirmation.
- OpenClaw bridge: a separately sandboxed, authenticated ingress translator, never an unrestricted executor.

### E. Quality

- Automated unit + HTTP tests on every pull request.
- Document threat model, retention, backup and incident response.
- Smoke-test browser and speech on actual Mac before marking those as verified.
- Track defects by severity, block releases for safety/permission bypass issues.
- Use test fixtures with fictitious names, dates and event titles only.

## 7. Version roadmap, gates and exit criteria

### M0 — Source control and baseline (CURRENT)

**Scope:** private repo, README, `.gitignore`, CI, tests, issue backlog, security rules.  
**Exit:** clone or unzip → run offline locally → tests green; Git tracks no personal data.  
**Major risk:** committing private OSIS records; review staged files carefully.

### M1 — v0.2: Projects and task improvements

- Project create/list/update/archive, project-specific tasks, owner/priority/due date, project dashboard.
- Milestones, task descriptions, due date filters, searchable notes and tags.
- Safe schema migration and backup/restore drill.
- Add test cases for missing projects, empty fields, invalid status transitions and concurrent approvals.

**Exit:** plan a fictional event with at least 12 tasks, four milestones and a stable dashboard; all changes have auditable approval.

### M2 — v0.3: Meetings, decisions, handover

- Meeting agenda generator, minutes workflow, explicit decision register, action-item extraction **as proposed edits**.
- Draft library: broadcast, invitation, MC script, speech, proposal, report template.
- Structured handover export with field-level privacy filtering.
- User-configurable tone and language settings (Indonesian/English).

**Exit:** complete a fictional meeting lifecycle end-to-end without falsely claiming anybody was notified.

### M3 — v0.4: Voice and reliable context

- Evaluate supported browser and local ASR options; add manual microphone quality check.
- Editable transcript, optional TTS, voice privacy settings.
- Project-aware retrieval and citations to stored records; context budget guardrails.
- Offline help/intents improvement; hallucination and injection red-team tests.

**Exit:** 20 predetermined commands recognized or gracefully clarified; no voice command bypasses approval.

### M4 — v0.5: Executive dashboard

- Today view, weekly brief, risk register, overdue and dependency dashboard.
- Project health score based only on transparent deterministic factors (not opaque grades of people).
- Draft recommendations with source links and explicit uncertainty.
- Local search and history browser with retention controls.

**Exit:** user can answer "What needs my decision?" and "What is blocked?" from verifiable stored records.

### M5 — v0.6: Safe integrations

- Least-privilege read-only connectors for a selected personal account (school accounts only with permission).
- Token/key storage outside repo; credential revocation path and access tests.
- No contact with students/teachers; no messaging in this milestone.

**Exit:** permissions and data sent to provider shown clearly; disconnect restores offline-only operation.

### M6 — v0.7: Approved outbound workflows

- Draft → exact recipient preview → explicit approval → send → provider delivery result.
- Retries with idempotency keys; no duplicate sends; failure and partial success states.
- Communication audit with redacted metadata, not full private messages.

**Exit:** integration test suite proves rejected proposals never send; duplicate retries never double-send.

### M7 — v0.8–0.9: Reliability and handover

- Data migrations, backup/restore, OSIS end-of-term summary generator.
- Workspace isolation, permission tests, possibly local multi-user identity if actually needed.
- An optional tray launcher; signed distribution only after platform testing.

**Exit:** backup can be restored on a clean test device, and data from one workspace never appears in another.

### M8 — v1.0: Dependable personal command center

- End-to-end tested event management; useful briefings; documented privacy and approval system.
- Sufficient accessibility, recovery paths, error reporting and stable basic workflows.
- At least one meaningful real OSIS use case performed with privacy-safe data and user consent.

**Exit:** not "AI is perfect"; rather, the supported features are tested, repeatable and trustworthy.

### M9 — v1.x: Personal workspaces

- Separate school/personal workspaces with separate stores, credentials and permissions.
- Add study/task planning only where appropriate; no invasive monitoring.
- Preserve portability and export/import for user-owned data.

### M10 — Later: ATLAS executive workspace

- Separate business data/identity/approval controls; industry compliance and security reviewed then.
- Future research agents, operational analytics and financial planning modules remain human-governed.
- A corporate platform would require a much more rigorous security architecture, contracts, access model, threat assessment and professional review.

## 8. Prioritization method

Score backlog items across: user impact (1–5), reliability/safety importance (1–5), implementation cost (1–5) and dependency readiness (0 or 1). Prioritize high-value, low-risk, ready items. Never prioritize a flashy integration ahead of backup/restore, approvals or data security.

**First four issues:** add project data model; migration framework; security/HTTP integration tests; meeting agenda generator.

## 9. Explicit non-goals, until safe to revisit

- Secret access to other people's accounts, bypassing school permissions, or impersonating school officials.
- Scraping student contact lists or exporting classmates' personal information to AI services.
- Recording meetings or listening continuously without informed consent.
- Autonomous spending, payments, mass messaging or public posting.
- Arbitrary shell execution, unrestricted browser control, password extraction.
- Automatically modifying records merely because the AI said they changed.
- Treating the model's generated answer as a reliable fact without verifying the source.

## 10. Future release scorecard

Every release must answer:

1. What exact problems does it solve that v0.1 didn't?
2. What can a model read, propose, write or send?
3. How does the owner understand and reverse mistakes?
4. Which tests validate that approval boundaries cannot be bypassed?
5. What user/private data leaves the Mac, and why?
6. Are real student/school records absent from source, examples and CI logs?
7. Can the previous database be backed up and upgraded safely?
8. Are connected accounts scoped, revocable and authorized by their owners?
9. What behavior is still unsupported?
10. Does a 15-minute real OSIS task feel simpler with NEXUS than without it?

## 11. Your practical development rhythm

Use short, verifiable sessions rather than trying to build everything at once. For a typical session: (1) choose one GitHub issue, (2) define acceptance criteria, (3) write/modify a test, (4) implement the smallest working change, (5) run tests, (6) review `git diff`, (7) commit in a feature branch, (8) merge after checks, (9) note the new behavior in CHANGELOG. Don't store school secrets in issues or screenshots.

**First actual OSIS pilot:** choose one non-sensitive, school-approved event; add a few real project tasks through the local app; use the daily brief and note which steps feel awkward; then build the specific missing feature. No invented deadlines or made-up approval outcomes.

## 12. Resources and current reference documentation

- GitHub Desktop: https://docs.github.com/en/desktop/overview/creating-your-first-repository-using-github-desktop
- GitHub Python CI: https://docs.github.com/en/actions/tutorials/build-and-test-code/python
- GitHub secret protection: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- OpenClaw security: https://docs.openclaw.ai/gateway/security
- OpenClaw permissions: https://docs.openclaw.ai/gateway/security/tool-permissions

Always re-check external tooling versions and policies before installing or integrating.
