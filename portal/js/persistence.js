/* Revisioned snapshots plus a durable browser outbox. One serialized request at a time. */
class StudyPersistence {
    constructor() {
        this.writer = crypto.randomUUID();
        this.id = null; this.revision = 0; this.blocked = false; this.conflict = false;
        this.dirty = false; this.running = null; this.pending = null; this.updated = null;
        this.ready = false;
        setInterval(() => { if(this.id && this.ready && !this.conflict){this.dirty=true;this.flush();} }, 1500);
    }
    async api(path, body) {
        const response = await fetch('/api/'+path, {method:body?'POST':'GET', headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(5000)});
        const data=await response.json();
        if(!response.ok){const error=new Error(data.error||'Save failed');error.status=response.status;throw error;}
        return data;
    }
    key(){return 'sns-outbox-'+this.id;}
    canOperate(){return !this.blocked && !this.conflict && this.ready;}
    status(text, bad=false) {
        const el=document.getElementById('saveStatus');if(el){el.textContent=text;el.className='badge '+(bad?'save-error':'green');el.title=this.updated?'Last saved '+new Date(this.updated).toLocaleString():text;}
        window.dispatchEvent(new Event('save-status'));
    }
    async create() {
        this.id=crypto.randomUUID();this.revision=0;this.ready=true;this.blocked=true;
        sessionStorage.setItem('sns-current',this.id);
        this.dirty=true;await this.flush();return !this.blocked;
    }
    changed(){if(!this.ready)return;this.dirty=true;queueMicrotask(()=>{
        try{localStorage.setItem(this.key()+'-latest',JSON.stringify(window.studyWorkspace.snapshot()));}
        catch(error){this.blocked=true;window.studyStateMachineInstance.pauseStudy();this.status('Browser backup unavailable · picks suspended',true);}
        this.flush();
    });}
    async flush() {
        if(this.running)return this.running;
        if(!this.id||!this.ready||this.conflict)return false;
        this.running=this.drain();
        try{return await this.running;}finally{this.running=null;}
    }
    async drain(){
        try{
            while(this.dirty||this.pending){
                if(!this.pending){
                    this.dirty=false;
                    this.pending={writer:this.writer,revision:this.revision,requestId:crypto.randomUUID(),snapshot:window.studyWorkspace.snapshot()};
                    localStorage.setItem(this.key(),JSON.stringify(this.pending));
                }
                this.status('Saving…');
                const result=await this.api(`sessions/${this.id}/save`,this.pending);
                this.revision=result.revision;this.updated=result.updated;this.pending=null;
                localStorage.removeItem(this.key());
            }
            const recovered=this.blocked&&this.revision>1;this.blocked=false;
            localStorage.removeItem(this.key()+'-latest');
            this.status('Saved · '+new Date(this.updated).toLocaleTimeString());
            if(recovered)window.studyWorkspace.tell('Saving recovered. Review the session and resume when ready.');
            return true;
        }catch(error){
            this.blocked=true;this.conflict=error.status===409;
            const machine=window.studyStateMachineInstance;
            if(!['SETUP','READY','PAUSED','COMPLETED'].includes(machine.currentState)){
                machine.resumeState=machine.currentState;
                machine.setState('PAUSED');
            }
            // Keep the in-flight request unchanged for idempotent retries, plus the latest paused recovery state.
            try{localStorage.setItem(this.key()+'-latest',JSON.stringify(window.studyWorkspace.snapshot()));}catch{}
            this.dirty=true;
            this.status(this.conflict?'Save conflict · reopen session':'Save failed · picks suspended',true);
            window.studyWorkspace?.tell(error.message);
            return false;
        }
    }
    async open(id, canonical=false){
        let result;
        const initialPending=localStorage.getItem('sns-outbox-'+id);
        try{result=await this.api(`sessions/${id}/claim`,{writer:this.writer});}
        catch(error){
            const unsaved=initialPending?JSON.parse(initialPending):null;
            if(error.status!==404||!unsaved||unsaved.revision!==0)throw error;
            unsaved.writer=this.writer;
            await this.api(`sessions/${id}/save`,unsaved);
            result=await this.api(`sessions/${id}/claim`,{writer:this.writer});
        }
        if(canonical){
            const archived={pending:localStorage.getItem('sns-outbox-'+id),latest:localStorage.getItem('sns-outbox-'+id+'-latest')};
            localStorage.setItem('sns-conflict-'+id+'-'+Date.now(),JSON.stringify(archived));
            localStorage.removeItem('sns-outbox-'+id);localStorage.removeItem('sns-outbox-'+id+'-latest');
        }
        const savedPending=localStorage.getItem('sns-outbox-'+id);
        // Replay exactly the original request; a lost response returns the same receipt.
        if(savedPending){
            const p=JSON.parse(savedPending);
            p.writer=this.writer;
            await this.api(`sessions/${id}/save`,p);
            localStorage.removeItem('sns-outbox-'+id);
            result=await this.api(`sessions/${id}`);
        }
        // Refresh uses a new writer. An existing tab's lease must expire before takeover.
        this.id=id;this.revision=result.revision;this.updated=result.updated;this.ready=false;this.conflict=false;this.blocked=false;this.pending=null;
        sessionStorage.setItem('sns-current',id);
        const latestRaw=localStorage.getItem(this.key()+'-latest');
        const snapshot=latestRaw?JSON.parse(latestRaw):result.snapshot;
        // Only use a newer local recovery snapshot with an identical immutable pick prefix.
        const stable=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
        const validLatest=latestRaw&&snapshot.savedAt>=result.snapshot.savedAt&&stable(snapshot.metadata)===stable(result.snapshot.metadata)&&['picks','corrections','exceptions'].every(k=>stable((snapshot[k]||[]).slice(0,(result.snapshot[k]||[]).length))===stable(result.snapshot[k]||[]));
        window.studyWorkspace.restore(validLatest?snapshot:result.snapshot);
        this.ready=true;this.dirty=true;
        await this.flush();if(!this.blocked)localStorage.removeItem(this.key()+'-latest');
    }
    detach(){this.ready=false;this.id=null;this.pending=null;this.dirty=false;this.blocked=false;this.conflict=false;sessionStorage.removeItem('sns-current');}
}
window.studyPersistence=new StudyPersistence();
