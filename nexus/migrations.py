"""Versioned, additive migration. Existing OSIS tables/column order stay intact."""
SCHEMA_VERSION = 1


def initialize_schema(con, workspace_id):
    # Check ownership/version before any DDL or data changes.
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "workspace_identity" in tables:
        row = con.execute("SELECT workspace_id FROM workspace_identity WHERE singleton=1").fetchone()
        if row and row[0] != workspace_id:
            raise ValueError("Database belongs to another workspace")
    if "nexus_schema" in tables:
        row = con.execute("SELECT version FROM nexus_schema WHERE singleton=1").fetchone()
        if row and row[0] > SCHEMA_VERSION:
            raise ValueError("Database schema is newer than this application")
    # executescript starts a transaction explicitly; caller commits or rolls back
    # all schema changes, backfill and identity together.
    con.executescript("""BEGIN IMMEDIATE;

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
    """)
    con.execute("INSERT OR IGNORE INTO workspace_identity VALUES(1, ?)", (workspace_id,))
    # Recheck under the write lock, in case initialization raced on a new file.
    if con.execute("SELECT workspace_id FROM workspace_identity WHERE singleton=1").fetchone()[0] != workspace_id:
        raise ValueError("Database belongs to another workspace")
    con.execute("""INSERT OR IGNORE INTO memory_metadata
        SELECT key, 'legacy', updated_at, updated_at, '' FROM memories""")
    con.execute("INSERT OR REPLACE INTO nexus_schema VALUES(1, ?)", (SCHEMA_VERSION,))
