/* Test the copied executable with no Python or Node in its runtime PATH. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn,spawnSync}=require('node:child_process');
const assert=require('node:assert/strict');
const net=require('node:net');
(async()=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'sns-portable-'));
 const exe=path.join(folder,'Stack n Stock Portal.exe');
 fs.copyFileSync(process.env.SNS_TEST_EXE || path.join(__dirname,'..','portable','Stack n Stock Portal.exe'),exe);
 const port=await new Promise(resolve=>{const s=net.createServer().listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});
 const url=`http://127.0.0.1:${port}`;
 const env={...process.env,PATH:path.join(process.env.SystemRoot,'System32')};delete env.SNS_STUDY_DB;delete env.PYTHONPATH;delete env.PYTHONHOME;
 let child,output='';
 const delay=ms=>new Promise(r=>setTimeout(r,ms));
 async function start(){
  child=spawn(exe,['--port',String(port),'--no-browser'],{cwd:folder,env,windowsHide:true});
  child.stdout.on('data',d=>output+=d);child.stderr.on('data',d=>output+=d);
  for(let i=0;i<80;i++){try{const r=await fetch(url+'/api/sessions');if(r.ok)return;}catch{}await delay(250);}
  throw Error('Portable app failed to start: '+output);
 }
 function stop(){if(child)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true});}
 let browser;
 try{
  await start();assert.ok(fs.existsSync(path.join(folder,'data','study_sessions.sqlite3')));
  for(const asset of ['sns_study_portal.html','css/portal.css','css/advanced.css','js/workspace.js','js/advanced.js','js/persistence.js','assets/logo/horizontal_white.png'])assert.equal((await fetch(url+'/'+asset)).status,200,asset);
  browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(url);await page.fill('#setupOperator','Portable verification');await page.click('#btnLockSetup');
  try { await page.waitForFunction(()=>studyPersistence.canOperate()); }
  catch(e) { console.error('Setup diagnostics', errors, await page.locator('body').innerText(), output); throw e; }
  await page.click('#btnStartStudy');await page.waitForFunction(()=>hardwareManager.activePTLSlot!==null);await page.click('#btnManualConfirm');await page.click('#btnPauseStudy');
  await page.waitForFunction(()=>!studyPersistence.running&&!studyPersistence.dirty&&!studyPersistence.pending);
  const id=await page.evaluate(()=>studyPersistence.id);assert.equal((await (await fetch(url+`/api/sessions/${id}`)).json()).snapshot.picks.length,1);
  await page.close();stop();await delay(8500);await start();
  const restored=await browser.newPage();await restored.goto(url);await restored.click('[data-target="tab-history"]');await restored.click(`[data-open="${id}"]`);await restored.waitForFunction(()=>studyPersistence.canOperate());
  assert.equal(await restored.evaluate(()=>studyStateMachineInstance.currentState),'PAUSED');assert.equal(await restored.evaluate(()=>studyDataExport.pickRecords.length),1);
  assert.deepEqual(errors,[]);
  console.log('PASS: standalone EXE starts without Python/Node on PATH; bundled assets, SQLite next to EXE, pick save, process restart and paused recovery verified.');
 }finally{if(browser)await browser.close();stop();}
})().catch(error=>{console.error(error);process.exitCode=1;});
