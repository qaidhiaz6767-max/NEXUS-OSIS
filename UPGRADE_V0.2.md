# NEXUS OSIS v0.2 — Executive Workspace UI

This release modernizes the user interface only. **Your local SQLite database remains compatible and untouched.**

## What's new

- Clean executive overview, real assignment table with search and status filters.
- Task status and owner change controls (every write still needs approval).
- Dedicated event timeline, meeting notes, memory and approval inbox views.
- Quick-add forms for tasks, events, notes and memory (proposals only).
- Dedicated Chief of Staff conversation, retaining the local command parser and optional AI/voice features.
- Responsive layout, keyboard shortcut `⌘K` / `Ctrl+K` to open assistant, focus states and safe text-only rendering.

## What hasn't changed

- No login or multi-user access. Do **not** expose the server to a network.
- The database remains unencrypted and stored locally in `data/nexus.sqlite3`.
- AI conversation still requires separately configured model API credentials. Without them, offline slash commands work.
- Event/task assignments inside NEXUS do not notify other people, or sync to school systems.
- The OpenClaw integration remains a future adapter, not installed.

## Upgrade an existing NEXUS without losing your tasks

If you've already used the GitHub starter, **do not delete your old project**. The easiest approach is the separate `NEXUS-UI-Upgrade-v0.2.zip` file with an installer that copies **only the three web files**, saving backups of their old versions. The installer never accesses your SQLite data.

1. Stop the old NEXUS server using `Control+C` in its Terminal window.
2. Download the UI upgrade ZIP to `~/Downloads`.
3. Open Terminal and run:

```bash
cd ~/Downloads
unzip -o NEXUS-UI-Upgrade-v0.2.zip -d NEXUS-UI-Upgrade-v0.2
python3 ~/Downloads/NEXUS-UI-Upgrade-v0.2/upgrade.py
```

4. Restart the server in its existing project directory:

```bash
cd ~/Downloads/NEXUS/NEXUS-OSIS-GitHub-Starter
python3 -m unittest discover -s tests -v
python3 app.py
```

5. Open `http://127.0.0.1:8765` and press `Command+R (or Option+Command+R to reload from origin)` in Safari if the old stylesheet remains cached.

If the project lives elsewhere, provide its full directory to the installer:

```bash
python3 ~/Downloads/NEXUS-UI-Upgrade-v0.2/upgrade.py "/path/to/your/NEXUS/project"
```

## Installing the full v0.2 package as a separate folder

The full `NEXUS-OSIS-v0.2-GitHub.zip` is for a new project or GitHub upload. Its default database path is *inside that new folder*, so it won't automatically see records from your existing v0.1 folder. Either use the UI upgrade installer above, or safely copy the existing database **after shutting down the old server**. Avoid overwriting your only copy of personal data.

## Safety and development

This is a single-user local prototype, not a production-ready school system. Do not store sensitive student data; do not upload SQLite files or API keys to GitHub. Manual browser and microphone tests on your Mac are still recommended.
