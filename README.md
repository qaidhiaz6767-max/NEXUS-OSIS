# NEXUS OSIS — Your AI Chief of Staff

**NEXUS (Neural Executive Coordination & Unified System)** is a local-first Python project for a student council president: a command center that can track OSIS assignments, events, notes, approved memories, and follow-ups. Its architecture is designed to grow toward a personal assistant and, much later, a separately controlled executive workspace.

> **Version:** v0.2 Executive Workspace UI (backward-compatible with v0.1 data). **Status:** single-user prototype, not a production school system. **OpenClaw is not installed or integrated.**

## What is working today

- Redesigned browser command center at `http://127.0.0.1:8765`, plus a terminal-only mode.
- Dedicated overview, assignments (search/filter), events, meeting notes, institutional memory, assistant chat and approval inbox.
- Quick-add forms and task status/delegation buttons; every database write still requires explicit approval.
- Persistent SQLite tasks, events, notes, memories, messages and audit records.
- Text command parser and daily OSIS briefing.
- One-time approval proposals before supported task/event/note/memory changes.
- JSON backup export and `.ics` event export (manual, not synchronized).
- Optional AI chat via separately configured API and the Python OpenAI SDK.
- Browser push-to-talk transcription and spoken replies **where supported**; speech recognition may use an online service.
- Offline automated tests; GitHub Actions CI; detailed project, architecture, privacy and GitHub guides.

**Not available:** full project management module, meeting minutes automation, WhatsApp/Telegram sending, cloud calendar sync, Google Drive reading, OpenClaw gateway, unrestricted autonomous actions, always-on voice, multi-user login or guaranteed private/offline AI conversation. See the phased plan below.

See **[UPGRADE_V0.2.md](UPGRADE_V0.2.md)** if you are upgrading an existing NEXUS with saved OSIS tasks. Use the UI upgrade ZIP to preserve your existing database.

## Quick start — MacBook Air M2

1. Unzip the starter archive into a normal folder in Downloads or Documents.
2. In Terminal, type `cd `, drag the unzipped folder to the Terminal, and press Return.
3. Run the tests and start the local dashboard:

```bash
python3 --version
python3 -m unittest discover -s tests -v
python3 app.py
```

Open `http://127.0.0.1:8765` if the browser does not open automatically. `Control+C` stops the server.

Try these commands:

```text
/help
/brief
/task add Prepare OSIS proposal | OSIS Secretary | 2026-11-20 | high
/tasks
/event add Committee planning | 2026-11-21 | 14:00 | Meeting room | Review task owners
```

Every data-changing command creates a **proposal**. Review it and click **Approve change** to save. The demo examples use role names rather than real people.

**Requirements:** Python 3.10+, macOS recommended. Offline command mode uses only the Python standard library; no installation of Docker, Node, OpenClaw or model API is needed.

### Terminal-only mode

```bash
python3 app.py --cli
```

### Optional AI conversation

Without a model key, natural conversation is not active; only `/` commands and a few matching phrases work. For AI chat, use a supported API account, the optional SDK and provider credentials. Separate provider usage charges and age/payment requirements may apply; under-18 users should involve a parent/guardian.

```bash
python3 -m pip install -r requirements-ai.txt
read -s OPENAI_API_KEY
export OPENAI_API_KEY
python3 app.py
```

The `read -s` prompt hides input while you paste a key and press Return. Do **not** save the key in Git, the `.env.example`, an issue or a screenshot. A ChatGPT subscription is separate from model API billing. If AI is enabled, relevant bounded OSIS context is sent to the API; do not include private school records.

### Optional voice

Select Indonesian or English, click the microphone if available, review the transcription, then submit. You can enable spoken replies. Browser support varies; macOS Dictation can be a fallback. Voice recognition may contact an external service and is *not* an always-on assistant.

## Repository map

```text
nexus-osis/
├── app.py                        # localhost API + optional terminal interface
├── core.py                       # database, policy, coordinator and commands
├── web/                          # browser dashboard / voice controls
├── tests/                        # offline unit tests
├── integrations/OPENCLAW_FUTURE.md
├── docs/
│   ├── MASTER_PLAN.md            # complete long-term plan & stages
│   ├── ARCHITECTURE.md           # current and future design
│   ├── GITHUB_SETUP.md           # publish private repo step by step
│   ├── ISSUE_BACKLOG.md          # 36 GitHub issues + acceptance criteria
│   ├── SECURITY_AND_PRIVACY.md   # data policy + threat model
│   ├── TESTING_AND_RELEASES.md   # test plan + quality gates
│   ├── DECISIONS.md              # important architectural decisions
│   ├── QUICK_REFERENCE.md        # OSIS commands
│   └── OSIS_PLAYBOOK.md          # Daily president workflow
├── .github/                      # CI + issue / PR templates + Dependabot
├── requirements-ai.txt           # optional API SDK dependency
├── .env.example                  # safe configuration example, NO secrets
├── .gitignore                    # keep school data and credentials off GitHub
├── CONTRIBUTING.md
└── CHANGELOG.md
```

## Long-term goals (planned, not yet implemented)

| Stage | Focus | State |
|---|---|---|
| M0 | Clean GitHub source, safety review, CI | **Starter available** |
| M1 / v0.2+ | Projects, milestones, improved tasks | UI updated; project module still planned |
| M2 / v0.3 | Meetings, decisions, minutes and templates | Planned |
| M3 / v0.4 | Better voice and context-aware conversation | Planned |
| M4 / v0.5 | Executive dashboard and risk/priority briefings | Planned |
| M5 / v0.6 | School-authorized read-only integrations | Planned |
| M6 / v0.7 | Carefully approved outbound workflows | Planned |
| M7 / v0.8–0.9 | Handover, backup/restore and hardening | Planned |
| M8 / v1.0 | Dependable single-user OSIS assistant | Planned |
| M9+ | Separate personal and future ATLAS workspaces | Long-term concept |

**Full specification:** [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md)  
**Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
**GitHub setup:** [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md)  
**Suggested issues:** [docs/ISSUE_BACKLOG.md](docs/ISSUE_BACKLOG.md)  
**Security rules:** [docs/SECURITY_AND_PRIVACY.md](docs/SECURITY_AND_PRIVACY.md)  
**OSIS operations:** [docs/OSIS_PLAYBOOK.md](docs/OSIS_PLAYBOOK.md)

## OSIS safety and privacy

This is a **single-user prototype without login authentication**, and the SQLite database is not encrypted. It listens on localhost and is not intended to be exposed to other devices or to the internet. Do not store restricted student/teacher information, grades, health or disciplinary records, phone numbers or addresses. Consult school policy and appropriate advisers before connecting school-owned services or recording/transcribing meetings.

**Never commit `data/`, SQLite files, backups, exports, raw meeting transcripts, API credentials, tokens, or other people's private information to GitHub.** `.gitignore` helps but is not a substitute for reviewing your staged files before pushing.

NEXUS never sends a message, contacts a person, or changes an external calendar in v0.1. Project tasks assigned in its local database are internal planning records and do not notify the assignee.

## Contributing / development

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

Use GitHub issue descriptions with fake names. Work on feature branches, require tests for changes, and review staged diffs. See [CONTRIBUTING.md](CONTRIBUTING.md). The repo has no open-source license by default; select one deliberately if/when you decide to open-source.

## Credits and limitations

Built as a learning and practical OSIS coordination project. This code is not a guarantee of security, accuracy or autonomy; it requires real-device usability tests and further hardening before broader use. The official GitHub and OpenClaw documentation linked in the docs should be rechecked before integrations and major upgrades.
