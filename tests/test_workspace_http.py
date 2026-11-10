"""Workspace routing is explicit per request, with no shared active-workspace state."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from app import handler_factory
from nexus.workspaces import WorkspaceRegistry

class WorkspaceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.registry=WorkspaceRegistry(root/'osis.sqlite3',root/'workspaces',grants={
            'osis':{'read','propose','approve','export'},
            'personal':{'read','propose','approve','export'},
            'atlas':{'read'},
        })
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.registry.store('osis'),0,registry=self.registry))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,path,body=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        headers={'Content-Type':'application/json','X-NEXUS-Local':'1'}
        connection.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=connection.getresponse();status=response.status;raw=response.read();connection.close()
        return status,raw

    def test_explicit_routing_approval_and_export_isolation(self):
        status,raw=self.request('/api/chat?workspace=osis',{'message':'/task add School only'})
        self.assertEqual(status,200);action=json.loads(raw)['pending']['id']
        status,_=self.request('/api/decide?workspace=personal',{'id':action,'approve':True})
        self.assertEqual(status,400)
        self.assertEqual(self.registry.store('osis').state()['tasks'],[])
        status,_=self.request('/api/decide?workspace=osis',{'id':action,'approve':True})
        self.assertEqual(status,200)
        status,raw=self.request('/api/backup?workspace=personal')
        self.assertEqual(status,200);self.assertNotIn('School only',raw.decode())
        status,raw=self.request('/api/state?workspace=personal')
        self.assertEqual(json.loads(raw)['tasks'],[])
        status,raw=self.request('/api/state')
        self.assertEqual(len(json.loads(raw)['tasks']),1)

    def test_permissions_enforced_for_every_entrypoint(self):
        for path in ('/api/backup','/api/calendar.ics'):
            self.assertEqual(self.request(path+'?workspace=atlas')[0],403)
        self.assertEqual(self.request('/api/chat?workspace=atlas',{'message':'/brief'})[0],403)
        self.assertEqual(self.request('/api/decide?workspace=atlas',{'id':'x','approve':True})[0],403)
        self.assertEqual(self.request('/api/state?workspace=atlas')[0],200)
        status,raw=self.request('/api/workspaces')
        self.assertEqual({w['id'] for w in json.loads(raw)['workspaces']},{'osis','personal','atlas'})

    def test_workspace_and_search_validation(self):
        for value,expected in (('../osis',400),('unknown',400),('',400),('research',403),('osis&workspace=personal',400)):
            self.assertEqual(self.request('/api/state?workspace='+value)[0],expected)
        self.assertEqual(self.request('/api/search?workspace=atlas&q=missing')[0],200)
        self.assertEqual(self.request('/api/search?q=')[0],400)
        self.assertEqual(self.request('/api/search?q='+'x'*201)[0],400)

    def test_dashboard_exposes_new_panels_and_scopes_requests(self):
        _,body=self.request('/')
        for marker in (b'workspace-select',b'view-projects',b'memory-search-form',b'plan-report'):
            self.assertIn(marker,body)
        _,body=self.request('/api.js')
        self.assertIn(b'encodeURIComponent(workspace)',body)
        self.assertNotIn(b'innerHTML',body)
