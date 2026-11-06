import json
import tempfile
import unittest
from pathlib import Path

from core import Coordinator, Store, offline_command, validate_action
from app import make_ics, ics_escape


class NexusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "data.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_task_requires_approval(self):
        result = offline_command(self.store, "/task add Finalize proposal | OSIS Deputy | 2026-11-20 | high")
        self.assertEqual(self.store.state()["tasks"], [])
        self.store.decide(result["pending"]["id"], True)
        task = self.store.state()["tasks"][0]
        self.assertEqual((task["title"], task["owner"], task["priority"]), ("Finalize proposal", "OSIS Deputy", "high"))

    def test_reject_leaves_data_unchanged(self):
        item = self.store.propose("remember", {"key": "Meeting day", "value": "Friday"})
        result = self.store.decide(item["id"], False)
        self.assertIn("cancelled", result)
        self.assertEqual(self.store.state()["memories"], [])

    def test_approval_cannot_replay(self):
        item = self.store.propose("create_task", {"title": "Check stage", "owner": "Unassigned", "due_date": "", "priority": "medium"})
        self.store.decide(item["id"], True)
        with self.assertRaisesRegex(ValueError, "already decided"):
            self.store.decide(item["id"], True)
        self.assertEqual(len(self.store.state()["tasks"]), 1)

    def test_invalid_dates_and_priorities(self):
        with self.assertRaisesRegex(ValueError, "real date"):
            validate_action("create_event", {"title": "Assembly", "day": "2026-02-30"})
        with self.assertRaisesRegex(ValueError, "Priority"):
            validate_action("create_task", {"title": "Task", "priority": "urgent!!"})
        with self.assertRaisesRegex(ValueError, "Time"):
            validate_action("create_event", {"title": "Meeting", "day": "2026-11-25", "time": "26:00"})

    def test_update_and_delegate(self):
        task = self.store.propose("create_task", {"title": "Recruit", "owner": "Unassigned"})
        self.store.decide(task["id"], True)
        change = self.store.propose("assign_task", {"task_id": 1, "owner": "OSIS Deputy"})
        self.store.decide(change["id"], True)
        done = offline_command(self.store, "/task done 1")
        self.store.decide(done["pending"]["id"], True)
        t = self.store.state()["tasks"][0]
        self.assertEqual((t["owner"], t["status"]), ("OSIS Deputy", "done"))

    def test_unrecognized_operation_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.store.propose("run_shell", {"command": "echo hi"})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.store.propose("send_message", {"message": "Hello"})

    def test_sql_injection_text_is_just_text(self):
        content = "Hi'); DROP TABLE tasks; --"
        item = self.store.propose("create_note", {"title": "Security review", "body": content})
        self.store.decide(item["id"], True)
        self.assertEqual(self.store.state()["notes"][0]["body"], content)
        self.assertEqual(self.store.state()["tasks"], [])

    def test_brief_and_export(self):
        self.assertIn("OSIS BRIEFING", self.store.brief())
        item = self.store.propose("create_event", {"title": "Meeting", "day": "2027-03-10", "time": "15:30", "location": "Room A", "details": "Review"})
        self.store.decide(item["id"], True)
        raw = self.store.export()
        self.assertEqual(raw["format"], "nexus-osis-v1")
        self.assertNotIn("messages", raw)
        self.assertNotIn("pending", raw)
        self.assertIn(b"BEGIN:VCALENDAR", make_ics(self.store.state()["events"]))

    def test_memory_persists_after_reopen(self):
        item = self.store.propose("remember", {"key": "Theme", "value": "Leadership"})
        self.store.decide(item["id"], True)
        reopened = Store(self.store.path)
        self.assertEqual(reopened.state()["memories"][0]["value"], "Leadership")

    def test_ai_offline_returns_honest_message(self):
        # This test does not require network credentials and is only about the deterministic command parser.
        import unittest.mock as mock
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            result = Coordinator(self.store).chat("How can we improve our next OSIS meeting?")
        self.assertIn("offline", result["message"].lower())

    def test_model_tool_calls_are_proposals_only(self):
        import os
        import sys
        import types
        from unittest.mock import patch

        class FakeResponse:
            output = [types.SimpleNamespace(type="function_call", name="create_task",
                        arguments=json.dumps({"title":"Plan assembly", "owner":"OSIS Deputy", "due_date":"2026-11-30", "priority":"high"}))]
            output_text = ""

        class FakeClient:
            def __init__(self, **kwargs):
                pass
            responses = types.SimpleNamespace(create=lambda **kwargs: FakeResponse())

        fake_openai = types.SimpleNamespace(OpenAI=FakeClient)
        with patch.dict(sys.modules, {"openai": fake_openai}), patch.dict(os.environ, {"OPENAI_API_KEY": "test-token"}):
            result = Coordinator(self.store).chat("Give OSIS Deputy an assembly task")
        self.assertIn("pending", result)
        self.assertEqual(self.store.state()["tasks"], [])
        self.store.decide(result["pending"]["id"], True)
        self.assertEqual(self.store.state()["tasks"][0]["title"], "Plan assembly")

    def test_event_no_auto_send(self):
        result = offline_command(self.store, "/event add Meeting | 2026-11-21 | 14:00 | Library | Budget")
        self.assertEqual(self.store.state()["events"], [])
        self.store.decide(result["pending"]["id"], True)
        self.assertEqual(len(self.store.state()["events"]), 1)


if __name__ == "__main__":
    unittest.main()
