# NEXUS — Security, privacy, and school-use rules

NEXUS v0.3 is a personal localhost prototype. The phrase "local-first" does not guarantee security, encryption, or privacy when optional cloud features are enabled. Treat this guide as mandatory before adding integrations or real school data.

## 1. Data categories

| Classification | Examples | In NEXUS? | In GitHub? |
|---|---|---|---|
| Public/demo | Fictional task, publicly published event theme, code and UI | Yes | Yes, if approved and fictional |
| Internal minimal | Program deadlines, committee roles, non-sensitive decisions | Only if authorized | Never as records |
| Restricted school | Contact lists, disciplinary notes, attendance/grades, health, private staff/student info | Not in this prototype | Never |
| Credentials | API keys, OAuth tokens, passwords, cookies | OS env / secure vault only if necessary | Never |
| Voice/raw chat | Recorded meetings, dictated personal info | Avoid by default | Never |
| Exported archives | SQLite and backup JSON, calendar ICS | Personal local storage only | Never |

Even private GitHub repos may be accessible to authorized collaborators or services; private is not the same as an encrypted private vault. `.gitignore` prevents *untracked* ignored files from being staged by default, but it does not remove files already tracked. Review staged files every time.

## 2. Controls in the current Core

- Localhost-only HTTP server; not intended for remote access.
- Model tools are allowlisted and arguments validated.
- No arbitrary shell, browser control, messaging or payment tool exposed to AI.
- Approval is required to mutate task/event/note/memory records.
- Approvals are single-use and expire (local database).
- SQLite transactions and an audit event accompany decisions.
- JS renders user/model content as text, not raw HTML.
- `.gitignore` includes data directory and common credential/export patterns.

## Mission 001 additions

- Independent workspace database files and trusted capability grants; grants are
  host configuration, not authenticated user roles. Default local owner has all grants.
- Ownership and schema-version checks, additive transactional migrations, and
  rollback/replay/concurrent-approval tests.
- Cloud AI requires `--enable-ai` plus the workspace `ai` grant and a key.
- Model-suggested facts retain provenance and enter saved memory only after approval.
- Atomic approved plans contain at most five local writes. No external effects.
- Memory deletion removes the saved fact/provenance, **not** historical proposal
  payloads, chat, audit descriptions or previously exported copies.
- New database files use mode 0600 on POSIX; existing file permissions are retained.
- Error audit records use exception categories, not provider messages or secrets.
- Demo mode uses temporary invented records and disables the cloud AI planner.

## 3. Known limitations and open risks

- **No authentication**: anyone/process with access to the local HTTP server may be able to view or submit state/requests. Localhost binding and basic browser-request protections are not authentication.
- **No encrypted database**: macOS account security matters; do not store restricted records.
- **Browser speech recognition can use cloud services**: don't dictate private information or record meetings without consent.
- **Optional AI sends bounded authorized context externally**: don't enter restricted school data into chats; school policy may prohibit sending even internal records.
- **Chat history is persisted locally**: the existing backup export excludes messages, but local messages remain in SQLite until deleted. Add retention controls before long-term use.
- **No per-user permissions**: a "task owner" is text in a record, not an authenticated user account.
- **No active backup scheduler**: export is manual; a file download by itself does not prove a backup is restorable.
- **Limited testing**: automated unit tests do not cover actual microphone/browser behavior on your Mac.

## 4. Threat scenarios and desired defenses

| Threat | Impact | Mitigation now / future |
|---|---|---|
| Model hallucinates a fact or says an action happened | False reporting | Tool-result verification, explicit status labels, testing |
| Prompt injection in a note / document | Permission bypass attempt | Treat retrieved text as data, never policy; strict allowlist |
| Malicious page talks to localhost | Data access/action attempt | Host/origin checks and headers; future session auth, request token |
| Stolen API key pushed to Git | Financial/security exposure | Environment variable, ignore, staged diff review, secret protection |
| School data entered into cloud chat | Privacy exposure | Minimize data, consent and policy gate, offline mode |
| OpenClaw bridge with shell permissions | Device compromise | Sandboxed separate adapter, deny shell, allowlisted read-only calls |
| OSIS record changed without approval | Corrupt coordination | Approval queue and atomic execute/audit |
| Sending duplicate announcements | Confusion/spam | Disabled today; future idempotent send and explicit preview |
| Loss/corruption of SQLite file | Lost tasks | Manual backup + tested restore; migrations |
| Leaked session screenshots on issues | Student privacy harm | Redact or use synthetic fixtures only |

## 5. Security release gates

**Before v0.2:** preserve permission boundary in tests; document backup & restore; add schema migrations before changing DB tables; validate HTTP host and request handling; audit package dependencies.

**Before any cloud connector:** school account authorization, minimum OAuth scopes, token storage, revocation route, privacy review, meaningful user disclosure of outgoing data, rate limit, test double for CI.

**Before any outbound messaging:** exact recipients preview, proposed body preview, explicit one-time approval, provider status, idempotency, fail-closed behavior, and no bulk messaging by default.

**Before OpenClaw:** read official security docs, run its security audit, constrain gateway access, use allowlisted senders, deny elevated/shell tools, sandbox and separate workspaces; put NEXUS behind a private authenticated bridge with no approval bypass.

**Before LAN/cloud deployment:** do a fresh threat model, implement real authentication/session handling, authorization per operation, TLS when remote, rate limits, monitoring with redaction, secure data storage and school approval. Do not just change `127.0.0.1` to `0.0.0.0`.

## 6. Git and account safety

Before first push:

```bash
git status --short
git diff --cached --name-only
git check-ignore -v data/nexus.sqlite3
```

If your database exists, `git check-ignore` should identify the `.gitignore` rule. Do not paste keys into any example file or GitHub issue. If you accidentally commit a key, **revoke and rotate the key immediately**; removing the current file doesn't necessarily remove it from the repository's history. Consult GitHub's official remediation guidance.

Privacy rules for commit descriptions, issues, PRs and screenshots: no full student names, no addresses, no school-issued IDs, no raw class/group lists, no private teachers' data, no audio recordings.

## 7. User consent and student council responsibility

A student's role as council president does not grant automatic permission to access classmates' personal information, teachers' accounts, attendance systems or private messages. Ask the school's designated adviser before connecting school services or importing non-public documents. For meetings, seek clear consent from participants and school approval before any transcription/recording.

## 8. Incident response (simple version)

1. Stop the local server and disconnect any affected integration.
2. If a secret leaked: immediately revoke/rotate through provider; update local environment.
3. Identify what data may have been included; inform an appropriate trusted adult/school adviser when school data is involved.
4. Restore from a clean backup if records were modified; do not hide evidence from administrators.
5. Document the bug with **dummy** reproduction data; add a regression test before re-enabling.

External sources:
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- https://docs.github.com/en/code-security/concepts/secret-security/command-line-push-protection
- https://docs.openclaw.ai/gateway/security
