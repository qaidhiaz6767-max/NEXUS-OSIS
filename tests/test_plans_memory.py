"""Atomic plans, provenance and migration failure boundaries."""
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Store, Coordinator, offline_command, validate_action

class PlanMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.sqlite3'
        self.store=Store(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_offline_plan_is_one_approval_and_atomic_success(self):
        response=Coordinator(self.store).chat('/plan\n/task add Compare models\n/remember Focus | Offline first')
        self.assertEqual(len(response['plan']['steps']),2)
        self.assertEqual(len(self.store.state()['pending']),1)
        self.assertEqual(self.store.state()['tasks'],[])
        self.store.decide(response['pending']['id'],True)
        self.assertEqual(len(self.store.state()['tasks']),1)
        self.assertEqual(self.store.state()['memories'][0]['source'],'command')
        with self.assertRaises(ValueError):
            self.store.decide(response['pending']['id'],True)

    def test_later_plan_failure_rolls_back_all_earlier_steps(self):
        item=self.store.propose('execute_plan',{'steps':[
            {'name':'remember','args':{'key':'Temporary','value':'Must roll back'}},
            {'name':'set_task_status','args':{'task_id':999,'status':'done'}}]})
        with self.assertRaisesRegex(ValueError,'does not exist'):
            self.store.decide(item['id'],True)
        self.assertEqual(self.store.state()['memories'],[])
        with self.store._conn() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM memory_metadata').fetchone()[0],0)
        self.assertEqual(self.store.state()['pending'][0]['id'],item['id'])

    def test_invalid_later_command_creates_no_partial_proposals(self):
        for command in ('/plan\n/task add First\n/task add Bad | Owner | impossible',
                        '/plan\n/task add First\n/tasks',
                        '/plan\n/task add First\n/plan\n/task add Nested'):
            result=Coordinator(self.store).chat(command)
            self.assertNotIn('pending',result)
            self.assertEqual(self.store.state()['pending'],[])

    def test_plan_limits_unknown_tools_and_nesting(self):
        for steps in ([],[{'name':'create_task','args':{'title':'x'}}]*6,
                      [{'name':'run_shell','args':{}}],
                      [{'name':'execute_plan','args':{'steps':[]}}],
                      [{'name':'create_task','arguments_json':'invalid json'}]):
            with self.assertRaises(ValueError):
                self.store.propose('execute_plan',{'steps':steps})

    def test_memory_update_and_delete_require_approval_and_preserve_provenance(self):
        item=self.store.propose('remember',{'key':'Focus','value':'Original'},source='ai')
        self.assertEqual(self.store.state()['memories'],[])
        self.store.decide(item['id'],True)
        original=self.store.state()['memories'][0]
        self.assertEqual(original['source'],'ai')
        self.assertEqual(original['approval_id'],item['id'])
        update=offline_command(self.store,'/remember focus | Revised')
        self.assertEqual(self.store.state()['memories'][0]['value'],'Original')
        self.store.decide(update['pending']['id'],True)
        updated=self.store.state()['memories'][0]
        self.assertEqual((updated['value'],updated['source']),('Revised','command'))
        self.assertEqual(updated['created_at'],original['created_at'])
        deletion=offline_command(self.store,'/forget FOCUS')
        self.store.decide(deletion['pending']['id'],False)
        self.assertEqual(len(self.store.state()['memories']),1)
        deletion=offline_command(self.store,'/forget focus')
        self.store.decide(deletion['pending']['id'],True)
        self.assertEqual(self.store.state()['memories'],[])
        with self.store._conn() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM memory_metadata').fetchone()[0],0)

    def test_model_multiple_calls_become_one_plan_with_ai_provenance(self):
        calls=[types.SimpleNamespace(type='function_call',name='remember',arguments=json.dumps({'key':k,'value':'Suggestion'})) for k in ('First','Second')]
        fake=types.SimpleNamespace(OpenAI=lambda **kw: types.SimpleNamespace(responses=types.SimpleNamespace(create=lambda **kw:types.SimpleNamespace(output=calls,output_text=''))))
        with patch.dict(sys.modules,{'openai':fake}),patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}):
            result=Coordinator(self.store,allow_ai=True).chat('Save two facts')
        self.assertEqual(len(result['plan']['steps']),2)
        self.assertEqual(self.store.state()['memories'],[])
        self.store.decide(result['pending']['id'],True)
        self.assertEqual({x['source'] for x in self.store.state()['memories']},{'ai'})

    def test_future_schema_refused_without_mutation(self):
        with self.store._conn() as con:
            con.execute('UPDATE nexus_schema SET version=999')
        before=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'newer'):
            Store(self.path)
        self.assertEqual(before,self.path.read_bytes())

    def test_failed_migration_rolls_back_new_tables(self):
        broken=Path(self.tmp.name)/'broken.sqlite3'
        with sqlite3.connect(broken) as con:
            con.execute('CREATE TABLE memories(unexpected TEXT)')
        with self.assertRaises(sqlite3.OperationalError):
            Store(broken)
        with sqlite3.connect(broken) as con:
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables,{'memories'})

    def test_exports_include_records_beyond_dashboard_limit(self):
        with self.store._conn() as con:
            con.executemany("INSERT INTO notes(title,body,created_at) VALUES(?,?,'2026-01-01')",[(f'Note {i}','Sample') for i in range(110)])
        self.assertEqual(len(self.store.state()['notes']),100)
        self.assertEqual(len(self.store.export()['notes']),110)

    def test_demo_cli_never_opens_configured_real_db(self):
        import subprocess
        target = Path(self.tmp.name)/"untouched-real.sqlite3"
        target.write_bytes(b"must remain unchanged")
        env = dict(os.environ, NEXUS_DB=str(target), OPENAI_API_KEY="fake")
        result = subprocess.run([sys.executable, "app.py", "--demo", "--cli"],
                                input="/brief\n/quit\n", text=True, capture_output=True,
                                env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEMO: invented temporary records", result.stdout)
        self.assertIn("Open tasks: 2", result.stdout)
        self.assertEqual(target.read_bytes(), b"must remain unchanged")

    def test_approval_only_operator_can_decide_without_proposal_permission(self):
        store = Store(self.path, capabilities={"read", "approve"})
        proposal = self.store.propose("remember", {"key":"Approved", "value":"Fact"})
        self.assertIn("Saved memory", store.decide(proposal["id"], True))

    def test_large_project_listing_is_bounded_and_history_is_saved(self):
        with self.store._conn() as con:
            con.executemany("INSERT INTO projects(title,goal,status,created_at) VALUES(?,?,'active','2026-01-01')",
                            [(f"Project {i}", "Long goal " * 150) for i in range(20)])
        result = Coordinator(self.store).chat('/projects')
        self.assertIn('Result truncated', result['message'])
        self.assertEqual(self.store.recent_messages()[-1]['content'], result['message'])

    def test_provider_error_text_never_enters_messages_or_audit(self):
        def fail(**kwargs):
            raise ValueError('sensitive-provider-error-detail')
        fake = types.SimpleNamespace(OpenAI=lambda **kw: types.SimpleNamespace(responses=types.SimpleNamespace(create=fail)))
        with patch.dict(sys.modules, {'openai':fake}), patch.dict(os.environ, {'OPENAI_API_KEY':'fake'}):
            result = Coordinator(self.store, allow_ai=True).chat('Help plan my day')
        self.assertIn('unavailable', result['message'])
        self.assertNotIn('sensitive-provider-error-detail', json.dumps(self.store.state()))

    def test_invalid_port_fails_before_opening_any_database(self):
        import subprocess
        target = Path(self.tmp.name)/"never-created.sqlite3"
        result = subprocess.run([sys.executable, "app.py", "--port", "80", "--db", str(target)],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Port must be', result.stderr)
        self.assertFalse(target.exists())
