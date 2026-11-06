# Test strategy and release gates

## Automated checks shipped

`python3 -m unittest discover -s tests -v` runs offline and requires no paid API or live school account. GitHub Actions runs Python compile + tests on Linux with Python 3.11 and 3.13. This validates important core behavior, but **not** microphone availability, actual browser UX or remote integrations.

Current tests check approval-before-write, rejection, one-time approval, date/priority validation, task update and delegation, unsupported operation rejection, SQL injection handling, briefing/export, restart persistence, optional API fallback, mocked model tool proposal and event non-sending.

## Future test layers

1. **Unit:** validators, status transitions, date math, project/task models, prompt context filters.
2. **Integration:** local HTTP API, SQLite transaction/concurrency, migrations, backup and restore.
3. **Contract:** fake model and fake adapters validate exact tool schemas and outcomes.
4. **Security:** origin/Host checks, state disclosure, replay, expired actions, prompt injection and secret patterns.
5. **UI:** browser smoke checks for task approval, keyboard accessibility, speech fallback.
6. **Privacy:** simulated data export/import, retention, no cross-workspace leakage and no real account tokens in logs.
7. **Resilience:** network timeouts, model absence, duplicate requests, partial database failure, canceled approvals.
8. **Release:** fresh install on Mac, upgrade from older DB backup, manual voice test, documentation review.

## Acceptance scenarios

**S1** User creates a task: before approval, row count unchanged; after approval, one row exists and audit indicates approval.

**S2** User rejects or lets approval expire: row count unchanged; cannot reuse token.

**S3** User asks to send a WhatsApp message: offline v0.1 must not send; model has no send tool.

**S4** User gives invalid date `2026-02-30`: rejected, no partial record.

**S5** User inserts SQL-like or HTML-like strings: stored/escaped as text; no SQL execution or page script injection.

**S6** User restarts the app: task/event list persists.

**S7** User disconnects the internet or removes AI key: `/help`, `/tasks`, `/brief` continue working.

**S8** User refreshes pending approvals: correct state displayed; a previously approved ID cannot run again.

**S9** User asks about facts not in the database: system expresses uncertainty rather than claiming a non-existent event.

**S10** Future model reads hostile meeting notes: hostile instructions must be ignored by tool/policy layer.

**S11** Future connector send fails: no misleading "delivered" status, and retry doesn't create duplicates.

**S12** Future OSIS and ATLAS workspaces: querying OSIS cannot retrieve ATLAS records, even when text resembles a similar project.

## Manual Mac smoke checklist

- [ ] Starts with `python3 app.py` using Python 3.10+.
- [ ] Loads at http://127.0.0.1:8765; browser can send `/brief`.
- [ ] New dummy task appears only after approving it.
- [ ] Restart preserves task.
- [ ] Export calendar and backup produce local file with expected format; do not upload exports.
- [ ] Chrome/Safari speech capability is tested; unsupported browsers show honest fallback.
- [ ] TTS uses user-selected language and can be turned off.
- [ ] No forced cloud key or unexpected network requests in offline mode.
- [ ] Closing app stops server.

## Release checklist

A release can be tagged only if: all appropriate tests pass; planned/available features are described accurately; no actual school information or keys are present in Git; permissions have not broadened unexpectedly; the backup/migration path is tested if schema changed; and manual Mac tests for user-facing features are recorded.

Use semantic versioning loosely at prototype stage (`0.1.1`, `0.2.0`, etc.). Do not call something `1.0` solely because it looks polished.
