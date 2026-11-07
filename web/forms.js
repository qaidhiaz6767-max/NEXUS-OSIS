import {app} from './state.js';
import {$, el} from './ui.js';
import {currentWorkspace} from './views.js';
const fields = {
  task:[['title','Task title','text',240,true],['owner','Assignee','text',100,false],['due_date','Deadline','date',10,false],['priority','Priority','select',0,true]],
  project:[['title','Project name','text',240,true],['goal','Goal or description','textarea',2000,true]],
  event:[['title','Event title','text',240,true],['day','Date','date',10,true],['time','Time','time',5,false],['location','Location','text',180,false],['details','Event details','textarea',1500,false]],
  note:[['title','Meeting or note title','text',240,true],['body','Notes, context and follow-up actions','textarea',5000,true]],
  memory:[['key','Fact or reference name','text',100,true],['value','Information to save','textarea',2000,true]],
  assign:[['owner','New assignee','text',100,true]],
};
const titles={task:'New task',project:'New project',event:'Plan an event',note:'Meeting notes',memory:'Save a fact',assign:'Change assignee'};
export function openForm(type,record=null) {
  if(app.busy||app.stale||!(app.data.capabilities||[]).includes('propose')||!fields[type])return;
  app.focusReturn=document.activeElement;app.modal={type,record,workspace:app.workspace};
  $('modal-title').textContent=type==='memory'&&record?'Update a saved fact':titles[type];
  $('modal-workspace').textContent=currentWorkspace().label+' · changes require your approval';
  $('form-error').hidden=true;const wrap=$('modal-fields');wrap.replaceChildren();
  for(const [name,label,kind,max,required] of fields[type]){
    const group=el('div','form-field'),title=el('label','',label+(required?' *':''));title.htmlFor='field-'+name;
    let field;
    if(kind==='textarea')field=el('textarea');
    else if(kind==='select'){field=el('select');for(const value of ['medium','high','low']){const option=el('option','',value.charAt(0).toUpperCase()+value.slice(1));option.value=value;field.append(option);}}
    else{field=el('input');field.type=kind;}
    field.id='field-'+name;field.name=name;field.required=required;if(max&&['text','textarea'].includes(kind))field.maxLength=max;
    if(type==='assign')field.value=record?.owner||'';
    if(type==='memory'&&record)field.value=record[name]||'';
    if(name==='owner'&&type!=='assign')field.placeholder='Unassigned';
    group.append(title,field);
    if(name==='time')group.append(el('small','', 'Local time in '+(app.data.timezone||'Asia/Jakarta')));
    if(name==='body')group.append(el('small','', 'Your notes are a draft until you review and approve the proposal.'));
    wrap.append(group);
  }
  $('create-modal').showModal();wrap.querySelector('input,textarea,select')?.focus();
}
export function formAction() {
  if(!app.modal||app.modal.workspace!==app.workspace)throw new Error('The workspace changed. Close the form and create a new proposal.');
  const args=Object.fromEntries(new FormData($('create-form')).entries());
  const names={task:'create_task',project:'create_project',event:'create_event',note:'create_note',memory:'remember',assign:'assign_task'};
  if(app.modal.type==='task')args.owner=args.owner.trim()||'Unassigned';
  if(app.modal.type==='assign')args.task_id=app.modal.record.id;
  return {name:names[app.modal.type],args,workspace:app.modal.workspace};
}
