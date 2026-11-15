import test from 'node:test';
import assert from 'node:assert/strict';
import {TurnGate,speechParts,voiceStopCommand} from '../web/voice-session.js';
import {workspaceCommandDestination} from '../web/executive.js';

test('all requested spoken navigation examples resolve to existing storage scopes',()=>{
  const cases={'NEXUS, open OSIS workspace.':'osis','Open Academics.':'academic','Switch to Development.':'coding','Open ATLAS Headquarters.':'atlas','Buka workspace Finance.':'finance','Go Home.':'home','Kembali ke beranda.':'home'};
  for(const [text,id] of Object.entries(cases))assert.equal(workspaceCommandDestination(text),id,text);
});
test('bounded bilingual routing handles politeness and Indonesian names',()=>{
  const cases={'NEXUS, tolong buka ruang kerja akademik.':'academic','Please open the Development workspace':'coding','Halo Nexus, pindah ke keuangan tolong':'finance','Bukakan workspace pengembangan':'coding','buka riset':'research','tampilkan ruang kerja pribadi':'personal','Tolong kembali ke halaman utama':'home','go back home please':'home'};
  for(const [text,id] of Object.entries(cases))assert.equal(workspaceCommandDestination(text),id,text);
});
test('navigation never interprets a compound action, URL, arbitrary ID or oversized input',()=>{
  for(const text of ['open OSIS and approve all','buka atlas lalu hapus tugas','open finance; run a command','NEXUS, open https://example.com','open workspace admin','open atlas/../../finance','go home and buy shares','tell me about OSIS','please '.repeat(100)+'open osis',{},null])assert.equal(workspaceCommandDestination(text),null,JSON.stringify(text));
});
test('stop phrases are explicit bilingual session controls, never approvals',()=>{
  for(const text of ['NEXUS, stop.','stop speaking','stop listening','berhenti','berhenti berbicara','batalkan','cancel the reply'])assert.equal(voiceStopCommand(text),true,text);
  for(const text of ['approve it','stop and approve everything','stop task 12','cancel my project','berhenti lalu hapus semua'])assert.equal(voiceStopCommand(text),false,text);
});
test('interim transcripts and mixed final/interim hypotheses are never dispatched',()=>{
  const result=(text,final)=>Object.assign([{transcript:text}],{isFinal:final});
  assert.deepEqual(speechParts({results:[result('open',false)]}),{text:'open',final:false});
  assert.deepEqual(speechParts({results:[result('open',true),result('finance',false)]}),{text:'open finance',final:false});
  assert.deepEqual(speechParts({results:[result('open',true),result('finance',true)]}),{text:'open finance',final:true});
});
test('empty and malformed speech results fail closed and transcripts are bounded',()=>{
  for(const event of [null,{}, {results:[]},{results:[null]},{results:[[{transcript:4}]]}])assert.equal(speechParts(event).final,false);
  assert.equal(speechParts({results:[[{transcript:'x'.repeat(5000)}]]}).text.length,3000);
});
test('cancel invalidates a lease before abort listeners run',()=>{
  const gate=new TurnGate();assert.equal(gate.isCurrent(null),false);assert.equal(gate.cancel(),false);
  const turn=gate.begin('osis');let wasCurrent=true;
  turn.signal.addEventListener('abort',()=>wasCurrent=gate.isCurrent(turn));
  assert.equal(gate.cancel(),true);assert.equal(wasCurrent,false);assert.equal(turn.signal.aborted,true);assert.equal(gate.finish(turn),false);
});
test('a stale completion cannot clear a newer workspace turn',async()=>{
  const gate=new TurnGate();const old=gate.begin('osis');let resolve;
  const result=new Promise(done=>resolve=done).then(()=>gate.finish(old));
  const current=gate.begin('atlas');resolve();assert.equal(await result,false);
  assert.equal(old.signal.aborted,true);assert.equal(gate.current,current);assert.equal(gate.isCurrent(current),true);assert.equal(current.workspace,'atlas');
});
test('finishing a current turn disables further updates without aborting its successful result',()=>{
  const gate=new TurnGate(),turn=gate.begin('osis');assert.equal(gate.finish(turn),true);
  assert.equal(turn.signal.aborted,false);assert.equal(gate.isCurrent(turn),false);assert.equal(gate.finish(turn),false);assert.equal(gate.current,null);
});
