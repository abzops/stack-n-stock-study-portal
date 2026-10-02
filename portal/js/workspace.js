/* Operator workspace: configuration, live session controls and presentation. */
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const machine = window.studyStateMachineInstance;
    let locked = false, metadata = null, toastTimer, logVersion = -1;
    const draft = { A: [], B: [] };
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const tell = message => { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4500); };
    function navigate(target) {
        document.querySelectorAll('.nav-tab').forEach(tab => { const active=tab.dataset.target===target; tab.classList.toggle('active',active); tab.setAttribute('aria-current',active?'page':'false'); if(active) $('breadcrumbCurrent').textContent=tab.childNodes[1].textContent; });
        document.querySelectorAll('.tab-pane').forEach(pane=>pane.classList.toggle('active',pane.id===target));
        window.scrollTo(0,0);
    }
    document.querySelectorAll('.nav-tab').forEach(tab=>tab.addEventListener('click',()=>navigate(tab.dataset.target)));
    function readDraft() {
        for (const tote of ['A','B']) document.querySelectorAll(`#tableTote${tote} tbody tr`).forEach((row,i)=>{
            const [sku,name,physical,digital]=row.querySelectorAll('input');
            draft[tote][i]={id:i+1,skuId:sku.value,skuName:name.value,physicalQty:physical.value,digitalQty:digital.value};
        });
    }
    function renderInventoryTables() {
        readDraft();
        const count=Number($('setupToteConfig').value);
        for(const tote of ['A','B']) {
            document.querySelector(`#tableTote${tote} tbody`).innerHTML=Array.from({length:count},(_,i)=>{
                const s=draft[tote][i]||{skuId:`SKU-00${i+1}`,skuName:`Item ${i+1}`,physicalQty:20,digitalQty:20};
                return `<tr><td><span class="slot-id">${String(i+1).padStart(2,'0')}</span></td>${[['sku',s.skuId,'SKU ID','text'],['name',s.skuName,'Item name','text'],['phys',s.physicalQty,'Physical quantity','number'],['dig',s.digitalQty,'Portal quantity','number']].map(([key,v,label,type])=>`<td><input id="${tote.toLowerCase()}_${key}_${i+1}" aria-label="Tote ${tote} slot ${i+1} ${label}" type="${type}" ${type==='number'?'min="0" max="100000" step="1"':'maxlength="100"'} value="${escape(v)}"></td>`).join('')}<td class="match-status"></td></tr>`;
            }).join('');
        }
        updateSetup();
    }
    window.renderInventoryTables=renderInventoryTables;
    function validQty(value) { return value!=='' && Number.isInteger(Number(value)) && Number(value)>=0 && Number(value)<=100000; }
    function updateSetup() {
        readDraft(); let total=0, allMatched=true;
        for(const tote of ['A','B']) {
            let matched=0,units=0;
            document.querySelectorAll(`#tableTote${tote} tbody tr`).forEach((row,i)=>{
                const s=draft[tote][i];
                const good=validQty(s.physicalQty)&&validQty(s.digitalQty)&&Number(s.physicalQty)===Number(s.digitalQty)&&s.skuId.trim()&&s.skuName.trim();
                if(good) matched++; else allMatched=false;
                units+=validQty(s.digitalQty)?Number(s.digitalQty):0;
                row.querySelector('.match-status').className=`match-status ${good?'matched':'mismatch'}`;
                row.querySelector('.match-status').textContent=good?'✓ Matched':'Check values';
            });
            total+=units;
            $(`tote${tote}Status`).textContent=`${matched} / ${$('setupToteConfig').value} matched`;
            $(`tote${tote}Total`).textContent=`${units} units total`;
        }
        $('summaryUnits').textContent=`${total} units`;
        $('summaryConfig').textContent=`${$('setupToteConfig').value} slots × 2 totes`;
        const active=$('setupMode').value==='MODE_B';
        $('sessionDuration').innerHTML=active?'68<span> min </span>30<span> sec</span>':'60<span> min</span>';
        $('durationExplanation').textContent=active?'60 minutes of picking + scheduled breaks':'A 60-minute session, including breaks';
        $('inventoryStep').classList.toggle('active',allMatched);
        return allMatched;
    }
    $('setupToteConfig').addEventListener('change',renderInventoryTables);
    $('tab-setup').addEventListener('input',updateSetup);
    $('setupMode').addEventListener('change',updateSetup);
    $('btnLockSetup').addEventListener('click',async()=>{
        if(locked)return;
        const matched=updateSetup(), count=Number($('setupToteConfig').value);
        if(!matched||!$('setupOperator').value.trim()||!$('setupStudyId').value.trim()||['A','B'].some(t=>!draft[t].slice(0,count).some(s=>Number(s.digitalQty)>0))) {
            $('setupValidationMsg').textContent='Enter a study ID and operator, complete each SKU, and match whole-number quantities. Each tote needs at least one stocked slot.'; return;
        }
        metadata={studyId:$('setupStudyId').value.trim(),operator:$('setupOperator').value.trim(),mode:$('setupMode').value,numSlots:count,configuration:`${count}-slot`,inventory:Object.fromEntries(['A','B'].map(t=>[t,draft[t].slice(0,count).map(s=>({...s,physicalQty:Number(s.physicalQty),digitalQty:Number(s.digitalQty)}))]))};
        try { metadata.protocol=window.studyAdvanced.readProtocol(); } catch(error){$('setupValidationMsg').textContent=error.message;return;}
        studyInventory.initialize({...metadata,maxCycles:metadata.protocol.maxCycles,completion:metadata.protocol.completion}); machine.mode=metadata.mode;
        locked=true;
        document.querySelectorAll('#tab-setup input,#tab-setup select').forEach(input=>input.disabled=true);
        $('btnLockSetup').disabled=true; $('btnLockSetup').textContent='Configuration locked ✓'; $('setupValidationMsg').textContent=''; $('readyStep').classList.add('active');
        $('sessionCaption').textContent=`${metadata.studyId} · ${metadata.operator} · ${count} slots · ${metadata.protocol.completion==='cycles'?metadata.protocol.maxCycles+' tote cycles':metadata.protocol.durationSec/60+' min '+(metadata.mode==='MODE_B'?'active picking':'wall clock')}`;
        studyEventBus.emit('STUDY_SETUP_COMPLETE',metadata); renderGrid(); navigate('tab-dashboard'); tell('Setup locked. Your station is ready to start.');
        await studyPersistence.create();updateControls();
    });
    async function issuePick() {
        if(window.studyPersistence && (!studyPersistence.canOperate() || !await studyPersistence.flush()))return;
        if(machine.currentState!=='PICKING'||hardwareManager.activePTLSlot!==null)return;
        const slot=studyInventory.getNextRandomSlot();
        if(slot!==null)hardwareManager.turnOnPTL(slot);
        renderGrid();
    }
    function renderGrid() {
        if(!locked)return;
        const id=studyInventory.activeToteId;
        $('dashboardPtlGrid').dataset.slots=metadata.numSlots;
        $('dashboardPtlGrid').innerHTML=studyInventory.getToteInventory(id).map(s=>`<div class="ptl-slot ${hardwareManager.activePTLSlot===s.id?'active':''}" id="ptl-slot-${s.id}"><span class="slot-signal"></span><div class="ptl-label">Slot ${String(s.id).padStart(2,'0')}</div><div class="ptl-sku">${escape(s.skuId)}</div><div class="ptl-qty">${escape(s.skuName)}</div><div class="ptl-qty" style="margin-top:8px">${s.digitalQty} units remaining</div></div>`).join('');
        $('dashActiveTote').textContent=`TOTE ${id||'—'}`; $('dashCycle').textContent=`CYCLE ${studyInventory.getCycleProgress()}`;
    }
    $('btnStartStudy').addEventListener('click',()=>{
        if(!studyPersistence.canOperate())return;
        if(Object.values(studyInventory.totes).some(t=>t.slots.some(s=>s.physicalQty!==s.digitalQty))){tell('Verify and reconcile inventory mismatches before resuming.');return;}
        const tote=studyInventory.totes[studyInventory.activeToteId];
        if(machine.currentState==='PAUSED'&&tote?.status==='ACTIVE'&&tote.slots.every(s=>s.digitalQty===0)){
            studyInventory.checkToteDepletion(studyInventory.activeToteId);return;
        }
        if(machine.currentState==='READY')studyEventBus.emit('STUDY_START',metadata);
        else if(machine.currentState==='PAUSED')studyEventBus.emit('STUDY_RESUME');
    });
    $('btnPauseStudy').addEventListener('click',()=>studyEventBus.emit('STUDY_PAUSE'));
    function endSession(emergency) { if(!['SETUP','COMPLETED'].includes(machine.currentState)){studyEventBus.emit(emergency?'EMERGENCY_STOP':'ADMIN_END_SESSION');machine.setState('COMPLETED');tell('Session ended. Your records are available in Data export.');} }
    $('btnEndStudy').addEventListener('click',()=>{if(window.confirm('End this study? The session cannot be resumed. Collected data will remain available for export.'))endSession(false);});
    $('btnEmergencyStop').addEventListener('click',()=>endSession(true));
    $('btnManualConfirm').addEventListener('click',()=>hardwareManager.manualConfirm());
    $('btnSimulateIR').addEventListener('click',()=>hardwareManager.triggerIRSensor());
    $('btnSimulateToteChange').addEventListener('click',()=>{
        if(machine.currentState!=='TOTE_CHANGE')return;
        const replacing=Object.keys(studyInventory.totes).find(t=>studyInventory.totes[t].status==='REPLACING');
        if(replacing)window.studyAdvanced.verifyRefill(replacing);
        renderGrid();
    });
    document.addEventListener('keydown',event=>{
        if(event.repeat||!['Enter',' '].includes(event.key)||/INPUT|SELECT|TEXTAREA|BUTTON/.test(event.target.tagName)||!$('tab-dashboard').classList.contains('active'))return;
        if(machine.currentState==='PICKING'){event.preventDefault();hardwareManager.manualConfirm();}
    });
    studyEventBus.on('SYSTEM_STATE_CHANGED',({newState})=>{
        if(newState!=='PICKING') {
            if(hardwareManager.activePTLSlot!==null)studyEventBus.emit('PICK_INTERRUPTED',{slot:hardwareManager.activePTLSlot,reason:newState});
            hardwareManager.turnOffAllPTL();
        }else setTimeout(issuePick,0);
        renderGrid(); updateControls();
    });
    studyEventBus.on('PICK_COMPLETE',()=>{updateMetrics();setTimeout(issuePick,120);setTimeout(renderGrid,0);});
    function updateControls() {
        const s=machine.currentState, live=s==='PICKING' && studyPersistence.canOperate();
        $('headerSystemStatus').textContent=s.replaceAll('_',' '); $('dashState').textContent=s.replaceAll('_',' ');
        $('btnStartStudy').disabled=!['READY','PAUSED'].includes(s)||!studyPersistence.canOperate(); $('btnStartStudy').textContent=s==='PAUSED'?'Resume study →':'Start study →';
        $('btnPauseStudy').disabled=!['PICKING','BREAK'].includes(s);
        $('btnManualConfirm').disabled=!live; $('btnSimulateIR').disabled=!live;
        $('btnSimulateToteChange').disabled=s!=='TOTE_CHANGE'||!studyPersistence.canOperate();
        $('btnEndStudy').disabled=$('btnEmergencyStop').disabled=['SETUP','COMPLETED'].includes(s);
        $('stationMessage').textContent={SETUP:'Lock your setup to prepare the picking station.',READY:'Station ready. Start the study when the participant is ready.',PICKING:'Pick 1 unit from the highlighted slot, then confirm. Enter or Space also confirms.',PAUSED:'Session paused. Light indicators and confirmations are suspended.',BREAK:'Rest break. Picking will resume automatically after the countdown.',TOTE_CHANGE:'Tote depleted. Refill the depleted tote to its configured quantities, then confirm replacement.',COMPLETED:'Session complete. Export your records before closing this workspace.',HARDWARE_FAULT:'Hardware fault. Picking is suspended.'}[s];
    }
    function updateMetrics() {
        const times=window.studyAdvanced.effectivePicks().filter(p=>p.valid!==false).map(p=>p.cycleTimeMs/1000), sorted=[...times].sort((a,b)=>a-b);
        ['kpiAvgTime','kpiP90Time','kpiSLA'].forEach(id=>$(id).textContent='—');
        $('kpiTotalPicks').textContent=studyDataExport.pickRecords.length;
        $('chartCaption').textContent='Waiting for valid timing samples';
        if(times.length){$('kpiAvgTime').textContent=(times.reduce((a,b)=>a+b,0)/times.length).toFixed(2)+' s';$('kpiP90Time').textContent=sorted[Math.ceil(times.length*.9)-1].toFixed(2)+' s';$('kpiSLA').textContent=Math.round(times.filter(t=>t<=5).length/times.length*100)+'%';}
        const last=times.slice(-30),max=Math.max(6,...last)*1.1,y=v=>120-v/max*110;
        let plot=[0,2,4,6].map(v=>`<line x1="0" x2="600" y1="${y(v)}" y2="${y(v)}" stroke="#e9ede2"/>`).join('');
        plot+=`<line x1="0" x2="600" y1="${y(5)}" y2="${y(5)}" stroke="#c3b03b" stroke-dasharray="5 5"/>`;
        if(last.length){const points=last.map((v,i)=>[last.length===1?300:10+i/(last.length-1)*580,y(v)]);plot+=`<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#627a45" stroke-width="2"/>`+points.map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3" fill="#627a45"/>`).join('');$('chartCaption').textContent=`${last.length} confirmed ${last.length===1?'pick':'picks'} · scale 0–${max.toFixed(1)} s`;}
        $('cycleChart').innerHTML=plot;
    }
    function updateLog(force=false){
        const all=studyEventBus.getEventLog(); if(!force&&logVersion===all.length)return;logVersion=all.length;
        const term=$('logSearch').value.toLowerCase(),events=all.filter(e=>(e.event+' '+JSON.stringify(e.payload)).toLowerCase().includes(term));
        $('eventCount').textContent=`${all.length} events recorded${term?` · ${events.length} matching`:''}`;
        $('eventLogContainer').innerHTML=events.slice(-200).reverse().map(e=>`<div class="log-row"><time>${new Date(e.timestamp).toLocaleTimeString([], {hour12:false})}</time><strong>${escape(e.event)}</strong><code>${escape(JSON.stringify(e.payload))}</code></div>`).join('')||'<div class="empty">No matching events yet.</div>';
    }
    $('logSearch').addEventListener('input',()=>updateLog(true));
    function exportData(kind){
        if(!['PAUSED','COMPLETED','READY','SETUP'].includes(machine.currentState)){tell('Pause or end the session before exporting.');return;}
        if(kind==='picks')studyDataExport.exportPickDataCSV();else if(kind==='cycles')studyDataExport.exportToteCycleCSV();else studyDataExport.exportEventLogCSV();
    }
    [['btnExportPicks','picks'],['btnExportCycles','cycles'],['btnExportEvents','events'],['btnExportLog','events']].forEach(([id,kind])=>$(id).addEventListener('click',()=>exportData(kind)));
    const format=ms=>{const sec=Math.floor(Math.max(0,ms)/1000);return `${String(Math.floor(sec/60)).padStart(2,'0')}:${String(sec%60).padStart(2,'0')}`;};
    setInterval(()=>{
        $('dashBlockTime').textContent=format(machine.BLOCK_DURATION_MS-machine.currentBlockPickingMs);
        $('dashBreakTime').textContent=machine.currentState==='BREAK'||(machine.currentState==='PAUSED'&&machine.lastActiveState==='BREAK')?format(machine.BREAK_DURATION_MS-machine.currentBreakMs):'—';
        $('dashActiveTime').textContent=format(machine.activePickingMs);$('dashElapsedTime').textContent=format(machine.totalElapsedMs);
        const progress=Math.min(100,(machine.completion==='cycles'?studyDataExport.toteCycles.length/metadata.protocol.maxCycles:(machine.mode==='MODE_B'?machine.activePickingMs:machine.totalElapsedMs)/machine.TARGET_TOTAL_TIME_MS)*100);
        $('sessionProgress').style.width=progress+'%';$('progressCaption').textContent=`${Math.floor(progress)}% of session complete`;
        $('ledIR').textContent=hardwareManager.states.irSensor==='Triggered'?'Triggered':'Simulated';
        const counts=[studyDataExport.pickRecords.length,studyDataExport.toteCycles.length,studyEventBus.getEventLog().length];
        ['exportPickCount','exportCycleCount','exportEventCount'].forEach((id,i)=>$(id).textContent=counts[i]);
        const allowed=['PAUSED','COMPLETED','READY','SETUP'].includes(machine.currentState);
        ['btnExportPicks','btnExportCycles','btnExportEvents'].forEach((id,i)=>$(id).disabled=!allowed||!counts[i]);$('btnExportLog').disabled=!allowed||!counts[2];
        $('exportState').textContent=locked?`${metadata.studyId} · ${machine.currentState.toLowerCase().replaceAll('_',' ')}`:'No session started';
        updateLog();
    },200);
    window.addEventListener('beforeunload',e=>{if(studyPersistence.pending||studyPersistence.dirty){e.preventDefault();e.returnValue='';}});
    window.addEventListener('save-status',updateControls);
    const machineKeys=['currentState','previousState','lastActiveState','resumeState','mode','BLOCK_DURATION_MS','BREAK_DURATION_MS','TARGET_TOTAL_TIME_MS','completion','totalElapsedMs','activePickingMs','breakMs','interruptionMs','currentBlockPickingMs','currentBreakMs','blockNumber','startedAt'];
    window.studyWorkspace={tell,navigate,updateMetrics,renderGrid,updateControls,
        get metadata(){return metadata;},
        getDraft(){readDraft();const count=Number($('setupToteConfig').value);return {studyId:$('setupStudyId').value,operator:$('setupOperator').value,numSlots:count,mode:$('setupMode').value,protocol:studyAdvanced.readProtocol(),inventory:Object.fromEntries(['A','B'].map(t=>[t,draft[t].slice(0,count)]))};},
        snapshot(){return JSON.parse(JSON.stringify({metadata,machine:Object.fromEntries(machineKeys.map(k=>[k,machine[k]])),inventory:{config:studyInventory.config,configuredInventory:studyInventory.configuredInventory,totes:studyInventory.totes,activeToteId:studyInventory.activeToteId,cycleCounter:studyInventory.cycleCounter,slotDeck:studyInventory.slotDeck},picks:studyDataExport.pickRecords,cycles:studyDataExport.toteCycles,events:studyEventBus.eventLog,corrections:studyAdvanced.corrections,exceptions:studyAdvanced.exceptions,savedAt:Date.now()}));},
        applyDraft(config){
            if(locked)return;
            $('setupStudyId').value=config.studyId||'STUDY-'+Date.now();$('setupOperator').value=config.operator||'';$('setupToteConfig').value=config.numSlots||6;$('setupMode').value=config.mode||'MODE_B';
            for(const t of ['A','B']){draft[t]=config.inventory?.[t]||[];document.querySelector(`#tableTote${t} tbody`).innerHTML='';}
            studyAdvanced.setProtocol(config.protocol);renderInventoryTables();navigate('tab-setup');
        },
        restore(snapshot){
            metadata=snapshot.metadata;locked=true;machine.stopTick();Object.assign(machine,snapshot.machine);Object.assign(studyInventory,snapshot.inventory);
            studyDataExport.pickRecords=snapshot.picks;studyDataExport.toteCycles=snapshot.cycles||[];studyDataExport.studyMetadata=metadata;studyEventBus.eventLog=snapshot.events;studyAdvanced.corrections=snapshot.corrections||[];studyAdvanced.exceptions=snapshot.exceptions||[];
            // Reconnect cycle references so replacement timestamps update the saved cycle.
            for(const t of Object.values(studyInventory.totes)){const c=studyDataExport.toteCycles.find(c=>c.cycleNumber===t.cycleData?.cycleNumber);if(c)t.cycleData=c;}
            if(!['READY','COMPLETED'].includes(machine.currentState)){
                const prior=machine.currentState;machine.resumeState=prior==='PAUSED'?(machine.resumeState||machine.lastActiveState):prior;
                machine.currentState='PAUSED';
                if(machine.startedAt){const elapsed=Date.now()-machine.startedAt;machine.interruptionMs+=Math.max(0,elapsed-machine.totalElapsedMs);machine.totalElapsedMs=elapsed;}
                machine.startTick();
                studyEventBus.emit('SESSION_RECOVERED',{previousState:prior});
            }
            hardwareManager.setStudyState(machine.currentState);hardwareManager.turnOffAllPTL();
            $('setupStudyId').value=metadata.studyId;$('setupOperator').value=metadata.operator;$('setupMode').value=metadata.mode;$('setupToteConfig').value=metadata.numSlots;
            for(const t of ['A','B']){draft[t]=structuredClone(metadata.inventory[t]);document.querySelector(`#tableTote${t} tbody`).innerHTML='';}renderInventoryTables();studyAdvanced.setProtocol(metadata.protocol);
            document.querySelectorAll('#tab-setup input,#tab-setup select,#tab-setup button').forEach(e=>e.disabled=true);
            $('btnLockSetup').textContent='Saved configuration · locked';$('sessionCaption').textContent=`${metadata.studyId} · ${metadata.operator} · recovered session`;
            renderGrid();updateMetrics();updateControls();navigate('tab-dashboard');
        }
    };
    studyEventBus.on('*',()=>studyPersistence.changed());
    renderInventoryTables();updateMetrics();updateControls();
});
