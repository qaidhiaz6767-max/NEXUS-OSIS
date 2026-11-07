import {app, VIEW_NAMES} from './state.js';
import {$, all, el, clear, icon, button, badge, empty as makeEmpty, detailsList, richText} from './ui.js';
import {STATUS, SOURCE, localDay, dayLabel, timestamp, dueText, priorityOrder, selectTasks, isExpired, actionTitle} from './domain.js';

let actions = {};
export function bindActions(handlers) { actions=handlers; }
export const currentWorkspace = () => app.workspaces.find(w=>w.id===app.workspace) || {id:app.workspace,label:app.workspace.toUpperCase(),domain:'local',capabilities:app.data.capabilities||[]};
export const today = () => localDay(app.data.timezone || 'Asia/Jakarta');
const zone = () => app.data.timezone || 'Asia/Jakarta';
const can = capability => !app.stale && (app.data.capabilities||[]).includes(capability);
function empty(...args){const node=makeEmpty(...args);for(const control of node.querySelectorAll('button')){control.dataset.capability='propose';control.disabled=app.busy||!can('propose');}return node;}
const titleCase = value => value ? value.charAt(0).toUpperCase()+value.slice(1) : '';
const dateTile = day => { const node=el('div','date-tile');node.append(el('strong','',day.slice(8,10)),el('span','',dayLabel(day,{day:undefined,month:'short'}).toUpperCase()));return node; };
const countLabel = (number,noun) => `${number} ${noun}${number===1?'':'s'}`;
const inlineEmpty = text => el('p','inline-empty',text);

export function renderSystem() {
  const data=app.data,w=currentWorkspace(),status=data.system||{};
  $('workspace-label').textContent=w.label.toUpperCase()+' · '+(w.domain||'local').toUpperCase();
  $('workspace-initial').textContent=w.label.slice(0,1);
  for(const node of all('[data-workspace-label]'))node.textContent=w.label;
  $('local-status').replaceChildren(el('span','status-dot'),document.createTextNode('Local core online'));
  $('local-status').dataset.state='online';
  const aiLabel=status.ai==='verified'?'AI responded · verified':status.ai==='error'?'AI request failed':status.ai==='configured'?'AI configured · unverified':'AI off · local commands';
  $('mode-label').textContent=aiLabel;$('assistant-mode').textContent=aiLabel;
  $('home-command-hint').textContent=status.ai==='configured'||status.ai==='verified'?'Active-workspace context may be sent to AI':'Use /brief or /help in offline mode';
  const now=new Date();
  const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:zone(),hour:'2-digit',hourCycle:'h23'}).format(now));
  $('welcome-title').textContent=`Good ${hour<12?'morning':hour<18?'afternoon':'evening'}. What’s our next move?`;
  $('today-label').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:zone(),weekday:'short',day:'numeric',month:'long',year:'numeric'}).format(now);
  $('calendar-timezone').textContent='All event times are local to '+zone()+'. Events without a time are marked “Time not set”.';
  $('memory-scope').textContent='Searching '+w.label+' only · facts, projects, notes and saved conversation history.';
  $('environment-banner').hidden=!data.demo;
  $('environment-banner').textContent='DEMO WORKSPACE · Invented sample records. Changes are temporary and disappear when you stop NEXUS.';
  $('summary-scope').textContent=w.label+' workspace · stored records';
  for(const link of all('a[data-export]')){
    const path=link.dataset.export==='calendar'?'/api/calendar.ics':'/api/backup';
    link.href=path+'?workspace='+encodeURIComponent(app.workspace);
    if(!can('export')){link.setAttribute('aria-disabled','true');link.removeAttribute('href');link.title='Export permission is not granted';}else{link.removeAttribute('aria-disabled');link.removeAttribute('title');}
  }
  for(const control of all('[data-create],.command-submit,#send-button,#chat-input,#home-input')) control.disabled=app.busy||!can('propose');
  const details=[['Version',status.version||'0.4 development'],['Workspace',w.label],['Domain',titleCase(w.domain)],['Storage',data.demo?'Temporary demo records':'Persistent local SQLite'],['Timezone',zone()],['AI status',aiLabel],['Permissions',(data.capabilities||[]).join(', ')||'Read only'],['Privacy','Active-workspace context only; cloud AI requires explicit startup opt-in.']];
  $('system-details').replaceChildren(detailsList(details));
}
export function renderMetrics() {
  const data=app.data,summary=data.summary||{},open=data.tasks.filter(t=>t.status!=='done');
  const pending=data.pending.filter(p=>!isExpired(p));
  $('metric-projects').textContent=summary.active_projects??data.projects.filter(p=>p.status==='active').length;
  $('metric-open').textContent=summary.open_tasks??open.length;
  $('metric-events').textContent=summary.upcoming_events??data.events.filter(e=>e.day>=today()).length;
  $('metric-pending').textContent=summary.pending_approvals??pending.length;
  $('metric-due').textContent=(summary.overdue_tasks??open.filter(t=>t.due_date&&t.due_date<today()).length)+' overdue · '+(summary.due_soon??open.filter(t=>t.due_date===today()).length)+' due in 7 days';
  $('nav-task-count').textContent=$('metric-open').textContent;
  $('nav-pending-count').textContent=$('metric-pending').textContent;
  $('approval-indicator').setAttribute('aria-label','Review '+$('metric-pending').textContent+' pending approvals');
}
export function renderOverview() {
  const panel=$('overview-tasks');clear(panel);
  const priorities=app.data.tasks.filter(t=>t.status!=='done').sort((a,b)=>priorityOrder(a,b,today())).slice(0,4);
  if(!priorities.length)panel.append(empty('A clear runway.','No open tasks in this workspace. Give your next action a place to land.','Create a task',()=>actions.create('task'),'tasks'));
  priorities.forEach((task,index)=>{
    const row=el('div','priority-row'),copy=el('div','priority-copy');
    copy.append(button(task.title,()=>showTask(task),'record-link'),el('small','',task.owner+' · '+STATUS[task.status]));
    row.append(el('span','rank-number',String(index+1).padStart(2,'0')),copy,el('span','due-label'+(task.due_date&&task.due_date<today()?' overdue':''),dueText(task,today())));panel.append(row);
  });
  const calendar=$('overview-events');clear(calendar);
  const events=app.data.events.filter(e=>e.day>=today()).slice(0,3);
  if(!events.length)calendar.append(empty('Room for what’s next.','Upcoming events will appear here.','Plan an event',()=>actions.create('event'),'calendar'));
  for(const event of events){const row=el('div','mini-event'),copy=el('div','mini-event-copy');copy.append(button(event.title,()=>showEvent(event),'record-link'),el('small','',(event.time||'Time not set')+' · '+(event.location||'Location not set')));row.append(dateTile(event.day),copy);calendar.append(row);}
  $('context-summary').textContent=`${countLabel(Number($('metric-open').textContent),'open task')} and ${countLabel(Number($('metric-projects').textContent),'active project')} in ${currentWorkspace().label}.`;
  $('context-priorities').replaceChildren(...priorities.slice(0,2).map(task=>{const item=el('div','context-item');item.append(el('strong','',task.title),el('small','',dueText(task,today())+' · '+task.owner));return item;}));
  $('chat-approval-notice').textContent=$('metric-pending').textContent==='0'?'No changes waiting for review.':$('metric-pending').textContent+' proposed changes awaiting your decision.';
}
export function renderProjects() {
  const query=$('project-search').value.trim().toLowerCase(),filter=$('project-filter').value,sort=$('project-sort').value;
  const projects=app.data.projects.filter(p=>(filter==='all'||p.status===filter)&&(!query||`${p.title} ${p.goal}`.toLowerCase().includes(query))).sort((a,b)=>sort==='name'?a.title.localeCompare(b.title):b.id-a.id);
  const panel=$('project-list');clear(panel);$('project-result-count').textContent=countLabel(projects.length,'project');
  if(!projects.length){panel.append(empty(app.data.projects.length?'No projects match.':'Everything starts with a clear goal.',app.data.projects.length?'Try another search or status.':'Give an idea a name and a direction. Your projects stay in this workspace.',app.data.projects.length?null:'New project',()=>actions.create('project'),'projects'));return;}
  for(const project of projects){const card=el('article','project-card'),top=el('div','record-card-top'),symbol=el('span','project-symbol'),footer=el('div','project-card-footer');symbol.append(icon('projects'));top.append(symbol,badge(STATUS[project.status]||project.status,project.status));footer.append(el('span','',currentWorkspace().label+' · '+dayLabel(project.created_at)),button('Open project',()=>showProject(project),'text-button','arrow'));card.append(top,el('h2','',project.title),el('p','',project.goal),footer);panel.append(card);}
}
export function renderTasks() {
  const rows=selectTasks(app.data.tasks,{query:$('task-search').value,status:$('task-filter').value,priorityFilter:$('task-priority').value,sort:$('task-sort').value,today:today()});
  $('task-result-count').textContent=countLabel(rows.length,'task');const body=$('task-table-body');clear(body);
  $('tasks-empty').hidden=rows.length!==0;
  if(!rows.length)$('tasks-empty').replaceChildren(empty(app.data.tasks.length?'No tasks match.':'Let’s make the next step clear.',app.data.tasks.length?'Try changing your search or filters.':'Create a task, review the proposal and approve it when you’re ready.',app.data.tasks.length?null:'Create a task',()=>actions.create('task'),'tasks'));
  for(const task of rows){
    const row=el('tr');
    const cell=(label,node)=>{const td=el('td');td.dataset.label=label;td.append(typeof node==='string'?document.createTextNode(node):node);row.append(td);return td;};
    const name=el('div');name.append(button(task.title,()=>showTask(task),'record-link task-title'),el('span','task-id','#'+task.id+' · '+currentWorkspace().label));
    cell('Task',name);cell('Assignee',task.owner);cell('Deadline',el('span',task.due_date&&task.due_date<today()&&task.status!=='done'?'due-label overdue':'',dueText(task,today())));cell('Priority',badge(titleCase(task.priority),task.priority));cell('Status',badge(STATUS[task.status],task.status));
    const controls=el('div','row-actions');const assign=button('Assign',()=>actions.create('assign',task),'tiny-action');assign.setAttribute('aria-label','Change assignee of '+task.title);
    const status=task.status==='todo'?'doing':task.status==='doing'?'done':'todo';const change=button(task.status==='todo'?'Start':task.status==='doing'?'Complete':'Reopen',()=>actions.propose('set_task_status',{task_id:task.id,status}),'tiny-action');
    assign.dataset.capability=change.dataset.capability='propose';
    assign.disabled=change.disabled=!can('propose')||app.busy;controls.append(assign,change);cell('Actions',controls);body.append(row);
  }
}
export function renderEvents() {
  const panel=$('event-list');clear(panel);
  if(!app.data.events.length){panel.append(empty('A little room to plan.','Add a meeting, an event or an important commitment to your local agenda.','Plan an event',()=>actions.create('event'),'calendar'));return;}
  const groups=new Map();
  // Upcoming first; keep older events accessible after the upcoming agenda.
  const rows=[...app.data.events].sort((a,b)=>(a.day<today())-(b.day<today())||a.day.localeCompare(b.day)||a.time.localeCompare(b.time));
  for(const event of rows){if(!groups.has(event.day))groups.set(event.day,[]);groups.get(event.day).push(event);}
  for(const [day,events] of groups){const group=el('section'),heading=el('h2','agenda-day-heading',(day===today()?'TODAY · ':day<today()?'PAST · ':'')+dayLabel(day,{weekday:'long',year:'numeric'}));group.append(heading);
    for(const event of events){const card=el('article','agenda-event'),time=el('div','agenda-time',event.time||'—'),copy=el('div','event-copy'),meta=el('div','event-meta');time.append(el('small','',event.time?zone():'Time not set'));copy.append(el('h2','',event.title));if(event.details)copy.append(el('p','',event.details));const location=el('span','',event.location||'Location not set');location.prepend(icon('pin'));meta.append(location,el('span','',currentWorkspace().label));copy.append(meta,button('View details',()=>showEvent(event),'text-button','arrow'));card.append(time,copy);group.append(card);}panel.append(group);
  }
}
export function renderNotes() {
  const panel=$('notes-list');clear(panel);
  if(!app.data.notes.length){panel.append(empty('Keep the important context.','Draft meeting notes, review the wording and approve them to save.','Add meeting notes',()=>actions.create('note'),'meetings'));return;}
  for(const note of app.data.notes){const card=el('article','note-card'),top=el('div','record-top');top.append(badge('Approved note','approved'),el('span','',timestamp(note.created_at,zone())));card.append(top,el('h2','',note.title),el('p','record-body',note.body.slice(0,400)+(note.body.length>400?'…':'')),button('Read notes',()=>showNote(note),'text-button','arrow'));panel.append(card);}
}
function factCard(memory) {
  const card=el('article','memory-card'),top=el('div','record-top'),source=el('span','memory-source',SOURCE[memory.source]||'Source not recorded');source.prepend(icon(memory.source==='ai'?'core':'user'));top.append(source,el('span','',dayLabel(memory.updated_at)));
  card.append(top,el('h2','',memory.key),el('p','record-body',memory.value));
  const controls=el('div','record-actions');
  const details=button('Provenance',()=>showMemory(memory),'tiny-action');
  const edit=button('Update',()=>actions.create('memory',memory),'tiny-action'),remove=button('Delete',()=>actions.propose('forget',{key:memory.key}),'tiny-action destructive');
  edit.dataset.capability=remove.dataset.capability='propose';
  edit.disabled=remove.disabled=!can('propose')||app.busy;controls.append(details,edit,remove);card.append(controls);return card;
}
export function renderMemory() {
  const panel=$('memory-list'),results=$('memory-results');clear(panel);clear(results);const source=$('memory-source').value;
  if(app.memoryResults!==null){const data=app.memoryResults;
    for(const [category,label] of [['facts','Saved facts'],['projects','Project context'],['notes','Saved meeting notes'],['history','Conversation history · not verified facts']]){
      if(source!=='all'&&category!=='facts')continue;
      const rows=(data[category]||[]).filter(r=>category!=='facts'||source==='all'||r.source===source);if(!rows.length)continue;
      const group=el('section','search-category');group.append(el('h2','',label+' · '+rows.length));
      for(const row of rows){if(category==='facts'){group.append(factCard(row));continue;}const card=el('article','search-record');card.append(el('h3','',row.title||(row.role==='user'?'You':'NEXUS')),el('p','',(row.goal||row.body||row.content||'').slice(0,1000)));if(category==='history')card.append(el('small','',timestamp(row.at,zone())+' · Conversation text, not a saved fact'));group.append(card);}results.append(group);
    }
    if(!results.children.length)results.append(empty('No matching context.','Try another phrase or source filter. Search is limited to this workspace.',null,null,'search'));return;
  }
  const facts=app.data.memories.filter(m=>source==='all'||m.source===source);
  if(!facts.length){panel.append(empty(app.data.memories.length?'No facts from this source.':'Build a little continuity.','Save a useful fact or preference. NEXUS keeps its source and your approval with it.',app.data.memories.length?null:'Save a fact',()=>actions.create('memory'),'memory'));return;}
  for(const memory of facts)panel.append(factCard(memory));
}
export function approvalCard(item,{compact=false}={}) {
  const workspace=app.workspace,expired=isExpired(item),card=el('article',compact?'inline-action-card':'approval-card');
  const header=el('div','approval-heading'),symbol=el('span');symbol.append(icon('shield'));const heading=el('div');heading.append(el('h2','',actionTitle(item.name)),el('small','',currentWorkspace().label+' · '+(expired?'Expired':'Awaiting approval')));header.append(symbol,heading);card.append(header,el('p','',item.description));
  let args;try{args=JSON.parse(item.args_json);}catch{args={};}
  if(item.name==='forget')card.append(el('p','small-muted','This removes the saved fact and its provenance. Earlier chat, audit entries and exports are retained.'));
  const details=el('details'),summary=el('summary','',item.name==='execute_plan'?'Review every step and exact argument':'Review the exact proposed values');details.append(summary,el('pre','approval-details',JSON.stringify(args,null,2)));card.append(details);
  const footer=el('div','approval-controls');if(expired)card.append(el('p','expired-note','This proposal expired. It cannot be approved. Dismiss it and request a new proposal if needed.'));else footer.append(el('span','small-muted','Expires '+timestamp(item.expires_at,zone())));
  const reject=button(expired?'Dismiss expired':'Reject',()=>actions.decide(item.id,false,workspace),'button approval-no');reject.disabled=!can('approve')||app.busy;footer.append(reject);
  if(!expired){const approve=button('Approve',()=>actions.decide(item.id,true,workspace),'button approval-yes');approve.disabled=!can('approve')||app.busy;footer.append(approve);}
  card.append(footer);return card;
}
export function renderApprovals() {
  const panel=$('approvals-list');clear(panel);
  if(!app.data.pending.length){panel.append(empty('You’re all caught up.','Proposed changes appear here before they become records.',null,null,'shield'));return;}
  for(const item of app.data.pending)panel.append(approvalCard(item));
}
export function renderChat() {
  const panel=$('chat-messages');const signature=app.workspace+':'+app.data.messages.map(m=>m.id+':'+m.content).join('|')+':'+app.data.pending.map(p=>p.id+p.expires_at+isExpired(p)).join('|')+':'+app.busy;
  if(signature===app.messageSignature)return;app.messageSignature=signature;
  const nearBottom=panel.scrollHeight-panel.scrollTop-panel.clientHeight<90;
  const wanted=new Set(app.data.messages.map(message=>String(message.id)));
  const existing=new Map([...panel.querySelectorAll('[data-message-id]')].map(node=>[node.dataset.messageId,node]));
  for(const [id,node] of existing)if(!wanted.has(id))node.remove();
  for(const node of panel.querySelectorAll('.inline-action-card,.processing-notice'))node.remove();
  if(app.data.messages.length)panel.querySelector('.conversation-intro')?.remove();
  if(!app.data.messages.length&&!panel.querySelector('.conversation-intro')){const intro=el('div','chat-item assistant conversation-intro'),avatar=el('div','chat-avatar','N'),body=el('div','chat-content');body.append(el('div','chat-by','NEXUS'),richText('A clear place to think.\n\nI can help organize tasks, projects, events and approved facts in '+currentWorkspace().label+'. Start with /brief, or use /help to see what’s available.\n\nNatural-language AI needs a separately configured model. Your changes always wait for approval.'));intro.append(avatar,body);panel.append(intro);}
  for(const message of app.data.messages){if(existing.has(String(message.id)))continue;const row=el('article','chat-item '+message.role);row.dataset.messageId=String(message.id);const avatar=el('div','chat-avatar',message.role==='user'?'YOU':'N'),body=el('div','chat-content');body.append(el('div','chat-by',message.role==='user'?'YOU':'NEXUS'),richText(message.content));const copy=button('Copy',()=>actions.copy(message.content),'text-button copy-message','copy');copy.setAttribute('aria-label','Copy '+(message.role==='user'?'your':'NEXUS')+' message');body.append(copy);row.append(avatar,body);panel.append(row);}
  for(const item of app.data.pending.slice(0,3))panel.append(approvalCard(item,{compact:true}));
  if(app.busy)panel.append(el('p','small-muted processing-notice','Processing your request…'));
  if(nearBottom||app.busy){
    panel.scrollTop=panel.scrollHeight;
    if(!app.busy&&panel.scrollHeight>panel.clientHeight){
      const newest=panel.querySelector('.inline-action-card')||[...panel.querySelectorAll('.chat-item')].at(-1);
      if(newest)panel.scrollTop+=newest.getBoundingClientRect().top-panel.getBoundingClientRect().top-16;
    }
  }
}
export function renderActivity() {
  const panel=$('activity-list');clear(panel);
  if(!app.data.audit.length){panel.append(empty('A fresh start.','Proposals and approval outcomes will leave a record here.',null,null,'activity'));return;}
  for(const item of app.data.audit){const row=el('article','activity-row'),mark=el('span','activity-icon'),copy=el('div');mark.append(icon(item.event==='approved'?'check':item.event==='rejected'?'close':item.event.includes('error')?'info':'shield'));copy.append(el('h2','',item.event.replaceAll('_',' ')),el('p','',item.detail));const time=el('time','',timestamp(item.at,zone()));time.dateTime=item.at;row.append(mark,copy,time);panel.append(row);}
}
export function renderAll() {renderSystem();renderMetrics();renderOverview();renderProjects();renderTasks();renderEvents();renderNotes();renderMemory();renderApprovals();renderChat();renderActivity();}

function openDetail(title,kicker,children) {
  app.focusReturn=document.activeElement;$('detail-title').textContent=title;$('detail-kicker').textContent=kicker+' / '+currentWorkspace().label.toUpperCase();$('detail-content').replaceChildren(...children);$('detail-modal').showModal();
}
function section(title,content) {const wrap=el('section','detail-section');wrap.append(el('h3','',title),el('p','',content));return wrap;}
function showProject(project) {openDetail(project.title,'PROJECT',[badge(STATUS[project.status]||project.status,project.status),el('p','record-body',project.goal),detailsList([['Workspace',currentWorkspace().label],['Created',timestamp(project.created_at,zone())],['Coordinator','Not recorded'],['Deadline','Not recorded']]),section('Milestones & associated tasks','The current Core stores projects as goal records. Milestones, task links, project notes and related-event associations are not yet supported; no connections are inferred.')]);}
function showTask(task) {openDetail(task.title,'TASK #'+task.id,[badge(STATUS[task.status],task.status),detailsList([['Workspace',currentWorkspace().label],['Assignee',task.owner],['Deadline',task.due_date?dayLabel(task.due_date,{year:'numeric'}):'Not set'],['Priority',titleCase(task.priority)],['Created',timestamp(task.created_at,zone())],['Notification','Not sent · local assignment only'],['Acknowledgment','Not tracked']]),section('Task description','This version stores task titles, assignees, deadlines, priority and status. A separate description field is not yet supported.')]);}
function showEvent(event) {openDetail(event.title,'CALENDAR EVENT',[detailsList([['Workspace',currentWorkspace().label],['Date',dayLabel(event.day,{year:'numeric'})],['Time',event.time||'Not set'],['Timezone',zone()],['Location',event.location||'Not set']]),el('p','record-body',event.details||'No event details recorded.')]);}
function showNote(note) {openDetail(note.title,'APPROVED MEETING NOTE',[badge('Approved to save · not independently verified','approved'),detailsList([['Workspace',currentWorkspace().label],['Saved',timestamp(note.created_at,zone())]]),el('p','record-body',note.body),section('Record scope','This is an approved note. It does not separately verify participants, decisions or follow-up completion.')]);}
function showMemory(memory) {openDetail(memory.key,'SAVED FACT',[el('p','record-body',memory.value),detailsList([['Workspace',currentWorkspace().label],['Source',SOURCE[memory.source]||'Not recorded'],['Created',timestamp(memory.created_at,zone())],['Last updated',timestamp(memory.updated_at,zone())],['Approved',timestamp(memory.approved_at,zone())],['Approval ID',memory.approval_id||'Legacy record · no approval identifier']]),section('What approval means','You approved saving this information. Approval does not independently verify a statement’s factual accuracy.')]);}
