"""Capture actual local UI using temporary invented demo records only.
NEXUS_SCREENSHOT_DIR=docs/screenshots python3 tests/capture_ui.py
"""
import os
import sys
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from app import handler_factory
from nexus.demo import seed_demo
from nexus.workspaces import WorkspaceRegistry

output=Path(os.environ.get('NEXUS_SCREENSHOT_DIR','work/screenshots'))
output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OPENAI_API_KEY':'','NEXUS_TIMEZONE':'Asia/Jakarta'}):
    registry=WorkspaceRegistry(Path(tmp)/'osis.sqlite3',Path(tmp)/'workspaces');seed_demo(registry)
    store=registry.store('osis')
    note=store.propose('create_note',{'title':'Planning session','body':'Agenda\n• Review the upcoming event timeline.\n• Confirm the next planning session.\n\nNotes approved to save. Decisions and follow-ups are not independently verified.'});store.decide(note['id'],True)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(store,0,registry=registry,demo=True))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page.goto(f'http://127.0.0.1:{server.server_port}');expect(page.locator('#workspace-select')).to_be_enabled()
            for view in ('overview','assistant','projects','tasks','events','notes','memory','approvals','activity','settings'):
                page.locator(f'.nav-item[data-view="{view}"]').click()
                expect(page.locator('#view-'+view)).to_be_visible()
                if view=='assistant':
                    page.locator('#chat-input').fill('/brief');page.locator('#chat-input').press('Enter');expect(page.locator('#send-button')).to_be_enabled();expect(page.locator('#chat-messages')).to_contain_text('OSIS BRIEFING')
                page.screenshot(path=str(output/(view+'-desktop.png')),full_page=True,animations='disabled')
            for view in ('overview','tasks','assistant'):
                page.locator(f'.nav-item[data-view="{view}"]').click();page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(output/(view+'-mobile.png')),full_page=True,animations='disabled')
                page.set_viewport_size({'width':1440,'height':1000})
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
print('Captured 13 UI screenshots with temporary demo records:',output)
