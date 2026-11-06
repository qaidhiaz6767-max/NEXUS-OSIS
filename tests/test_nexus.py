"""Universal-core security and persistence tests; invented records only."""
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core import Store, Coordinator, offline_command
from nexus.workspaces import WorkspaceRegistry


class UniversalCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = WorkspaceRegistry(self.root/'legacy.sqlite3', self.root/'workspaces')

    def tearDown(self):
        self.tmp.cleanup()

    def approved(self, store, name, args):
        item = store.propose(name, args)
        store.decide(item['id'], True)
        return item

    def test_workspace_isolation_all_record_types_and_exports(self):
        a, b = self.registry.store('osis'), self.registry.store('atlas')
        self.approved(a, 'create_task', {'title': 'School stage'})
        self.approved(a, 'remember', {'key': 'Theme', 'value': 'School only'})
        self.approved(a, 'create_project', {'title': 'School project', 'goal': 'School goal'})
        a.record('user', 'School private history')
        proposal = a.propose('create_note', {'title': 'School', 'body': 'School note'})
        for key in ('tasks', 'memories', 'projects', 'messages', 'pending', 'audit'):
            self.assertEqual(b.state()[key], [], key)
        self.assertNotIn('School', json.dumps(b.export()))
        self.assertFalse(any(b.search('School').values()))
        with self.assertRaisesRegex(ValueError, 'not found'):
            b.decide(proposal['id'], True)
        self.assertEqual(a.state()['pending'][0]['id'], proposal['id'])

    def test_identity_prevents_relabeling_existing_db(self):
        store = self.registry.store('osis')
        with self.assertRaisesRegex(ValueError, 'another workspace'):
            Store(store.path, workspace_id='atlas')
        with self.assertRaisesRegex(ValueError, 'distinct'):
            WorkspaceRegistry(self.root/'workspaces/personal/nexus.sqlite3', self.root/'workspaces')

    def test_unknown_workspace_and_path_traversal_fail_closed(self):
        for value in ('../osis', '/tmp/another', '', 'OSIS', 'unknown'):
            with self.assertRaises(ValueError):
                self.registry.store(value)
        self.assertFalse((self.root/'workspaces').exists())

    def test_grants_enforced_in_store_and_coordinator(self):
        registry = WorkspaceRegistry(self.root/'legacy.sqlite3', self.root/'ws',
                                     grants={'osis': {'read'}})
        store = registry.store('osis')
        self.assertEqual(store.state()['tasks'], [])
        for operation in (lambda: store.propose('create_task', {'title':'x'}),
                          lambda: store.decide('anything', True), store.export,
                          lambda: Coordinator(store).chat('/brief')):
            with self.assertRaises(PermissionError):
                operation()
        with self.assertRaises(PermissionError):
            registry.store('atlas')
        self.assertEqual([w['id'] for w in registry.list()], ['osis'])

    def test_proposer_cannot_approve(self):
        store = Store(self.root/'p.sqlite3', capabilities={'read', 'propose'})
        item = store.propose('create_task', {'title':'Requires owner'})
        with self.assertRaises(PermissionError):
            store.decide(item['id'], True)
        self.assertEqual(store.state()['tasks'], [])

    def test_projects_and_structured_facts_persist_search_literal(self):
        store = self.registry.store('research')
        response = Coordinator(store).chat('/project add Local models | Compare latency')
        self.assertEqual(response['plan']['status'], 'awaiting_approval')
        self.assertEqual(response['plan']['workspace'], 'research')
        self.assertEqual(store.state()['projects'], [])
        store.decide(response['pending']['id'], True)
        self.approved(store, 'remember', {'key':'Preference', 'value':'100% local_model'})
        store.record('user', 'Compare latency for local models')
        reopened = self.registry.store('research')
        self.assertEqual(len(reopened.search('latency')['projects']), 1)
        self.assertTrue(any(r['content'] == 'Compare latency for local models' for r in reopened.search('latency')['history']))
        self.assertEqual(len(reopened.search('%')['facts']), 1)
        self.assertEqual(len(reopened.search('_')['facts']), 1)
        self.assertFalse(any(reopened.search("' OR 1=1 --").values()))
        self.assertIn('Local models', offline_command(reopened, '/projects')['message'])

    def test_expired_action_never_executes(self):
        store = self.registry.store('personal')
        item = store.propose('create_task', {'title':'Expired'})
        with store._conn() as con:
            con.execute('UPDATE pending_actions SET expires_at=? WHERE id=?',
                        ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),item['id']))
        self.assertIn('expired', store.decide(item['id'], True))
        self.assertEqual(store.state()['tasks'], [])
        self.assertEqual(store.state()['audit'][0]['event'], 'expired')

    def test_concurrent_approval_executes_once(self):
        store = self.registry.store('personal')
        item = store.propose('create_task', {'title':'Exactly once'})
        def decide():
            try:
                return store.decide(item['id'], True)
            except ValueError:
                return 'already decided'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: decide(), range(2)))
        self.assertEqual(results.count('already decided'), 1)
        self.assertEqual(len(store.state()['tasks']), 1)

    def test_failed_execution_rolls_back_and_revalidates(self):
        store = self.registry.store('personal')
        item = store.propose('set_task_status', {'task_id':123, 'status':'done'})
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            store.decide(item['id'], True)
        self.assertEqual(store.state()['pending'][0]['id'], item['id'])
        with store._conn() as con:
            con.execute('UPDATE pending_actions SET name=? WHERE id=?', ('run_shell',item['id']))
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            store.decide(item['id'], True)
        with self.assertRaises(ValueError):
            store.decide(item['id'], 'yes')

    def test_cloud_ai_requires_explicit_opt_in(self):
        store = self.registry.store('personal')
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake'}), patch.object(Coordinator, '_ai') as ai:
            result = Coordinator(store).chat('Plan my day')
        ai.assert_not_called()
        self.assertIn('offline', result['message'])

    def test_model_context_is_scoped_and_unknown_tool_rejected(self):
        school = self.registry.store('osis')
        self.approved(school, 'remember', {'key':'School secret', 'value':'School context only'})
        personal = self.registry.store('personal')
        self.approved(personal, 'remember', {'key':'Focus', 'value':'Personal context only'})
        captured = {}
        def create(**kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(output=[types.SimpleNamespace(
                type='function_call',name='run_shell',arguments='{"command":"anything"}')],output_text='')
        fake = types.SimpleNamespace(OpenAI=lambda **kw: types.SimpleNamespace(responses=types.SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {'openai':fake}), patch.dict(os.environ, {'OPENAI_API_KEY':'fake'}):
            result = Coordinator(personal, allow_ai=True).chat('Help plan my work')
        self.assertIn('Personal context only', captured['instructions'])
        self.assertNotIn('School context only', captured['instructions'])
        self.assertFalse(captured['store'])
        self.assertNotIn('pending', result)
        self.assertNotIn('run_shell', [t['name'] for t in captured['tools']])
        self.assertEqual(personal.state()['pending'], [])

    def test_ai_grant_blocks_provider_even_when_enabled(self):
        store = Store(self.root/'limited.sqlite3', capabilities={'read', 'propose'})
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake'}), patch.object(Coordinator, '_ai') as ai:
            Coordinator(store, allow_ai=True).chat('Hello')
        ai.assert_not_called()

    def test_legacy_schema_and_pending_proposal_are_compatible(self):
        # Build the previous schema directly, not through the new Store initializer.
        db = self.root/'v02.sqlite3'
        with sqlite3.connect(db) as con:
            con.executescript('''
                CREATE TABLE tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,
                  owner TEXT NOT NULL,due_date TEXT NOT NULL,priority TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'todo',created_at TEXT NOT NULL);
                CREATE TABLE memories(key TEXT PRIMARY KEY COLLATE NOCASE,value TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE pending_actions(id TEXT PRIMARY KEY,name TEXT NOT NULL,args_json TEXT NOT NULL,
                  description TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL);
                INSERT INTO tasks VALUES(42,'Legacy task','Owner','','high','doing','2026-01-01');
                INSERT INTO memories VALUES('Theme','Original','2026-01-01');
            ''')
            expires = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
            con.execute('INSERT INTO pending_actions VALUES(?,?,?,?,?,?,?)',
                        ('legacy-id','remember',json.dumps({'key':'New fact','value':'Retained'}),
                         'Remember new fact','pending','2026-01-01',expires))
        store = Store(db)
        self.assertEqual(store.state()['tasks'][0]['id'], 42)
        self.assertEqual(store.state()['memories'][0]['value'], 'Original')
        store.decide('legacy-id', True)
        item = self.approved(store, 'create_task', {'title':'New task'})
        self.assertEqual({r['id'] for r in store.state()['tasks']}, {42,43})
        self.assertEqual(Store(db).state()['tasks'], store.state()['tasks'])
