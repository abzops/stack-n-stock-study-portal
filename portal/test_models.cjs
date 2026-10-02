const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const {analyze}=require('./js/analysis.js');
let now=100000;
function make(){
 const handlers={},bus={on:(k,fn)=>(handlers[k]??=[]).push(fn),emit:(k,v)=>(handlers[k]||[]).forEach(fn=>fn(v))};
 const context={console,Date:{now:()=>now},setInterval:()=>1,clearInterval:()=>{},module:{exports:{}},studyEventBus:bus};context.window=context;
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'js/state_machine.js'),'utf8'),context);
 return{m:context.studyStateMachineInstance,bus};
}
{
 const {m,bus}=make();bus.emit('STUDY_SETUP_COMPLETE',{protocol:{durationSec:60,workSec:10,breakSec:2,completion:'time'}});bus.emit('STUDY_START',{mode:'MODE_A'});
 now+=1000;m.tick();m.pauseStudy();now+=10000;m.tick();assert.equal(m.activePickingMs,1000);assert.equal(m.interruptionMs,10000);assert.equal(m.totalElapsedMs,11000);
 now+=50000;m.tick();assert.equal(m.currentState,'COMPLETED');
}
{
 const {m,bus}=make();bus.emit('STUDY_SETUP_COMPLETE',{protocol:{durationSec:20,workSec:10,breakSec:2,completion:'time'}});bus.emit('STUDY_START',{mode:'MODE_B'});
 now+=10000;m.tick();assert.equal(m.currentState,'BREAK');now+=1000;m.tick();m.pauseStudy();now+=5000;m.tick();m.resumeStudy();assert.equal(m.currentBreakMs,1000);
 now+=1000;m.tick();assert.equal(m.currentState,'PICKING');assert.equal(m.blockNumber,2);now+=10000;m.tick();assert.equal(m.currentState,'COMPLETED');assert.equal(m.activePickingMs,20000);
}
{
 const {m,bus}=make();bus.emit('STUDY_SETUP_COMPLETE',{protocol:{durationSec:1,workSec:60,breakSec:2,completion:'cycles'}});bus.emit('STUDY_START',{mode:'MODE_A'});now+=5000;m.tick();assert.equal(m.currentState,'PICKING');
}
const picks=Array.from({length:40},(_,i)=>({id:String(i),cycleTimeMs:(i<20?3:7)*1000,slot:i%4+1,pickBlock:1,valid:true}));
assert.equal(analyze({picks:picks.slice(0,19)}).alerts.length,0);assert.equal(analyze({picks}).alerts.length,2);assert.equal(analyze({picks}).accuracy,'not assessed');
assert.equal(analyze({picks,corrections:[{pickId:'1',valid:false}]}).overall.count,39);assert.equal(analyze({picks:[]}).overall.p90,null);
console.log('PASS: wall-clock pauses, active work/break accounting, paused break recovery, final-block completion, cycles-only duration, analytics sample gates and invalid trials.');
