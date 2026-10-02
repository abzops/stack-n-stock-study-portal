document.addEventListener('DOMContentLoaded',()=>{
    const $=id=>document.getElementById(id), e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const machine=studyStateMachineInstance, store=studyPersistence;
    const defaults={durationSec:3600,workSec:600,breakSec:102,maxCycles:13,completion:'either'};
    const state={corrections:[],exceptions:[],effectivePicks(){return StudyAnalysis.effective(studyDataExport.pickRecords,this.corrections);}};
    window.studyAdvanced=state;
    const card=(title,body)=>`<article class="card"><div class="card-head"><h2>${title}</h2></div><div class="card-body">${body}</div></article>`;
    const input=(id,label,value,min=1,max=86400)=>`<div class="form-group"><label for="${id}">${label}</label><input id="${id}" type="number" min="${min}" max="${max}" step="1" value="${value}"></div>`;
    document.querySelector('.top-actions').insertAdjacentHTML('afterbegin','<button class="badge green" id="saveStatus" title="Click to retry saving">Not started</button>');
    $('saveStatus').onclick=()=>{if(store.conflict)tell('Reopen the saved session from History after closing the other tab.');else store.flush();};
    document.querySelector('#tab-setup .setup-layout > div').insertAdjacentHTML('afterbegin',card('Study protocol',`<div class="form-grid">${input('protocolDuration','Study duration · minutes',60,1,1440)}${input('protocolWork','Work block · seconds',600)}${input('protocolBreak','Break · seconds',102)}${input('protocolCycles','Tote cycle target',13,1,10000)}<div class="form-group"><label for="protocolCompletion">End the study by</label><select id="protocolCompletion"><option value="either">Time or cycles · whichever first</option><option value="time">Time only</option><option value="cycles">Tote cycles only</option></select></div></div><div class="preset-tools"><select id="presetSelect" aria-label="Saved protocol presets"><option value="">Choose a saved preset</option></select><button class="btn" id="loadPreset">Apply</button><button class="btn" id="savePreset">Save preset</button></div><p class="micro">Protocol freezes when setup is locked. Wall-clock time includes pauses and interruptions.</p>`));
    state.readProtocol=()=>{
        const p={durationSec:Number($('protocolDuration').value)*60,workSec:Number($('protocolWork').value),breakSec:Number($('protocolBreak').value),maxCycles:Number($('protocolCycles').value),completion:$('protocolCompletion').value};
        if(!Number.isInteger(Number($('protocolDuration').value))||Object.entries(p).some(([k,v])=>k!=='completion'&&(!Number.isInteger(v)||v<1||v>(k==='maxCycles'?10000:86400))))throw Error('Enter positive whole-number protocol values within the displayed limits.');return p;
    };
    state.setProtocol=p=>{p={...defaults,...p};$('protocolDuration').value=p.durationSec/60;$('protocolWork').value=p.workSec;$('protocolBreak').value=p.breakSec;$('protocolCycles').value=p.maxCycles;$('protocolCompletion').value=p.completion;updateSummary();};
    function tell(message){window.studyWorkspace?.tell(message);}
    function updateSummary(){
        try{
            const p=state.readProtocol(),active=$('setupMode').value==='MODE_B';
            const total=active?p.durationSec+Math.max(0,Math.ceil(p.durationSec/p.workSec)-1)*p.breakSec:p.durationSec;
            $('sessionDuration').innerHTML=p.completion==='cycles'?`${p.maxCycles}<span> cycles</span>`:`${Math.floor(total/60)}<span> min </span>${total%60}<span> sec</span>`;
            $('durationExplanation').textContent=p.completion==='cycles'?'Duration depends on picking and replenishment':p.completion==='either'?'Time estimate; cycle target may end the study earlier':'Includes planned breaks; interruptions may extend active mode';
            const summary=document.querySelectorAll('.summary-card .summary-row strong');
            summary[0].textContent=`${p.workSec}s`;summary[1].textContent=`${p.breakSec}s`;summary[4].textContent=`${p.maxCycles} cycles`;
            document.querySelector('.timeline').hidden=true;document.querySelector('.legend').hidden=true;
        }catch{}
    }
    $('tab-setup').addEventListener('input',()=>queueMicrotask(updateSummary));$('tab-setup').addEventListener('change',()=>queueMicrotask(updateSummary));
    const timerBody=$('dashElapsedTime').closest('.card-body');timerBody.insertAdjacentHTML('beforeend','<div class="timer-row"><span>Scheduled breaks</span><strong id="dashRestTime">00:00</strong></div><div class="timer-row"><span>Interruptions</span><strong id="dashInterruptTime">00:00</strong></div>');
    $('tab-dashboard').insertAdjacentHTML('beforeend',`<div class="section-spacer"></div>${card('Inventory & replenishment','<div class="tote-overview" id="inventoryOverview"></div>')}${card('Exceptions & corrections','<p class="micro">A confirmation does not prove accuracy. Assess or annotate a completed pick while paused. Original records are always retained.</p><div class="action-row"><button class="btn" id="recordException">Record exception</button><button class="btn" id="annotatePick">Assess / annotate pick</button></div><div id="auditRecent"></div>')}`);
    $('tab-dashboard').insertAdjacentHTML('beforeend',card('Study advice','<div id="dashboardAdvice"><p>Advice will appear as the study collects evidence.</p></div>'));
    for(const [id,label] of [['history','Session history'],['analysis','Smart analysis']]){
        document.querySelector('.nav-tabs').insertAdjacentHTML('beforeend',`<button class="nav-tab" data-target="tab-${id}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>${label}</button>`);
        document.querySelector('.footer').insertAdjacentHTML('beforebegin',`<section class="tab-pane" id="tab-${id}" aria-label="${label}"><div class="page-heading"><div><div class="eyebrow">Study control & insight</div><h1>${label}</h1><p>${id==='history'?'Saved on this computer. Reopen a session or reuse its setup.':'Advice based on recorded evidence. Your protocol stays unchanged.'}</p></div></div><div id="${id}Content"></div></section>`);
    }
    $('historyContent').innerHTML='<div class="action-row"><button class="btn btn-primary" id="newSession">New session +</button><button class="btn" id="refreshHistory">Refresh history</button><input id="historyFilter" type="search" placeholder="Filter by study, operator or configuration" aria-label="Filter saved sessions"></div><div id="recoveryNotice" role="status"></div><div id="historyRows"></div>';
    $('refreshHistory').insertAdjacentHTML('afterend','<button class="btn" id="downloadRecovery">Download pending recovery</button>');
    $('downloadRecovery').onclick=()=>{
        const records=Object.fromEntries(Object.keys(localStorage).filter(k=>k.startsWith('sns-outbox-')||k.startsWith('sns-conflict-')).map(k=>[k,JSON.parse(localStorage.getItem(k))]));
        const url=URL.createObjectURL(new Blob([JSON.stringify(records,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='study-pending-recovery.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    };
    document.querySelector('#tab-export .note').innerHTML='<strong>Saved locally. Export when you need a copy.</strong>Session records are automatically saved to this computer. Pause or finish the study for a consistent CSV snapshot. Smart analysis also includes detailed exports, the correction audit, and a printable summary.';
    $('analysisContent').innerHTML=`<div id="analysisSummary"></div>${card('Slot heatmap','<div id="slotHeatmap" class="heatmap"></div>')}${card('Work-block trends','<div class="table-wrap" id="blockTrends"></div>')}${card('Evidence & suggested actions','<div id="smartAlerts"></div>')}${card('Compare saved studies','<div class="form-grid"><div class="form-group"><label for="compareA">First session</label><select id="compareA"></select></div><div class="form-group"><label for="compareB">Second session</label><select id="compareB"></select></div><div class="form-group"><label for="compareSku">SKU filter · optional</label><input id="compareSku" placeholder="Exact SKU ID"></div></div><div class="action-row"><button class="btn" id="compareSessions">Compare sessions</button><button class="btn" id="printSummary">Print current summary</button><button class="btn" id="exportDetailed">Detailed CSV</button><button class="btn" id="exportAudit">Audit CSV</button></div><div id="comparisonResult"></div>')}`;
    document.body.insertAdjacentHTML('beforeend','<dialog id="studyDialog"><form id="dialogForm"><div class="card-head"><h2 id="dialogTitle"></h2><button type="button" class="btn" id="closeDialog">Close</button></div><div class="card-body" id="dialogBody"></div><div class="card-body"><p class="status-message" id="dialogError" role="alert"></p><button class="btn btn-primary" type="submit">Save & confirm</button></div></form></dialog><div id="printReport"></div>');
    let submitDialog=()=>{},history=[],presets=[];
    function modal(title,body,submit){$('dialogTitle').textContent=title;$('dialogBody').innerHTML=body;$('dialogError').textContent='';submitDialog=submit;$('studyDialog').showModal();}
    $('closeDialog').onclick=()=>$('studyDialog').close();
    $('dialogForm').onsubmit=async event=>{event.preventDefault();try{await submitDialog();$('studyDialog').close();}catch(error){$('dialogError').textContent=error.message;}};
    function requireWritable(){if(!store.canOperate())throw Error('Saving must recover before making changes.');}
    function requirePaused(){requireWritable();if(machine.currentState!=='PAUSED')throw Error('Pause the study before making corrections.');}
    async function loadPresets(){presets=await store.api('presets');$('presetSelect').innerHTML='<option value="">Choose a saved preset</option>'+presets.map(p=>`<option value="${e(p.id)}">${e(p.name)}</option>`).join('');}
    $('savePreset').onclick=()=>modal('Save study preset','<label for="presetName">Preset name</label><input id="presetName" required maxlength="100" placeholder="e.g. Six-slot baseline">',async()=>{const config=studyWorkspace.getDraft();await store.api('presets',{id:crypto.randomUUID(),name:$('presetName').value,config});await loadPresets();tell('Preset saved.');});
    $('loadPreset').onclick=()=>{const p=presets.find(p=>p.id===$('presetSelect').value);if(p)studyWorkspace.applyDraft({...p.config,studyId:$('setupStudyId').value,operator:$('setupOperator').value});};
    async function startFresh(config){
        if(store.id){if(!['READY','PAUSED','COMPLETED'].includes(machine.currentState))machine.pauseStudy();store.changed();if(!await store.flush())throw Error('Save the current session before leaving it.');}
        if(config)sessionStorage.setItem('sns-draft',JSON.stringify({...config,studyId:config.studyId+'-copy'}));
        store.detach();location.reload();
    }
    $('newSession').onclick=()=>startFresh().catch(error=>tell(error.message));
    function renderHistory(){
        const pending=Object.keys(localStorage).filter(k=>k.startsWith('sns-outbox-')&&!k.endsWith('-latest')).map(k=>{try{const p=JSON.parse(localStorage.getItem(k));return{id:k.slice(11),metadata:p.snapshot.metadata,state:'PENDING SAVE',picks:p.snapshot.picks.length,updated:new Date(p.snapshot.savedAt).toISOString()};}catch{return null;}}).filter(r=>r&&!history.some(h=>h.id===r.id));
        const filter=$('historyFilter').value.toLowerCase(),rows=[...pending,...history].filter(r=>JSON.stringify(r.metadata).toLowerCase().includes(filter));
        $('historyRows').innerHTML=rows.length?rows.map(r=>card(e(r.metadata.studyId),`<div class="history-session"><div><strong>${e(r.metadata.operator)}</strong><p>${e(r.metadata.configuration)} · ${e(r.state)} · ${r.picks} picks<br>Saved ${e(new Date(r.updated).toLocaleString())}</p></div><div class="action-row"><button class="btn btn-primary" data-open="${e(r.id)}">Reopen</button><button class="btn" data-copy="${e(r.id)}">Duplicate setup</button></div></div>`)).join(''):'<div class="empty">No saved sessions match.</div>';
    }
    async function refreshHistory(){history=await store.api('sessions');renderHistory();for(const id of ['compareA','compareB']){const val=$(id).value;$(id).innerHTML=history.map(r=>`<option value="${e(r.id)}">${e(r.metadata.studyId)} · ${e(r.metadata.operator)}</option>`).join('');if(history.some(r=>r.id===val))$(id).value=val;}if(!$('compareB').value&&history[1])$('compareB').value=history[1].id;}
    $('refreshHistory').onclick=()=>refreshHistory().catch(error=>tell(error.message));$('historyFilter').oninput=renderHistory;
    $('historyRows').onclick=async event=>{try{
        const open=event.target.dataset.open,copy=event.target.dataset.copy;if(!open&&!copy)return;
        if(copy){const record=await store.api(`sessions/${copy}`);await startFresh(record.snapshot.metadata);return;}
        if(store.id===open&&store.conflict){await store.open(open,true);tell('Saved version reopened. Conflicting data is retained in Download pending recovery.');return;}
        if(store.id===open){studyWorkspace.navigate('tab-dashboard');return;}
        if(store.id){if(!['READY','PAUSED','COMPLETED'].includes(machine.currentState))machine.pauseStudy();store.changed();if(!await store.flush())return;store.detach();}
        await store.open(open);tell('Session reopened. Review the state before resuming.');
    }catch(error){tell(error.message);}};
    state.verifyRefill=toteId=>{
        const slots=studyInventory.configuredInventory[toteId];
        modal(`Verify Tote ${toteId} refill`,`<p>Count each slot. Quantities must match the locked configuration.</p><div class="form-grid">${slots.map(s=>input(`refill-${s.id}`,`${e(s.skuId)} · expected ${s.digitalQty}`,0,0,100000)).join('')}</div>`,()=>{
            requireWritable();if(machine.currentState!=='TOTE_CHANGE')throw Error('The study is no longer waiting for a tote replacement.');
            if(slots.some(s=>Number($('refill-'+s.id).value)!==s.digitalQty))throw Error('Every refill count must match the configured quantity.');
            studyEventBus.emit('REFILL_VERIFIED',{toteId,counts:slots.map(s=>({slot:s.id,qty:s.digitalQty}))});studyEventBus.emit('TOTE_READY',{toteId});studyWorkspace.renderGrid();
        });
    };
    function renderInventory(){
        if(!studyWorkspace.metadata){$('inventoryOverview').innerHTML='<p>Lock a study to see both totes.</p>';return;}
        const valid=state.effectivePicks().filter(p=>p.valid!==false),recent=valid.slice(-20),mean=recent.length>=20?recent.reduce((sum,p)=>sum+p.cycleTimeMs,0)/recent.length/1000:null;
        $('inventoryOverview').innerHTML=Object.entries(studyInventory.totes).map(([id,t])=>{
            const units=t.slots.reduce((sum,s)=>sum+s.digitalQty,0);
            return `<div class="tote-card"><h3>Tote ${id} <span class="badge">${e(t.status)}</span></h3><p>${units} units remaining${mean&&t.status==='ACTIVE'?` · approx. ${Math.ceil(units*mean/60)} active min to depletion`:''}</p><div class="table-wrap"><table><thead><tr><th>Slot</th><th>SKU</th><th>Physical</th><th>Portal</th><th></th></tr></thead><tbody>${t.slots.map(s=>`<tr><td>${s.id}</td><td>${e(s.skuId)}</td><td>${s.physicalQty}</td><td>${s.digitalQty}</td><td><button class="btn" data-adjust="${id}:${s.id}" ${machine.currentState!=='PAUSED'||!store.canOperate()?'disabled':''}>Adjust</button></td></tr>`).join('')}</tbody></table></div><p class="micro">${t.status==='REPLACING'?'Refill verification required.':'Physical balance assumes each confirmed pick removed one unit; verify by counting.'}</p></div>`;
        }).join('');
    }
    $('inventoryOverview').onclick=event=>{if(!event.target.dataset.adjust)return;const [tote,id]=event.target.dataset.adjust.split(':'),slot=studyInventory.totes[tote].slots.find(s=>s.id===Number(id));
        modal(`Adjust Tote ${tote} · slot ${id}`,`<div class="form-grid">${input('adjustPhysical','Physical quantity',slot.physicalQty,0,100000)}${input('adjustDigital','Portal quantity',slot.digitalQty,0,100000)}</div><label for="adjustReason">Reason</label><input id="adjustReason" required maxlength="300">`,()=>{
            requirePaused();const physical=Number($('adjustPhysical').value),digital=Number($('adjustDigital').value),reason=$('adjustReason').value.trim();
            if(!reason||[physical,digital].some(v=>!Number.isInteger(v)||v<0||v>100000))throw Error('Enter whole-number quantities and a reason.');
            const correction={id:crypto.randomUUID(),timestamp:new Date().toISOString(),type:'inventory',toteId:tote,slot:Number(id),before:{physical:slot.physicalQty,digital:slot.digitalQty},after:{physical,digital},reason};
            state.corrections.push(correction);slot.physicalQty=physical;slot.digitalQty=digital;studyEventBus.emit('INVENTORY_CORRECTED',correction);studyWorkspace.renderGrid();renderInventory();
        });
    };
    $('recordException').onclick=()=>{
        if(!studyWorkspace.metadata||['READY','COMPLETED'].includes(machine.currentState)){tell('Start a study before recording an exception.');return;}
        const activeSlot=hardwareManager.activePTLSlot,activeTote=studyInventory.activeToteId;
        if(!['READY','PAUSED'].includes(machine.currentState)){machine.resumeState=machine.currentState;machine.pauseStudy();}
        modal('Record an exception',`<label for="exceptionKind">Type</label><select id="exceptionKind">${['wrong slot','wrong quantity','dropped item','sensor miss','delay'].map(v=>`<option>${v}</option>`).join('')}</select><label for="exceptionTarget">Applies to</label><select id="exceptionTarget"><option value="unfinished">Unfinished task / session</option>${studyDataExport.pickRecords.length?'<option value="last">Last completed pick</option>':''}</select><label for="exceptionReason">What happened?</label><input id="exceptionReason" required maxlength="300">`,()=>{
            requirePaused();const reason=$('exceptionReason').value.trim();if(!reason)throw Error('A reason is required.');
            const last=studyDataExport.pickRecords.at(-1),target=$('exceptionTarget').value,kind=$('exceptionKind').value;
            const record={id:crypto.randomUUID(),timestamp:new Date().toISOString(),type:kind,reason,slot:target==='last'?last.slot:activeSlot,toteId:target==='last'?last.toteId:activeTote,pickId:target==='last'?last.id:null,incomplete:target!=='last'};
            state.exceptions.push(record);
            if(target==='last')state.corrections.push({id:crypto.randomUUID(),timestamp:record.timestamp,type:'pick',pickId:last.id,reason,valid:false,exception:kind,...(kind.startsWith('wrong')?{accuracy:'incorrect'}:{})});
            studyEventBus.emit('EXCEPTION_RECORDED',record);studyWorkspace.updateMetrics();tell('Exception recorded. Review inventory before resuming.');
        });
    };
    $('annotatePick').onclick=()=>{
        try{requirePaused();}catch(error){tell(error.message);return;}
        if(!studyDataExport.pickRecords.length){tell('No completed picks to annotate.');return;}
        modal('Assess or annotate a pick',`<label for="annotationPick">Completed pick</label><select id="annotationPick">${studyDataExport.pickRecords.slice().reverse().map(p=>`<option value="${e(p.id)}">#${p.pickNumber} · ${e(p.skuId)} · slot ${p.slot}</option>`).join('')}</select><label for="annotationValidity">Timing assessment</label><select id="annotationValidity"><option value="keep">Keep current assessment</option><option value="invalid">Exclude from valid timing</option><option value="valid">Include in valid timing</option></select><label for="annotationAccuracy">Pick accuracy</label><select id="annotationAccuracy"><option value="keep">Keep current assessment</option><option value="not assessed">Not assessed</option><option value="correct">Verified correct</option><option value="incorrect">Verified incorrect</option></select><label for="annotationReason">Reason / observation</label><input id="annotationReason" required maxlength="300">`,()=>{
            requirePaused();const reason=$('annotationReason').value.trim();if(!reason)throw Error('A reason is required.');
            const correction={id:crypto.randomUUID(),timestamp:new Date().toISOString(),type:'pick',pickId:$('annotationPick').value,reason};
            if($('annotationValidity').value!=='keep')correction.valid=$('annotationValidity').value==='valid';
            if($('annotationAccuracy').value!=='keep')correction.accuracy=$('annotationAccuracy').value;
            state.corrections.push(correction);studyEventBus.emit('PICK_ANNOTATED',correction);studyWorkspace.updateMetrics();
        });
    };
    const fmt=v=>v==null?'—':Number(v).toFixed(2);
    function statsTable(rows,label){return `<table><thead><tr><th>${label}</th><th>Valid picks</th><th>Avg s</th><th>P50 s</th><th>P90 s</th><th>≤5s %</th><th>Errors</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${e(r.label)}</td><td>${r.count}</td><td>${fmt(r.average)}</td><td>${fmt(r.p50)}</td><td>${fmt(r.p90)}</td><td>${fmt(r.compliance)}</td><td>${r.errors||0}</td></tr>`).join('')}</tbody></table>`;}
    function renderAnalysis(){
        if(!studyWorkspace.metadata){$('analysisSummary').innerHTML='<p class="note">Open or start a study to see its analysis. Saved studies can be compared below.</p>';return;}
        const result=StudyAnalysis.analyze({picks:studyDataExport.pickRecords,corrections:state.corrections,exceptions:state.exceptions,inventory:{totes:studyInventory.totes}});
        $('slotHeatmap').classList.toggle('four-slots',studyWorkspace.metadata.numSlots===4);
        $('analysisSummary').innerHTML=`<div class="kpis"><div class="metric"><label>Valid timing samples</label><strong>${result.overall.count}</strong><small>${result.invalid} excluded</small></div><div class="metric"><label>Assessed accuracy</label><strong>${typeof result.accuracy==='string'?'Not assessed':fmt(result.accuracy.correctPercent)+'%'}</strong><small>${typeof result.accuracy==='string'?'Confirmation alone is not verification':result.accuracy.assessed+' picks assessed'}</small></div><div class="metric"><label>Exceptions</label><strong>${result.exceptions}</strong><small>Includes unfinished tasks</small></div><div class="metric"><label>Corrections</label><strong>${result.corrections}</strong><small>Original records retained</small></div></div>`;
        $('slotHeatmap').innerHTML=Array.from({length:studyWorkspace.metadata.numSlots},(_,i)=>{
            const s=result.slots.find(s=>s.label===i+1)||{label:i+1,count:0};return `<div class="heat-cell ${s.p90>5?'slow':''}"><h3>Slot ${s.label}</h3><strong>${fmt(s.p90)} <small>P90 seconds</small></strong><p>${s.count} valid picks · ${s.errors||0} errors</p><p>Average ${fmt(s.average)}s · P50 ${fmt(s.p50)}s<br>Within target ${fmt(s.compliance)}%</p></div>`;
        }).join('');
        $('blockTrends').innerHTML=result.blocks.length?statsTable(result.blocks,'Block'):'<p>No completed picks yet.</p>';
        $('smartAlerts').innerHTML=result.alerts.length?result.alerts.map(a=>`<div class="advice">${e(a)}</div>`).join(''):`<p>${result.overall.count<20?'Collect at least 20 valid picks for speed alerts; slowdown comparison requires 40.':'No threshold alerts in the current data.'}</p>`;
        $('dashboardAdvice').innerHTML=$('smartAlerts').innerHTML;
        $('auditRecent').innerHTML=[...state.exceptions,...state.corrections].sort((a,b)=>b.timestamp.localeCompare(a.timestamp)).slice(0,6).map(r=>`<div class="audit-line"><strong>${e(r.type)}</strong> ${e(r.reason)} <span>${e(new Date(r.timestamp).toLocaleTimeString())}</span></div>`).join('');
    }
    $('compareSessions').onclick=async()=>{try{
        if(!$('compareA').value||!$('compareB').value)throw Error('Save at least one study to compare.');
        const records=await Promise.all([$ ('compareA').value,$('compareB').value].map(id=>store.api(`sessions/${id}`)));
        const sku=$('compareSku').value.trim();
        const rows=records.map(r=>{const snap=r.snapshot,all=StudyAnalysis.effective(snap.picks,snap.corrections).filter(p=>!sku||p.skuId===sku);return{label:snap.metadata.studyId,...StudyAnalysis.stats(all.filter(p=>p.valid!==false)),errors:all.filter(p=>p.accuracy==='incorrect').length};});
        const [a,b]=records.map(r=>r.snapshot.metadata),different=['operator','configuration','mode','protocol','inventory'].filter(k=>JSON.stringify(a[k])!==JSON.stringify(b[k]));
        const conditions=[a,b].map(m=>`<div class="tote-card"><h3>${e(m.studyId)}</h3><p>${e(m.operator)} · ${e(m.configuration)}<br>${m.mode==='MODE_A'?'Wall clock':'Active picking'} · ${m.protocol.durationSec/60} min<br>Work ${m.protocol.workSec}s / rest ${m.protocol.breakSec}s<br>${m.protocol.maxCycles} cycles · completion: ${e(m.protocol.completion)}</p></div>`).join('');
        $('comparisonResult').innerHTML=`<div class="advice">${different.length?'Different conditions: '+e(different.join(', '))+'. Interpret comparisons with these differences in mind.':'Matching recorded conditions; this is a descriptive comparison.'}</div><div class="tote-overview">${conditions}</div><p>${sku?'SKU '+e(sku):'All SKUs'}</p><div class="table-wrap">${statsTable(rows,'Study')}</div>`;
    }catch(error){tell(error.message);}};
    function exportAllowed(){if(!studyWorkspace.metadata)throw Error('Open a study first.');if(!['PAUSED','COMPLETED','READY'].includes(machine.currentState))throw Error('Pause the study before exporting.');}
    function downloadRows(rows,filename){const cell=v=>studyDataExport.csvCell(typeof v==='object'?JSON.stringify(v):v);const keys=[...new Set(rows.flatMap(r=>Object.keys(r)))];studyDataExport.downloadCSV(keys.map(cell).join(',')+'\n'+rows.map(r=>keys.map(k=>cell(r[k]??'')).join(',')).join('\n'),filename);}
    $('exportDetailed').onclick=()=>{try{exportAllowed();const m=studyWorkspace.metadata;downloadRows(state.effectivePicks().map(p=>({session_id:store.id,study_id:m.studyId,operator_id:m.operator,configuration:m.configuration,protocol:JSON.stringify(m.protocol),...p,cycle_time_s:p.cycleTimeMs/1000})),`${m.studyId}-detailed.csv`);}catch(error){tell(error.message);}};
    $('exportAudit').onclick=()=>{try{exportAllowed();downloadRows([...state.exceptions,...state.corrections],`${studyWorkspace.metadata.studyId}-audit.csv`);}catch(error){tell(error.message);}};
    $('printSummary').onclick=()=>{try{exportAllowed();const snapshot=studyWorkspace.snapshot(),r=StudyAnalysis.analyze(snapshot),m=snapshot.metadata;
        $('printReport').innerHTML=`<h1>Stack n Stock · Study summary</h1><h2>${e(m.studyId)}</h2><p>Operator: ${e(m.operator)} · ${e(m.configuration)} · ${m.mode === 'MODE_A' ? 'Wall-clock mode' : 'Active-picking mode'} · ${e(machine.currentState)}</p><h2>Protocol</h2><p>Duration: ${m.protocol.durationSec / 60} min · Work block: ${m.protocol.workSec}s · Rest: ${m.protocol.breakSec}s · Tote target: ${m.protocol.maxCycles} · End by: ${e(m.protocol.completion)}</p><p>Active: ${Math.round(machine.activePickingMs/1000)}s · elapsed: ${Math.round(machine.totalElapsedMs/1000)}s · breaks: ${Math.round(machine.breakMs/1000)}s · interruptions: ${Math.round(machine.interruptionMs/1000)}s</p><h2>Metrics</h2>${statsTable([{label:'Overall',...r.overall,errors:state.effectivePicks().filter(p=>p.accuracy==='incorrect').length}],'Group')}<p>Accuracy: ${typeof r.accuracy==='string'?'not assessed':fmt(r.accuracy.correctPercent)+'% of '+r.accuracy.assessed+' assessed picks'}. ${r.invalid} invalid trials excluded.</p><h2>Slots</h2>${statsTable(r.slots,'Slot')}<h2>Blocks</h2>${statsTable(r.blocks,'Block')}<h2>Exceptions and corrections</h2>${[...state.exceptions,...state.corrections].map(c=>`<p>${e(c.timestamp)} · ${e(c.type)} · ${e(c.reason)}<br>Tote ${e(c.toteId || '—')} · Slot ${e(c.slot || '—')} ${c.before ? '· Physical ' + c.before.physical + ' → ' + c.after.physical + '; portal ' + c.before.digital + ' → ' + c.after.digital : ''} ${c.pickId ? '· Pick reference: ' + e(c.pickId) : ''} ${'valid' in c ? '· Timing: ' + (c.valid ? 'included' : 'excluded') : ''} ${c.accuracy ? '· Accuracy: ' + e(c.accuracy) : ''}</p>`).join('')||'<p>None recorded.</p>'}<h2>Advisory observations</h2>${r.alerts.map(a=>`<p>${e(a)}</p>`).join('')||'<p>No threshold alerts.</p>'}<p>Browser simulation. Report generated ${e(new Date().toLocaleString())}.</p>`;window.print();
    }catch(error){tell(error.message);}};
    const clock=ms=>`${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;
    setInterval(()=>{if(!window.studyWorkspace)return;renderInventory();renderAnalysis();$('dashRestTime').textContent=clock(machine.breakMs);$('dashInterruptTime').textContent=clock(machine.interruptionMs);},1000);
    document.querySelector('[data-target="tab-history"]').addEventListener('click',()=>refreshHistory().catch(error=>tell(error.message)));
    document.querySelector('[data-target="tab-analysis"]').addEventListener('click',()=>{renderAnalysis();refreshHistory().catch(error=>tell(error.message));});
    studyEventBus.on('*',()=>queueMicrotask(()=>{if(window.studyWorkspace){renderInventory();renderAnalysis();}}));
    setTimeout(async()=>{
        updateSummary();try{await loadPresets();await refreshHistory();}catch(error){tell('Local server unavailable. Launch the portal with Start_Study_Portal.bat.');}
        const draft=sessionStorage.getItem('sns-draft');if(draft){sessionStorage.removeItem('sns-draft');studyWorkspace.applyDraft(JSON.parse(draft));return;}
        const current=sessionStorage.getItem('sns-current');if(current){
            studyWorkspace.navigate('tab-history');$('recoveryNotice').innerHTML='<div class="advice">A saved session is available. Reopening safely…</div>';
            try{await store.open(current);$('recoveryNotice').textContent='';}catch(error){$('recoveryNotice').innerHTML=`<div class="advice">${e(error.message)} <button class="btn" id="retryRecovery">Retry recovery</button></div>`;$('retryRecovery').onclick=async()=>{try{await store.open(current);$('recoveryNotice').textContent='';}catch(err){tell(err.message);}};}
        }
    },0);
});
