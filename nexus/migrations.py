"""Versioned, additive migration. Existing OSIS tables/column order stay intact."""

SCHEMA_VERSION = 2


def initialize_schema(con, workspace_id):
    # Check ownership/version before any DDL or data changes.
    tables = {
        row[0]
        for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "workspace_identity" in tables:
        row = con.execute(
            "SELECT workspace_id FROM workspace_identity WHERE singleton=1"
        ).fetchone()
        if row and row[0] != workspace_id:
            raise ValueError("Database belongs to another workspace")
    if "nexus_schema" in tables:
        row = con.execute(
            "SELECT version FROM nexus_schema WHERE singleton=1"
        ).fetchone()
        if row and row[0] > SCHEMA_VERSION:
            raise ValueError("Database schema is newer than this application")
    # executescript starts a transaction explicitly; caller commits or rolls back
    # all schema changes, backfill and identity together.
    con.executescript(
        """BEGIN IMMEDIATE;

                CREATE TABLE IF NOT EXISTS workspace_identity (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), workspace_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    goal TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, owner TEXT NOT NULL, due_date TEXT NOT NULL,
                    priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'todo',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, day TEXT NOT NULL, time TEXT NOT NULL,
                    location TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY COLLATE NOCASE, value TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_actions (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, args_json TEXT NOT NULL,
                    description TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    event TEXT NOT NULL, detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nexus_schema (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_metadata (
                    action_id TEXT PRIMARY KEY REFERENCES pending_actions(id),
                    source TEXT NOT NULL CHECK(source IN ('command','ai'))
                );
                CREATE TABLE IF NOT EXISTS memory_metadata (
                    key TEXT PRIMARY KEY COLLATE NOCASE REFERENCES memories(key) ON DELETE CASCADE,
                    source TEXT NOT NULL, created_at TEXT NOT NULL,
                    approved_at TEXT NOT NULL, approval_id TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_details (
                    project_id INTEGER PRIMARY KEY REFERENCES projects(id),
                    owner TEXT NOT NULL DEFAULT 'Unassigned', target_date TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS milestones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL REFERENCES projects(id),
                    title TEXT NOT NULL, target_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_details (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id), description TEXT NOT NULL DEFAULT '',
                    project_id INTEGER REFERENCES projects(id), milestone_id INTEGER REFERENCES milestones(id),
                    completed_at TEXT, follow_up_context TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id INTEGER NOT NULL REFERENCES tasks(id), depends_on INTEGER NOT NULL REFERENCES tasks(id),
                    PRIMARY KEY(task_id,depends_on), CHECK(task_id!=depends_on)
                );
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, held_on TEXT NOT NULL,
                    project_id INTEGER REFERENCES projects(id), agenda TEXT NOT NULL,
                    draft_minutes TEXT NOT NULL, participants_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER REFERENCES meetings(id),
                    project_id INTEGER REFERENCES projects(id), title TEXT NOT NULL, body TEXT NOT NULL,
                    status TEXT NOT NULL, source_ref TEXT NOT NULL, created_at TEXT NOT NULL,
                    approved_at TEXT, approval_id TEXT
                );
                CREATE TABLE IF NOT EXISTS meeting_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL REFERENCES meetings(id),
                    title TEXT NOT NULL, owner TEXT NOT NULL, due_date TEXT NOT NULL, priority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft', task_id INTEGER REFERENCES tasks(id),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_details (
                    key TEXT PRIMARY KEY COLLATE NOCASE REFERENCES memories(key) ON DELETE CASCADE,
                    category TEXT NOT NULL DEFAULT 'operational_fact', source_ref TEXT NOT NULL DEFAULT '',
                    valid_until TEXT NOT NULL DEFAULT '', confirmation TEXT NOT NULL DEFAULT 'confirmed'
                );
                CREATE TABLE IF NOT EXISTS plan_records (
                    id TEXT PRIMARY KEY REFERENCES pending_actions(id), objective TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    result_json TEXT, error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS pending_context (
                    action_id TEXT PRIMARY KEY REFERENCES pending_actions(id), fingerprints_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS command_runs (
                    id TEXT PRIMARY KEY, command TEXT NOT NULL, intent TEXT NOT NULL,
                    status TEXT NOT NULL, action_id TEXT REFERENCES pending_actions(id),
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, result_json TEXT, error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS command_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT NOT NULL REFERENCES command_runs(id),
                    from_status TEXT NOT NULL, to_status TEXT NOT NULL, at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_references (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_task_id INTEGER REFERENCES tasks(id),
                    last_project_id INTEGER REFERENCES projects(id), last_meeting_id INTEGER REFERENCES meetings(id)
                );
                CREATE INDEX IF NOT EXISTS task_project_idx ON task_details(project_id);
                CREATE INDEX IF NOT EXISTS task_completion_idx ON task_details(completed_at);
                CREATE INDEX IF NOT EXISTS meeting_project_idx ON meetings(project_id);
                CREATE INDEX IF NOT EXISTS command_action_idx ON command_runs(action_id);
    """
    )
    current = con.execute(
        "SELECT version FROM nexus_schema WHERE singleton=1"
    ).fetchone()
    if current and current[0] > SCHEMA_VERSION:
        raise ValueError("Database schema is newer than this application")
    con.execute(
        "INSERT OR IGNORE INTO workspace_identity VALUES(1, ?)", (workspace_id,)
    )
    # Recheck under the write lock, in case initialization raced on a new file.
    if (
        con.execute(
            "SELECT workspace_id FROM workspace_identity WHERE singleton=1"
        ).fetchone()[0]
        != workspace_id
    ):
        raise ValueError("Database belongs to another workspace")
    con.execute(
        """INSERT OR IGNORE INTO memory_metadata
        SELECT key, 'legacy', updated_at, updated_at, '' FROM memories"""
    )
    con.execute(
        "INSERT OR IGNORE INTO project_details(project_id,updated_at) SELECT id,created_at FROM projects"
    )
    con.execute("INSERT OR IGNORE INTO task_details(task_id) SELECT id FROM tasks")
    con.execute("INSERT OR IGNORE INTO memory_details(key) SELECT key FROM memories")
    con.execute(
        "INSERT OR IGNORE INTO conversation_references VALUES(1,NULL,NULL,NULL)"
    )
    con.execute(
        """INSERT OR IGNORE INTO plan_records(id,objective,status,created_at,updated_at)
        SELECT id,description,CASE status WHEN 'pending' THEN 'awaiting_approval'
        WHEN 'approved' THEN 'completed' ELSE 'cancelled' END,created_at,created_at FROM pending_actions"""
    )
    con.execute("INSERT OR REPLACE INTO nexus_schema VALUES(1, ?)", (SCHEMA_VERSION,))
