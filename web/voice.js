import {app} from './state.js';
import {$,all,icon,toast} from './ui.js';
let recognizer=null,target=null,update=()=>{},starting=false;
export function voiceAvailable(){return recognizer!==null;}
function controls() {
  for(const button of all('[data-mic-target]')){
    const active=app.audioState==='listening'&&target?.id===button.dataset.micTarget;
    button.classList.toggle('listening',active);button.setAttribute('aria-label',active?'Stop listening':'Dictate '+(button.dataset.micTarget==='home-input'?'a command':'a message'));
    button.setAttribute('title',active?'Stop listening':recognizer?'Dictate after reviewing privacy notice':'Browser dictation unavailable');
    button.setAttribute('aria-pressed',String(active));button.replaceChildren(icon(active?'stop':'mic'));
    button.disabled=app.busy||starting||!recognizer||!(app.data.capabilities||[]).includes('propose');
  }
}
export function syncVoiceControls(){controls();}
export function stopAudio(){recognizer?.abort();window.speechSynthesis?.cancel();starting=false;app.audioState='idle';controls();update();}
export function speak(text) {
  if(!$('speak-toggle').checked||!('speechSynthesis' in window))return;
  window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(String(text).slice(0,1500));utterance.lang=$('voice-language').value;
  utterance.onstart=()=>{app.audioState='speaking';update();};utterance.onend=()=>{app.audioState='idle';update();};
  utterance.onerror=()=>{app.audioState='idle';toast('Spoken playback stopped or was unavailable.');update();};
  window.speechSynthesis.speak(utterance);
}
export function setupVoice(onState) {
  update=onState;const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(Recognition){
    recognizer=new Recognition();recognizer.interimResults=false;recognizer.continuous=false;
    recognizer.onstart=()=>{starting=false;app.audioState='listening';$('chat-notice').textContent='Listening. Use the highlighted mic button to stop.';controls();update();};
    recognizer.onresult=event=>{if(!target)return;const transcript=Array.from(event.results).map(r=>r[0].transcript).join(' ');const next=target.value+(target.value?' ':'')+transcript;target.value=next.slice(0,3000);$('chat-notice').textContent='Transcript ready. Review it before sending.';};
    recognizer.onend=()=>{starting=false;app.audioState='idle';controls();update();};
    recognizer.onerror=event=>{starting=false;app.audioState='idle';toast('Dictation unavailable: '+event.error+'. You can type your command.','error');controls();update();};
  }
  $('voice-support').textContent=recognizer?'Browser dictation is available. Audio may leave this device through the browser’s speech service.':'Browser dictation is unavailable. Use your keyboard or the device’s own dictation feature.';
  $('speak-toggle').disabled=!('speechSynthesis' in window);$('stop-speaking').disabled=!('speechSynthesis' in window);
  for(const button of all('[data-mic-target]'))button.onclick=()=>{
    if(app.audioState==='listening'){recognizer?.stop();return;}
    target=$(button.dataset.micTarget);app.focusReturn=button;$('voice-consent').showModal();
  };
  $('voice-cancel').onclick=()=>$('voice-consent').close();
  $('voice-start').onclick=()=>{$('voice-consent').close();if(!recognizer||app.busy)return;try{window.speechSynthesis?.cancel();recognizer.lang=$('voice-language').value;starting=true;controls();recognizer.start();$('chat-notice').textContent='Waiting for microphone permission…';}catch{starting=false;controls();toast('The microphone could not start. Check browser permissions.','error');}};
  $('stop-speaking').onclick=stopAudio;controls();
}
