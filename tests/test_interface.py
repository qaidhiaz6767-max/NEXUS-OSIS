"""Additive interface contracts and honest status; no live AI or real records."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from app import handler_factory
from nexus.workspaces import WorkspaceRegistry
from nexus.validation import configured_timezone

class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.registry=WorkspaceRegistry(root/'osis.sqlite3',root/'workspaces',grants={
            'osis':{'read','propose','approve','export','ai'},'atlas':{'read'}})
        self.store=self.registry.store('osis')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.store,0,registry=self.registry,allow_ai=True))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,body=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=4)
        conn.request('POST' if body is not None else 'GET',path,body=None if body is None else json.dumps(body),headers={'Content-Type':'application/json','X-NEXUS-Local':'1'})
        response=conn.getresponse();status=response.status;raw=response.read();conn.close()
        return status,raw
    def test_configuration_does_not_claim_a_verified_ai_connection(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-never-called','NEXUS_TIMEZONE':'America/Los_Angeles'}):
            status,raw=self.request('/api/state');state=json.loads(raw)
        self.assertEqual(status,200)
        self.assertEqual(state['system']['ai'],'configured')
        self.assertIsNone(state['system']['ai_checked_at'])
        self.assertEqual(state['timezone'],'America/Los_Angeles')
        self.assertEqual(state['capabilities'],sorted(self.store.capabilities))
        self.assertNotIn('fake-never-called',raw.decode())
    def test_ai_status_is_based_on_observed_response_and_failure(self):
        import sys,types
        responses=types.SimpleNamespace(create=lambda **kw:types.SimpleNamespace(output=[],output_text='A draft response.'))
        fake=types.SimpleNamespace(OpenAI=lambda **kw:types.SimpleNamespace(responses=responses))
        with patch.dict(sys.modules,{'openai':fake}),patch.dict(os.environ,{'OPENAI_API_KEY':'fake-never-called'}):
            status,raw=self.request('/api/chat',{'message':'Help plan my day'})
            self.assertEqual(status,200);self.assertEqual(json.loads(raw)['provider_status'],'verified')
            state=json.loads(self.request('/api/state')[1]);self.assertEqual(state['system']['ai'],'verified')
            self.assertIsNotNone(state['system']['ai_checked_at'])
            self.assertEqual(json.loads(self.request('/api/state?workspace=atlas')[1])['system']['ai'],'disabled')
            def fail(**kw):raise ValueError('provider-secret-error-detail')
            responses.create=fail
            self.request('/api/chat',{'message':'Another request'})
            state=json.loads(self.request('/api/state')[1]);self.assertEqual(state['system']['ai'],'error')
            self.assertNotIn('provider-secret-error-detail',json.dumps(state))
    def test_typed_proposal_preserves_pipe_text_and_waits_for_approval(self):
        title='A pipe | and <script> is only text'
        status,raw=self.request('/api/propose',{'name':'create_task','args':{'title':title}})
        self.assertEqual(status,200);item=json.loads(raw)['pending']
        self.assertEqual(self.store.state()['tasks'],[])
        status,raw=self.request('/api/decide',{'id':item['id'],'approve':True})
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['outcome'],'approved')
        self.assertEqual(self.store.state()['tasks'][0]['title'],title)
        self.assertEqual(self.request('/api/decide',{'id':item['id'],'approve':True})[0],400)
    def test_typed_proposals_enforce_permissions_and_allowlist(self):
        self.assertEqual(self.request('/api/propose?workspace=atlas',{'name':'create_task','args':{'title':'No'}})[0],403)
        self.assertEqual(self.request('/api/propose',{'name':'run_shell','args':{}})[0],400)
        self.assertEqual(self.request('/api/propose',{'name':'create_task','args':{'title':'Bad','due_date':'2026-02-30'}})[0],400)
        self.assertEqual(self.store.state()['pending'],[])
    def test_expiry_outcome_is_reported_without_execution(self):
        item=self.store.propose('create_task',{'title':'Expired'})
        with self.store._conn() as con:con.execute('UPDATE pending_actions SET expires_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),item['id']))
        status,raw=self.request('/api/decide',{'id':item['id'],'approve':True})
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['outcome'],'expired')
        self.assertEqual(self.store.state()['tasks'],[])
    def test_search_returns_fact_provenance(self):
        item=self.store.propose('remember',{'key':'Source check','value':'Approved suggestion'},source='ai');self.store.decide(item['id'],True)
        status,raw=self.request('/api/search?q=Source')
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['facts'][0]['source'],'ai')
    def test_summary_does_not_use_dashboard_row_limits(self):
        with self.store._conn() as con:
            con.executemany("INSERT INTO tasks(title,owner,due_date,priority,status,created_at) VALUES(?,'Owner','','medium','todo','2026-01-01')",[(str(i),) for i in range(260)])
        state=self.store.state();self.assertEqual(len(state['tasks']),250)
        self.assertEqual(state['summary']['open_tasks'],260)
    def test_all_frontend_modules_are_local_and_allowlisted(self):
        for module in ('state','api','domain','ui','views','forms','voice'):
            status,raw=self.request('/'+module+'.js');self.assertEqual(status,200)
            self.assertNotIn(b'innerHTML',raw)
        self.assertEqual(self.request('/package.json')[0],404)
        self.assertEqual(self.request('/../app.py')[0],404)
    def test_invalid_timezone_falls_back_to_an_available_named_zone(self):
        with patch.dict(os.environ,{'NEXUS_TIMEZONE':'invalid/timezone'}):self.assertIn(configured_timezone(),{'Asia/Jakarta','UTC'})

class DesignContrastTests(unittest.TestCase):
    def test_text_and_primary_control_palette_meets_aa_text_contrast(self):
        def lum(color):
            vals=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            vals=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in vals]
            return sum(x*y for x,y in zip(vals,(.2126,.7152,.0722)))
        for foreground,background in [('#f2f5fa','#151e2b'),('#a0adbe','#151e2b'),('#8c9db3','#151e2b'),('#071824','#48b9f2')]:
            a,b=sorted([lum(foreground),lum(background)])
            self.assertGreaterEqual((b+.05)/(a+.05),4.5,(foreground,background))

class OfflineClockTests(unittest.TestCase):
    def test_missing_zoneinfo_data_keeps_offline_dates_functional(self):
        from zoneinfo import ZoneInfoNotFoundError
        from nexus.validation import today_local
        with patch('nexus.validation.ZoneInfo',side_effect=ZoneInfoNotFoundError):
            self.assertEqual(configured_timezone(),'UTC')
            self.assertEqual(today_local(),datetime.now(timezone.utc).date())
