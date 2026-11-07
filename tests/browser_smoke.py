"""Optional UI check: requires Playwright and a local Chromium executable."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
from pathlib import Path
import tempfile
import threading
from datetime import date,timedelta
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from app import handler_factory
from nexus.workspaces import WorkspaceRegistry

with tempfile.TemporaryDirectory() as tmp:
    registry=WorkspaceRegistry(Path(tmp)/'osis.sqlite3',Path(tmp)/'workspaces')
    store=registry.store('osis')
    due=(date.today()+timedelta(days=3)).isoformat()
    for name,args in [('create_task',{'title':'Prepare the leadership briefing','owner':'OSIS team','due_date':due,'priority':'high'}),('create_task',{'title':'Review the event timeline','owner':'Planning team','due_date':due}),('create_project',{'title':'Leadership workspace','goal':'Clear plans, shared responsibilities and decisions ready for review.'}),('create_event',{'title':'Weekly planning session','day':due,'time':'14:00','location':'Meeting room','details':'Invented sample event for the preview.'}),('remember',{'key':'Meeting rhythm','value':'Weekly planning session'})]:
        item=store.propose(name,args);store.decide(item['id'],True)
    store.propose('create_task',{'title':'Draft the weekly agenda','owner':'Planning team','due_date':due})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(store,0,registry=registry))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
            errors=[];page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_selector('#workspace-select:not([disabled])')
            import os
            if os.environ.get('NEXUS_SCREENSHOT'):
                page.screenshot(path=os.environ['NEXUS_SCREENSHOT'],full_page=True)
            assert page.locator('#metric-open').inner_text()=='2'
            page.locator('#workspace-select').select_option('personal')
            page.wait_for_function("() => document.getElementById('workspace-label').textContent.startsWith('PERSONAL')")
            assert page.locator('#metric-open').inner_text()=='0'
            page.get_by_role('button',name='Projects',exact=True).click()
            page.get_by_role('button',name='New project',exact=False).first.click()
            page.locator('#field-title').fill('Personal research')
            page.locator('#field-goal').fill('Evaluate local AI tools')
            page.locator('#create-form button[type=submit]').click()
            page.wait_for_selector('#view-approvals .approval-yes')
            assert registry.store('personal').state()['projects']==[]
            page.locator('#view-approvals .approval-yes').click()
            page.wait_for_function("() => document.getElementById('nav-pending-count').textContent==='0'")
            assert registry.store('personal').state()['projects'][0]['title']=='Personal research'
            assert len(store.state()['projects'])==1
            page.get_by_role('button',name='Projects',exact=True).click()
            assert 'Personal research' in page.locator('#project-list').inner_text()
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            browser.close()
            print('Browser: dashboard, isolated workspace switch, project proposal/approval, and mobile width passed.')
    finally:
        server.shutdown();server.server_close();thread.join()
