"""Real encrypted SQLite backup/recovery drills, synthetic data only."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from core import Store
from nexus.backup import create_backup, restore_backup, opened_backup, database_lease


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "live.sqlite3"
        self.store = Store(self.path)
        item = self.store.propose(
            "remember", {"key": "Synthetic fact", "value": "Private sample only"}
        )
        self.store.decide(item["id"], True)
        self.archive = self.root / "backup.nxbak"
        self.password = "synthetic-test-passphrase"

    def tearDown(self):
        self.temp.cleanup()

    def backup(self):
        return create_backup(self.path, self.archive, "osis", self.password)

    def test_authenticated_backup_round_trip_and_permissions(self):
        result = self.backup()
        self.assertTrue(result["encrypted"])
        self.assertNotIn(b"Private sample only", self.archive.read_bytes())
        self.assertEqual(os.stat(self.archive).st_mode & 0o777, 0o600)
        with opened_backup(self.archive, "osis", self.password) as (_, preview):
            self.assertEqual(preview["counts"]["memories"], 1)
        restored = self.root / "recovered.sqlite3"
        preview = restore_backup(self.archive, restored, "osis", self.password)
        self.assertFalse(preview["restored"])
        self.assertFalse(restored.exists())
        self.assertTrue(
            restore_backup(self.archive, restored, "osis", self.password, confirm=True)[
                "restored"
            ]
        )
        self.assertEqual(
            Store(restored).state()["memories"][0]["value"], "Private sample only"
        )

    def test_wrong_password_tampering_and_workspace_fail_without_target_change(self):
        self.backup()
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            restore_backup(
                self.archive,
                self.path,
                "osis",
                "wrong-password-long-enough",
                confirm=True,
            )
        with self.assertRaises(ValueError):
            restore_backup(
                self.archive, self.path, "atlas", self.password, confirm=True
            )
        doc = json.loads(self.archive.read_bytes())
        data = doc["ciphertext"]
        doc["ciphertext"] = ("A" if data[0] != "A" else "B") + data[1:]
        self.archive.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            restore_backup(self.archive, self.path, "osis", self.password, confirm=True)
        self.assertEqual(before, self.path.read_bytes())

    def test_existing_target_has_encrypted_rollback_and_old_approvals_are_invalidated(
        self,
    ):
        pending = self.store.propose(
            "create_task", {"title": "Must not replay after restore"}
        )
        self.backup()
        later = self.store.propose("create_task", {"title": "Later task"})
        self.store.decide(later["id"], True)
        result = restore_backup(
            self.archive, self.path, "osis", self.password, confirm=True
        )
        self.assertTrue(Path(result["rollback_backup"]).is_file())
        recovered = Store(self.path)
        self.assertEqual(recovered.state()["tasks"], [])
        with self.assertRaises(ValueError):
            recovered.decide(pending["id"], True)
        with opened_backup(Path(result["rollback_backup"]), "osis", self.password) as (
            _,
            preview,
        ):
            self.assertEqual(preview["counts"]["tasks"], 1)

    def test_running_application_lease_blocks_restore(self):
        self.backup()
        before = self.path.read_bytes()
        with database_lease(self.path):
            with self.assertRaisesRegex(ValueError, "in use"):
                restore_backup(
                    self.archive, self.path, "osis", self.password, confirm=True
                )
        self.assertEqual(before, self.path.read_bytes())

    def test_no_overwrite_symlink_or_repository_backup_destination(self):
        self.backup()
        with self.assertRaises(ValueError):
            create_backup(self.path, self.archive, "osis", self.password)
        link = self.root / "link.sqlite3"
        link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            restore_backup(self.archive, link, "osis", self.password, confirm=True)
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main")
        with self.assertRaisesRegex(ValueError, "outside"):
            create_backup(self.path, repo / "backup.nxbak", "osis", self.password)

    def test_malformed_or_future_backup_cannot_be_restored(self):
        from nexus.backup import seal

        self.archive.write_bytes(seal(b"not SQLite", "osis", self.password))
        with self.assertRaises(ValueError):
            restore_backup(self.archive, self.path, "osis", self.password, confirm=True)

    def test_registry_runtime_lock_is_released_on_exit(self):
        from nexus.workspaces import WorkspaceRegistry

        with WorkspaceRegistry(
            self.path, self.root / "workspaces", runtime_locks=True
        ) as registry:
            registry.store("osis")
            with self.assertRaises(ValueError):
                with database_lease(self.path, exclusive=True):
                    pass
        with database_lease(self.path, exclusive=True):
            pass

    def test_restore_cancels_command_lifecycle_and_keeps_history(self):
        from core import Coordinator

        request = Coordinator(self.store).chat("/task add Snapshot pending task")
        self.backup()
        result = restore_backup(
            self.archive, self.path, "osis", self.password, confirm=True
        )
        recovered = Store(self.path)
        command = recovered.command(request["command_id"])
        self.assertEqual(command["status"], "cancelled")
        self.assertEqual(command["history"][-1]["to_status"], "cancelled")
        self.assertEqual(
            recovered.plans(request["pending"]["id"])[0]["status"], "cancelled"
        )
        with self.assertRaises(ValueError):
            recovered.decide(request["pending"]["id"], True)

    def test_restore_refuses_a_different_target_workspace(self):
        self.backup()
        target = self.root / "atlas.sqlite3"
        Store(target, workspace_id="atlas")
        before = target.read_bytes()
        with self.assertRaises(ValueError):
            restore_backup(self.archive, target, "osis", self.password, confirm=True)
        self.assertEqual(before, target.read_bytes())

    def test_sqlite_backup_excludes_uncommitted_wal_changes(self):
        import sqlite3

        con = sqlite3.connect(self.path)
        con.execute("PRAGMA journal_mode=WAL")
        try:
            con.execute(
                "INSERT INTO tasks(title,owner,due_date,priority,status,created_at) VALUES('Uncommitted','Owner','','low','todo','2026-01-01')"
            )
            self.backup()
            with opened_backup(self.archive, "osis", self.password) as (_, preview):
                self.assertEqual(preview["counts"]["tasks"], 0)
        finally:
            con.rollback()
            con.close()

    def test_restore_confirmation_is_strictly_boolean(self):
        self.backup()
        with self.assertRaises(ValueError):
            restore_backup(
                self.archive, self.path, "osis", self.password, confirm="yes"
            )
