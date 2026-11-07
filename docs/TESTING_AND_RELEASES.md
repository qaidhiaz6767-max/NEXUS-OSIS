# Tests and release evidence — Missions 001–002

## Runtime and checks

Offline runtime: Python 3.11+, standard library and SQLite. The optional OpenAI
package is not needed for tests. No live AI key or school/company accounts are
used. Tests create temporary invented records and use loopback HTTP only.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q app.py core.py nexus tests
node --check web/app.js
```

The configured GitHub Actions workflow runs compile, unit/HTTP tests and JS syntax
checks on Python 3.11 and 3.13. Local execution evidence uses Python 3.12; a workflow
file is not evidence that hosted CI has passed. Consult the PR's actual checks.

## Automated coverage

- Original OSIS task/event/note/fact commands, assignment/status updates and imports.
- Validation, SQL-like text, tool allowlisting and approval-before-write.
- Rejection, expiry, replay, concurrent double approval and rollback on failure.
- Legacy schema migration, preserved task IDs and pending approvals; future-schema
  refusal and rollback after an incompatible-schema migration failure.
- Scoped workspace state, proposals, history, projects, search, exports and AI context.
- Unknown/path-like/duplicate workspace parameters and independent capability grants.
- Cloud opt-in and `ai` grant enforcement; fake provider output, tool rejection
  and multiple calls grouped into one approved atomic plan.
- Memory update/delete, source/approval provenance and rollback of sidecar changes.
- Search wildcard escaping, persisted history, complete business-record JSON export.
- Existing HTTP Host/Origin/body/header protections and new dashboard assets/routes.
- Demo CLI ignores the configured real database path and uses invented records.

## Optional real-browser smoke

Development-only dependencies: Playwright Python package and local Chromium at
`/usr/bin/chromium` (adjust `executable_path` for another platform).

```bash
python3 tests/browser_smoke.py
```

This starts a temporary local app with invented records, checks desktop rendering,
switches to Personal, creates a project proposal in the form, approves it, verifies
the database outcome and OSIS isolation, checks a 390px mobile width, and fails on
browser JavaScript errors. It does not require public hosting or a paid API.
Set `NEXUS_SCREENSHOT` to a local scratch path to capture the sample dashboard.

## Manual gates still required

Before using real records: privately copy the complete SQLite file and try the
upgrade on a copy. Restore that pre-upgrade copy to roll back. JSON record export
is not a full database restore mechanism; it excludes chat and pending actions.

Before a release: run a fresh Mac install, manually verify keyboard/screen-reader
navigation, speech permissions/dictation/TTS on the owner's browser, timezone
behavior and recovery. These hardware checks have not been completed in Linux CI.

Before external adapters: add authorization/scope, redacted audit, timeout,
idempotency, recipient/content previews and verified-delivery tests. Before any
remote deployment: real authentication and a fresh threat model are required.
Do not change the loopback binding as a substitute for those controls.

## Mission 002 interface verification

- `node --test tests/frontend.test.mjs`: timezone date boundaries, deterministic
  priorities, combined task filters, expiry and completed/missing-deadline labels.
- `python3 tests/browser_redesign.py`: full operational/approval journeys,
  persistence, literal text and rich formatting, clipboard, stale-state recovery,
  read-only/isolation/replay/expiry, keyboard focus, shortcuts and simulated speech.
- `NEXUS_SCREENSHOT_DIR=work/screenshots python3 tests/capture_ui.py`: 13 sample-data
  desktop/mobile captures using real local API records.
- Browser reflow checks cover all views at 320px and 390px, plus laptop/desktop.
- `tests/test_interface.py` verifies additive routes, configured-versus-observed AI
  status, non-secret metadata, full-table counts, provenance, local assets,
  timezone fallback and selected text/control contrast ratios.

Playwright and system Chromium remain development-only prerequisites. Real model
calls, Mac/Safari, screen readers and microphone/speaker hardware were not verified.
See [Mission 002 evidence and limits](MISSION_002_REPORT.md).
