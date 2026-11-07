import {app,VIEW_NAMES} from './state.js';
import {api,post} from './api.js';
import {$,all,hydrateIcons,toast,announce} from './ui.js';
import {bindActions,currentWorkspace,renderAll,renderChat,renderApprovals,renderTasks,renderProjects,renderMemory} from './views.js';
import {openForm,formAction} from './forms.js';
import {setupVoice,syncVoiceControls,speak,stopAudio} from './voice.js';

let drawerReturn=null;
let expiryTimer=null;
function setDrawer(open){
  if(open)drawerReturn=document.activeElement;
  $('sidebar').classList.toggle('open',open);$('nav-backdrop').hidden=!open;$('open-nav').setAttribute('aria-expanded',String(open));
  document.body.classList.toggle('drawer-lock',open);
  const mobile=matchMedia('(max-width:760px)').matches;
  $('sidebar').inert=mobile&&!open;
  $('main').inert=mobile&&open;$('view-overview').closest('.workspace').querySelector('.topbar').inert=mobile&&open;
  if(open)$('close-nav').focus();else if(drawerReturn?.isConnected)drawerReturn.focus();
}
function navigate(view,{focus=true}={}){
  if(!VIEW_NAMES[view])view='overview';
  app.view=view;
  for(const section of all('main>.view')){const active=section.id==='view-'+view;section.hidden=!active;section.classList.toggle('active',active);}
  for(const node of all('.nav-item')){const active=node.dataset.view===view;node.classList.toggle('active',active);if(active)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current');}
  $('breadcrumb-page').textContent=VIEW_NAMES[view].toUpperCase();document.title='NEXUS — '+VIEW_NAMES[view];
  history.replaceState(null,'','#'+view);
  if($('sidebar').classList.contains('open'))setDrawer(false);
  if(view==='assistant'){$('chat-messages').scrollTop=$('chat-messages').scrollHeight;}
  window.scrollTo({top:0,behavior:'instant'});
  if(focus){$('main').focus({preventScroll:true});announce(VIEW_NAMES[view]+' · '+currentWorkspace().label);}
}
function syncStatus(){
  const state=app.busy?'Processing':app.audioState==='listening'?'Listening':app.audioState==='speaking'?'Speaking':app.assistantState;
  $('assistant-state').textContent=state;$('assistant-state').dataset.state=app.error?'error':app.busy?'processing':'ready';
  $('core-state').textContent=app.loaded?state==='Ready'?'Ready for your next move':state:'Connecting to local core';
  $('ai-presence').dataset.state=app.busy?'processing':app.audioState!=='idle'?app.audioState:app.error?'error':'idle';
  $('main').setAttribute('aria-busy',String(app.busy||!app.loaded));
  $('workspace-select').disabled=app.busy||!app.loaded;
  for(const node of all('.command-submit,#send-button,[data-create],#review-change'))node.disabled=app.busy||app.stale||!app.loaded||!(app.data.capabilities||[]).includes('propose');
  for(const node of all('#home-input,#chat-input'))node.disabled=!app.loaded||!(app.data.capabilities||[]).includes('propose');
  for(const node of all('.approval-controls button'))node.disabled=app.busy||app.stale||!(app.data.capabilities||[]).includes('approve');
  for(const node of all('[data-capability]'))node.disabled=app.busy||app.stale||!app.loaded||!(app.data.capabilities||[]).includes(node.dataset.capability);
  syncVoiceControls();
}
async function refresh({notify=false}={}){
  const workspace=app.workspace;
  try{
    const data=await api('/api/state',{workspace});
    if(workspace&&workspace!==app.workspace)return false;
    app.data=data;app.workspace=data.workspace;app.loaded=true;app.stale=false;$('load-error').hidden=true;
    if(app.error){app.error=false;app.assistantState='Ready';}
    renderAll();syncStatus();scheduleExpiryRefresh();if(notify)toast('Workspace refreshed.');return true;
  }catch(error){
    $('load-error-message').textContent=error.message+(app.loaded?' Showing the last loaded records.':'');$('load-error').hidden=false;
    app.error=true;app.stale=true;app.assistantState='Error';$('local-status').textContent='Local core unavailable';$('local-status').dataset.state='error';syncStatus();
    // Fail closed while the currently displayed state may be stale.
    for(const node of all('[data-create],.command-submit,#send-button,#review-change,.approval-controls button'))node.disabled=true;
    return false;
  }
}
function resultState(result){
  app.error=result.status==='error'||['error','unavailable'].includes(result.provider_status);
  app.assistantState=app.error?'Error':result.pending?'Awaiting approval':'Ready';
}
async function command(message){
  if(app.busy||app.stale||!app.loaded||!message.trim())return false;
  app.busy=true;app.error=false;syncStatus();navigate('assistant',{focus:false});renderChat();
  let ok=false;
  try{
    const result=await post('/api/chat',{message});resultState(result);
    $('plan-report').textContent=result.pending?'Proposal prepared. No records have changed. Review the action card below.':app.error?result.message:'Response ready · saved in '+currentWorkspace().label+'.';
    $('plan-report').hidden=false;
    ok=await refresh();if(ok){resultState(result);renderChat();if(!result.pending&&!app.error)speak(result.message);announce(result.pending?'Approval required.':result.message.slice(0,180));}
  }catch(error){app.error=true;app.assistantState='Error';toast(error.message,'error');$('plan-report').hidden=false;$('plan-report').textContent=error.message;}
  finally{app.busy=false;renderChat();syncStatus();}
  return ok;
}
async function propose(name,args,{fromForm=false,workspace=app.workspace}={}){
  if(app.busy||app.stale||!app.loaded||workspace!==app.workspace)return false;
  app.busy=true;app.error=false;syncStatus();
  try{
    const result=await post('/api/propose',{name,args},workspace);
    if(fromForm)$('create-modal').close();
    app.assistantState='Awaiting approval';$('plan-report').textContent='Proposal prepared. Review the exact values before approving.';$('plan-report').hidden=false;
    const loaded=await refresh();app.assistantState=loaded?'Awaiting approval':'Error';navigate('approvals');toast('Approval required. No records have changed.');return true;
  }catch(error){app.error=true;app.assistantState='Error';if(fromForm){$('form-error').textContent=error.message;$('form-error').hidden=false;}else toast(error.message,'error');return false;}
  finally{app.busy=false;syncStatus();renderApprovals();}
}
async function decide(id,approve,workspace){
  if(app.busy||app.stale||workspace!==app.workspace)return;
  app.busy=true;app.error=false;syncStatus();
  try{
    const result=await post('/api/decide',{id,approve},workspace);
    $('plan-report').textContent=result.message;$('plan-report').hidden=false;
    const loaded=await refresh();
    app.assistantState=!loaded?'Error':result.outcome==='approved'?'Tool operation completed':result.outcome==='expired'?'Approval expired':'Action rejected';
    toast(result.message,result.outcome==='expired'?'error':'info');announce(result.message);
  }catch(error){app.error=true;app.assistantState='Error';toast(error.message,'error');$('plan-report').hidden=false;$('plan-report').textContent=error.message;await refresh();app.error=true;app.assistantState='Error';}
  finally{app.busy=false;renderApprovals();renderChat();syncStatus();}
}
async function copy(text){try{await navigator.clipboard.writeText(text);toast('Message copied.');}catch{toast('Clipboard access is unavailable. Select and copy the message text.','error');}}
async function searchMemory(event){
  event.preventDefault();const query=$('memory-search').value.trim();if(!query){app.memoryResults=null;renderMemory();return;}
  const workspace=app.workspace,button=$('memory-search-form').querySelector('[type=submit]');button.disabled=true;
  try{const results=await api('/api/search?q='+encodeURIComponent(query),{workspace});if(workspace!==app.workspace)return;app.memoryResults=results;renderMemory();announce('Workspace search results updated.');}catch(error){toast(error.message,'error');}finally{button.disabled=false;}
}
async function load(){
  const loaded=await refresh();if(!loaded)return;
  try{
    const result=await api('/api/workspaces');app.workspaces=result.workspaces;
    const select=$('workspace-select');select.replaceChildren();
    for(const workspace of result.workspaces){const option=document.createElement('option');option.value=workspace.id;option.textContent=workspace.label+(workspace.id==='atlas'?' · foundation':'');select.append(option);}
    select.value=app.workspace;renderAll();syncStatus();
  }catch(error){toast('Could not load workspace options. '+error.message,'error');}
}
function setup(){
  hydrateIcons();setupVoice(syncStatus);bindActions({create:openForm,command,propose,decide,navigate,copy});
  document.addEventListener('click',event=>{
    const control=event.target.closest('[data-view],[data-create],[data-command],[data-priorities]');if(!control||control.disabled||control.getAttribute('aria-disabled')==='true')return;
    if(control.dataset.view)navigate(control.dataset.view);
    else if(control.dataset.create)openForm(control.dataset.create);
    else if(control.dataset.command)command(control.dataset.command);
    else if(control.hasAttribute('data-priorities')){navigate('overview');$('priorities-panel').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'center'});$('priorities-panel').focus({preventScroll:true});}
  });
  for(const [form,input] of [['home-command-form','home-input'],['chat-form','chat-input']]){
    $(form).onsubmit=async event=>{event.preventDefault();const value=$(input).value;if(await command(value))$(input).value='';};
    $(input).onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$(form).requestSubmit();}};
  }
  for(const id of ['task-search','task-filter','task-priority','task-sort'])$(id).addEventListener(id==='task-search'?'input':'change',renderTasks);
  for(const id of ['project-search','project-filter','project-sort'])$(id).addEventListener(id==='project-search'?'input':'change',renderProjects);
  $('memory-search-form').onsubmit=searchMemory;$('memory-source').onchange=renderMemory;
  $('clear-memory-search').onclick=()=>{app.memoryResults=null;$('memory-search').value='';$('memory-source').value='all';renderMemory();};
  $('workspace-select').onchange=()=>{if(app.busy){$('workspace-select').value=app.workspace;return;}stopAudio();const selected=$('workspace-select').value;location.href=location.pathname+'?workspace='+encodeURIComponent(selected)+'#'+app.view;};
  $('refresh-button').onclick=$('settings-refresh').onclick=()=>refresh({notify:true});$('retry-load').onclick=load;
  $('create-form').onsubmit=async event=>{event.preventDefault();if(app.busy)return;try{const action=formAction();await propose(action.name,action.args,{fromForm:true,workspace:action.workspace});}catch(error){$('form-error').textContent=error.message;$('form-error').hidden=false;}};
  $('modal-close').onclick=$('modal-cancel').onclick=()=>$('create-modal').close();
  $('detail-close').onclick=$('detail-done').onclick=()=>$('detail-modal').close();
  for(const dialog of all('dialog')){
    dialog.addEventListener('close',()=>{if(app.focusReturn?.isConnected)app.focusReturn.focus({preventScroll:true});});
    dialog.addEventListener('keydown',event=>{
      if(event.key!=='Tab')return;
      const nodes=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),a[href],summary')].filter(node=>node.getClientRects().length);
      const first=nodes[0],last=nodes.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    });
  }
  $('open-nav').onclick=()=>setDrawer(true);$('close-nav').onclick=$('nav-backdrop').onclick=()=>setDrawer(false);
  const media=matchMedia('(max-width:760px)');media.addEventListener('change',()=>setDrawer(false));$('sidebar').inert=media.matches;
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&$('sidebar').classList.contains('open')){event.preventDefault();setDrawer(false);return;}
    if(event.key==='Tab'&&$('sidebar').classList.contains('open')){const nodes=[...$('sidebar').querySelectorAll('a,button:not([disabled]),select:not([disabled])')].filter(n=>n.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}return;}
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){
      const editing=event.target.closest('input,textarea,select,[contenteditable=true]');if(editing||document.querySelector('dialog[open]'))return;
      event.preventDefault();navigate('assistant');$('chat-input').focus();
    }
  });
  window.addEventListener('hashchange',()=>navigate(location.hash.slice(1)||'overview'));
  navigate(location.hash.slice(1)||'overview',{focus:false});syncStatus();load();
  // Expiry-driven local refresh, not routine polling.
}
function scheduleExpiryRefresh(){
  clearTimeout(expiryTimer);
  const future=app.data.pending.map(p=>Date.parse(p.expires_at)).filter(at=>Number.isFinite(at)&&at>Date.now());
  if(!future.length)return;
  expiryTimer=setTimeout(()=>{if(!app.busy)refresh();else scheduleExpiryRefresh();},Math.min(2147483647,Math.max(50,Math.min(...future)-Date.now()+50)));
}

setup();
