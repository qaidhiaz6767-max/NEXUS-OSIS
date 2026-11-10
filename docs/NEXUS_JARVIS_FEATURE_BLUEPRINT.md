# NEXUS — JARVIS Experience + Functional Capability Blueprint

> **Status:** product roadmap, not an implementation claim. **Date:** 2026-11-10.  
> **Baseline:** NEXUS integrated Cognitive Core + Executive Home merged to `main` through PR #7.  
> **Vision:** a minimal, premium, voice-first personal AI command center that actually helps with decisions, projects, learning, development, and planning.  
> **Rule:** visual spectacle is valuable only when it serves a truthful, accessible, permission-controlled function.

## Product direction

**NEXUS = Neural Executive Coordination & Unified System.** Its central intelligence operates a local-first, single-user workspace system, with optional AI assistance and explicit authorization for changes. The aspirational *JARVIS feeling* is an interface and orchestration experience, **not** a promise of fictional autonomy, unrestricted computer access, permanent listening, or any ability absent from the code.

**Final Home direction:** dark navy/black, central responsive liquid-glass orb, "NEXUS" name, quiet top bar, voice-first navigation; avoid Home chat box, calendar, markets, quick actions and unnecessary text. The merged Executive Home currently **still displays five workspace portal cards and supporting copy**. The orb-only design is a proposed refinement, not shipped. Workspaces retain full dedicated pages and may be opened by voice.

## The 20 JARVIS-style capabilities

Statuses refer to the current integrated codebase, **not** the completion of the full concept. Priority: P0 next foundational work, P1 subsequent, P2 later.

| # | Capability | JARVIS experience | Useful real-world behavior | Current status | Priority |
|---|---|---|---|---|---|
| 01 | **Living Liquid-Glass Orb** | The sphere breathes, glows and responds to listening/thinking/speaking/error | Honest state feedback and accessible fallback text; no fake "thinking" loops | **Basic built** (SVG/CSS, not volumetric 3D) | P0 polish |
| 02 | **Cinematic Startup Protocol** | Greeting → formation → real initialization → NEXUS IS READY | Check the Core before announcing ready; retry and reduced-motion support | **Built** | Maintain |
| 03 | **Voice Workspace Navigation** | "NEXUS, open ATLAS" changes the interface | Map approved English/Indonesian phrases to available workspace IDs without an AI call | **Built**, limited command grammar | P0 improve |
| 04 | **Natural Two-Way Voice** | Talk to NEXUS instead of using menus | Browser speech recognition → Core command/AI → spoken reply, with transcript and error feedback | **Partial** (browser dependent) | P0 |
| 05 | **Consent-Based Wake Phrase** | "Hey NEXUS" during an active session | Activate responses only after microphone opt-in; visible listening indicator and stop control | **Partial**, not always-on | P1 |
| 06 | **Barge-In / Voice Interruption** | Interrupt a long reply to change the task | Stop speech, cancel stale output, distinguish interruption from approval or execution | **Planned** | P0 |
| 07 | **Executive Voice Persona** | Calm, concise, sophisticated, bilingual speech | Choose installed voice, language, speed and concise/expanded reply mode | **Partial** (browser voice controls exist) | P1 |
| 08 | **Adaptive Holographic Panels** | A relevant information panel appears when requested | Show actual task, meeting, source, note or project data rather than decorative fake panels | **Planned** | P1 |
| 09 | **Mission Control Mode** | "Initiate mission control" opens a command workspace | Show goals, blockers, owners, approvals, deadlines and workstreams from stored records | **Planned** as integrated mode; underlying records built | P0 |
| 10 | **One-Command Executive Briefing** | "NEXUS, brief me" | Summarize deadlines, current tasks, meetings and decision backlog with record references and truthful freshness | **Basic built** | P0 deepen |
| 11 | **Evidence-Linked Memory Timeline** | "Recall our decision about ATLAS" with a source trail | Retrieve approved memory, timestamps, provenance and conflicts without fabricating previous decisions | **Partial** (memory framework built) | P0 |
| 12 | **Universal Intelligence Search** | Search NEXUS as if consulting one brain | Search approved documents, tasks, projects and decisions within each authorized workspace | **Partial**, scoped search exists | P1 |
| 13 | **Multi-Step Plan Composer** | NEXUS shows a proposed mission before acting | Generate bounded task/project/milestone plans, display exact proposed changes, approve and verify | **Built** for bounded local operations | Maintain |
| 14 | **Specialist Agent Squadron** | Delegate subproblems to Research, Coding, Strategy and Operations agents | Bounded, inspectable research/planning outputs; no silent background actions or permissions | **Planned** | P2 |
| 15 | **Screen Co-Pilot** | "NEXUS, look at this" on an explicitly shared view | Analyze a screenshot or selected window after active user consent; never covert screen capture | **Planned** | P2 |
| 16 | **Document Intelligence Room** | Open a floating dossier view and ask questions | Import user-approved documents, summarize, compare revisions and cite exact passages | **Planned**; current notes are basic text | P1 |
| 17 | **System Health & Diagnostics** | "Run NEXUS diagnostics" | Check local Core connectivity, schema/integrity, API availability, backups and test status based on observed results | **Partial** capability/status reporting | P0 |
| 18 | **Global Intelligence Globe** | Expand a stylized globe and world-data views | Show city clocks and source-labeled public reference feeds on demand, including stale/unavailable states | **Basic built in Legacy HUD** | P2 |
| 19 | **Strategy Simulation Lab** | Interactive "what if?" panels for ATLAS and Finance | Test synthetic renewable-energy scenarios and educational paper portfolios, with clear assumptions | **Planned** | P2 |
| 20 | **Permissioned Computer Operator** | "Prepare my environment" shows a precise execution preview | Eventually operate allowlisted app/file/workflow actions with per-action review, verification and rollback; no arbitrary shell via AI | **Planned**, requires substantial security work | P2 |

### Boundaries for the 20 features

- "Built" means a specific current implementation exists, not that it is flawless or feature-complete. "Partial" means some supporting capability exists. "Planned" means this document **does not add implementation**.
- The orb must reflect observed app state; never invent successful connectivity, diagnostics, financial results, approvals or task completion.
- Voice and screen features must be actively opted in, visibly indicated and immediately stoppable. No background microphone recording or covert screenshot capture.
- External writes, messages, account access, computer control, permission changes, and financial actions are disabled until separately authorized, designed and tested; NEXUS must not autonomously spend or trade real money.
- Keep live student or third-party personal records out of prototype demos and external AI contexts unless proper authorization and safeguards are established.
- No misleading "always on" claims when the Mac is shut, sleeping, or the browser is closed. Scheduled activity requires a separately installed and authorized runner.

## Existing functional foundation (retained alongside JARVIS features)

| Domain | Current functional capability | Status or limitation |
|---|---|---|
| **Cognitive Core** | Local command parsing, optional model reasoning, bounded tool proposals and verified outcomes | Built foundation; AI requires user-configured provider |
| **Memory** | SQLite-backed approved facts, provenance, source/reference handling and workspace isolation | Built foundation; semantic intelligence incomplete |
| **Task & Project Management** | Tasks, assignments, dates, status, projects, milestones, dependencies | Built local planning records; no automatic real-world delegation |
| **Meetings** | Draft agendas/minutes, decisions, action items, separate confirmation/approval | Built structured local workflows, no automatic attendee recording |
| **Documents** | Text notes with search and reading | Basic; full document ingestion/editing planned |
| **Events** | Local event records, .ics export | Built; external calendar synchronization not built |
| **Approvals & Audit** | Human-reviewed mutation proposals, audit trail, one-time approval | Built |
| **Data Recovery** | Manual encrypted snapshot backup/restore CLI with validation | Built but must be assessed on the target Mac; live DB plaintext |
| **Executive UI** | Responsive dark glass layout, stateful orb, startup and workspace pages | Built baseline; orb-only final Home still pending |
| **Voice** | Browser push-to-talk, browser speech output, active-session voice loop, local workspace commands | Partial; varies by browser/device |
| **Market References** | Limited public reference data and world clocks on demand | Partial; no brokerage or live execution |
| **Finance** | Manual browser-only ledger and educational research areas | Partial; ledger not in Core backup |
| **GitHub** | Saved repo references in Development | Direct remote GitHub control inside NEXUS not built |
| **Specialist Agents/Automation** | Roadmap and limited Core plans | No autonomous agent workforce or always-on scheduler |
| **Safety** | Localhost, scoped capabilities, proposal/approve/verify flow and HTTP restrictions | Prototype; no production-grade authentication or encrypted live DB |

### Workspace functionality matrix

The shipped Executive interface has **five primary portals**; the underlying Core also supports secondary Personal and Research workspaces.

| Primary workspace | Six dedicated areas |
|---|---|
| **OSIS** | Programs · Tasks · Meetings · Documents · Team · Budget |
| **Academics** | Subjects · Assignments · Study Planner · Notes & Materials · Academic Progress · Goals & Milestones |
| **Development** | Projects · GitHub Repositories · Coding Assistant · Agent Tasks · Testing & Diagnostics · Development Roadmap |
| **ATLAS** | ATLAS Master List · Corporate Strategy · Energy Projects · ATLAS Intelligence · Research & Advanced Systems · Investments & Finance |
| **Finance** | Financial Overview · Savings & Goals · Budget & Expenses · Market Watchlist · Paper Portfolio · Financial Research |

A section's presence in the UI is **not** evidence of a complete specialized backend. Some areas reuse general project, task, note, fact or browser-ledger storage, and some display honest not-yet-connected states.

## Phased execution order

**P0 — Build the dependable JARVIS core first.** Make voice sessions interruption-safe (06), reduce command/navigation friction (03–04), deepen sourced briefings and memory (10–11), build a real Mission Control mode (09), and improve observable diagnostics (17). Keep core records and approvals authoritative.

**P1 — Make the experience polished and useful.** Finish orb-first Home with accessible keyboard fallback (01), voice persona (07), contextual panels (08), universal scoped search (12), and document intelligence on user-selected files (16).

**P2 — Carefully expand capabilities.** Introduce consent-bound active-session wake phrase refinement (05), a specialist-agent system (14), user-shared screen analysis (15), on-demand global views (18), educational simulations (19), and allowlisted computer-operator capabilities (20). All require separate design, tests, privacy review and approval models.

**Maintenance:** preserve the verified startup protocol (02) and plan/approve/verify system (13) throughout every phase.

## Acceptance gates before calling any feature 'done'

1. A clear user-visible scenario and truthful response when offline or unsupported.
2. State is loaded from the right workspace, with stale data identified.
3. No hidden external side effects; risk-appropriate review for changes.
4. Unit/regression tests including error paths; browser tests for voice/UI controls; Mac Safari checks when relevant.
5. Accessible keyboard controls, screen reader labels, reduced motion and usable small-screen layouts.
6. No secret keys, private school records, transcripts or user data in GitHub; documentation updated to distinguish shipped from planned.
7. No fictional capabilities or success claims without evidence from actual Core/tool results.

**Product principle:** Simple on the outside. Intelligent on the inside. Dependable in everything it does.
