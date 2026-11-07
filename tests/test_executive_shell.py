"""Security and first-paint integration checks for the executive shell."""
import os,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import urlopen
from app import handler_factory
from core import Store

class ExecutiveShellTests(unittest.TestCase):
 def test_configured_timezone_and_canonical_local_assets_are_served_with_strict_csp(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'NEXUS_TIMEZONE':'America/Los_Angeles'}):
   store=Store(Path(tmp)/'fixture.sqlite3');server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(store,0,demo=True));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    base=f'http://127.0.0.1:{server.server_port}'
    with urlopen(base) as response:
     markup=response.read().decode();policy=response.headers['Content-Security-Policy']
    self.assertIn('data-timezone="America/Los_Angeles"',markup)
    self.assertNotIn('__NEXUS_TIMEZONE__',markup)
    self.assertIn('<script type="module" src="/app.js"></script>',markup)
    self.assertNotIn('<script type="module">',markup)
    self.assertNotIn('unsafe-inline',policy);self.assertNotIn('unsafe-eval',policy)
    self.assertIn("connect-src 'self'",policy)
    for name in ['app.js','style.css','executive.js']:
     with urlopen(base+'/'+name) as response:self.assertGreater(len(response.read()),100)
    self.assertEqual(store.state()['tasks'],[])
   finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
