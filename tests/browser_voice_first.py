"""Voice-first acceptance over the real Core; synthetic stores and fake audio only.

NEXUS_CHROMIUM selects an installed browser. Without it use Playwright Chromium.
No paid AI calls, real microphones, external accounts or personal data are used.
"""
import json
import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import expect, sync_playwright
from app import Coordinator, handler_factory
from nexus.workspaces import WorkspaceRegistry

MOCK_AUDIO = """
window.recognitions=[];window.voiceStarts=0;window.spoken=[];window.audioClashes=0;
window.SpeechRecognition=class {
 constructor(){this.active=false;window.recognitions.push(this);window.mockRecognition=this;}
 start(){window.voiceStarts++;if(window.micHang)return;this.active=true;
   if(window.testSpeaking)window.audioClashes++;this.onstart?.();}
 stop(){this.active=false;this.onend?.();}
 abort(){this.active=false;this.onend?.();}
};
window.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
Object.defineProperty(window,'speechSynthesis',{value:{
 getVoices:()=>[{voiceURI:'synthetic-en',name:'Synthetic voice',lang:'en-GB'}],
 addEventListener(){},resume(){},current:null,
 cancel(){const old=this.current;this.current=null;window.testSpeaking=false;old?.onerror?.({error:'canceled'});},
 speak(u){this.current=u;window.spoken.push(u);if(window.speechHang)return;
  if(window.recognitions.some(r=>r.active))window.audioClashes++;
  window.testSpeaking=true;u.onstart?.();}
}});
window.finishSpeech=()=>{const u=window.speechSynthesis.current;window.speechSynthesis.current=null;window.testSpeaking=false;u?.onend?.();};
"""


def ready(page):
    expect(page.locator('body')).to_have_attribute('data-startup', 'home', timeout=15000)
    expect(page.locator('#workspace-select')).to_be_enabled()


def activate(page):
    page.locator('#nexus-ring' if page.locator('body').get_attribute('data-page') == 'home' else '#global-voice').click()
    if page.locator('#voice-consent').is_visible():
        page.locator('#voice-start').click()


def listen(page):
    activate(page)
    expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')


def say(page, text):
    page.evaluate("text=>window.mockRecognition.onresult({results:[Object.assign([{transcript:text}],{isFinal:true})]})", text)


def end_speech(page):
    page.evaluate('window.finishSpeech()')
    expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')


def snapshot(store):
    # Includes persisted conversation, audit, tasks, projects and pending records.
    return store.state()


class ObservedServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        server_errors.append(type(sys.exc_info()[1]).__name__)


slow_started = threading.Event()
slow_release = threading.Event()
slow_finished = threading.Event()
original_chat = Coordinator.chat
server_errors = []


def controlled_chat(self, message):
    if message == '/task add Interrupted synthetic proposal | Test role':
        slow_started.set()
        if not slow_release.wait(15):
            raise TimeoutError('Synthetic delay not released')
        try:
            return original_chat(self, message)
        finally:
            slow_finished.set()
    return original_chat(self, message)


with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'OPENAI_API_KEY': '', 'NEXUS_TIMEZONE': 'Asia/Jakarta'}), patch.object(Coordinator, 'chat', controlled_chat):
    root = Path(directory)
    registry = WorkspaceRegistry(root/'osis.sqlite3', root/'workspaces')
    scopes = ['osis', 'personal', 'academic', 'research', 'coding', 'finance', 'atlas']
    for workspace in scopes:
        store = registry.store(workspace)
        pending = store.propose('remember', {'key': 'Synthetic scope sentinel', 'value': workspace+' only'})
        store.decide(pending['id'], True)
    before = {workspace: snapshot(registry.store(workspace)) for workspace in scopes}
    server = ObservedServer(('127.0.0.1', 0), handler_factory(registry.store('osis'), 0, registry=registry, demo=True))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('NEXUS_CHROMIUM') or p.chromium.executable_path, headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
            context.add_init_script(MOCK_AUDIO)
            page = context.new_page()
            errors, posts, external = [], [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else external.append(request.url) if not request.url.startswith(base+'/') else None)
            page.goto(base)
            ready(page)
            assert page.evaluate('window.voiceStarts') == 0
            expect(page.locator('#home-command-form')).not_to_be_visible()
            assert page.locator('.workspace-portal').count() == 0
            assert page.locator('#view-home').locator('button:visible').count() == 1

            # Immediate local routing: no Send, model request, or record write.
            routes = [('NEXUS, open OSIS workspace.', 'osis'), ('Open Academics.', 'academic'), ('Switch to Development.', 'coding'), ('Open ATLAS Headquarters.', 'atlas'), ('Buka workspace Finance.', 'finance'), ('tolong buka riset', 'research'), ('buka ruang kerja pribadi', 'personal'), ('buka workspace OSIS', 'osis')]
            for phrase, destination in routes:
                listen(page)
                say(page, phrase)
                page.wait_for_url(f'**?workspace={destination}#headquarters') if destination != 'osis' or '?workspace=osis' in page.url else None
                ready(page)
                expect(page.locator('#view-headquarters')).to_be_visible()
                assert page.locator('#workspace-select').input_value() == destination
                assert not page.evaluate('window.recognitions.some(r=>r.active)')
                listen(page)
                say(page, 'Kembali ke beranda.')
                expect(page.locator('#view-home')).to_be_visible()
                expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'idle')
            assert not posts, posts
            for workspace in scopes:
                assert snapshot(registry.store(workspace)) == before[workspace]

            # Hypotheses never execute; a final greeting reaches the real Core.
            listen(page)
            page.evaluate("()=>{const r=Object.assign([{transcript:'open finance'}],{isFinal:false});window.mockRecognition.onresult({results:[r]});}")
            expect(page.locator('#voice-heard')).to_contain_text('open finance')
            assert not posts
            page.evaluate('window.oldRecognition=window.mockRecognition')
            say(page, 'hey')
            expect(page.locator('#nexus-response')).to_contain_text('Hey')
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'speaking')
            assert not page.evaluate('window.recognitions.some(r=>r.active)')
            page.evaluate('window.oldSpeech=window.spoken.at(-1)')

            # Explicit interruption pauses output before activating another mic.
            listen(page)
            page.evaluate("()=>{window.oldSpeech.onstart?.();window.oldSpeech.onend?.();window.oldSpeech.onerror?.({error:'network'});window.oldRecognition.onresult?.({results:[[{transcript:'open finance'}]]});window.oldRecognition.onerror?.({error:'not-allowed'});}")
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')
            assert page.locator('#workspace-select').input_value() == 'osis'
            assert page.evaluate('window.audioClashes') == 0
            say(page, 'berhenti')
            expect(page.locator('#nexus-ring')).to_have_attribute('aria-pressed', 'false')

            # Visible permission recovery; cancelled recognizer cannot break retry.
            listen(page)
            page.evaluate("window.failedRecognition=window.mockRecognition;window.mockRecognition.onerror({error:'not-allowed'})")
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'error')
            expect(page.locator('#voice-status')).to_contain_text('permission was denied')
            page.locator('#voice-retry').click()
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')
            page.evaluate("window.failedRecognition.onerror({error:'network'})")
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')
            say(page, 'approve it')
            expect(page.locator('#nexus-response')).to_contain_text('manually')
            end_speech(page)
            assert not any('/api/decide' in url for url in posts)
            page.keyboard.press('Escape')
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'idle')

            # An interrupted request can finish server-side, but must not replace
            # the current voice response or approve its resulting proposal.
            listen(page)
            say(page, '/task add Interrupted synthetic proposal | Test role')
            assert slow_started.wait(5)
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'thinking')
            listen(page)
            say(page, 'hello')
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'speaking')
            fresh_reply = page.locator('#nexus-response').text_content()
            slow_release.set()
            assert slow_finished.wait(5)
            page.wait_for_timeout(200)
            assert page.locator('#nexus-response').text_content() == fresh_reply
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'speaking')
            assert registry.store('osis').state()['tasks'] == []
            assert len(registry.store('osis').state()['pending']) == 1
            end_speech(page)
            say(page, 'stop')

            # Real voice task draft still needs a separate manual approval.
            listen(page)
            say(page, 'add a task Synthetic voice task')
            expect(page.locator('#nexus-response')).to_contain_text('Approval inbox')
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'speaking')
            assert registry.store('osis').state()['tasks'] == []
            page.keyboard.press('Control+k')
            expect(page.locator('#chat-input')).to_be_focused()
            page.locator('#profile-button').click()
            page.locator('.nav-item[data-view=approvals]').click()
            card = page.locator('#approvals-list .approval-card').filter(has_text='Synthetic voice task')
            card.locator('.approval-yes').click()
            expect(card).not_to_be_visible()
            tasks = registry.store('osis').state()['tasks']
            assert len(tasks) == 1 and tasks[0]['title'] == 'Synthetic voice task'
            assert any('Interrupted synthetic' in row['description'] for row in registry.store('osis').state()['pending'])
            for workspace in scopes[1:]:
                assert snapshot(registry.store(workspace)) == before[workspace], workspace

            # Dictation remains a reviewed draft; obsolete events cannot append.
            page.keyboard.press('Control+k')
            mic = page.locator('[data-mic-target=chat-input]')
            mic.click();page.locator('#voice-start').click()
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')
            page.evaluate('window.oldDictation=window.mockRecognition')
            count = len(posts)
            say(page, 'Review this synthetic transcript')
            expect(page.locator('#chat-input')).to_have_value('Review this synthetic transcript')
            page.evaluate("window.oldDictation.onresult({results:[[{transcript:'obsolete words'}]]})")
            expect(page.locator('#chat-input')).to_have_value('Review this synthetic transcript')
            assert len(posts) == count
            page.locator('#chat-input').fill('')

            # Optional spoken output falls back to a visible conversation.
            page.locator('#profile-button').click();page.locator('.nav-item[data-view=settings]').click()
            page.locator('#voice-output-toggle').uncheck()
            page.keyboard.press('Control+k');page.locator('#chat-input').fill('go home');page.locator('#chat-input').press('Enter')
            spoken = page.evaluate('window.spoken.length')
            listen(page);say(page, 'hello')
            expect(page.locator('#view-assistant')).to_be_visible()
            expect(page.locator('#nexus-response')).to_contain_text('Hey')
            assert page.evaluate('window.spoken.length') == spoken
            assert not page.evaluate('window.recognitions.some(r=>r.active)')
            page.locator('#profile-button').click();page.locator('.nav-item[data-view=settings]').click()
            page.locator('#voice-output-toggle').check();page.locator('#wake-word-toggle').check()
            page.keyboard.press('Control+k');page.locator('#chat-input').fill('go home');page.locator('#chat-input').press('Enter')
            listen(page);count=len(posts);say(page, 'unrelated background words')
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')
            assert len(posts) == count
            say(page, 'Hey NEXUS, open OSIS workspace')
            expect(page.locator('#view-headquarters')).to_be_visible()
            assert len(posts) == count
            page.locator('#profile-button').click();page.locator('.nav-item[data-view=settings]').click()
            page.locator('#wake-word-toggle').uncheck()

            # Fallback, missing destinations, wake tails and quiet recovery.
            page.keyboard.press('Control+k')
            page.locator('#chat-input').fill('Go Home.')
            page.locator('#chat-input').press('Enter')
            expect(page.locator('#view-home')).to_be_visible()
            for _ in range(3):
                if page.locator('#nexus-ring').get_attribute('aria-pressed') != 'true':
                    listen(page)
                page.evaluate('window.mockRecognition.active=false;window.mockRecognition.onend()')
                if _ < 2:
                    expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'listening')
            expect(page.locator('#voice-status')).to_contain_text('No transcript')
            expect(page.locator('#voice-retry')).to_be_visible()

            shots = Path(os.environ.get('NEXUS_SCREENSHOT_DIR', 'work/screenshots/voice-first'))
            shots.mkdir(parents=True, exist_ok=True)
            page.keyboard.press('Control+k')
            page.locator('#chat-input').fill('go home');page.locator('#chat-input').press('Enter')
            expect(page.locator('#toast')).not_to_be_visible(timeout=8000)
            page.screenshot(path=str(shots/'home-1440.jpg'), type='jpeg', quality=90)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(shots/'home-390.jpg'), type='jpeg', quality=90)
            page.set_viewport_size({'width':1440,'height':900})
            listen(page);say(page, 'hey')
            expect(page.locator('#orb-stage')).to_have_attribute('data-state', 'speaking')
            page.screenshot(path=str(shots/'orb-speaking.jpg'), type='jpeg', quality=90)
            page.keyboard.press('Escape')
            assert page.evaluate('window.audioClashes') == 0

            # Deterministic watchdog checks, without real-time sleeps.
            page.clock.install()
            page.evaluate('window.micHang=true')
            activate(page);page.clock.run_for(250);page.clock.fast_forward(12100)
            expect(page.locator('#voice-status')).to_contain_text('microphone did not start')
            expect(page.locator('#nexus-ring')).to_have_attribute('aria-pressed', 'false')
            page.evaluate('window.micHang=false;window.speechHang=true')
            listen(page);say(page,'Hey Nexus')
            page.wait_for_function('window.speechSynthesis.current!==null')
            page.clock.fast_forward(7100)
            expect(page.locator('#voice-status')).to_contain_text('Speech playback failed')
            expect(page.locator('#nexus-ring')).to_have_attribute('aria-pressed', 'false')
            page.screenshot(path=str(shots/'voice-recovery.jpg'), type='jpeg', quality=90)
            assert not errors, errors
            assert not external, external
            assert not server_errors, server_errors

            # Unsupported recognition never traps the user on the orb.
            fallback = browser.new_context(reduced_motion='reduce')
            fallback.add_init_script('delete window.SpeechRecognition;delete window.webkitSpeechRecognition;')
            f = fallback.new_page();f.goto(base);ready(f);f.locator('#nexus-ring').click()
            expect(f.locator('#chat-input')).to_be_focused()
            expect(f.locator('#chat-notice')).to_contain_text('unavailable')
            print(json.dumps({'passed':'Bilingual local routing, all seven scopes, no navigation POSTs, interim transcript safety, real Core greeting/task draft, manual approval only, microphone errors/retry, stale recognition and speech events, explicit speech/request interruption, late server reply suppression, keyboard/text fallback, watchdogs and orb states', 'hardware':'not tested; mocked speech only', 'page_errors':errors,'unexpected_external_requests':external,'screenshots':str(shots)}))
            browser.close()
    finally:
        slow_release.set()
        server.shutdown();server.server_close();thread.join()
