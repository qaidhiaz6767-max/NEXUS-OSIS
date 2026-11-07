# Try the NEXUS Command Center

## Get the redesign without Terminal GitHub authentication

1. Open the `feat/nexus-command-center` branch in GitHub while signed in.
2. Select **Code → Download ZIP** and double-click the ZIP in Finder → Downloads.
3. Stop your old running NEXUS with **Control+C** in its Terminal window.
4. In Terminal, run these lines separately:

```bash
cd ~/Downloads/NEXUS-OSIS-feat-nexus-command-center
python3 app.py --demo
```

Open **http://127.0.0.1:8765**. No GitHub password is needed to run an unzipped
copy. If Terminal still displays a Git password prompt, cancel it with Control+C
before entering the commands. The redesign is on its review branch, not `main`.

Demo mode creates invented temporary records, shows a visible demo banner, and
never opens your normal OSIS database. Changes disappear when you stop the demo.
Use `--port 8766` and open that port if another app is using 8765.

## A useful first walkthrough

- On Command Center, select **Give me my briefing**. The Assistant responds with
  a real overview of this workspace's stored records.
- Open **Tasks → New task**, fill in a title, owner, deadline and priority, then
  choose **Review change**. The task is still a proposal.
- In **Approvals**, open the exact-value details. Choose **Approve** to save or
  **Reject** to discard the proposed change.
- Search tasks, filter status/priority and sort by deadline. Open the task title
  for details. Assignments are local records; no one is notified automatically.
- Open **Projects** for project goals, **Calendar** for the agenda, **Meetings**
  for approved notes and **Memory** for facts and their sources.
- Switch **OSIS → Personal**. The records and chat change with the workspace.
- Open **Activity** to see actual proposals/decisions and **Settings** for the
  current timezone, storage mode, capabilities and optional speech settings.

## Keyboard and speech

Enter sends a command; Shift+Enter adds a line. Ctrl/Command+K opens Assistant
when focus is outside another input or dialog. Escape closes dialogs/drawer and
returns focus. Tab stays within an open modal or mobile drawer.

The microphone requires a separate consent step because browser transcription
may use an external service. A highlighted microphone means recognition actually
started; click it to stop. Dictation fills the input only. Review before sending.
Read aloud is optional. The Settings page has a stop-playback button.

## Current limits

Offline commands such as `/brief`, `/tasks`, `/help` and `/plan` work without a
model. Natural-language AI requires trusted startup opt-in and a configured key.
“Configured · unverified” is not a successful connection; verified status appears
only after a model response. API keys are never entered in the dashboard.

Projects currently store goals/status. Project owners, milestones and task links
are future extensions. Meetings currently use reviewed note records, not a formal
participant/decision database. Search is literal and workspace-local, not semantic.
Lists retain Core limits; metrics count all applicable stored records. Exports are
manual and do not provide a full restore interface. There is no notification,
external sync, payment/trading or unrestricted terminal tool.

This is a local single-user prototype. Mission 001's data/security limits still
apply. No new database migration is introduced by the interface redesign.
