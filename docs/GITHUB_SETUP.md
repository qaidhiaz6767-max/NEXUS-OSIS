# Set up the NEXUS GitHub repository on a MacBook Air M2

**Recommended repository name:** `nexus-osis`  
**Recommended visibility:** **Private**  
**Recommended default branch:** `main`  
**Recommended first release tag:** `v0.1.1` after local tests pass.

## A. Prepare the source folder

1. Download `NEXUS-OSIS-GitHub-Starter.zip` and unzip it.
2. Keep the unzipped `NEXUS-OSIS-GitHub-Starter` folder separate from any previous NEXUS data folder; this version contains code, tests, and documentation, but **no private SQLite database**.
3. Open Terminal; type `cd ` (with trailing space); drag the unzipped folder from Finder into the Terminal, press Return.
4. Check Python, run automated tests, and launch:

```bash
python3 --version
python3 -m unittest discover -s tests -v
python3 app.py
```

Open `http://127.0.0.1:8765`. Test `/help`, `/brief`, and one sample task. Stop with `Control+C`.

**Important:** When the app starts, it creates `data/nexus.sqlite3` locally. `.gitignore` excludes it. The code works without a paid API. Never include real student information in a sample task that you plan to publish or screenshot.

## B. GitHub Desktop method (recommended for a first repository)

1. Install **GitHub Desktop** from its official website: https://desktop.github.com/ (or use an installation you already trust).
2. Sign in to your own GitHub account.
3. In GitHub Desktop choose **File → Add Local Repository**, select the unzipped NEXUS project folder. If it is not already a Git repository, choose **Create a Repository Here**, then create one in that existing folder. Do not create a second nested `nexus-osis` folder.
4. In the Changes tab, verify source/docs are present but **no** `.env`, `data/`, SQLite, backup, exported `.ics`, screenshots containing student information, or API key.
5. Enter summary **"Initial NEXUS OSIS starter"**; choose **Commit to main**.
6. Click **Publish repository**, name it `nexus-osis` and select **Keep this code private**.
7. Confirm Publish, then open the repository on GitHub; check that the `NEXUS tests` workflow runs and passes.
8. Under **Settings** review security options: Dependabot alerts, secret scanning/push protection when available, and branch protection/rulesets when applicable.

Official Desktop walk-through: https://docs.github.com/en/desktop/overview/creating-your-first-repository-using-github-desktop

## C. Terminal / GitHub CLI method (alternative)

You need **git** and **GitHub CLI (`gh`)**. If `gh` isn't installed, use GitHub Desktop instead, or install it using the current official instructions: https://cli.github.com/.

From inside the unzipped NEXUS project folder:

```bash
# Check the tools
git --version
gh --version

# GitHub CLI will guide you to authenticate in the browser;
# do not paste your password or access tokens into your source files.
gh auth login

# Create a repository locally and stage only specific project directories/files.
git init -b main
git add README.md CHANGELOG.md CONTRIBUTING.md \
  app.py core.py requirements-ai.txt run.command \
  .gitignore .env.example .editorconfig \
  web/ tests/ integrations/ docs/ .github/

# Review what will be published. STOP if private records appear.
git diff --cached --name-only
git diff --cached --stat

# Create first commit
git commit -m "Initial NEXUS OSIS chief-of-staff prototype"

# Create a PRIVATE remote repository and push.
gh repo create nexus-osis --private --source=. --remote=origin --push
```

If `git commit` asks for identity, set your own Git configuration (`git config --global user.name "YOUR-NAME"`, `git config --global user.email "YOUR-VERIFIED-GITHUB-EMAIL"`); you may prefer a GitHub-provided noreply address for privacy. Do not copy the illustrative placeholder literally.

**Do not run both Desktop and CLI creation flows** against separate new repositories. Pick one. If `git init -b main` reports that Git is already initialized, use `git status` and proceed accordingly.

Official import instructions: https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github

## D. First GitHub configuration

- Private visibility; review collaborators carefully.
- Enable two-factor authentication on your GitHub account.
- Enable Dependabot and secret scanning/push protection where available.
- Let CI run on pull requests. If rulesets/branch protection are available, require passing tests before merging.
- Use Issues for engineering work only; do not paste real OSIS decisions with identifying people.
- Optionally create a GitHub Project board with columns: `Backlog`, `Ready`, `In Progress`, `Review`, `Done`.
- Add labels: `priority:P0`, `priority:P1`, `priority:P2`, `area:core`, `area:ux`, `area:privacy`, `area:ai`, `area:voice`, `area:integration`, `bug`, `docs`.

## E. Suggested first project board

| Column | Example item |
|---|---|
| Backlog | Searchable meeting notes |
| Ready | Project data model and migration |
| In Progress | HTTP permission and Host tests |
| Review | Meeting agenda draft prototype |
| Done | Baseline local DB approval tests |

Create issues from `docs/ISSUE_BACKLOG.md`. Keep issues free of names, emails and real school records.

## F. Normal development workflow after publishing

```bash
# From project folder
git switch -c feat/projects
# edit files in VS Code
python3 -m unittest discover -s tests -v
git status --short
# review file list and contents before staging
git add core.py tests/test_core.py docs/ARCHITECTURE.md
git diff --cached
git commit -m "Add initial project model and tests"
git push -u origin feat/projects
```

Open GitHub → Pull requests → New pull request. Review CI and merge when green. Afterwards `git switch main` and `git pull` to update the local main branch. This process protects working code from half-finished experiments.

## G. How to move from the previous v0.1 folder

This starter is intentionally a **clean source repo**. Don't copy the old `data/` directory into GitHub. If you need your existing task records, close both apps and make a private local copy of the prior `data/nexus.sqlite3` into the new project's `data/` directory (not Git). The database schema is based on the same v0.1 code; verify with the current test suite and back up first. Never put backup files in the repo.

## H. Common problems

**`python3` not found:** install a supported Python from python.org or via your managed environment; use the same Python for tests and app.

**`Address already in use`:** an older NEXUS process is still running. Stop it with Control+C, or use `python3 app.py --port 8766`.

**`gh: command not found`:** use GitHub Desktop or install `gh` from official site.

**GitHub reports repo already exists:** choose a different repository name or attach to the correct existing remote; don't force-push unknown history.

**AI not working:** `/brief` and `/tasks` should still work offline. Natural-language reasoning needs a separately billed API key, provider package, connectivity and guardian involvement when applicable; ChatGPT subscription is not an API credential.

**Mic doesn't work:** try Chrome/Edge or macOS Dictation. Safari/browser support varies; do not assume speech recognition is offline. Review speech transcript before sending.

**CI fails:** open the Actions tab and read the first error, then reproduce using `python3 -m unittest discover -s tests -v`. CI should not require your API key.

**Accidentally pushed private data:** immediately rotate any leaked credentials, stop further sharing, and consult GitHub's sensitive data removal guide. Deleting the latest version of a file does not necessarily remove Git history.

## I. Checklist before clicking Publish

- [ ] All local tests pass.
- [ ] Repository visibility set to **Private**.
- [ ] Only code and fictional/dummy examples staged.
- [ ] No `data`, `.env`, exports, backups, school photos or real student details.
- [ ] No API keys, tokens or passwords inside source or docs.
- [ ] README accurately lists shipped vs planned features.
- [ ] CI workflow has least-privilege `contents: read` permissions.
- [ ] GitHub account has a secure login and MFA.
- [ ] You have not enabled remote access to the local app.
