export const STATUS = {todo:'To do', doing:'In progress', done:'Completed', active:'Active', planned:'Planned', on_hold:'On hold', completed:'Completed', archived:'Archived'};
export const SOURCE = {command:'User-provided', ai:'AI-suggested · approved', legacy:'Legacy record'};
export function localDay(timezone='Asia/Jakarta', now=new Date()) {
  return new Intl.DateTimeFormat('sv-SE',{timeZone:timezone, year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
}
export function dayLabel(value, options={}) {
  if (!value) return 'No deadline';
  const day = new Date(value.slice(0,10)+'T12:00:00Z');
  if (Number.isNaN(day.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',day:'numeric',month:'short',...options}).format(day);
}
export function timestamp(value, timezone='Asia/Jakarta') {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-GB',{timeZone:timezone,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(date);
}
export function dueText(task, today) {
  if (!task.due_date) return 'No deadline';
  if (task.status!=='done' && task.due_date<today) return 'Overdue · '+dayLabel(task.due_date);
  if (task.due_date===today) return 'Today';
  return dayLabel(task.due_date);
}
const priority = {high:0,medium:1,low:2};
export function priorityOrder(a,b,today) {
  const overdue = t => t.status!=='done' && t.due_date && t.due_date<today ? 0 : 1;
  return overdue(a)-overdue(b) || (priority[a.priority]??3)-(priority[b.priority]??3) || (a.due_date||'9999').localeCompare(b.due_date||'9999') || a.id-b.id;
}
export function selectTasks(tasks,{query='',status='all',priorityFilter='all',sort='deadline',today}={}) {
  query=query.trim().toLowerCase();
  const rows=tasks.filter(t=>(status==='all'||t.status===status)&&(priorityFilter==='all'||t.priority===priorityFilter)&&(!query||`${t.title} ${t.owner} ${t.id}`.toLowerCase().includes(query)));
  return rows.sort((a,b)=>sort==='priority'?priorityOrder(a,b,today):sort==='newest'?b.id-a.id:(a.due_date||'9999').localeCompare(b.due_date||'9999') || priorityOrder(a,b,today));
}
export const isExpired = (item, now=Date.now()) => !Number.isFinite(Date.parse(item.expires_at)) || Date.parse(item.expires_at)<=now;
export function actionTitle(name) {
  return {create_task:'Create task',set_task_status:'Change task status',assign_task:'Assign task',create_project:'Create project',create_event:'Create event',create_note:'Save meeting notes',remember:'Save or update a fact',forget:'Delete saved fact',execute_plan:'Approve a multistep plan'}[name]||'Proposed action';
}
