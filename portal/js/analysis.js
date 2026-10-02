/* Deterministic advice only: these functions never change the study protocol. */
(function(root){
    function effective(picks, corrections=[]){return picks.map(p=>{
        const out={...p};for(const c of corrections)if(c.pickId===p.id)for(const k of ['valid','accuracy','exception'])if(k in c)out[k]=c[k];return out;
    });}
    function stats(picks){
        const values=picks.map(p=>p.cycleTimeMs/1000).filter(n=>Number.isFinite(n)&&n>=0).sort((a,b)=>a-b),n=values.length;
        return {count:n,average:n?values.reduce((a,b)=>a+b,0)/n:null,p50:n?(values[Math.floor((n-1)/2)]+values[Math.floor(n/2)])/2:null,p90:n?values[Math.ceil(n*.9)-1]:null,compliance:n?values.filter(v=>v<=5).length/n*100:null};
    }
    function analyze(snapshot){
        const picks=effective(snapshot.picks||[],snapshot.corrections),valid=picks.filter(p=>p.valid!==false);
        const result={overall:stats(valid),slots:[],blocks:[],alerts:[],accuracy:'not assessed',invalid:picks.length-valid.length,exceptions:(snapshot.exceptions||[]).length,corrections:(snapshot.corrections||[]).length};
        const assessed=picks.filter(p=>['correct','incorrect'].includes(p.accuracy));
        if(assessed.length)result.accuracy={assessed:assessed.length,correctPercent:assessed.filter(p=>p.accuracy==='correct').length/assessed.length*100};
        for(const [kind,key] of [['slots','slot'],['blocks','pickBlock']])for(const group of [...new Set(picks.map(p=>p[key]||1))].sort((a,b)=>a-b)){
            const rows=picks.filter(p=>(p[key]||1)===group);result[kind].push({label:group,...stats(rows.filter(p=>p.valid!==false)),errors:rows.filter(p=>p.accuracy==='incorrect').length,invalid:rows.filter(p=>p.valid===false).length});
        }
        if(valid.length>=20){
            const recent=stats(valid.slice(-20));
            if(recent.p90>5)result.alerts.push(`Recent P90 is ${recent.p90.toFixed(2)}s across 20 valid picks (target 5s). Review slow slots and recorded delays.`);
            const base=stats(valid.slice(0,20)).p50;
            if(valid.length>=40&&base>0&&recent.p50>base*1.2)result.alerts.push(`Recent median is ${recent.p50.toFixed(2)}s versus the first 20-pick baseline of ${base.toFixed(2)}s, over 20% slower. Review conditions and ask the operator before changing the protocol.`);
        }
        for(const [id,tote] of Object.entries(snapshot.inventory?.totes||{}))if(tote.slots.some(s=>s.physicalQty!==s.digitalQty))result.alerts.push(`Tote ${id}: physical and portal quantities differ. Pause and verify the count.`);
        return result;
    }
    root.StudyAnalysis={effective,stats,analyze};
    if(typeof module!=='undefined')module.exports=root.StudyAnalysis;
})(typeof window!=='undefined'?window:globalThis);
