import test from 'node:test';
import assert from 'node:assert/strict';
import {localDay,priorityOrder,selectTasks,isExpired,dueText} from '../web/domain.js';

test('local day respects configured timezone on date boundaries',()=>{
  const now=new Date('2026-11-07T00:30:00Z');
  assert.equal(localDay('America/Los_Angeles',now),'2026-11-06');
  assert.equal(localDay('Asia/Jakarta',now),'2026-11-07');
});
const tasks=[
  {id:1,title:'Future high',owner:'Owner',priority:'high',status:'todo',due_date:'2026-11-10'},
  {id:2,title:'Overdue low',owner:'Team',priority:'low',status:'doing',due_date:'2026-11-01'},
  {id:3,title:'Undated high',owner:'Owner',priority:'high',status:'todo',due_date:''},
  {id:4,title:'Complete',owner:'Team',priority:'medium',status:'done',due_date:'2026-10-01'},
];
test('deterministic priorities put overdue open work before future high priority',()=>{
  assert.deepEqual(tasks.filter(t=>t.status!=='done').sort((a,b)=>priorityOrder(a,b,'2026-11-07')).map(t=>t.id),[2,1,3]);
});
test('task filters combine assignee, status and priority without changing source data',()=>{
  const original=JSON.stringify(tasks);
  assert.deepEqual(selectTasks(tasks,{query:'owner',status:'todo',priorityFilter:'high',sort:'deadline',today:'2026-11-07'}).map(t=>t.id),[1,3]);
  assert.deepEqual(selectTasks(tasks,{query:'no matching text'}),[]);
  assert.equal(JSON.stringify(tasks),original);
});
test('expiry fails closed for malformed timestamps and exact boundary',()=>{
  const now=Date.parse('2026-11-07T10:00:00Z');
  assert.equal(isExpired({expires_at:'invalid'},now),true);
  assert.equal(isExpired({expires_at:'2026-11-07T10:00:00Z'},now),true);
  assert.equal(isExpired({expires_at:'2026-11-07T11:00:00Z'},now),false);
});
test('completed work is not labeled overdue and missing dates are explicit',()=>{
  assert.equal(dueText(tasks[2],'2026-11-07'),'No deadline');
  assert.equal(dueText(tasks[1],'2026-11-07').startsWith('Overdue'),true);
  assert.equal(dueText(tasks[3],'2026-11-07').startsWith('Overdue'),false);
});
