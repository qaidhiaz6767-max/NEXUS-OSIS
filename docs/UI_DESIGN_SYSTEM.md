# NEXUS Command Center — interface system

Mission 002 / v0.4 development. The interface stays on the existing Python server
and uses native browser ES modules, HTML, CSS and lightweight local SVG icons.
No framework, build step, runtime dependency, external font or CDN was added.

## Design direction

A quiet dark shell, restrained cyan controls, a recognizable ring-based Core, and
consistent navigation across operational pages. The Core is static at idle;
processing, listening and speaking treatments correspond to actual request or
browser speech events. It is not a permanently spinning loader or a simulated AI.

| Token | Value | Purpose |
|---|---|---|
| `--page` | `#080B12` | Main background |
| `--surface` | `#101722` | Panels and sidebar controls |
| `--elevated` | `#151E2B` | Elevated controls and surfaces |
| `--text` | `#F2F5FA` | Primary text |
| `--secondary` | `#A0ADBE` | Supporting text |
| `--muted` | `#8C9DB3` | Accessible metadata; raised from the proposed starting value |
| `--accent` | `#48B9F2` | Primary controls and selected context |
| `--accent-hover` | `#78D2FF` | Interactive feedback |
| `--border` | `#283445` | Structure without heavy shadows |
| `--success` | `#37C892` | Confirmed positive status |
| `--warning` | `#F3B85F` | Review/expiry notices |
| `--danger` | `#EF7373` | Error state |

Spacing tokens are 4, 8, 12, 16, 24, 32 and 48px, with a 4px-based layout rhythm.
System typography avoids network/font loading. Page titles are 28–30px, section
headings 18–23px, primary conversation/body text 14px, supporting text generally
12–13px, and compact navigation/metadata labels smaller where necessary.
Counts and dates use tabular numerals. Active states use borders, labels and
icons alongside color. Core palette text/control contrast is checked in tests;
this does not certify every interface state as WCAG conformant.

## Shell and navigation

- A 240px desktop sidebar (212px at smaller laptop widths), workspace selector,
  primary navigation, approvals, Activity and Settings.
- Main content has a shared heading/toolbar system and real loading/error states.
- The Assistant has a contextual panel on wider screens; it collapses when width
  is better used for the conversation.
- At 760px and below the sidebar becomes an inert-when-closed drawer with a
  keyboard focus loop, Escape dismissal and focus restoration.
- Task tables become labeled cards at constrained widths. Other grids reduce to
  one column as needed. Automated reflow checks cover 320px and 390px screens.

The workspace is explicit in every API request. Switching reloads the page with
that workspace and the selected view, clearing drafts and context. It never
merely hides another workspace's data in CSS. All separation and grants remain
server-enforced.

## Components and state

| Browser module | Responsibility |
|---|---|
| `state.js` | Session state, loaded/stale flags and view names |
| `api.js` | Scoped local requests, timeout and readable errors; no automatic write retry |
| `domain.js` | Date formatting, deterministic ordering, task filtering and expiry |
| `ui.js` | Safe DOM primitives, SVGs, badges, notifications and structured message text |
| `views.js` | Rendered operational pages and details, using stored records |
| `forms.js` | Typed, bounded proposal forms with workspace snapshots |
| `voice.js` | Consent, speech event state, transcript review and optional playback |
| `app.js` | Navigation, interaction orchestration, status and lifecycle |

`web/package.json` declares the existing browser JavaScript as ES modules for
Node checks. It adds no packages or build pipeline.

Conversation messages reuse existing DOM nodes; unchanged history is not rebuilt
for each busy state. Project/event/task details are created only when opened.
Filters run locally on the loaded bounded records. There is no routine polling;
known approval expiry can trigger a local refresh. No ambient idle animation runs.

## Honest status and approvals

`GET /api/state` adds timezone, demo mode, capabilities, aggregate counts and
non-secret system metadata. Counts use the full workspace tables rather than
just visible list lengths, and records/counts share one read transaction.

AI status is disabled, configured/unverified, last response verified, or last
request failed. Key presence is not a verified connection. Last-request observations
are scoped to a workspace and live in server memory; restart resets them. UI
request state reports Ready, Processing, Awaiting approval, actual outcome or Error.
Speech state changes only from real speech lifecycle events, not from decorative
animation or the initial microphone click.

Forms call additive `POST /api/propose` with typed name/arguments. It uses the same
Store allowlist, validation, permissions and proposal engine as commands, preserving
literal pipes and markup-like text without slash-command parsing. It does not
execute records. Existing chat/decision routes and command syntax remain available.
`POST /api/decide` adds the actual persisted outcome and workspace to its response.

Approval cards appear in the inbox and conversation. They show workspace, expiry,
description, exact values/plan steps, and distinct approve/reject controls. Expired
cards offer dismissal only. An approval always carries its original workspace and
ID; the backend independently checks expiry, grants and replay. Read-only controls
are disabled, including empty-state creation actions. Failed state refreshes show
last-loaded data as stale and disable writes until recovery.

## Supported page scope

- Command Center: greeting/local date, actual system indicators, functional command
  composer/shortcuts, aggregate metrics, deterministic priorities and agenda.
- Assistant: persisted workspace chat, safe paragraphs/lists/tables/code blocks,
  copy, action cards and real outcomes. Raw HTML is never interpreted.
- Projects: create, search, filter, sort and goal/status details. No invented owners,
  milestones, deadlines or task links; absent backend features are explained.
- Tasks: title, owner, status/priority filters, deadline/priority/newest sorting,
  detail view, creation, delegation and status proposals. No notification/sending
  or acknowledgment is implied.
- Calendar: local-time agenda, upcoming/past grouping, missing-time labels,
  creation, details and existing calendar export. No unsupported edit/sync control.
- Meetings: draft notes → review proposal → approved-to-save notes. Notes are not
  labeled independently verified decisions or complete meeting records.
- Memory: source labels, provenance details, typed create/update/delete and grouped
  workspace-only search across facts, project context, notes and conversation.
- Activity: real recent audit entries. Settings: runtime facts, voice language,
  stop playback and permitted exports; no credentials or secret-editing UI.

## Accessibility and motion

Native semantic controls, associated labels, visible focus rings, skip link,
logical headings, modal focus loops/restoration, drawer keyboard handling and
screen-reader statuses are implemented. Enter sends, Shift+Enter inserts a line;
Ctrl/Command+K opens Assistant only when not editing another field or in a dialog.
Reduced-motion preferences disable decorative/processing movement. Errors are
readable and never replaced by a fabricated success notification.

Automated keyboard/reflow/contrast checks are evidence of selected behavior, not
a complete WCAG 2.2 AA audit. Screen readers, Safari and the owner's Mac still need
manual verification. Real microphones, speakers and paid model calls were not used.
