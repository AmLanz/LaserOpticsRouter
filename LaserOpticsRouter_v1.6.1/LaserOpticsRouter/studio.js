/* Visual sequence editor and local draft workflow; no optical solver here. */
'use strict';
let studioSelected=null, studioHistory=new RouterEditor.History(), studioRestoring=false;
let studioSaveTimer, studioLiveTimer, studioSaving=false, studioSaveAgain=false;
let studioRecovery=null, studioDirty=false, studioTab='route', studioInsertRow=0, studioReplaceStep=null;
const studioInvalidInputs=new Set();
function studioHasInvalid(){
  for(const e of studioInvalidInputs)if(e.isConnected===false)studioInvalidInputs.delete(e);
  return studioInvalidInputs.size>0;
}
function studioValidateNumber(e){
  if(e.type!=='number')return true;
  const value=Number(e.value),min=e.min,max=e.max;
  if(e.value.trim()===''||!Number.isFinite(value)||(min!==undefined&&min!==''&&value<Number(min))||(max!==undefined&&max!==''&&value>Number(max))){
    studioInvalidInputs.add(e);clearTimeout(timer);clearTimeout(studioLiveTimer);sequence++;setValid(false);
    $('validation').className='notice error';$('validation').textContent='Complete the highlighted numeric field before previewing or building.';
    $('map-state').textContent='Last valid projection · incomplete input';
    e.classList?.add('invalid');return false;
  }
  studioInvalidInputs.delete(e);e.classList?.remove('invalid');return true;
}
const studioNames={generic:'Generic optic',propagate:'Free space',lens:'Lens',mirror:'Mirror',oap:'Off-axis parabola',pol:'Polarizer',bs:'Plate splitter',bsc:'Cube splitter',wp:'Wollaston prism',rp:'Rochon prism',bd:'Beam displacer',unknown:'Command'};
Object.assign(studioNames,{laha:'Half-wave plate',laqu:'Quarter-wave plate',nd:'ND filter',tp:'Tweaker plate'});
const studioCatalogue=[
  ['propagate','Free space','Distance along the current beam',['p10','p50','p100']],
  ['lens','Lens','Signed focal length: negative diverges, positive focuses',['l-100','l-50','l50','l100']],
  ['mirror','Mirror','Signed azimuth turn; elevation is available in Inspector',['r-90','r90','r45']],
  ['oap','Off-axis parabola','_ puts the parent axis on the outgoing leg; without _ it is on the incoming leg',['_r90f50','r90f50']],
  ['pol','Polarizer','Layout disc with manually entered throughput',['pol']],
  ['laha','Half-wave plate','λ/2 disc; manual loss and dispersion, no polarization simulation',['laha']],
  ['laqu','Quarter-wave plate','λ/4 disc; manual loss and dispersion, no polarization simulation',['laqu']],
  ['nd','ND filter','Neutral-density disc; example OD 1 (90% loss), adjustable in reference budget',['nd']],
  ['tp','Tweaker plate','Incidence from the normal and explicit parallel displacement in mm',['tp30d0.5','tp-30d0.5','tp0d0']],
  ['bs','Plate splitter','Straight transmitted beam and a signed reflected turn',['bs90','bs-90','bs30']],
  ['bsc','Cube splitter','Trailing − chooses the opposite reflected side; prefix +/− changes the size',['bsc','bsc-','+bsc','-bsc']],
  ['wp','Wollaston prism','Total separation; h/v is the local split plane',['wp20h','wp20v','wp10h']],
  ['rp','Rochon prism','Main ray stays straight; trailing − reverses the secondary side',['rp10.6h','rp10.6v','rp10.6h-']],
  ['bd','Beam displacer','Offset in mm; h/v selects the local displacement plane',['bd2.7h','bd4h','bd4v','bd4h-']],
  ['bd-combine','Combine displacer pair','_ combines a matching pair; use the same plane and side as the split',['_bd4h','_bd4v','_bd2.7h']],
  ['generic','Generic optic','Named placeholder, manual reference budget and optional beam color change',['g']]
];
function studioPresetLabel(raw){
  const t=RouterEditor.parse(raw);
  if(t.kind==='propagate')return fmt(t.length)+' mm';
  if(t.kind==='lens')return 'f '+(t.focal>0?'+':'')+fmt(t.focal)+' mm';
  if(t.kind==='mirror')return (t.horizontal>0?'+':'')+fmt(t.horizontal)+'°';
  if(t.kind==='oap')return t.flip?'Outgoing parent axis':'Incoming parent axis';
  if(t.kind==='bsc')return (t.size==='large'?'Large · ':t.size==='small'?'Small · ':'')+(t.reverse?'− side':'+ side');
  return raw;
}

function studioSnapshot(){return {config:RouterEditor.clone(config),editTarget:editTarget?{...editTarget}:null};}
function studioReset(){
  clearTimeout(studioSaveTimer);clearTimeout(studioLiveTimer);
  studioCloseCatalogue();
  studioInvalidInputs.clear();studioSelected=null;studioDirty=false;studioMeasuredEndpoint='';studioMapController?.reset();studioHistory.reset(studioSnapshot());studioHistoryButtons();
}
function studioHistoryButtons(){
  $('undo-draft').disabled=busy||studioHistory.index<1;
  $('redo-draft').disabled=busy||studioHistory.index>=studioHistory.items.length-1;
}
function studioChanged(){
  if(studioRestoring||!config)return;
  const active=document.activeElement,group=['INPUT','TEXTAREA'].includes(active?.tagName)?active.id||'':'';
  studioHistory.record(studioSnapshot(),group);studioHistoryButtons();
  studioDirty=true;$('draft-status').textContent='Unsaved changes';
  clearTimeout(studioSaveTimer);studioSaveTimer=setTimeout(studioSaveDraft,800);
  clearTimeout(studioLiveTimer);
  $('route-map').classList.add('outdated');
  $('map-state').textContent='Last valid projection · checking edits';
}
async function studioSaveDraft(){
  if(!config||studioRecovery)return;
  if(studioSaving){studioSaveAgain=true;return;}
  studioSaving=true;const key=docKey;
  try{await request('save_draft',{config,edit_target:editTarget});if(key===docKey)$('draft-status').textContent='Recovery draft saved locally';}
  catch(e){if(key===docKey)$('draft-status').textContent='Recovery unavailable · '+errorText(e);}
  finally{studioSaving=false;if(studioSaveAgain){studioSaveAgain=false;studioSaveDraft();}}
}
function studioTravel(delta){
  const state=studioHistory.travel(delta);if(!state)return;
  studioCloseCatalogue();
  const defaults=config.component_defaults;config=state.config;config.component_defaults=defaults;editTarget=state.editTarget;
  plan=null;opticSignature='';studioSelected=null;studioRestoring=true;studioInvalidInputs.clear();
  renderEditState();renderSettings();renderRows();schedule();studioRestoring=false;
  studioDirty=true;studioHistoryButtons();studioSaveDraft();showTab('route');
}
function studioFind(){
  if(!config?.rows?.length)return null;
  if(studioSelected){
    const ri=config.rows.findIndex(r=>r.id===studioSelected.row);
    if(ri>=0){const entries=RouterEditor.ensure(config.rows[ri]),index=entries.findIndex(s=>s.id===studioSelected.id);if(index>=0)return {row:config.rows[ri],ri,entries,index,step:entries[index]};}
  }
  const ri=Math.min(selectedRow||0,config.rows.length-1), row=config.rows[ri],entries=RouterEditor.ensure(row);
  if(!entries.length)return null;
  studioSelected={row:row.id,id:entries[0].id};return {row,ri,entries,index:0,step:entries[0]};
}
function studioDetail(s){
  if(s.kind==='propagate')return fmt(s.length)+' mm';
  if(s.kind==='lens')return 'f '+fmt(s.focal)+' mm';
  if(s.kind==='tp')return fmt(s.angle)+'° · '+fmt(s.displacement)+' mm offset';
  if(s.kind==='laha')return 'λ/2 · passive disc';
  if(s.kind==='laqu')return 'λ/4 · passive disc';
  if(s.kind==='nd')return 'Neutral density · manual loss';
  if(['mirror','oap','bs'].includes(s.kind))return fmt(s.horizontal)+'° / '+fmt(s.vertical)+'°'+(s.kind==='oap'?' · f '+fmt(s.focal)+' mm':'');
  if(['wp','rp','bd'].includes(s.kind))return fmt(s.amount)+(s.kind==='bd'?' mm':'°')+' · '+(s.axis==='v'?'vertical':'horizontal')+(s.flip?' · combine':'');
  if(s.kind==='bsc')return s.reverse?'90° · opposite port':'90° split';
  return s.kind==='unknown'?s.raw:'Transmission';
}
function studioStepsHtml(row,ri){
  const entries=RouterEditor.ensure(row);
  const byId=new Map((plan?.optics||[]).map(o=>[o.id,o]));
  return `<div class="sequence-list">${entries.map((s,i)=>{
    const selected=studioSelected?.row===row.id&&studioSelected.id===s.id;
    const candidate=byId.get(row.id+':'+s.id),o=candidate?.token===s.raw?candidate:null;
    return `<div class="sequence-step ${selected?'selected':''}"><button class="step-select" data-select-step="${ri}:${i}" aria-pressed="${selected}"><span class="step-index">${i+1}</span><span class="step-symbol ${s.kind}" aria-hidden="true">${s.kind==='propagate'?'↦':s.kind==='lens'?'()':s.kind==='mirror'?'∕':s.kind==='oap'?'⌒':'◇'}</span><span class="step-caption"><strong>${escapeHtml(s.label||studioNames[s.kind])}</strong><span>${escapeHtml(RouterEditor.isStarter(row,s)?'100 mm starter · click to replace':studioDetail(s))}</span></span><code>${escapeHtml(s.raw)}</code>${o?.settings?.custom?'<span class="cad-tag">CAD</span>':''}</button><button class="step-settings" data-select-step="${ri}:${i}" aria-label="Edit step ${i+1}">›</button></div>`;
  }).join('')}</div><div class="sequence-bottom"><button data-insert-step="${ri}">+ Add step</button><span class="hint">${entries.length} steps</span></div>`;
}
function studioRows(){
  studioFind();
  config.rows.forEach((row,ri)=>{const e=$('sequence-'+row.id);if(e)e.innerHTML=studioStepsHtml(row,ri);});
  studioInspector();
}
function studioInspector(){
  const f=studioFind(),box=$('step-editor');if(!f){box.innerHTML='<p class="empty">Enter a command or add a step.</p>';$('optics').innerHTML='';return;}
  const {step:s,entries,index,ri}=f,focus=rememberFocus();
  const field=(key,label,value,extra='')=>`<label>${label}<input id="step-${key}" data-step-field="${key}" type="number" step="any" value="${escapeHtml(value)}" ${extra}></label>`;
  const check=(key,label)=>`<label class="check"><input data-step-field="${key}" type="checkbox" ${s[key]?'checked':''}>${label}</label>`;
  let fields='';
  if(s.kind==='propagate')fields+=field('length','Distance · mm',s.length,'min="0"');
  if(['lens','oap'].includes(s.kind))fields+=field('focal','Focal length · mm',s.focal);
  if(s.kind==='tp')fields+=field('angle','Incidence from normal · °',s.angle,'min="-89.999" max="89.999"')+field('displacement','Signed displacement · mm',s.displacement,'min="-10000" max="10000"');
  if(['mirror','oap','bs'].includes(s.kind))fields+=field('horizontal','Azimuth change · °',s.horizontal)+field('vertical','Elevation change · °',s.vertical);
  if(['wp','rp','bd'].includes(s.kind))fields+=field('amount',s.kind==='bd'?'Displacement · mm':'Separation · °',s.amount)+`<label>Separation plane<select data-step-field="axis"><option value="h" ${s.axis==='h'?'selected':''}>Local horizontal</option><option value="v" ${s.axis==='v'?'selected':''}>Local vertical</option></select></label>`;
  if(!['propagate','unknown'].includes(s.kind))fields+=`<label>Nominal size<select data-step-field="size">${['small','normal','large'].map(k=>`<option value="${k}" ${s.size===k?'selected':''}>${k[0].toUpperCase()+k.slice(1)}</option>`).join('')}</select></label>`;
  if(['wp','rp','bd','bsc'].includes(s.kind))fields+=check('reverse','Opposite output side');
  if(s.kind==='oap')fields+=check('flip','Parent axis on outgoing leg (_)');
  if(s.kind==='bd')fields+=check('flip','Combine pair (_)');
  if(!['propagate','unknown'].includes(s.kind))fields+=check('visual_flip','Rotate CAD 180° around local Z (f)');
  box.innerHTML=`<p class="eyebrow">${escapeHtml(f.row.name)} / STEP ${index+1}</p><h3>${escapeHtml(studioNames[s.kind])}</h3><label class="step-name">Label<input id="step-label" data-step-label value="${escapeHtml(s.label)}" placeholder="Optional, e.g. steering mirror"></label><div class="grid two step-fields">${fields}</div>${s.kind==='unknown'?'<p class="notice warning">Edit this step using Commands on the path line.</p>':''}<div class="step-tools"><button data-step-op="up" ${index===0?'disabled':''} title="Move one step earlier">↑ Earlier</button><button data-step-op="down" ${index===entries.length-1?'disabled':''} title="Move one step later">↓ Later</button><button data-step-op="duplicate">Duplicate</button><button data-step-op="remove" class="danger" ${entries.length===1?'disabled':''}>Remove</button><button data-insert-step="${ri}">+ Insert after</button></div><p class="hint">${s.kind==='propagate'?'Both active prism/displacer outputs propagate by this distance.':'Changing the physical specification resets only this step’s custom assignment. Orientation variants retain shared calibration.'}</p>`;
  restoreFocus(focus);
}
function studioSelectedOptics(){
  const f=studioFind();if(!f)return [];
  return (plan?.optics||[]).filter(o=>o.id===f.row.id+':'+f.step.id&&o.token===f.step.raw);
}
function studioCatalogueRender(){
  const q=$('insert-filter').value.toLowerCase();
  $('insert-catalogue').innerHTML=studioCatalogue.map(([kind,label,desc,defaults])=>{
    const presets=RouterEditor.presets(config,kind,defaults);
    if(![label,desc,...presets.map(p=>p.raw)].join(' ').toLowerCase().includes(q))return '';
    const buttons=kind==='generic'?['disc','cube','ball'].map(shape=>`<button class="preset" data-add-command="g" data-generic-shape="${shape}"><strong>${shape[0].toUpperCase()+shape.slice(1)}</strong><code>g</code></button>`).join(''):presets.map(p=>`<button class="preset" data-add-command="${escapeHtml(p.raw)}"><strong>${escapeHtml(studioPresetLabel(p.raw))}</strong><code>${escapeHtml(p.raw)}</code>${p.count>1?`<span class="preset-used">Used ${p.count}×</span>`:''}</button>`).join('');
    return `<section class="catalogue-family"><h3>${escapeHtml(label)}</h3><p class="hint">${escapeHtml(desc)}</p><div class="preset-row">${buttons}<button class="preset custom-preset" data-add-command="${escapeHtml(defaults[0])}" data-custom-step="true"><strong>Custom…</strong><span>Edit in Inspector</span></button></div></section>`;
  }).join('')||'<p class="empty">No matching step type.</p>';
}
function studioOpenCatalogue(ri,step=null){
  studioInsertRow=ri;studioReplaceStep=step?{row:config.rows[ri].id,id:step.id}:null;
  $('insert-title').textContent=step?'Choose the first step':'Add a step';
  $('insert-hint').textContent=step?'Replace the starter p100 with any step below. Custom opens its parameters in the inspector.':'Insert after the selected step, then edit its parameters in the inspector.';
  $('insert-modal').hidden=false;$('insert-filter').value='';studioCatalogueRender();$('insert-filter').focus();
}
function studioCloseCatalogue(){studioReplaceStep=null;$('insert-modal').hidden=true;}

let studioMapController=null,studioMeasuredEndpoint='',studioUpstreamKey='';
function studioContextScene(endpoint){
  const direction=s=>{const a=(s.azimuth||0)*Math.PI/180,e=(s.elevation||0)*Math.PI/180;return [Math.cos(e)*Math.cos(a),Math.cos(e)*Math.sin(a),Math.sin(e)];};
  const wanted=new Set((endpoint?.state?.trace||[]).map(e=>e.id));
  const local=new Set([...(plan?.lines||[]),...(plan?.optics||[])].flatMap(o=>o.event_ids||[]));
  const inherited=(endpoint?.state?.trace||[]).slice(0,endpoint?.trace_start||0).some(e=>!local.has(e.id));
  if(!inherited)return {scene:plan,complete:true,key:''};
  if(!savedScene){ensureSavedScene();return {scene:plan,complete:false,key:''};}
  const tokens=new Set(),seen=new Set();let start=endpoint.start_state;
  while(start?.link){
    const link=start.link,key=[link.run_id,link.endpoint_id,JSON.stringify(start.position)].join('|');if(seen.has(key))break;seen.add(key);
    const matching=saved.filter(e=>e.run_id===link.run_id&&e.endpoint_id===link.endpoint_id&&e.state&&
      Math.hypot(...e.state.position.map((x,i)=>x-start.position[i]))<.001&&
      Math.hypot(...direction(e.state).map((x,i)=>x-direction(start)[i]))<.00002);
    if(matching.length!==1)break;
    const source=matching[0];tokens.add(source.run_token);start=source.start_state;
  }
  const keep=o=>tokens.has(o.run_token)&&(o.event_ids||[]).some(id=>wanted.has(id));
  const lines=(savedScene.lines||[]).filter(keep),optics=(savedScene.optics||[]).filter(keep);
  const available=new Set([...local,...lines.flatMap(l=>l.event_ids),...optics.flatMap(o=>o.event_ids)]);
  return {scene:{lines:[...lines,...(plan.lines||[])],optics:[...optics,...(plan.optics||[])]},
    complete:(endpoint.state.trace||[]).every(e=>available.has(e.id)),key:[...tokens].sort().join('|')};
}
function studioMap(){
  const host=$('route-map');if(!plan){host.innerHTML='<p class="empty">A valid route will appear here.</p>';$('route-metrics').innerHTML='';return;}
  if(!studioMapController)studioMapController=new RouterSchematic.Controller(host,id=>studioSelectMapOptic(id),()=>busy);
  const selected=studioFind(),rid=selected?.row.id||config.rows[selectedRow]?.id;
  const active=plan.rows.find(r=>r.id===rid)||plan.rows[0];
  const endpoints=active?[active.endpoint,...active.ports.filter(e=>e.kind==='end')]:[];
  const end=endpoints.find(e=>e.id===studioMeasuredEndpoint)||endpoints[0];
  studioMeasuredEndpoint=end?.id||'';
  $('map-endpoint').innerHTML=endpoints.map(e=>`<option value="${escapeHtml(e.id)}" ${e.id===studioMeasuredEndpoint?'selected':''}>${escapeHtml(e.name)}</option>`).join('');
  const event_ids=(end?.state?.trace||[]).map(e=>e.id);
  const context=studioContextScene(end);
  if(context.key!==studioUpstreamKey){studioMapController.reset();studioUpstreamKey=context.key;}
  studioMapController.update(context.scene,$('map-projection').value||'XY',{
    selectedOptic:selected?selected.row.id+':'+selected.step.id:'',polarization:$('map-polarization').checked!==false,
    layers:end?[{event_ids,color:'#164d70',name:end.name}]:[]});
  host.classList.toggle('outdated',!valid);
  $('map-state').textContent=valid?(context.complete?'Measured path highlighted · accumulated from source':'Available path highlighted · some upstream sections are unavailable'):'Last valid schematic and endpoint values';
  const stats=end?.stats;
  const diameter=stats?.status==='geometric focus'?'0 mm · ideal geometric focus':fmt(stats?.diameter_mm)+' mm';
  $('route-metrics').innerHTML=stats?[
    ['Measured endpoint',end.name],['From source',fmt(stats.path_mm)+' mm'],
    ['Diameter at this endpoint',diameter],['Reference GDD',fmt(stats.gdd_fs2)+' fs²']
  ].map(([k,v])=>`<div><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join(''):'';
}
function studioSelectMapOptic(id){
  if(!valid){status('Correct input before selecting from the schematic');return;}
  const optic=plan?.optics.find(o=>o.id===id);if(optic)studioClick({dataset:{selectStep:optic.row+':'+optic.step}});
}
function studioAfterAnalysis(){
  studioRows();studioMap();
  if($('live-preview').checked&&valid&&!busy&&studioTab==='route'){
    const revision=sequence;clearTimeout(studioLiveTimer);
    studioLiveTimer=setTimeout(async()=>{
      if(revision!==sequence||busy||!valid||!$('live-preview').checked)return;
      try{await request('preview',{config,edit_token:editTarget?.token,quality:'draft'});if(revision===sequence)status('Live draft · nominal planes, no CAD geometry');}
      catch(e){$('live-preview').checked=false;globalError(e);status('Live preview paused');}
    },350);
  }
}
function studioRecoveryOffer(data){
  studioRecovery=data.recovery||null;
  $('recovery-notice').hidden=!studioRecovery;
  if(studioRecovery)$('recovery-description').textContent='A local draft is available from '+new Date(studioRecovery.saved_at*1000).toLocaleString()+'. Restore it before editing, or discard it.';
  if(data.recovery_error)globalError({message:data.recovery_error});
}
function studioInput(e){
  if(e.id==='insert-filter'){studioCatalogueRender();return true;}
  if(e.dataset.stepLabel!==undefined){const f=studioFind();if(f){if(RouterEditor.isStarter(f.row,f.step))delete f.row.starter_step_id;f.row.step_labels[f.step.id]=e.value.slice(0,100);studioRowsOnly();schedule();}return true;}
  if(e.dataset.stepField&&e.type==='number'){
    const f=studioFind();if(!f)return true;
    const token={...f.step,[e.dataset.stepField]:Number(e.value)};
    const reset=RouterEditor.update(config,f.row,f.index,token);
    editingNotice=reset?'Physical specification changed: recheck the selected optic’s component.':'';
    $('commands-'+f.row.id).value=f.row.commands;studioRowsOnly();schedule();return true;
  }
  return false;
}
function studioRowsOnly(){config.rows.forEach((row,ri)=>{const e=$('sequence-'+row.id);if(e)e.innerHTML=studioStepsHtml(row,ri);});}
function studioRevealInspector(){
  if(window.matchMedia?.('(max-width:850px)').matches)
    document.querySelector('.inspector')?.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function studioChange(e){
  if(e.id==='map-projection'||e.id==='map-polarization'){studioMap();return true;}
  if(e.id==='map-endpoint'){studioMeasuredEndpoint=e.value;studioMap();return true;}
  if(e.id==='live-preview'){if(e.checked)studioAfterAnalysis();else clearTimeout(studioLiveTimer);return true;}
  if(e.dataset.stepField&&e.type!=='number'){
    const f=studioFind();if(!f)return true;
    RouterEditor.update(config,f.row,f.index,{...f.step,[e.dataset.stepField]:e.type==='checkbox'?e.checked:e.value});
    renderRows();schedule();return true;
  }
  return false;
}
async function studioClick(b){
  if(b.dataset.mapAction){const [target,action]=b.dataset.mapAction.split(':');const controller=target==='route'?studioMapController:target==='saved'?savedMapController:calculatorMapController;if(controller){if(action==='fit')controller.fit();else controller.zoom(action==='in'?1.3:1/1.3);}return true;}
  if(b.id==='undo-draft'){studioTravel(-1);return true;}
  if(b.id==='redo-draft'){studioTravel(1);return true;}
  if(b.dataset.selectStep){
    const [ri,i]=b.dataset.selectStep.split(':').map(Number),row=config.rows[ri];
    const step=RouterEditor.ensure(row)[i];
    studioSelected={row:row.id,id:step.id};selectedRow=ri;
    studioRows();renderOptics(true);studioMap();
    if(RouterEditor.isStarter(row,step)){studioOpenCatalogue(ri,step);return true;}
    studioRevealInspector();if(!valid&&!studioHasInvalid())schedule();return true;
  }
  if(b.dataset.stepOp){
    const f=studioFind();if(!f)return true;RouterEditor.operate(config,f.row,f.index,b.dataset.stepOp);
    if(b.dataset.stepOp==='duplicate')studioSelected={row:f.row.id,id:f.row.step_ids[f.index+1]};
    if(b.dataset.stepOp==='remove')studioSelected={row:f.row.id,id:f.row.step_ids[Math.min(f.index,f.row.step_ids.length-1)]};
    renderRows();renderOptics(true);schedule();return true;
  }
  if(b.dataset.insertStep!==undefined){studioOpenCatalogue(Number(b.dataset.insertStep));return true;}
  if(b.id==='insert-cancel'){studioCloseCatalogue();return true;}
  if(b.dataset.addCommand){
    const target=studioReplaceStep,row=target?config.rows.find(r=>r.id===target.row):config.rows[studioInsertRow],f=studioFind();
    const entries=row?RouterEditor.ensure(row):[],index=target?entries.findIndex(s=>s.id===target.id):f?.row===row?f.index+1:entries.length;
    if(!row||(target&&!RouterEditor.isStarter(row,entries[index]))){studioCloseCatalogue();throw Error('The selected starter step changed. Select it again.');}
    RouterEditor.operate(config,row,index,target?'replace':'insert',b.dataset.addCommand);
    if(b.dataset.genericShape)config.optic_overrides[row.id+':'+row.step_ids[index]]={token:'g',representation:'builtin',shape:b.dataset.genericShape};
    studioSelected={row:row.id,id:row.step_ids[index]};selectedRow=config.rows.indexOf(row);
    studioCloseCatalogue();renderRows();renderOptics(true);schedule();studioRevealInspector();
    if(b.dataset.customStep){const t=RouterEditor.parse(b.dataset.addCommand),id=t.kind==='propagate'?'step-length':t.kind==='tp'?'step-angle':['lens','oap'].includes(t.kind)?'step-focal':['mirror','bs'].includes(t.kind)?'step-horizontal':['wp','rp','bd'].includes(t.kind)?'step-amount':'step-label';$(id)?.focus();$(id)?.select?.();}
    return true;
  }
  if(b.id==='restore-recovery'){
    const data=studioRecovery;if(!data)return true;
    const defaults=config.component_defaults;config=data.config;config.component_defaults=defaults||{};
    const exact=savedRuns.find(r=>r.token===data.edit_target?.token&&r.editable!==false);
    const candidates=data.edit_target?savedRuns.filter(r=>r.run_id===(data.edit_target.run_id||config.route_id)&&r.editable!==false):[];
    const match=exact||(candidates.length===1?candidates[0]:null);
    editTarget=match?{token:match.token,name:match.name,run_id:match.run_id}:null;
    if(data.edit_target&&!editTarget){config.route_id=rowId();editingNotice='Original route is unavailable or ambiguous. Recovered as a new draft; check its placement before building.';}
    studioRecovery=null;$('recovery-notice').hidden=true;plan=null;opticSignature='';
    studioReset();renderSettings();renderRows();renderEditState();schedule();return true;
  }
  if(b.id==='discard-recovery'){await request('discard_draft');studioRecovery=null;$('recovery-notice').hidden=true;studioSaveDraft();return true;}
  if(b.id==='clear-preview'){clearTimeout(studioLiveTimer);$('live-preview').checked=false;await request('clear_preview');status('Preview cleared');return true;}
  return false;
}
function studioMapClick(e){
  const target=e.target.closest?.('[data-map-optic]');if(!target||busy)return false;
  if(!target.dataset?.mapOptic)return false;
  if(!valid){status('Correct input before selecting from the projection');return true;}
  const o=plan?.optics.find(o=>o.id===target.dataset.mapOptic);if(!o)return false;
  studioClick({dataset:{selectStep:o.row+':'+o.step}});return true;
}
function studioKey(e){
  if(busy)return;
  if(e.altKey&&e.key.toLowerCase()==='z'){e.preventDefault();studioTravel(e.shiftKey?1:-1);}
  else if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();if(valid)$('preview').click();}
  else if(e.key==='Escape')studioCloseCatalogue();
  else if((e.key==='Enter'||e.key===' ')&&e.target.dataset?.mapOptic){e.preventDefault();studioMapClick(e);}
}
