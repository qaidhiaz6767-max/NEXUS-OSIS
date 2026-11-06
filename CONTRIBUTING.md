# Contributing to NEXUS OSIS

NEXUS is primarily a local project. The repository can be private while you develop it.

1. Open an issue explaining the real need; use invented names and dummy event details.
2. Create a branch: `git switch -c feat/short-description`.
3. Keep `core.py` the authority for data writes; the browser and any model cannot bypass the policy/approval boundary.
4. Add tests for new behavior and failure cases. Run `python3 -m unittest discover -s tests -v`.
5. Review `git status` and `git diff --cached` before every commit.
6. Submit a pull request. Do not merge if CI fails or a high-risk permission is unclear.

Never include student grades, addresses, phone numbers, teacher/private personnel records, raw meeting transcripts, live OSIS documents, credentials, chat logs, backup archives, or database files in issues, screenshots or commits. If a credential leaks, revoke/rotate it immediately; deleting the file from the latest commit is not enough to erase Git history.

## Code quality conventions

- Prefer Python standard library for the offline core; document any extra dependency.
- Keep API and integrations explicit; validate arguments strictly and avoid arbitrary shell/filesystem tools.
- Favor user-visible proposal → approve/reject → execute → verify flows.
- Review all actions affecting people or external services before granting write scopes.
- Respect school policies and obtain consent before using any school-owned accounts or services.
