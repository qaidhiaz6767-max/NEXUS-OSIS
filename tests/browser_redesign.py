"""Mission 002 end-to-end journeys. All data is invented and temporary.

Optional: NEXUS_SCREENSHOT_DIR=docs/screenshots python3 tests/browser_redesign.py
Requires Playwright and local Chromium. No provider calls or live microphone use.
"""
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from app import handler_factory
from nexus.demo import seed_demo
from nexus.validation import today_local
from nexus.workspaces import WorkspaceRegistry

shots=Path(os.environ['NEXUS_SCREENSHOT_DIR']) if os.environ.get('NEXUS_SCREENSHOT_DIR') else None
if shots:shots.mkdir(parents=True,exist_ok=True)

def snapshot(page,name):
    if shots:page.screenshot(path=str(shots/(name+'.png')),full_page=True,animations='disabled')

def nav(page,view):
    if page.viewport_size['width']<=760 and not page.locator('#sidebar').evaluate('(el)=>el.classList.contains("open")'):
        page.locator('#open-nav').click()
    page.locator(f'.nav-item[data-view="{view}"]').click()
    expect(page.locator('#view-'+view)).to_be_visible()

def approve(page):
    page.locator('#view-approvals .approval-yes').last.click()
    expect(page.locator('#view-approvals .approval-yes')).to_have_count(0)

with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'NEXUS_TIMEZONE':'Asia/Jakarta','OPENAI_API_KEY':''}):
    root=Path(tmp)
    grants={w:{'read','propose','approve','export','ai'} for w in ('osis','personal','academic','research','coding','finance')}
    grants['atlas']={'read'}
    registry=WorkspaceRegistry(root/'osis.sqlite3',root/'workspaces',grants=grants)
    seed_demo(registry);store=registry.store('osis')
    # Clear the demo proposal to make each outcome in the test unambiguous.
    for pending in store.state()['pending']:store.decide(pending['id'],False)
    overdue=(today_local()-timedelta(days=1)).isoformat()
    for name,args in [
        ('create_task',{'title':'Overdue stage review','owner':'Stage team','due_date':overdue,'priority':'low'}),
        ('create_event',{'title':'Planning placeholder','day':(today_local()+timedelta(days=5)).isoformat()}),
        ('create_note',{'title':'Planning session notes','body':'Drafted by the operator; approved to save. This is not a verified decision register.'}),
    ]:
        item=store.propose(name,args);store.decide(item['id'],True)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(store,0,registry=registry,demo=True))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce',permissions=['clipboard-read','clipboard-write'])
            page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            external=[]
            page.on('request',lambda req:external.append(req.url) if not req.url.startswith(f'http://127.0.0.1:{server.server_port}/') else None)
            started=time.perf_counter();page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('#workspace-select')).to_be_enabled()
            expect(page.locator('#metric-open')).to_have_text('3')
            expect(page.locator('#mode-label')).to_have_text('AI off · local commands')
            expect(page.locator('#environment-banner')).to_be_visible()
            expect(page.locator('#open-nav')).not_to_be_visible()
            expect(page.locator('#close-nav')).not_to_be_visible()
            expect(page.locator('#overview-tasks .record-link').first).to_have_text('Overdue stage review')
            initial_ms=round((time.perf_counter()-started)*1000)
            snapshot(page,'command-center-desktop')
            # Home command -> persisted briefing in Assistant.
            page.locator('#home-input').fill('/brief');page.locator('#home-input').press('Enter')
            expect(page.locator('#view-assistant')).to_be_visible()
            expect(page.locator('#chat-messages')).to_contain_text('OSIS BRIEFING')
            expect(page.locator('#send-button')).to_be_enabled()
            expect(page.locator('#ai-presence')).to_have_attribute('data-state','idle')
            snapshot(page,'assistant-desktop')
            # Copy uses the real browser clipboard API on loopback.
            page.locator('#chat-messages .copy-message').last.click()
            assert 'OSIS BRIEFING' in page.evaluate('navigator.clipboard.readText()')
            # Exact form values, approval and persistence after refresh.
            nav(page,'tasks');page.get_by_role('button',name='New task',exact=False).click()
            expect(page.locator('#create-modal')).to_be_visible()
            page.locator('#field-title').fill('Test task | <img src=x onerror="alert(1)">')
            page.locator('#field-owner').fill('Sample coordinator');page.locator('#field-priority').select_option('high')
            page.locator('#review-change').click();expect(page.locator('#view-approvals')).to_be_visible()
            expect(page.locator('#view-approvals .approval-yes')).to_be_enabled()
            assert not any(t['title'].startswith('Test task') for t in store.state()['tasks'])
            snapshot(page,'approvals-desktop')
            proposal=store.state()['pending'][0]['id'];approve(page)
            expect(page.locator('#assistant-state')).to_have_text('Tool operation completed')
            task=next(t for t in store.state()['tasks'] if t['title'].startswith('Test task'))
            assert '<img' in task['title']
            nav(page,'tasks');page.locator('#task-search').fill('Sample coordinator');page.locator('#task-priority').select_option('high')
            expect(page.locator('#task-table-body tr')).to_have_count(1)
            expect(page.locator('#task-table-body img')).to_have_count(0)
            page.locator('#task-filter').select_option('done');expect(page.locator('#tasks-empty')).to_be_visible()
            page.locator('#task-filter').select_option('todo');page.locator('#task-sort').select_option('priority')
            expect(page.locator('#task-table-body tr')).to_have_count(1)
            page.locator('#task-table-body .record-link').click();expect(page.locator('#detail-content')).to_contain_text('Notification')
            page.keyboard.press('Escape');expect(page.locator('#detail-modal')).not_to_be_visible()
            page.reload();expect(page.locator('#workspace-select')).to_be_enabled();expect(page.locator('#task-table-body')).to_contain_text('Test task |')
            snapshot(page,'tasks-desktop')
            # Replay fails through the actual API and never duplicates a record.
            replay=page.evaluate("""async id=>{const r=await fetch('/api/decide?workspace=osis',{method:'POST',headers:{'Content-Type':'application/json','X-NEXUS-Local':'1'},body:JSON.stringify({id,approve:true})});return r.status;}""",proposal)
            assert replay==400
            # Reject a fact proposal.
            nav(page,'memory');page.get_by_role('button',name='Save a fact',exact=False).first.click()
            page.locator('#field-key').fill('Unapproved suggestion');page.locator('#field-value').fill('This must not become a fact')
            page.locator('#review-change').click();expect(page.locator('#view-approvals .approval-no')).to_be_enabled()
            page.locator('#view-approvals .approval-no').click();expect(page.locator('#view-approvals .approval-card')).to_have_count(0)
            assert not any(m['key']=='Unapproved suggestion' for m in store.state()['memories'])
            # Memory search and provenance display.
            nav(page,'memory');page.locator('#memory-search').fill('rhythm');page.locator('#memory-search-form button[type=submit]').click()
            expect(page.locator('#memory-results')).to_contain_text('Meeting rhythm')
            expect(page.locator('#memory-results')).to_contain_text('User-provided')
            page.locator('#memory-results button').filter(has_text='Provenance').click()
            expect(page.locator('#detail-content')).to_contain_text('Approval ID');page.locator('#detail-done').click()
            snapshot(page,'memory-desktop')
            page.locator('#clear-memory-search').click();page.locator('#memory-source').select_option('ai')
            expect(page.locator('#memory-list')).to_contain_text('No facts from this source.')
            page.locator('#memory-source').select_option('all')
            # Fact update and deletion use real proposals, not direct writes.
            page.locator('#memory-list button').filter(has_text='Update').first.click()
            page.locator('#field-value').fill('Every Thursday')
            page.locator('#review-change').click();expect(page.locator('#view-approvals .approval-yes')).to_be_enabled()
            assert store.state()['memories'][0]['value']!='Every Thursday'
            approve(page);assert store.state()['memories'][0]['value']=='Every Thursday'
            nav(page,'memory');page.locator('#memory-list button').filter(has_text='Delete').first.click()
            expect(page.locator('#view-approvals')).to_contain_text('Earlier chat, audit entries and exports are retained.')
            assert len(store.state()['memories'])==1
            approve(page);assert store.state()['memories']==[]
            # Event and note forms preserve local dates and literal note text.
            nav(page,'events');page.get_by_role('button',name='Plan an event',exact=False).first.click()
            page.locator('#field-title').fill('UI-created event');page.locator('#field-day').fill((today_local()+timedelta(days=6)).isoformat())
            page.locator('#review-change').click();expect(page.locator('#view-approvals .approval-yes')).to_be_enabled();approve(page)
            assert any(e['title']=='UI-created event' and not e['time'] for e in store.state()['events'])
            nav(page,'notes');page.get_by_role('button',name='Add meeting notes',exact=False).first.click()
            page.locator('#field-title').fill('UI meeting notes');page.locator('#field-body').fill('Review | <b>literal text</b>\nNo independently verified decision.')
            page.locator('#review-change').click();expect(page.locator('#view-approvals .approval-yes')).to_be_enabled();approve(page)
            assert any(n['title']=='UI meeting notes' and '| <b>' in n['body'] for n in store.state()['notes'])
            # Task delegation and status controls still require review.
            nav(page,'tasks');row=page.locator('#task-table-body tr').filter(has_text='Test task |')
            row.locator('.tiny-action').first.click();page.locator('#field-owner').fill('Delegate team')
            page.locator('#review-change').click();expect(page.locator('#view-approvals .approval-yes')).to_be_enabled();approve(page)
            assert next(t for t in store.state()['tasks'] if t['id']==task['id'])['owner']=='Delegate team'
            nav(page,'tasks');row=page.locator('#task-table-body tr').filter(has_text='Test task |');row.locator('.tiny-action').last.click()
            expect(page.locator('#view-approvals .approval-yes')).to_be_enabled();approve(page)
            assert next(t for t in store.state()['tasks'] if t['id']==task['id'])['status']=='doing'
            # API validation feedback leaves the draft form available for correction.
            nav(page,'tasks');page.get_by_role('button',name='New task',exact=False).click();page.locator('#field-title').fill('Validation feedback test')
            page.route('**/api/propose*',lambda route:route.fulfill(status=400,content_type='application/json',body='{"error":"Synthetic validation feedback"}'))
            page.locator('#review-change').click();expect(page.locator('#form-error')).to_have_text('Synthetic validation feedback')
            expect(page.locator('#create-modal')).to_be_visible();page.unroute('**/api/propose*');page.locator('#modal-cancel').click()
            # Projects and explicit unsupported detail fields.
            nav(page,'projects');page.locator('#project-search').fill('Leadership')
            expect(page.locator('#project-list .project-card')).to_have_count(1)
            page.get_by_role('button',name='Open project').click()
            expect(page.locator('#detail-content')).to_contain_text('not yet supported')
            page.locator('#detail-done').click();snapshot(page,'projects-desktop')
            # Upcoming agenda, note semantics, runtime settings and activity.
            nav(page,'events');expect(page.locator('#event-list')).to_contain_text('Time not set');snapshot(page,'calendar-desktop')
            nav(page,'notes');expect(page.locator('#notes-list')).to_contain_text('Approved note');snapshot(page,'meetings-desktop')
            nav(page,'activity');expect(page.locator('#activity-list')).to_contain_text('approved');snapshot(page,'activity-desktop')
            nav(page,'settings');expect(page.locator('#system-details')).to_contain_text('Asia/Jakarta');snapshot(page,'settings-desktop')
            # Shortcut must not hijack another field; native dialog traps focus and restores it.
            nav(page,'tasks');page.locator('#task-search').focus();page.keyboard.press('Control+k')
            expect(page.locator('#view-tasks')).to_be_visible()
            create=page.get_by_role('button',name='New task',exact=False);create.click()
            for _ in range(12):
                page.keyboard.press('Tab');assert page.evaluate("document.activeElement.closest('#create-modal')!==null")
            page.keyboard.press('Escape');expect(create).to_be_focused()
            page.locator('#main').focus();page.keyboard.press('Control+k');expect(page.locator('#chat-input')).to_be_focused()
            # Expired UI and backend refusal.
            expired=store.propose('create_task',{'title':'Never execute expired'})
            with store._conn() as con:con.execute('UPDATE pending_actions SET expires_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat(),expired['id']))
            nav(page,'approvals');page.locator('#refresh-button').click()
            expect(page.locator('#view-approvals')).to_contain_text('This proposal expired')
            expect(page.locator('#view-approvals .approval-yes')).to_have_count(0)
            page.get_by_role('button',name='Dismiss expired').click();expect(page.locator('#view-approvals .approval-card')).to_have_count(0)
            assert not any(t['title']=='Never execute expired' for t in store.state()['tasks'])
            # Message formatting is DOM-based and never interprets embedded HTML.
            store.record('assistant','## Formatting fixture\n- First sample item\n- Second sample item\n\n| Field | Value |\n| --- | --- |\n| Scope | OSIS |\n\n```python\nprint("sample")\n```\n<img src=x onerror=alert(1)>')
            nav(page,'assistant');page.locator('#refresh-button').click()
            expect(page.locator('#chat-messages table')).to_have_count(1)
            expect(page.locator('#chat-messages pre')).to_contain_text('print("sample")')
            expect(page.locator('#chat-messages img')).to_have_count(0)
            # Server error shows stale state, disables writes and can recover.
            page.route('**/api/state*',lambda route:route.fulfill(status=500,content_type='application/json',body='{"error":"Synthetic test failure"}'))
            page.locator('#refresh-button').click();expect(page.locator('#load-error')).to_be_visible()
            expect(page.locator('#send-button')).to_be_disabled();expect(page.locator('#core-state')).to_have_text('Error')
            page.unroute('**/api/state*');page.locator('#retry-load').click();expect(page.locator('#load-error')).not_to_be_visible()
            expect(page.locator('#send-button')).to_be_enabled()
            # Workspace navigation reloads all context; no school data is rendered in Personal.
            page.locator('#workspace-select').select_option('personal');expect(page.locator('#workspace-label')).to_have_text('PERSONAL · PERSONAL')
            nav(page,'overview');expect(page.locator('#metric-open')).to_have_text('0');expect(page.locator('#metric-projects')).to_have_text('0')
            assert 'Test task |' not in page.locator('body').inner_text()
            # Read-only workspace has disabled create and submit controls.
            page.locator('#workspace-select').select_option('atlas');expect(page.locator('#workspace-label')).to_have_text('ATLAS · COMPANY')
            nav(page,'projects');expect(page.get_by_role('button',name='New project',exact=False).first).to_be_disabled();expect(page.locator('#project-list button')).to_be_disabled()
            nav(page,'assistant');expect(page.locator('#send-button')).to_be_disabled()
            # Mobile drawer, focus trap, every page's viewport width and reduced motion.
            page.locator('#workspace-select').select_option('osis');expect(page.locator('#workspace-label')).to_have_text('OSIS · SCHOOL')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#open-nav').click();expect(page.locator('#open-nav')).to_have_attribute('aria-expanded','true')
            for _ in range(18):
                page.keyboard.press('Tab');assert page.evaluate("document.activeElement.closest('#sidebar')!==null")
            page.keyboard.press('Escape');expect(page.locator('#open-nav')).to_be_focused()
            for view in ('overview','assistant','projects','tasks','events','notes','memory','approvals','activity','settings'):
                nav(page,view)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),view
                if view in ('overview','tasks','assistant'):snapshot(page,view+'-mobile')
            page.set_viewport_size({'width':320,'height':780})
            for view in ('overview','assistant','projects','tasks','events','notes','memory','approvals','activity','settings'):
                nav(page,view)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),('320px',view)
            page.set_viewport_size({'width':1280,'height':800});nav(page,'overview');snapshot(page,'command-center-laptop')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.locator('.orb-orbit.outer').evaluate('(el)=>getComputedStyle(el).animationName')=='none'
            # Simulated speech events verify UI state transitions without a microphone.
            voice_context=browser.new_context(viewport={'width':1280,'height':800},reduced_motion='reduce')
            voice_context.add_init_script("""window.SpeechRecognition=class {
                constructor(){window.testRecognition=this;}
                start(){this.onstart?.();}
                stop(){this.onend?.();}
                abort(){this.onend?.();}
            };""")
            voice_page=voice_context.new_page();voice_page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(voice_page.locator('#workspace-select')).to_be_enabled()
            mic=voice_page.locator('[data-mic-target="home-input"]');expect(mic).to_be_enabled();mic.click()
            expect(voice_page.locator('#voice-consent')).to_be_visible();expect(voice_page.locator('#ai-presence')).to_have_attribute('data-state','idle')
            voice_page.locator('#voice-cancel').click();mic.click();voice_page.locator('#voice-start').click()
            expect(voice_page.locator('#ai-presence')).to_have_attribute('data-state','listening')
            voice_page.evaluate("window.testRecognition.onresult({results:[[{transcript:'Review the transcript before sending'}]]})")
            expect(voice_page.locator('#home-input')).to_have_value('Review the transcript before sending')
            mic.click();expect(voice_page.locator('#ai-presence')).to_have_attribute('data-state','idle')
            voice_context.close()
            assert not external,external
            assert not errors,errors
            print(json.dumps({'browser':'Chromium on Linux','journeys':'All 20 requested journeys plus permission, replay, expiry, clipboard, XSS text, stale-state recovery and focus checks passed','initial_ready_ms':initial_ms,'external_requests':len(external),'javascript_errors':len(errors),'screenshots':str(shots) if shots else None}))
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
