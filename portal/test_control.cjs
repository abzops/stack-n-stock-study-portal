const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process');
const root=__dirname,port=8012,base=`http://127.0.0.1:${port}`,tmp=fs.mkdtempSync(path.join(os.tmpdir(),'sns-study-test-'));
let server;
function boot(){server=spawn('python',[path.join(root,'launch_portal.py'),'--port',String(port),'--no-browser'],{env:{...process.env,SNS_STUDY_DB:path.join(tmp,'sessions.sqlite3')},stdio:'ignore'});}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 boot();for(let i=0;i<30;i++){try{await fetch(base+'/api/sessions');break;}catch{await delay(200);}}
 const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1440,height:1050}}),page=await context.newPage();
 const errors=[];context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 async function saved(p=page){try{await p.waitForFunction(()=>studyPersistence.ready&&!studyPersistence.running&&!studyPersistence.pending&&!studyPersistence.blocked,{},{timeout:15000});}catch(error){console.log(await p.evaluate(()=>({status:document.getElementById('saveStatus').textContent,recovery:document.getElementById('recoveryNotice').textContent,toast:document.getElementById('toast').textContent,id:studyPersistence.id,ready:studyPersistence.ready,conflict:studyPersistence.conflict})));console.log(errors);throw error;}}
 async function pick(p=page){await p.waitForFunction(()=>hardwareManager.activePTLSlot!==null);await p.click('#btnManualConfirm');await saved(p);}
 try{
  await page.goto(base);await page.fill('#setupOperator','Control QA');
  await page.fill('#protocolWork','2');await page.fill('#protocolBreak','1');await page.fill('#protocolCycles','2');await page.selectOption('#protocolCompletion','cycles');await page.selectOption('#setupToteConfig','4');
  await page.click('#savePreset');await page.fill('#presetName','QA short cycle');await page.click('#dialogForm button[type=submit]');await page.waitForSelector('#studyDialog',{state:'hidden'});
  await page.fill('#protocolWork','9');await page.selectOption('#presetSelect',{label:'QA short cycle'});await page.click('#loadPreset');assert.equal(await page.locator('#protocolWork').inputValue(),'2');
  await page.evaluate(()=>document.querySelectorAll('#tableToteA input[type=number],#tableToteB input[type=number]').forEach(el=>{el.value='1';el.dispatchEvent(new Event('input',{bubbles:true}));}));
  await page.click('#btnLockSetup');await saved();const id=await page.evaluate(()=>studyPersistence.id);assert.ok(id);
  await page.waitForTimeout(1100);await page.screenshot({path:path.join(root,'qa','control-ready.png'),fullPage:true});
  await page.click('#btnStartStudy');await pick();
  await page.click('#btnPauseStudy');await saved();
  await page.click('#annotatePick');await page.selectOption('#annotationValidity','invalid');await page.selectOption('#annotationAccuracy','incorrect');await page.fill('#annotationReason','Observed wrong item');await page.click('#dialogForm button[type=submit]');await saved();
  assert.equal(await page.evaluate(()=>studyAdvanced.effectivePicks()[0].valid),false);assert.equal(await page.evaluate(()=>studyDataExport.pickRecords[0].valid),true);
  await page.click('[data-adjust="A:1"]');await page.fill('#adjustReason','Count verified');await page.click('#dialogForm button[type=submit]');await saved();
  // The server accepts the save but its response is lost. The exact retry must not duplicate events.
  await page.route('**/api/sessions/*/save',async route=>{await route.fetch();await route.abort();});
  await page.evaluate(()=>studyEventBus.emit('QA_LOST_RESPONSE',{test:true}));await page.waitForFunction(()=>studyPersistence.blocked);
  await page.unroute('**/api/sessions/*/save');await page.evaluate(()=>studyPersistence.flush());await saved();
  assert.equal((await (await fetch(base+`/api/sessions/${id}`)).json()).snapshot.events.filter(e=>e.event==='QA_LOST_RESPONSE').length,1);
  await page.click('[data-target="tab-analysis"]');await page.waitForTimeout(1100);assert.match(await page.locator('#analysisSummary').innerText(),/1 excluded/);
  const original=await (await fetch(base+`/api/sessions/${id}`)).json();assert.equal(original.snapshot.picks.length,1);
  // A second tab cannot claim an actively owned session.
  const other=await context.newPage();await other.goto(base);await other.click('[data-target="tab-history"]');await other.click(`[data-open="${id}"]`);await other.waitForTimeout(300);assert.equal(await other.evaluate(()=>studyPersistence.ready),false);
  // Failed writes retain an outbox and suspend picks; retry restores saving without auto-resuming.
  await page.click('[data-target="tab-dashboard"]');await page.click('#btnStartStudy');await page.waitForFunction(()=>hardwareManager.activePTLSlot!==null);
  await page.click('#recordException');await page.selectOption('#exceptionKind','sensor miss');await page.fill('#exceptionReason','Sensor missed an unfinished task');await page.click('#dialogForm button[type=submit]');await saved();assert.equal(await page.evaluate(()=>studyAdvanced.exceptions.length),1);await page.click('#btnStartStudy');await page.waitForFunction(()=>hardwareManager.activePTLSlot!==null);
  await page.route('**/api/sessions/*/save',route=>route.abort());await page.click('#btnManualConfirm');await page.waitForFunction(()=>studyPersistence.blocked);
  assert.equal(await page.evaluate(()=>studyStateMachineInstance.currentState),'PAUSED');assert.ok(await page.evaluate(()=>localStorage.getItem(studyPersistence.key())));
  await page.unroute('**/api/sessions/*/save');await page.evaluate(()=>studyPersistence.flush());await saved();assert.equal(await page.evaluate(()=>studyStateMachineInstance.currentState),'PAUSED');
  // Server restart preserves the database.
  server.kill();await delay(400);boot();await delay(600);
  assert.equal((await (await fetch(base+`/api/sessions/${id}`)).json()).snapshot.picks.length,2);
  // Refresh must recover paused, never start a pick by itself. Expire the prior lease by closing that client.
  await page.evaluate(()=>{studyPersistence.ready=false;studyStateMachineInstance.stopTick();});await delay(8200);await page.reload();await saved();
  assert.equal(await page.evaluate(()=>studyStateMachineInstance.currentState),'PAUSED');assert.equal(await page.locator('.ptl-slot.active').count(),0);assert.equal(await page.evaluate(()=>studyDataExport.pickRecords.length),2);
  await page.click('#btnStartStudy');await pick();await pick();await page.waitForFunction(()=>studyStateMachineInstance.currentState==='TOTE_CHANGE');
  await page.click('#btnSimulateToteChange');await page.click('#dialogForm button[type=submit]');assert.match(await page.locator('#dialogError').innerText(),/match/);
  for(let i=1;i<=4;i++)await page.fill('#refill-'+i,'1');await page.click('#dialogForm button[type=submit]');
  for(let i=0;i<4;i++){await page.waitForFunction(()=>studyStateMachineInstance.currentState==='PICKING');await pick();}
  await page.waitForFunction(()=>studyStateMachineInstance.currentState==='COMPLETED');await saved();assert.equal(await page.evaluate(()=>studyDataExport.pickRecords.length),8);
  await page.click('[data-target="tab-analysis"]');await page.waitForTimeout(1200);await page.screenshot({path:path.join(root,'qa','control-analysis.png'),fullPage:true});
  const apiAnalysis=await (await fetch(base+`/api/sessions/${id}/analysis`)).json();assert.equal(apiAnalysis.overall.count,7);assert.equal(apiAnalysis.invalid,1);
  await page.click('#compareSessions');await page.waitForFunction(()=>document.getElementById('comparisonResult').textContent.includes('conditions'));
  const download=page.waitForEvent('download');await page.click('#exportDetailed');assert.match(fs.readFileSync(await (await download).path(),'utf8'),/accuracy/);
  await page.evaluate(()=>window.print=()=>{});await page.click('#printSummary');assert.match(await page.locator('#printReport').textContent(),/Observed wrong item/);
  await page.emulateMedia({media:'print'});await page.screenshot({path:path.join(root,'qa','control-report.png'),fullPage:true});await page.emulateMedia({media:'screen'});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(root,'qa','control-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  // Duplicate keeps the source intact and allows a new protocol.
  await page.click('[data-target="tab-history"]');await page.click(`[data-copy="${id}"]`);await page.waitForFunction(()=>document.getElementById('setupStudyId').value.endsWith('-copy'));
  assert.equal(await page.locator('#protocolWork').inputValue(),'2');await page.fill('#protocolCycles','13');await page.fill('#protocolWork','600');await page.click('#btnLockSetup');await saved();await page.click('#btnStartStudy');
  for(let cycle=1;cycle<=13;cycle++){
   for(let i=0;i<4;i++)await pick();
   if(cycle<13){await page.click('#btnSimulateToteChange');for(let i=1;i<=4;i++)await page.fill('#refill-'+i,'1');await page.click('#dialogForm button[type=submit]');}
  }
  await saved();assert.equal(await page.evaluate(()=>studyStateMachineInstance.currentState),'COMPLETED');assert.equal(await page.evaluate(()=>studyDataExport.pickRecords.length),52);
  const duplicateId=await page.evaluate(()=>studyPersistence.id);await page.click('[data-target="tab-analysis"]');await page.waitForFunction(()=>document.querySelectorAll('#compareA option').length===2);await page.selectOption('#compareA',duplicateId);await page.selectOption('#compareB',id);await page.click('#compareSessions');await page.waitForFunction(()=>document.getElementById('comparisonResult').textContent.includes('Different conditions'));
  // Recover a failed first save even when the session does not exist in SQLite yet.
  const firstFail=await context.newPage();await firstFail.goto(base);await firstFail.fill('#setupOperator','First save recovery');await firstFail.route('**/api/sessions/*/save',r=>r.abort());await firstFail.click('#btnLockSetup');await firstFail.waitForFunction(()=>studyPersistence.blocked&&studyPersistence.pending);
  await firstFail.unroute('**/api/sessions/*/save');await firstFail.reload();await saved(firstFail);assert.equal(await firstFail.evaluate(()=>studyStateMachineInstance.currentState),'READY');
  assert.deepEqual(errors,[]);console.log('PASS: durable sessions, preset, corrections, recovery, duplicate tab rejection, save failure/retry, server restart, refill validation, cycle completion, analytics API, CSV, report, mobile.');
 }finally{await browser.close();server.kill();}
})().catch(error=>{console.error(error);server?.kill();process.exitCode=1;});
