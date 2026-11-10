"""Private authenticated SQLite snapshots. Administrative CLI, never an AI tool.

Usage: python3 -m nexus.backup {create,inspect,restore} --help
Stop NEXUS before restoring. Passphrases are read interactively, never in argv.
"""

from __future__ import annotations
import argparse
import base64
import getpass
import json
import os
import secrets
import sqlite3
import tempfile
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

MAX_DATABASE = 32 * 1024 * 1024
FORMAT = "nexus-encrypted-sqlite-v1"


@contextmanager
def database_lease(path: Path, *, exclusive=False):
    """POSIX advisory lock shared by the running app and restoration CLI."""
    import fcntl

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(path) + ".nexus-lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(
                fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
            )
        except BlockingIOError as exc:
            raise ValueError(
                "Database is in use. Stop NEXUS before restoring."
            ) from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _crypto(passphrase: str, salt: bytes):
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Use a passphrase of at least 12 characters.")
    try:
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ValueError(
            "Install requirements-security.txt to use encrypted backups."
        ) from exc
    return AESGCM(
        Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(
            passphrase.encode("utf-8")
        )
    )


def _readonly(path):
    return sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=3
    )


def inspect_database(path: Path, workspace: str) -> dict:
    from .migrations import SCHEMA_VERSION

    if not path.is_file() or path.stat().st_size > MAX_DATABASE:
        raise ValueError("Missing or oversized SQLite snapshot.")
    try:
        with closing(_readonly(path)) as con:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Snapshot integrity check failed.")
            identity = con.execute(
                "SELECT workspace_id FROM workspace_identity WHERE singleton=1"
            ).fetchone()
            if not identity or identity[0] != workspace:
                raise ValueError("Snapshot belongs to another workspace.")
            version = con.execute(
                "SELECT version FROM nexus_schema WHERE singleton=1"
            ).fetchone()
            if (
                not version
                or not isinstance(version[0], int)
                or not 1 <= version[0] <= SCHEMA_VERSION
            ):
                raise ValueError("Snapshot schema is unsupported.")
            if con.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Snapshot relationships are invalid.")
            counts = {
                table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in (
                    "tasks",
                    "projects",
                    "events",
                    "notes",
                    "memories",
                    "messages",
                    "pending_actions",
                )
            }
            return {
                "workspace": workspace,
                "schema_version": version[0],
                "counts": counts,
            }
    except sqlite3.Error as exc:
        raise ValueError("Invalid or incompatible SQLite snapshot.") from exc


def snapshot_bytes(path: Path, workspace: str) -> bytes:
    inspect_database(path, workspace)
    with tempfile.TemporaryDirectory(prefix="nexus-snapshot-") as directory:
        target = Path(directory) / "snapshot.sqlite3"
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with closing(_readonly(path)) as source, closing(
            sqlite3.connect(target)
        ) as destination:
            source.backup(destination)
        inspect_database(target, workspace)
        return target.read_bytes()


def seal(database: bytes, workspace: str, passphrase: str) -> bytes:
    if len(database) > MAX_DATABASE:
        raise ValueError("Snapshot exceeds the 32 MiB limit.")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    metadata = {
        "format": FORMAT,
        "workspace": workspace,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kdf": "scrypt-n32768-r8-p1",
        "cipher": "AES-256-GCM",
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
    }
    aad = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    encrypted = _crypto(passphrase, salt).encrypt(nonce, database, aad)
    return json.dumps(
        {"metadata": metadata, "ciphertext": base64.b64encode(encrypted).decode()},
        separators=(",", ":"),
    ).encode()


def unseal(archive: bytes, workspace: str, passphrase: str) -> bytes:
    if len(archive) > MAX_DATABASE * 2:
        raise ValueError("Backup archive is too large.")
    try:
        document = json.loads(archive)
        if set(document) != {"metadata", "ciphertext"}:
            raise ValueError
        metadata = document["metadata"]
        if set(metadata) != {
            "format",
            "workspace",
            "created_at",
            "kdf",
            "cipher",
            "salt",
            "nonce",
        }:
            raise ValueError
        if metadata["format"] != FORMAT or metadata["workspace"] != workspace:
            raise ValueError
        if (
            metadata["kdf"] != "scrypt-n32768-r8-p1"
            or metadata["cipher"] != "AES-256-GCM"
        ):
            raise ValueError
        salt = base64.b64decode(metadata["salt"], validate=True)
        nonce = base64.b64decode(metadata["nonce"], validate=True)
        if len(salt) != 16 or len(nonce) != 12:
            raise ValueError
        ciphertext = base64.b64decode(document["ciphertext"], validate=True)
        aad = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid backup metadata or workspace mismatch.") from exc
    try:
        result = _crypto(passphrase, salt).decrypt(nonce, ciphertext, aad)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Backup authentication failed. Check the passphrase and file integrity."
        ) from exc
    if len(result) > MAX_DATABASE:
        raise ValueError("Decrypted snapshot is oversized.")
    return result


def write_private(path: Path, content: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            "Backup destination already exists; choose a new filename."
        ) from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def create_backup(
    database: Path, output: Path, workspace: str, passphrase: str
) -> dict:
    database, output = Path(database), Path(output)
    if database.resolve() == output.resolve():
        raise ValueError("Backup destination must differ from the database.")
    if any(
        (parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
        for parent in output.resolve().parents
    ):
        raise ValueError("Keep private backups outside the Git repository.")
    content = snapshot_bytes(database, workspace)
    write_private(output, seal(content, workspace, passphrase))
    return {
        "workspace": workspace,
        "file": str(output),
        "bytes": output.stat().st_size,
        "encrypted": True,
    }


@contextmanager
def opened_backup(archive: Path, workspace: str, passphrase: str):
    archive = Path(archive)
    if not archive.is_file() or archive.stat().st_size > MAX_DATABASE * 2:
        raise ValueError("Missing or oversized backup archive.")
    data = unseal(archive.read_bytes(), workspace, passphrase)
    with tempfile.TemporaryDirectory(prefix="nexus-restore-preview-") as directory:
        path = Path(directory) / "snapshot.sqlite3"
        write_private(path, data)
        preview = inspect_database(path, workspace)
        yield path, preview


def restore_backup(
    archive: Path,
    target: Path,
    workspace: str,
    passphrase: str,
    *,
    confirm: bool = False,
) -> dict:
    """Verify first; explicit confirmation and an exclusive application lock required."""
    if not isinstance(confirm, bool):
        raise ValueError("Restore confirmation must be true or false.")
    target = Path(target)
    if target.is_symlink():
        raise ValueError("Refusing to restore through a symbolic link.")
    if target.resolve() == Path(archive).resolve():
        raise ValueError("Source backup and target must differ.")
    with opened_backup(archive, workspace, passphrase) as (snapshot, preview):
        if not confirm:
            return {**preview, "restored": False, "requires_confirmation": True}
        with database_lease(target, exclusive=True):
            rollback = None
            if target.exists():
                inspect_database(target, workspace)
                rollback = Path(archive).resolve().parent / (
                    "nexus-recovery-"
                    + workspace
                    + "-"
                    + secrets.token_hex(6)
                    + ".nxbak"
                )
                create_backup(target, rollback, workspace, passphrase)
            # Stage on the target filesystem for an atomic replacement.
            staging = target.parent / (
                ".nexus-restore-" + secrets.token_hex(8) + ".sqlite3"
            )
            try:
                write_private(staging, snapshot.read_bytes())
                from .storage import Store

                restored = Store(staging, workspace_id=workspace)
                with restored._conn() as con:
                    con.execute(
                        "UPDATE pending_actions SET status='invalidated' WHERE status='pending'"
                    )
                    con.execute(
                        "UPDATE plan_records SET status='cancelled',error_code='snapshot_restored' WHERE status IN ('awaiting_approval','executing','failed')"
                    )
                    from .planning import transition

                    interrupted = con.execute(
                        "SELECT id FROM command_runs WHERE status IN ('received','planning','awaiting_approval','executing') OR (status='failed' AND action_id IN (SELECT id FROM pending_actions WHERE status='invalidated'))"
                    ).fetchall()
                    for row in interrupted:
                        transition(
                            con,
                            row["id"],
                            "cancelled",
                            result={"verified": False, "reason": "snapshot_restored"},
                            error="snapshot_restored",
                        )
                    con.execute(
                        "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                        (
                            datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "restored",
                            "Snapshot restored; pending approvals invalidated.",
                        ),
                    )
                inspect_database(staging, workspace)
                with staging.open("rb") as stream:
                    os.fsync(stream.fileno())
                os.replace(staging, target)
                directory_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                staging.unlink(missing_ok=True)
            return {
                **preview,
                "restored": True,
                "rollback_backup": str(rollback) if rollback else None,
                "approvals_invalidated": True,
            }


def main():
    parser = argparse.ArgumentParser(
        description="Private encrypted NEXUS SQLite backup and controlled recovery"
    )
    parser.add_argument("operation", choices=["create", "inspect", "restore"])
    parser.add_argument(
        "--workspace",
        required=True,
        choices=[
            "osis",
            "personal",
            "academic",
            "research",
            "coding",
            "finance",
            "atlas",
        ],
    )
    parser.add_argument("--db", type=Path)
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if args.operation in {"create", "restore"} and args.db is None:
        parser.error("--db is required for create/restore")
    password = getpass.getpass("Backup passphrase (12+ characters): ")
    try:
        if args.operation == "create":
            if password != getpass.getpass("Confirm passphrase: "):
                raise ValueError("Passphrases did not match.")
            result = create_backup(args.db, args.file, args.workspace, password)
        elif args.operation == "inspect":
            with opened_backup(args.file, args.workspace, password) as (_, result):
                print(json.dumps(result, indent=2))
                return
        else:
            preview = restore_backup(args.file, args.db, args.workspace, password)
            print(json.dumps(preview, indent=2))
            print(
                "Stop NEXUS first. Existing data will be replaced; an encrypted rollback copy will be kept."
            )
            if (
                input(f"Type RESTORE {args.workspace} to continue: ")
                != f"RESTORE {args.workspace}"
            ):
                print("Restore cancelled.")
                return
            result = restore_backup(
                args.file, args.db, args.workspace, password, confirm=True
            )
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
