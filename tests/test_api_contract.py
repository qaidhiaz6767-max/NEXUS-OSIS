"""Real HTTP examples for Claude's additive API contract."""

import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path
from app import handler_factory
from nexus.workspaces import WorkspaceRegistry


class ApiContractTests(unittest.TestCase):
    def test_unexpected_read_failure_returns_sanitized_json(self):
        with patch(
            "app.get_data", side_effect=RuntimeError("synthetic-private-detail")
        ):
            with self.assertLogs(level="ERROR") as logs:
                status, result = self.request("/api/tasks")
        self.assertEqual(status, 500)
        self.assertNotIn("synthetic-private-detail", json.dumps(result))
        self.assertNotIn("synthetic-private-detail", " ".join(logs.output))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = WorkspaceRegistry(
            root / "osis.sqlite3",
            root / "workspaces",
            grants={
                "osis": {"read", "propose", "approve", "export", "ai"},
                "personal": {"read"},
                "atlas": set(),
            },
        )
        self.store = self.registry.store("osis")
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(self.store, 0, registry=self.registry)
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        conn.request(
            "POST" if body is not None else "GET",
            path,
            body=None if body is None else json.dumps(body),
            headers={"Content-Type": "application/json", "X-NEXUS-Local": "1"},
        )
        response = conn.getresponse()
        status = response.status
        raw = response.read()
        conn.close()
        return status, json.loads(raw)

    def create(self, name, args):
        status, result = self.request("/api/propose", {"name": name, "args": args})
        self.assertEqual(status, 200, result)
        self.assertEqual(
            self.request(
                "/api/decide", {"id": result["pending"]["id"], "approve": True}
            )[0],
            200,
        )
        return result

    def test_old_chat_fields_and_new_command_lifecycle_coexist(self):
        status, result = self.request("/api/chat", {"message": "/task add HTTP task"})
        self.assertEqual(status, 200)
        for key in (
            "message",
            "pending",
            "plan",
            "provider_status",
            "command_id",
            "lifecycle",
            "kind",
            "authority_level",
        ):
            self.assertIn(key, result)
        command_id = result["command_id"]
        plan_id = result["pending"]["id"]
        self.assertEqual(
            self.request("/api/commands/" + command_id)[1]["status"],
            "awaiting_approval",
        )
        self.assertEqual(
            self.request("/api/plans/" + plan_id)[1]["approval_status"], "pending"
        )
        self.request("/api/decide", {"id": plan_id, "approve": True})
        self.assertEqual(
            self.request("/api/commands/" + command_id)[1]["status"], "completed"
        )
        self.assertTrue(self.request("/api/plans/" + plan_id)[1]["result"]["verified"])

    def test_project_milestone_and_task_relationships_are_actual(self):
        self.create(
            "create_project",
            {"title": "HTTP project", "goal": "Sample goal", "owner": "Role"},
        )
        self.create("create_milestone", {"project_id": 1, "title": "Sample phase"})
        self.create(
            "create_task",
            {
                "title": "Linked task",
                "project_id": 1,
                "milestone_id": 1,
                "description": "Explicit context",
            },
        )
        status, project = self.request("/api/projects/1")
        self.assertEqual(status, 200)
        self.assertEqual(project["tasks"][0]["description"], "Explicit context")
        self.assertEqual(project["milestones"][0]["title"], "Sample phase")
        task = self.request("/api/tasks/1")[1]
        self.assertEqual(task["notification"], "not_sent")
        self.assertEqual(task["acknowledgment"], "not_tracked")

    def test_meeting_and_decision_contract_preserves_draft_status(self):
        self.create(
            "create_meeting",
            {
                "title": "HTTP meeting",
                "draft_minutes": "Unconfirmed draft",
                "participants": ["Role"],
            },
        )
        self.create(
            "record_decision",
            {"meeting_id": 1, "title": "Option", "body": "Draft choice"},
        )
        meeting = self.request("/api/meetings/1")[1]
        self.assertEqual(meeting["minutes_status"], "draft")
        self.assertFalse(meeting["attendance_verified"])
        self.assertEqual(meeting["decisions"][0]["status"], "draft")
        self.assertEqual(self.request("/api/decisions")[1]["decisions"], [])
        self.create("approve_decision", {"decision_id": 1})
        self.assertEqual(len(self.request("/api/decisions")[1]["decisions"]), 1)

    def test_memory_and_context_are_scoped_and_confirmed(self):
        self.create(
            "remember",
            {"key": "Preference", "value": "Keep it local", "category": "preference"},
        )
        status, memory = self.request("/api/memory?category=preference")
        self.assertEqual(status, 200)
        self.assertEqual(memory["facts"][0]["confirmation"], "confirmed")
        self.assertEqual(self.request("/api/memory?workspace=personal")[1]["facts"], [])
        self.assertEqual(
            self.request("/api/context?q=Preference&workspace=personal")[1]["facts"], []
        )
        self.assertEqual(
            self.request("/api/context?q=Preference")[1]["facts"][0]["value"],
            "Keep it local",
        )

    def test_scoped_access_unknown_records_and_validation(self):
        self.assertEqual(self.request("/api/projects?workspace=atlas")[0], 403)
        self.assertEqual(self.request("/api/projects/999")[0], 404)
        self.assertEqual(self.request("/api/commands/not-found")[0], 404)
        self.assertEqual(self.request("/api/plans/not-found")[0], 404)
        self.assertEqual(self.request("/api/tasks/not-a-number")[0], 400)
        self.assertEqual(self.request("/api/decisions?status=fabricated")[0], 400)
        self.assertEqual(self.request("/api/briefing?period=forever")[0], 400)
        self.assertEqual(self.request("/api/memory?category=credential")[0], 400)

    def test_background_specialists_and_accounts_are_not_falsely_enabled(self):
        status, data = self.request("/api/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual(data["authority"]["supported"], [0, 1, 2, 3])
        self.assertFalse(data["authority"]["scheduled_enabled"])
        self.assertFalse(data["authority"]["specialist_agents_enabled"])
        self.assertFalse(data["external_accounts_connected"])
        self.assertFalse(data["voice"]["backend_audio_ingest"])

    def test_commands_alias_and_grounded_period_sources(self):
        self.create("create_task", {"title": "Sample work"})
        status, data = self.request(
            "/api/commands", {"message": "NEXUS, status report"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["kind"], "verified_information")
        report = self.request("/api/briefing?period=week")[1]
        self.assertEqual(report["counts"]["open_tasks"], 1)
        self.assertEqual(report["sources"]["tasks"], [1])
        self.assertIn("completion_period", report)

    def test_cross_workspace_plan_id_cannot_read_or_execute(self):
        result = self.request(
            "/api/propose", {"name": "create_task", "args": {"title": "School only"}}
        )[1]
        plan_id = result["pending"]["id"]
        self.assertEqual(
            self.request("/api/plans/" + plan_id + "?workspace=personal")[0], 404
        )
        self.assertEqual(
            self.request(
                "/api/decide?workspace=personal", {"id": plan_id, "approve": True}
            )[0],
            403,
        )
        self.assertEqual(self.store.state()["tasks"], [])

    def test_container_values_in_scalar_fields_are_validation_errors(self):
        for name, args in (
            (
                "create_project",
                {"title": "Sample", "goal": "Sample goal", "status": []},
            ),
            ("remember", {"key": "Sample", "value": "Value", "category": {}}),
            (
                "create_project_plan",
                {
                    "title": "Sample",
                    "goal": "Sample goal",
                    "tasks": [{"title": "Sample", "priority": []}],
                },
            ),
        ):
            status, _ = self.request("/api/propose", {"name": name, "args": args})
            self.assertEqual(status, 400)
        self.assertEqual(self.store.state()["pending"], [])
