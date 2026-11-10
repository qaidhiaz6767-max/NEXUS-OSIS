import test from 'node:test';
import assert from 'node:assert/strict';
import {WORKSPACES,greetingAt,orbState,runIntro,workspaceCommandDestination} from '../web/executive.js';

test('five portal labels retain canonical storage IDs',()=>{
 assert.deepEqual(WORKSPACES.map(w=>[w.label,w.id]),[['OSIS','osis'],['Academics','academic'],['Development','coding'],['ATLAS','atlas'],['Finance','finance']]);
 assert.deepEqual(WORKSPACES[0].sections.map(s=>s[0]),['Programs','Tasks','Meetings','Documents','Team','Budget']);
 assert.ok(WORKSPACES.every(w=>w.sections.length===6));
});
test('greeting follows the configured zone at noon, evening and date boundaries',()=>{
 for(const [date,zone,expected] of [['2026-11-07T04:59:00Z','Asia/Jakarta','morning'],['2026-11-07T05:00:00Z','Asia/Jakarta','afternoon'],['2026-11-07T11:00:00Z','Asia/Jakarta','evening'],['2026-11-07T18:00:00Z','Asia/Jakarta','morning'],['2026-11-07T18:00:00Z','Europe/London','evening']])assert.equal(greetingAt(new Date(date),zone),`Good ${expected}, Qai.`);
});
test('startup waits for real readiness, preserving order and exposing failure',async()=>{
 let finish;const stages=[];const ready=new Promise(r=>finish=r);
 const run=runIntro({initialize:()=>ready,stage:s=>stages.push(s),wait:()=>Promise.resolve()});
 await new Promise(r=>setImmediate(r));assert.deepEqual(stages,['greeting','formation','initializing']);
 finish(true);assert.equal(await run,true);assert.deepEqual(stages,['greeting','formation','initializing','ready','home']);
 const failed=[];assert.equal(await runIntro({initialize:async()=>false,stage:s=>failed.push(s),wait:async()=>{}}),false);assert.deepEqual(failed,['greeting','formation','initializing','error']);
});
test('skip and reduced motion never bypass actual readiness',async()=>{
 let finish;const stages=[];const run=runIntro({initialize:()=>new Promise(r=>finish=r),stage:s=>stages.push(s),wait:async()=>{},skip:()=>true,reduced:true});
 await new Promise(r=>setImmediate(r));assert.equal(stages.at(-1),'initializing');finish(false);await run;assert.equal(stages.at(-1),'error');
});
test('orb responds only to real request/audio state, including errors',()=>{
 assert.equal(orbState(),'idle');assert.equal(orbState({busy:true}),'thinking');assert.equal(orbState({audio:'listening'}),'listening');assert.equal(orbState({audio:'speaking'}),'speaking');assert.equal(orbState({busy:true,error:true}),'error');assert.equal(orbState({audio:'starting'}),'idle');
});

test('spoken and typed workspace commands map only to known local workspace IDs',()=>{
 const accepted={
  'open OSIS workspace':'osis',
  'NEXUS, open workspace OSIS':'osis',
  'Hey Nexus, switch to the Academics workspace':'academic',
  'show my development dashboard':'coding',
  'open ATLAS':'atlas',
  'go to the Finance workspace please':'finance',
  'buka workspace osis':'osis',
  'pindah ke ruang kerja atlas':'atlas',
  'open personal workspace':'personal',
  'show research':'research'
 };
 for(const [phrase,destination] of Object.entries(accepted))
  assert.equal(workspaceCommandDestination(phrase),destination,phrase);
 for(const phrase of [
  'approve all pending changes',
  'open a finance transaction',
  'delete OSIS workspace',
  'open https://example.com',
  'open external workspace',
  'open a new tab',
  '',
  'Please open the system settings'
 ])assert.equal(workspaceCommandDestination(phrase),null,phrase);
});
