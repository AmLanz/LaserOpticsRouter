/* Pure editing model. Python remains authoritative for optical calculations. */
'use strict';
const RouterEditor = (() => {
  const number = '[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:e[+-]?\\d+)?';
  let counter = 0;
  const uid = () => 's'+Date.now().toString(36)+'_'+(++counter).toString(36);
  const clone = value => JSON.parse(JSON.stringify(value));
  const words = text => String(text||'').split('#')[0].trim().split(/\s+/).filter(Boolean);
  const comment = text => String(text||'').includes('#')?' #'+String(text).split('#').slice(1).join('#'):'';
  function parse(raw) {
    const text=raw.toLowerCase(), p=text.match(/^([+_f-]*)(.*)$/), prefix=p[1], body=p[2];
    let m;
    if((m=text.match(new RegExp('^p('+number+')$','i'))))return {kind:'propagate',length:Number(m[1]),raw};
    const base={raw,size:prefix.includes('+')?'large':prefix.includes('-')?'small':'normal',flip:prefix.includes('_'),visual_flip:prefix.includes('f')};
    if((prefix.match(/[+-]/g)||[]).length>1||(prefix.match(/f/g)||[]).length>1||(prefix.match(/_/g)||[]).length>1)return {...base,kind:'unknown'};
    if(base.flip&&!/^(?:bd|r)/.test(body))return {...base,kind:'unknown'};
    if(body==='pol')return {...base,kind:'pol'};
    if(body==='g')return {...base,kind:'generic'};
    if(['laha','laqu','nd'].includes(body))return {...base,kind:body};
    if((m=body.match(new RegExp('^cyl('+number+')([hv])?$','i'))))return {...base,kind:'cyl',focal:Number(m[1]),axis:m[2]||'h'};
    if((m=body.match(new RegExp('^gr('+number+')a('+number+')m([+-]?\\d+)([hv])?$','i'))))return {...base,kind:'grating',grooves:Number(m[1]),angle:Number(m[2]),order:Number(m[3]),axis:m[4]||'h'};
    if((m=body.match(new RegExp('^resetd('+number+')f(inf|'+number+')$','i'))))return {...base,kind:'reset',reset_diameter:Number(m[1]),reset_focus:m[2]==='inf'?null:Number(m[2])};
    if((m=body.match(new RegExp('^tp('+number+')(?:d('+number+'))?$','i'))))return {...base,kind:'tp',angle:Number(m[1]),displacement:Number(m[2]||0)};
    if(/^bsc-?$/.test(body))return {...base,kind:'bsc',reverse:body.endsWith('-')};
    if((m=body.match(new RegExp('^l('+number+')$','i'))))return {...base,kind:'lens',focal:Number(m[1])};
    if((m=body.match(new RegExp('^(wp|rp|bd)('+number+')([hv])?(-)?$','i'))))return {...base,kind:m[1],amount:Number(m[2]),axis:m[3]||'h',reverse:!!m[4]};
    if((m=body.match(new RegExp('^(r|bs)('+number+')(?:v('+number+'))?(?:f('+number+'))?$','i')))){
      if((m[1]==='bs'&&m[4])||(base.flip&&!m[4]))return {...base,kind:'unknown'};
      return {...base,kind:m[4]?'oap':m[1]==='bs'?'bs':'mirror',horizontal:Number(m[2]),vertical:Number(m[3]||0),...(m[4]?{focal:Number(m[4])}:{})};
    }
    return {...base,kind:'unknown'};
  }
  function serialize(t) {
    const n=v=>{if(!Number.isFinite(Number(v)))throw Error('Enter a finite number.');return String(Number(v));};
    if(t.kind==='propagate')return 'p'+n(t.length);
    const prefix=(t.visual_flip?'f':'')+({small:'-',large:'+'}[t.size]||'')+(t.flip?'_':'');
    let body;
    if(t.kind==='lens')body='l'+n(t.focal);
    else if(t.kind==='cyl')body='cyl'+n(t.focal)+(t.axis||'h');
    else if(t.kind==='grating')body='gr'+n(t.grooves)+'a'+n(t.angle)+'m'+n(t.order)+(t.axis||'h');
    else if(t.kind==='reset')body='resetd'+n(t.reset_diameter)+'f'+(t.reset_focus==null?'inf':n(t.reset_focus));
    else if(t.kind==='pol')body='pol';
    else if(t.kind==='generic')body='g';
    else if(['laha','laqu','nd'].includes(t.kind))body=t.kind;
    else if(t.kind==='tp')body='tp'+n(t.angle)+'d'+n(t.displacement);
    else if(t.kind==='bsc')body='bsc'+(t.reverse?'-':'');
    else if(['wp','rp','bd'].includes(t.kind))body=t.kind+n(t.amount)+(t.axis||'h')+(t.reverse?'-':'');
    else if(['mirror','oap','bs'].includes(t.kind))body=(t.kind==='bs'?'bs':'r')+n(t.horizontal)+(Number(t.vertical)?'v'+n(t.vertical):'')+(t.kind==='oap'?'f'+n(t.focal):'');
    else throw Error('Edit this unrecognised step in Commands.');
    return prefix+body;
  }
  function part(t) {
    return JSON.stringify([t.kind,t.size,t.focal,t.amount,t.grooves,
      t.kind==='oap'?Math.acos(Math.max(-1,Math.min(1,Math.cos(t.horizontal*Math.PI/180)*Math.cos(t.vertical*Math.PI/180)))).toFixed(6):null]);
  }
  function ensure(row) {
    const tokens=words(row.commands);
    if(!Array.isArray(row.step_ids)||row.step_ids.length!==tokens.length||new Set(row.step_ids).size!==tokens.length)
      row.step_ids=tokens.map((_,i)=>String(i));
    row.step_labels??={};
    return tokens.map((raw,i)=>({...parse(raw),id:row.step_ids[i],label:row.step_labels[row.step_ids[i]]||''}));
  }
  function markStarter(row) {
    const entries=ensure(row);
    if(entries.length===1&&entries[0].raw==='p100')row.starter_step_id=entries[0].id;
  }
  const isStarter=(row,step)=>step?.id===row.starter_step_id&&step?.raw==='p100';
  function commit(config,row,entries) {
    const suffix=comment(row.commands);
    row.commands=entries.map(s=>s.raw).join(' ')+suffix;
    row.step_ids=entries.map(s=>s.id);
    if(!entries.some(s=>isStarter(row,s)))delete row.starter_step_id;
    const ids=new Set(row.step_ids.map(id=>row.id+':'+id));
    Object.keys(config.optic_overrides).forEach(key=>{if(key.startsWith(row.id+':')&&!ids.has(key))delete config.optic_overrides[key];});
    Object.keys(row.step_labels||{}).forEach(id=>{if(!row.step_ids.includes(id))delete row.step_labels[id];});
  }
  function reconcile(config,row,text) {
    delete row.starter_step_id;
    const old=ensure(row), incoming=words(text), assigned=new Map(), used=new Set();
    const normalized=s=>s.toLowerCase();
    const oldOpt=old.map((s,i)=>[s.raw,i]).filter(([s])=>parse(s).kind!=='propagate');
    const newOpt=incoming.map((s,i)=>[s,i]).filter(([s])=>parse(s).kind!=='propagate');
    if(JSON.stringify(oldOpt.map(([s])=>normalized(s)))===JSON.stringify(newOpt.map(([s])=>normalized(s)))){
      oldOpt.forEach(([,i],k)=>{assigned.set(newOpt[k][1],i);used.add(i);});
      // Preserve distance-step identities within unchanged runs between optics.
      const oa=[-1,...oldOpt.map(([,i])=>i),old.length],na=[-1,...newOpt.map(([,i])=>i),incoming.length];
      for(let k=1;k<oa.length;k++)if(oa[k]-oa[k-1]===na[k]-na[k-1])
        for(let j=1;j<oa[k]-oa[k-1];j++){assigned.set(na[k-1]+j,oa[k-1]+j);used.add(oa[k-1]+j);}
    }
    const unchanged=old.length===incoming.length&&old.every((s,i)=>normalized(s.raw)===normalized(incoming[i]));
    if(unchanged)old.forEach((_,i)=>{assigned.set(i,i);used.add(i);});
    const oldGroups=new Map(),newCounts=new Map();
    old.forEach((s,i)=>{const key=normalized(s.raw);if(!used.has(i)){if(!oldGroups.has(key))oldGroups.set(key,[]);oldGroups.get(key).push(i);}});
    incoming.forEach(raw=>newCounts.set(normalized(raw),(newCounts.get(normalized(raw))||0)+1));
    incoming.forEach((raw,i)=>{
      if(assigned.has(i))return;
      const key=normalized(raw),candidates=oldGroups.get(key)||[];
      if(candidates.length===1&&newCounts.get(key)===1){assigned.set(i,candidates[0]);used.add(candidates[0]);}
    });
    // Unique orientation-only edits keep a physical part's calibration. Repeated
    // identical candidates remain ambiguous and are deliberately not guessed.
    const oldParts=new Map(),newParts=new Map();
    const group=(map,key,i)=>{if(!map.has(key))map.set(key,[]);map.get(key).push(i);};
    old.forEach((s,i)=>{if(!used.has(i)&&!['propagate','unknown'].includes(s.kind))group(oldParts,part(s),i);});
    incoming.forEach((raw,i)=>{const t=parse(raw);if(!assigned.has(i)&&!['propagate','unknown'].includes(t.kind))group(newParts,part(t),i);});
    for(const [key,indices] of newParts){const before=oldParts.get(key)||[];if(indices.length===1&&before.length===1){assigned.set(indices[0],before[0]);used.add(before[0]);}}
    const entries=incoming.map((raw,i)=>({raw,id:assigned.has(i)?old[assigned.get(i)].id:uid()}));
    const lost=old.filter((s,i)=>!used.has(i)&&config.optic_overrides[row.id+':'+s.id]).length;
    row.commands=text;commit(config,row,entries);
    // Preserve exactly the user's whitespace and comments in text mode.
    row.commands=text;
    entries.forEach(s=>{const o=config.optic_overrides[row.id+':'+s.id];if(o)o.token=s.raw;});
    return lost;
  }
  function update(config,row,index,token) {
    const steps=ensure(row), before=steps[index], raw=serialize(token), key=row.id+':'+before.id;
    if(isStarter(row,before))delete row.starter_step_id;
    const changedPart=part(before)!==part(token);
    if(changedPart)delete config.optic_overrides[key];
    else if(config.optic_overrides[key])config.optic_overrides[key].token=raw;
    steps[index]={...before,...token,raw};commit(config,row,steps);
    return changedPart;
  }
  function operate(config,row,index,operation,raw='p100') {
    const entries=ensure(row), step=entries[index];
    if(operation==='insert')entries.splice(index,0,{raw,id:uid()});
    else if(operation==='replace'){
      if(!step)throw Error('Select a step to replace.');
      delete config.optic_overrides[row.id+':'+step.id];
      delete row.step_labels[step.id];
      if(isStarter(row,step))delete row.starter_step_id;
      entries[index]={raw,id:step.id};
    }
    else if(operation==='remove'){if(entries.length===1)throw Error('Keep at least one step in a path.');entries.splice(index,1);}
    else if(operation==='up'&&index>0)[entries[index-1],entries[index]]=[entries[index],entries[index-1]];
    else if(operation==='down'&&index<entries.length-1)[entries[index+1],entries[index]]=[entries[index],entries[index+1]];
    else if(operation==='duplicate'){
      const id=uid();entries.splice(index+1,0,{...step,id});
      const setting=config.optic_overrides[row.id+':'+step.id];
      if(setting)config.optic_overrides[row.id+':'+id]=clone(setting);
      if(step.label)row.step_labels[id]=step.label+' copy';
    }
    commit(config,row,entries);
    return entries;
  }
  class History {
    constructor(limit=60){this.limit=limit;this.reset(null);}
    reset(value){this.items=value?[JSON.stringify(value)]:[];this.index=this.items.length-1;this.lastGroup='';this.time=0;}
    record(value,group='',now=Date.now()){
      const text=JSON.stringify(value);if(this.items[this.index]===text)return;
      this.items=this.items.slice(0,this.index+1);
      if(group&&this.lastGroup===group&&now-this.time<700&&this.index>0)this.items[this.index]=text;
      else{this.items.push(text);if(this.items.length>this.limit)this.items.shift();this.index=this.items.length-1;}
      // Snapshot histories include copied endpoints; bound memory as well as count.
      let bytes=this.items.reduce((n,s)=>n+s.length,0);
      while(bytes>12000000&&this.items.length>2){bytes-=this.items.shift().length;this.index--;}
      this.lastGroup=group;this.time=now;
    }
    travel(delta){const i=this.index+delta;if(i<0||i>=this.items.length)return null;this.index=i;this.lastGroup='';return JSON.parse(this.items[i]);}
  }
  function presets(config,kind,defaults,limit=defaults.length){
    const counts=new Map();
    for(const row of config?.rows||[])for(const raw of words(row.commands)){
      const token=parse(raw),family=token.kind==='bd'&&token.flip?'bd-combine':token.kind;
      if(family!==kind||family==='unknown')continue;
      const normalized=serialize(token);counts.set(normalized,(counts.get(normalized)||0)+1);
    }
    const frequent=[...counts].filter(([,count])=>count>1).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([raw])=>raw);
    return [...new Set([...frequent,...defaults])].slice(0,Math.max(limit,1)).map(raw=>({raw,count:counts.get(raw)||0}));
  }
  return {parse,serialize,ensure,markStarter,isStarter,reconcile,update,operate,words,uid,clone,History,presets};
})();
if(typeof module!=='undefined')module.exports=RouterEditor;
