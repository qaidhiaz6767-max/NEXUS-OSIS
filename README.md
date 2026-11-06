# NEXUS — Universal Personal AI Core

NEXUS is a local-first personal AI operating system and executive assistant.
OSIS is the first operational workspace; the same Core also provides independent
containers for Personal, Academic, Research, Development, Finance and ATLAS.

**v0.3 prototype:** Python-first, one trusted local operator, no required cloud
service. OpenClaw, external integrations and autonomous specialist agents are
future extensions.

## See the dashboard safely

With Python 3.11+ installed, open a terminal in this repository and run:

```bash
python3 app.py --demo
```

Open **http://127.0.0.1:8765**. Demo mode uses invented records in a temporary
directory, disables cloud AI, and discards changes when the app stops. It never
opens your normal OSIS database. Use the workspace selector, Projects, Memory,
Chief of Staff and Approval inbox to inspect the new workflows.

For an ordinary persistent local session:

```bash
python3 app.py
```

The existing OSIS path (`data/nexus.sqlite3`, `NEXUS_DB` or `--db`) is retained.
Other workspace databases live under `data/workspaces/` by default.
`Control+C` stops the server. Use `--port 8766` if necessary.

**Existing installation:** stop the old app and privately copy your entire SQLite
database before upgrading. This release adds tables transactionally without
changing existing table columns or IDs. Test against a copy first. See the
[architecture and compatibility notes](docs/NEXUS_CORE_ARCHITECTURE.md).
Never upload your database or exports to GitHub.

## Implemented now

- Modular reusable `nexus/` Core with compatible `core.py` imports.
- Independent workspace databases, trusted grants and ownership checks.
- Navy responsive dashboard: overview, assignments, projects, calendar, notes,
  memory, assistant and approvals; safe per-request workspace selection.
- Existing OSIS task/delegation/status, event, note and briefing commands.
- Basic projects: create, list and search (title, goal, status, timestamp).
- Structured facts: approved create/update/delete, provenance, creation/approval
  timestamps and source (`command`, `ai`, `legacy`).
- Literal search of facts, projects, notes and persisted conversation history.
- Central command/model planner with a fixed tool registry, visible plan reports
  and atomic plans of 1–5 local writes behind one explicit approval.
- Expiring one-time approval tokens, transaction rollback and local audit.
- Full business-record JSON exports; calendar `.ics` export remains manual.
- Optional cloud AI only with explicit opt-in; offline commands always available.
- Existing browser dictation/TTS controls; external dictation requires confirmation.
- Standard-library unit/HTTP tests, optional browser smoke, and CI configuration.

No unrestricted shell/file tools, automatic sending, payment, trading, cloud sync,
agent swarm, authentication or encrypted storage are implemented. Other workspaces
are functional generic containers, without specialist domain applications.

## Commands

```text
/help
/brief
/tasks
/task add Prepare proposal | OSIS team | 2026-11-20 | high
/task doing 1
/task done 1
/task assign 1 | Planning team
/event add Planning session | 2026-11-21 | 14:00 | Meeting room | Review owners
/note add Planning notes | Confirm responsibilities before publishing
/project add Research roadmap | Compare local AI options
/projects
/remember Meeting rhythm | Weekly
/search roadmap
/forget Meeting rhythm
/audit
```

Every business-record change is proposed first. Review its full details in Approval
inbox before approving. Chat, proposals and audit records are saved as operational
history without a second confirmation.

In the assistant, use Shift+Enter for a multistep plan:

```text
/plan
/task add Compare local models | Research owner
/project add Local AI evaluation | Compare latency and privacy
/remember Research preference | Local-first
```

All steps commit together after approval or roll back together on failure. Plans
cannot reference newly generated task IDs or include external actions.

Terminal-only mode:

```bash
python3 app.py --cli --workspace personal
```

Enter `/plan` in the CLI, then each step on its own line and a blank line to finish.

## Optional natural-language AI

Offline and demo sessions need no dependencies. To opt in to OpenAI:

```bash
python3 -m pip install -r requirements-ai.txt
python3 app.py --enable-ai
```

Set `OPENAI_API_KEY` in your local environment first; never put it in source or
Git. `NEXUS_MODEL` defaults to `gpt-4.1-mini`; `NEXUS_TIMEZONE` defaults to
`Asia/Jakarta`. Key presence alone does not enable AI. Opt-in sends bounded context
and recent chat from the active workspace to the provider. No paid API requests
were made during development; provider behavior is tested with fakes.

Browser speech recognition may use a separate external service and is independent
of the OpenAI flag. Review dictated text before sending. Real microphone behavior
on the owner's device has not been tested.

## Development and verification

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q app.py core.py nexus tests
node --check web/app.js
```

The regression suite uses temporary invented records and loopback HTTP only.
For the optional UI smoke check, install Playwright in a development environment
with Chromium at `/usr/bin/chromium`, then run `python3 tests/browser_smoke.py`.
The runtime itself does not need Playwright or Node.

[Architecture](docs/NEXUS_CORE_ARCHITECTURE.md) ·
[Implementation plan](docs/IMPLEMENTATION_PLAN.md) ·
[Mission report](docs/MISSION_001_REPORT.md) ·
[Security](docs/SECURITY_AND_PRIVACY.md) ·
[Testing](docs/TESTING_AND_RELEASES.md)

Older roadmap documents describe long-term goals; the Mission 001 architecture
and report identify exactly what this iteration ships. This remains a localhost
prototype, not a production school or company system. Local account security is
the trust boundary. JSON export excludes history/proposals and has no restore UI;
use a private full SQLite copy for recovery.
