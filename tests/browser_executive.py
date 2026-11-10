"""Executive acceptance journeys. Only isolated temporary, labeled demo records."""
import os,sys,tempfile,threading,json,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from app import handler_factory
from nexus.workspaces import WorkspaceRegistry
from nexus.demo import seed_demo

SHOTS=Path(os.environ.get('NEXUS_SCREENSHOT_DIR','docs/screenshots/executive'))
SHOTS.mkdir(parents=True,exist_ok=True)
def shot(page,name):
 page.mouse.move(1,1)
 if page.locator('#toast').is_visible():page.locator('#toast').wait_for(state='hidden',timeout=8000)
 page.screenshot(path=str(SHOTS/(name+'.jpg')),full_page=True,type='jpeg',quality=90)
def ready(page):
 expect(page.locator('body')).to_have_attribute('data-startup','home',timeout=15000)
 expect(page.locator('#workspace-select')).to_be_enabled()
def nav(page,view):
 page.locator('#profile-button').click();page.locator(f'.nav-item[data-view="{view}"]').click()
def approve(page):
 expect(page.locator('#view-approvals')).to_be_visible();page.locator('#view-approvals .approval-yes').last.click()
 expect(page.locator('#view-approvals .approval-yes')).to_have_count(0)

with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'NEXUS_TIMEZONE':'Asia/Jakarta','OPENAI_API_KEY':''}):
 registry=WorkspaceRegistry(Path(tmp)/'osis.sqlite3',Path(tmp)/'workspaces');seed_demo(registry)
 store=registry.store('osis')
 for item in store.state()['pending']:store.decide(item['id'],False)
 # Additional preserved secondary-workspace evidence never appears in screenshots.
 for workspace in ['personal','research']:
  target=registry.store(workspace);item=target.propose('remember',{'key':'Isolation sentinel','value':workspace+' private fixture'});target.decide(item['id'],True)
 # Delay the first genuine state read so screenshots cannot race the short ready transition.
 real_state=type(store).state;first_read=[True]
 def slow_first_state(instance,*args,**kwargs):
  if first_read[0]:first_read[0]=False;time.sleep(2)
  return real_state(instance,*args,**kwargs)
 state_delay=patch.object(type(store),'state',slow_first_state);state_delay.start()
 server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(store,0,registry=registry,demo=True))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('NEXUS_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
   context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();errors=[];external=[];world=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:external.append(r.url) if not r.url.startswith(base+'/') else world.append(r.url) if '/api/world' in r.url else None)
   page.goto(base)
   expect(page.locator('body')).to_have_attribute('data-startup','greeting')
   assert page.locator('#orb-stage').evaluate('(e)=>getComputedStyle(e).visibility')=='hidden'
   assert not page.locator('#startup-speech').is_checked();assert not page.locator('#speak-toggle').is_checked()
   page.evaluate('window.originalOrb=document.getElementById("orb-stage");window.introStages=[];new MutationObserver(()=>window.introStages.push(document.body.dataset.startup)).observe(document.body,{attributes:true,attributeFilter:["data-startup"]})')
   shot(page,'01-startup-greeting')
   expect(page.locator('body')).to_have_attribute('data-startup','formation');page.wait_for_timeout(450);shot(page,'02-orb-formation')
   page.wait_for_function("() => document.body.dataset.startup==='initializing'",polling=25)
   expect(page.locator('#intro-status')).to_have_text('INITIALIZING NEXUS');shot(page,'03-initialization')
   assert page.locator('body').get_attribute('data-startup')=='initializing','Readiness bypassed the pending service request'
   expect(page.locator('body')).to_have_attribute('data-startup','ready');expect(page.locator('#intro-status')).to_have_text('NEXUS IS READY');shot(page,'04-ready')
   ready(page);page.wait_for_timeout(950)
   assert page.evaluate('window.originalOrb===document.getElementById("orb-stage")')
   assert page.evaluate('window.introStages').index('ready')>page.evaluate('window.introStages').index('initializing')
   assert len(world)==0,'Home fetched public feeds'
   assert page.locator('.workspace-portal').count()==5
   shot(page,'05-home-1440')
   for width,height in [(1280,800),(1024,768),(390,844)]:
    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(200)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),('home',width)
    boxes=page.locator('.workspace-portal').evaluate_all('(els)=>els.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.getBoundingClientRect().width}))')
    if width==1280:assert len(set(round(b['y']) for b in boxes))==1
    if width==390:assert len(set(round(b['y']) for b in boxes))==3
    shot(page,f'home-{width}')
   page.set_viewport_size({'width':1440,'height':900})
   for workspace in ['osis','academic','coding','atlas','finance']:
    page.goto(base+'?workspace='+workspace+'#headquarters');ready(page)
    expect(page.locator('#view-headquarters')).to_be_visible();expect(page.locator('.function-card')).to_have_count(6)
    assert page.locator('#workspace-select').input_value()==workspace
    boxes=page.locator('.function-card').evaluate_all('(els)=>els.map(e=>({x:e.offsetLeft,y:e.offsetTop}))')
    assert len(set(b['y'] for b in boxes))==2,(workspace,boxes)
    page.wait_for_timeout(250);shot(page,workspace+'-headquarters')
    for index in range(6):
     page.locator('.function-card').nth(index).click();page.wait_for_timeout(80)
     assert page.locator('main>.view.active').count()==1
     assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(workspace,index)
     assert page.locator('#feature-content').inner_text().find('could not load')<0,(workspace,index)
     page.locator('#trail-workspace').click();expect(page.locator('#view-headquarters')).to_be_visible()
   # Six real OSIS tools, including new approved structured records.
   page.goto(base+'?workspace=osis#headquarters');ready(page)
   page.locator('[data-function=meetings]').click();page.get_by_role('button',name='Record meeting',exact=True).click()
   page.locator('#field-title').fill('Synthetic planning meeting');page.locator('#field-agenda').fill('Review the synthetic program plan');page.locator('#field-participants').fill('Sample member A\nSample member B');page.locator('#field-draft_minutes').fill('Draft only. No decision is approved.');page.locator('#review-change').click()
   with store._conn() as con:assert con.execute('SELECT count(*) FROM meetings').fetchone()[0]==0
   approve(page)
   with store._conn() as con:assert con.execute('SELECT count(*) FROM meetings').fetchone()[0]==1
   page.locator('#trail-workspace').click();page.locator('[data-function=meetings]').click();page.get_by_role('button',name='Open meeting',exact=True).click();expect(page.locator('#detail-content')).to_contain_text('Sample member A');page.locator('#detail-done').click()
   page.get_by_role('button',name='Open meeting',exact=True).click();page.get_by_role('button',name='Draft a decision',exact=True).click();page.locator('#field-title').fill('Synthetic decision');page.locator('#field-body').fill('Approve the fictional planning approach');page.locator('#review-change').click();approve(page)
   with store._conn() as con:assert con.execute('SELECT status FROM decisions').fetchone()[0]=='draft'
   page.locator('#trail-workspace').click();page.locator('[data-function=meetings]').click();page.get_by_role('button',name='Open meeting',exact=True).click();page.get_by_role('button',name='Review approval of Synthetic decision',exact=True).click()
   with store._conn() as con:assert con.execute('SELECT status FROM decisions').fetchone()[0]=='draft'
   approve(page)
   with store._conn() as con:assert con.execute('SELECT status FROM decisions').fetchone()[0]=='approved'
   page.locator('#trail-workspace').click();page.locator('[data-function=meetings]').click();page.get_by_role('button',name='Open meeting',exact=True).click();page.get_by_role('button',name='Draft a follow-up',exact=True).click();page.locator('#field-title').fill('Synthetic meeting follow-up');page.locator('#field-owner').fill('Sample member A');page.locator('#review-change').click();approve(page)
   for label in ['Review confirmation of Synthetic meeting follow-up','Review task from Synthetic meeting follow-up']:
    page.locator('#trail-workspace').click();page.locator('[data-function=meetings]').click();page.get_by_role('button',name='Open meeting',exact=True).click();page.get_by_role('button',name=label,exact=True).click();approve(page)
   assert len([t for t in store.state()['tasks'] if t['title']=='Synthetic meeting follow-up'])==1
   page.locator('#trail-workspace').click();page.locator('[data-function=projects]').click();page.get_by_role('button',name='Open project',exact=True).first.click();page.get_by_role('button',name='New milestone',exact=True).click();page.locator('#field-title').fill('Synthetic milestone');page.locator('#review-change').click();approve(page)
   with store._conn() as con:assert con.execute('SELECT title FROM milestones').fetchone()[0]=='Synthetic milestone'
   page.locator('#trail-workspace').click();page.locator('[data-function=documents]').click();page.get_by_role('button',name='New document',exact=True).click();page.locator('#field-title').fill('Synthetic speech');page.locator('#field-body').fill('<img src=x onerror=alert(1)> This stays text.');page.locator('#review-change').click();approve(page)
   page.locator('#trail-workspace').click();page.locator('[data-function=documents]').click();expect(page.locator('#feature-content')).to_contain_text('Synthetic speech');assert page.locator('#feature-content img').count()==0
   page.locator('#trail-workspace').click();page.locator('[data-function=team]').click();page.get_by_role('button',name='Add member',exact=True).click();page.locator('#field-key').fill('Sample coordinator');page.locator('#field-value').fill('Events division · planning duties');page.locator('#review-change').click();approve(page)
   page.locator('#trail-workspace').click();page.locator('[data-function=team]').click();expect(page.locator('#feature-content')).to_contain_text('Sample coordinator')
   # Browser ledger review does not silently write; reject and approve are distinct.
   page.locator('#trail-workspace').click();page.locator('[data-function=budget]').click();page.locator('#ledger-amount').fill('20000');page.locator('#ledger-note').fill('Synthetic supplies');page.locator('#ledger-review').click()
   assert page.evaluate('JSON.parse(localStorage.getItem("nexus.ledger.v1:osis")||"[]").length')==0
   expect(page.locator('#view-approvals')).to_be_visible()
   shot(page,'approval-review')
   # All viewports for workspaces, including keyboard navigation and focus restoration.
   for width,height in [(1440,900),(1280,800),(1024,768),(390,844)]:
    page.set_viewport_size({'width':width,'height':height});page.locator('#trail-workspace').click()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),('workspace',width)
    shot(page,f'osis-{width}')
   page.locator('#profile-button').click();expect(page.locator('#sidebar')).to_have_class(__import__('re').compile('.*open.*'));expect(page.locator('#close-nav')).to_be_focused()
   for _ in range(20):
    page.keyboard.press('Tab');assert page.evaluate("document.activeElement.closest('#sidebar')!==null"),page.evaluate('document.activeElement.outerHTML')
   page.keyboard.press('Escape');expect(page.locator('#profile-button')).to_be_focused()
   for w in ['personal','research']:
    assert registry.store(w).state()['memories'][0]['value']==w+' private fixture'
   assert not external,external;assert not errors,errors
   # Failed initialization cannot show ready; retry uses the real service.
   failure=browser.new_context(viewport={'width':1280,'height':800},reduced_motion='reduce');f=failure.new_page()
   f.route('**/api/state*',lambda r:r.fulfill(status=503,content_type='application/json',body='{"error":"Synthetic offline check"}'))
   f.goto(base);expect(f.locator('body')).to_have_attribute('data-startup','error');expect(f.locator('#intro-retry')).to_be_visible();assert 'READY' not in f.locator('#intro-status').inner_text();shot(f,'initialization-error')
   f.unroute('**/api/state*');f.locator('#intro-retry').click();ready(f)
   assert f.locator('.glass-shell').evaluate('(e)=>getComputedStyle(e).animationName')=='none'
   # Slow actual initialization plus Skip Intro still waits, then succeeds.
   skip=browser.new_context();q=skip.new_page();q.goto(base);q.locator('#skip-intro').click();ready(q)
   assert q.evaluate('document.body.dataset.startup')=='home'
   voice=browser.new_context(reduced_motion='reduce');voice.add_init_script("""window.SpeechRecognition=class {constructor(){window.testVoice=this;}start(){this.onstart?.();}stop(){}abort(){}};""")
   v=voice.new_page();v.goto(base);ready(v)
   assert v.locator('#orb-stage').get_attribute('data-state')=='idle'
   v.locator('#nexus-ring').click();expect(v.locator('#voice-consent')).to_be_visible();v.locator('#voice-start').click()
   expect(v.locator('#orb-stage')).to_have_attribute('data-state','listening')
   v.evaluate("window.testVoice.onerror({error:'not-allowed'})")
   expect(v.locator('#orb-stage')).to_have_attribute('data-state','error');expect(v.locator('#voice-status')).to_contain_text('permission was denied')
   expect(v.locator('#home-input')).to_be_enabled()
   speech=browser.new_context(reduced_motion='reduce')
   speech.add_init_script("""localStorage.setItem('nexus.startupSpeech.v1','true');window.SpeechSynthesisUtterance=class {};
    Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>[],addEventListener:()=>{},cancel:()=>{},speak(utterance){window.testUtterance=utterance;if(window.testSpeechStarted)utterance.onstart?.();else queueMicrotask(()=>utterance.onerror?.({error:'not-allowed'}));}}});""")
   s=speech.new_page();s.goto(base);ready(s)
   expect(s.locator('#speech-output-status')).to_contain_text('Startup speech was unavailable')
   expect(s.locator('#orb-stage')).to_have_attribute('data-state','idle');expect(s.locator('#home-input')).to_be_enabled()
   nav(s,'settings');s.evaluate('window.testSpeechStarted=true');s.locator('#replay-intro').click();ready(s)
   expect(s.locator('#orb-stage')).to_have_attribute('data-state','speaking')
   nav(s,'settings');s.locator('#startup-speech').uncheck();expect(s.locator('#orb-stage')).to_have_attribute('data-state','idle')
   s.evaluate('window.testUtterance.onstart?.()');expect(s.locator('#orb-stage')).to_have_attribute('data-state','idle')
   print(json.dumps({'passed':'Executive startup, real readiness/retry, stable orb, default silence, five mapped portals, all 30 functions, structured records + manual approvals, isolated storage, 4 viewport sizes, keyboard focus, reduced motion','screenshots':len(list(SHOTS.glob('*.jpg'))),'page_errors':errors,'unexpected_external_requests':external}))
   browser.close()
 finally:server.shutdown();server.server_close();thread.join();state_delay.stop()
