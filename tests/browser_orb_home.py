"""Orb-first recovery acceptance: real server, synthetic isolated records, mocked audio."""
import json,os,sys,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from app import handler_factory
from nexus.workspaces import WorkspaceRegistry

def ready(page):
    expect(page.locator('body')).to_have_attribute('data-startup','home',timeout=15000)
    expect(page.locator('#workspace-select')).to_be_enabled()

def start_voice(page):
    page.locator('#nexus-ring' if page.locator('body').get_attribute('data-page')=='home' else '#global-voice').click()
    if page.locator('#voice-consent').is_visible():page.locator('#voice-start').click()
    expect(page.locator('#orb-stage')).to_have_attribute('data-state','listening')

def say(page,phrase):
    page.evaluate("text=>window.mockRecognition.onresult({results:[Object.assign([{transcript:text}],{isFinal:true})]})",phrase)

with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'OPENAI_API_KEY':'','NEXUS_TIMEZONE':'Asia/Jakarta'}):
    registry=WorkspaceRegistry(Path(tmp)/'osis.sqlite3',Path(tmp)/'workspaces')
    for workspace in ['osis','atlas','academic','coding','finance','personal','research']:
        store=registry.store(workspace);p=store.propose('remember',{'key':'Recovery sentinel','value':workspace+' fixture'});store.decide(p['id'],True)
    snapshots={w:registry.store(w).state() for w in registry.paths}
    server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(registry.store('osis'),0,registry=registry,demo=True))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('NEXUS_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce')
            context.add_init_script("""window.voiceStarts=0;window.SpeechRecognition=class {
                constructor(){window.mockRecognition=this;}start(){window.voiceStarts++;this.onstart?.();}
                stop(){this.onend?.();}abort(){}
            };""")
            page=context.new_page();errors=[];posts=[];external=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else external.append(r.url) if not r.url.startswith(base+'/') else None)
            page.goto(base);ready(page)
            assert page.evaluate('window.voiceStarts')==0,'Microphone started without activation'
            assert page.locator('.workspace-portal').count()==0
            expect(page.locator('#home-command-form')).not_to_be_visible()
            expect(page.locator('.app-footer')).not_to_be_visible()
            shots=Path(os.environ.get('NEXUS_SCREENSHOT_DIR','work/screenshots/orb-home'));shots.mkdir(parents=True,exist_ok=True)
            for width,height in [(1440,900),(1280,800),(1024,768),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                box=page.locator('#orb-stage').bounding_box()
                assert box['x']>=0 and box['x']+box['width']<=width
                assert box['y']>=0 and box['y']+box['height']<=height
                assert abs(box['x']+box['width']/2-width/2)<2
                page.screenshot(path=str(shots/f'home-{width}.jpg'),type='jpeg',quality=90,full_page=True)
            page.set_viewport_size({'width':1440,'height':900})
            start_voice(page);say(page,'open OSIS workspace');expect(page.locator('#view-headquarters')).to_be_visible()
            start_voice(page);say(page,'go home');expect(page.locator('#view-home')).to_be_visible()
            expect(page.locator('#orb-stage')).to_have_attribute('data-state','idle')
            start_voice(page);say(page,'NEXUS, open ATLAS workspace');page.wait_for_url('**?workspace=atlas#headquarters');ready(page)
            expect(page.locator('#headquarters-title')).to_have_text('ATLAS Headquarters')
            assert page.evaluate('window.voiceStarts')==0,'Navigation restarted the microphone'
            start_voice(page);say(page,'kembali ke beranda');expect(page.locator('#view-home')).to_be_visible()
            assert page.locator('#workspace-select').input_value()=='atlas','Home changed storage scope'
            # Typing remains on demand; navigation does not create chat or business records.
            page.keyboard.press('Control+k');expect(page.locator('#chat-input')).to_be_focused()
            page.locator('#chat-input').fill('go home');page.locator('#chat-input').press('Enter');expect(page.locator('#view-home')).to_be_visible()
            # A spoken permission failure remains visible on the otherwise quiet Home.
            start_voice(page);page.evaluate("window.mockRecognition.onerror({error:'not-allowed'})")
            expect(page.locator('#voice-feedback')).to_be_visible();expect(page.locator('#voice-status')).to_contain_text('permission was denied')
            page.locator('#voice-feedback .voice-transcript').click();expect(page.locator('#view-assistant')).to_be_visible()
            # A destination absent from the actual readable list must fail closed.
            def restrict(route):
                response=route.fetch();data=response.json();data['workspaces']=[w for w in data['workspaces'] if w['id']!='finance'];route.fulfill(response=response,json=data)
            page.route('**/api/workspaces*',restrict);page.reload();ready(page)
            page.keyboard.press('Control+k');page.locator('#chat-input').fill('open finance workspace');page.locator('#chat-input').press('Enter')
            expect(page.locator('#toast')).to_contain_text('not available');assert 'workspace=finance' not in page.url
            for w,before in snapshots.items():assert registry.store(w).state()==before,(w,'Unexpected storage change')
            assert posts==[],posts;assert external==[],external;assert errors==[],errors
            # When speech recognition is absent, the orb opens usable text input.
            fallback=browser.new_context(reduced_motion='reduce');fallback.add_init_script('delete window.SpeechRecognition;delete window.webkitSpeechRecognition;')
            f=fallback.new_page();f.goto(base);ready(f);expect(f.locator('#nexus-ring')).to_be_enabled();f.locator('#nexus-ring').click()
            expect(f.locator('#view-assistant')).to_be_visible();expect(f.locator('#chat-input')).to_be_focused();expect(f.locator('#chat-notice')).to_contain_text('unavailable')
            print(json.dumps({'passed':'Orb-only layout, explicit microphone activation, voice and typed navigation, Go Home, text fallback, visible failures, destination permissions, unchanged seven-workspace records','post_requests':len(posts),'page_errors':errors,'external_requests':external}))
            browser.close()
    finally:server.shutdown();server.server_close();thread.join()
