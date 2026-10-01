/* Offline Fusion palette. The Python core is the authority for all beam states. */
'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n, digits=5) => Number.isFinite(n) ? Number(n.toPrecision(digits)).toString() : '—';
const familyNames = {lens:'Lens',cyl:'Cylindrical lens',reset:'Reset plate',mirror:'Mirror',oap:'OAP mirror',pol:'Polarizer',bs:'Plate splitter',bsc:'Cube splitter',wp:'Wollaston prism',rp:'Rochon prism',bd:'Beam displacer',laha:'Half-wave plate · λ/2',laqu:'Quarter-wave plate · λ/4',nd:'ND filter',tp:'Tweaker plate',grating:'Reflection grating',generic:'Generic optic'};
const swatches = {lens:'#6fcfdf', mirror:'#98a8b7', oap:'#c6a35d', pol:'#737c88', bs:'#387dd8', bsc:'#70a6e0',wp:'#3b786c',rp:'#4a749e',bd:'#6b6387'};
swatches.generic='#aa94c7';
Object.assign(swatches,{cyl:'#6fcfdf',grating:'#be9f67',reset:'#74b6a0'});
Object.assign(swatches,{laha:'#aed0d3',laqu:'#b9c4dd',nd:'#596470',tp:'#a3c6d8'});
let config, plan, saved = [], savedRuns = [], editTarget = null, manageTarget = null, docKey = '', selectedRow = 0, valid = false, busy = false;
let sequence = 0, timer, opticSignature = '', pasteTarget = 0, editingNotice = '';
let analysisRunning=false, analysisAgain=false, loadEpoch=0;
let buildContext={intent:'legacy',can_build:true,requires_hybrid:false,message:''};
const budgetDefaults = {lens:{loss_pct:1,gdd_fs2:100},mirror:{loss_pct:1,gdd_fs2:0},oap:{loss_pct:2,gdd_fs2:0},pol:{loss_pct:5,gdd_fs2:100},bs:{transmission_pct:49,reflection_pct:49,gdd_t_fs2:100,gdd_r_fs2:0},bsc:{transmission_pct:49,reflection_pct:49,gdd_t_fs2:300,gdd_r_fs2:300}};
Object.assign(budgetDefaults,{wp:{transmission_pct:49,reflection_pct:49,gdd_t_fs2:0,gdd_r_fs2:0},rp:{transmission_pct:49,reflection_pct:49,gdd_t_fs2:0,gdd_r_fs2:0},bd:{transmission_pct:49,reflection_pct:49,gdd_t_fs2:0,gdd_r_fs2:0,loss_pct:1,gdd_fs2:0}});
budgetDefaults.generic={loss_pct:0,gdd_fs2:0};
Object.assign(budgetDefaults,{cyl:{loss_pct:1,gdd_fs2:100},grating:{loss_pct:0,gdd_fs2:0},reset:{loss_pct:0,gdd_fs2:0}});
Object.assign(budgetDefaults,{laha:{loss_pct:1,gdd_fs2:50},laqu:{loss_pct:1,gdd_fs2:50},nd:{loss_pct:90,gdd_fs2:100},tp:{loss_pct:1,gdd_fs2:100}});
let componentDefaultDrafts={},componentDefaultKey='bs',savingDefaultKey=null;
const componentDefaultDirty=new Set();
let calculatorSelection = new Set();
let calculatorColors=new Map(),calculatorResult=null,calculatorRevision=0,calculatorTimer;
let savedScene=null,savedSceneEpoch=0,savedScenePending=false,calculatorMapController=null;
let savedMapController=null,savedHighlight=null;
const selectionPalette=['#2878ce','#d63b4e','#258252','#8959bd','#d98728','#278f99'];
const softwareCitation='Amon P. Lanz (2026). LaserOpticsRouter (version 1.7.1). Computer software. Apache-2.0. https://github.com/AmLanz/LaserOpticsRouter';
const softwareBibtex='@software{lanz_laseropticsrouter_2026,\n  author = {Lanz, Amon P.},\n  title = {LaserOpticsRouter},\n  version = {1.7.1},\n  year = {2026},\n  license = {Apache-2.0},\n  url = {https://github.com/AmLanz/LaserOpticsRouter},\n  note = {Independent optical-layout add-in for Autodesk Fusion}\n}';
let refreshTarget = null;
const budgetLabels = {loss_pct:'Loss · %',gdd_fs2:'GDD · fs²',n:'Refractive index n',thickness_mm:'Effective glass thickness · mm',transmission_pct:'Transmission · %',reflection_pct:'Reflection · %',gdd_t_fs2:'Transmitted GDD · fs²',gdd_r_fs2:'Reflected GDD · fs²',n_t:'Transmitted n',n_r:'Reflected n',thickness_t_mm:'Transmitted glass thickness · mm',thickness_r_mm:'Reflected glass thickness · mm'};
function defaultBudgetLabel(kind,key) {
  const sides={transmission_pct:'Main output · %',reflection_pct:'Secondary output · %',gdd_t_fs2:'Main GDD · fs²',gdd_r_fs2:'Secondary GDD · fs²'};
  if(kind==='bd'&&['loss_pct','gdd_fs2'].includes(key))return 'Combiner '+budgetLabels[key].toLowerCase();
  return ['wp','rp','bd'].includes(kind)?sides[key]||budgetLabels[key]:budgetLabels[key];
}

async function request(action, data={}) {
  const requestDoc=docKey;
  const raw = await window.adsk.fusionSendData(action, JSON.stringify({...data, doc_key:requestDoc}));
  if(action!=='bootstrap'&&requestDoc!==docKey)throw {message:'Document changed; stale response discarded.',stale:true};
  const reply = typeof raw === 'string' ? JSON.parse(raw) : raw;
  if (!reply || !reply.ok) throw (reply?.error || {message:'No response from Fusion.'});
  return reply.result;
}
function errorText(error) { return error?.message || String(error); }
function globalError(error) {
  if(error?.stale)return;
  if(error?.build_context)acceptBuildContext(error.build_context);
  $('copy-diagnostic').hidden=!error;
  $('global-error').hidden = !error;
  $('global-error').textContent = error ? errorText(error) : '';
}
function status(text) { $('footer-status').textContent = text; }
function setValid(value) {
  value=!!value&&!studioHasInvalid();valid = value;
  $('preview').disabled = !value || busy;
  $('build').disabled = !value || busy || !buildContext.can_build;
  $('build-close').disabled = !value || busy || !buildContext.can_build;
  document.querySelectorAll('[data-live-endpoint]').forEach(b => b.disabled = !value || busy);
}
function setBusy(value) {
  busy = value; setValid(valid);
  if(value){clearTimeout(studioLiveTimer);clearTimeout(calculatorTimer);}
  studioHistoryButtons();
  for(const id of ['clear-preview','live-preview','preview-quality'])$(id).disabled=value;
  document.querySelector('main').inert = value;
  $('manage-confirm').disabled = value;
  document.querySelector('nav').inert = value;
}
function renderEditState() {
  $('edit-notice').hidden = !editTarget;
  $('edit-name').textContent = editTarget?.name || '';
  $('build').textContent = buildContext.requires_hybrid ? (editTarget?'Switch to Hybrid & replace':'Switch to Hybrid & build') : (editTarget ? 'Replace route' : 'Build');
  $('build-close').textContent = buildContext.requires_hybrid ? (editTarget?'Switch, replace & close':'Switch, build & close') : (editTarget ? 'Replace & close' : 'Build & close');
  $('route-title').textContent = editTarget ? 'Edit saved route' : 'Build a path';
}
function acceptBuildContext(context) {
  if(!context)return;
  buildContext=context;
  $('document-type-notice').hidden=!context.message;
  $('document-type-notice').textContent=context.message||'';
  $('document-type-notice').className='notice '+(context.can_build?'warning':'error');
  renderEditState();setValid(valid);
}
function acceptSaved(data) { savedScene=null;savedSceneEpoch++;savedScenePending=false;saved = data.items; savedRuns = data.runs || []; if(savedHighlight&&!savedRuns.some(r=>r.token===savedHighlight.run_token))savedHighlight=null;renderSaved(); renderCalculator(); }
function showTab(name) {
  studioTab=name;clearTimeout(studioLiveTimer);
  if(name==='calculator')renderCalculator();
  if(name==='saved')renderSaved();
  if(name==='settings')renderComponentDefaults();
  document.querySelectorAll('.tab-content').forEach(x => x.hidden = x.id !== 'tab-'+name);
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x.dataset.tab === name));
}
function rowId() { return 'line_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,7); }
function rememberFocus() {
  const e = document.activeElement;
  return e?.id ? {id:e.id, start:e.selectionStart, end:e.selectionEnd} : null;
}
function restoreFocus(old) {
  if (!old || !$(old.id)) return;
  const e = $(old.id); e.focus({preventScroll:true});
  if (typeof old.start === 'number') try { e.setSelectionRange(old.start, old.end); } catch (_) {}
}
function sourceChanged() {
  config.source.position = ['x','y','z'].map(a => Number($('src-'+a).value));
  ['azimuth','elevation','diameter_mm','wavelength_nm','m2'].forEach(k => config.source[k] = Number($('src-'+k).value));
  config.source.model = $('src-model').value;
  config.source.color = $('src-color').value||'red';
  const mode=$('src-spectrum-mode').value||'central';
  config.source.spectrum=mode==='central'?{}:{mode,width_nm:Number($('src-spectrum-width').value),samples:Number($('src-spectrum-samples').value)};
  sourceSummary(); schedule();
}
function sourceSummary() {
  const s = config.source;
  $('gaussian-fields').hidden = s.model !== 'gaussian';
  $('spectrum-fields').hidden=!(s.spectrum?.mode&&s.spectrum.mode!=='central');
  $('spectrum-width-label').textContent=s.spectrum?.mode==='gaussian'?'Spectral intensity FWHM · nm':'Sideband offset ±Δλ · nm';
  $('spectrum-samples-label').hidden=s.spectrum?.mode!=='gaussian';
  $('source-summary').textContent = `${fmt(s.diameter_mm)} mm · ${s.model === 'gaussian' ? 'Gaussian, M² '+fmt(s.m2) : 'geometric'}`;
}
function renderSettings() {
  config.options.use_assigned_components ??= true; // older saved routes retain their CAD build choice
  config.options.protect_components ??= true;
  config.options.reuse_gratings ??= true;
  config.budget_defaults ??= JSON.parse(JSON.stringify(budgetDefaults));
  config.sizes ??= {};Object.keys(familyNames).forEach(k=>config.sizes[k]??={small:12.7,normal:25.4,large:50.8});
  $('run-name').value = config.run_name || 'LaserOpticsRouter';
  ['x','y','z'].forEach((a,i) => $('src-'+a).value = config.source.position[i]);
  ['azimuth','elevation','diameter_mm','wavelength_nm','m2','model'].forEach(k => $('src-'+k).value = config.source[k]);
  $('src-color').value=config.source.color||'red';
  $('src-spectrum-mode').value=config.source.spectrum?.mode||'central';
  $('src-spectrum-width').value=config.source.spectrum?.width_nm??10;
  $('src-spectrum-samples').value=config.source.spectrum?.samples??9;
  sourceSummary();
  Object.keys(config.options).forEach(k => {
    const e = $('opt-'+k); if (!e) return;
    if (e.type === 'checkbox') e.checked = config.options[k]; else e.value = config.options[k];
  });
  $('sizes').innerHTML = Object.entries(familyNames).map(([k,label]) => `<tr><td>${label}</td>${['small','normal','large'].map(size => `<td><input type="number" min="0.01" step="any" aria-label="${label} ${size} size" data-size-kind="${k}" data-size="${size}" value="${escapeHtml(config.sizes[k][size])}"></td>`).join('')}</tr>`).join('');
  $('budget-defaults').innerHTML = Object.entries(budgetDefaults).map(([kind,fields])=>`<h3>${familyNames[kind]}</h3><div class="grid two">${Object.keys(fields).map(key=>`<label>${defaultBudgetLabel(kind,key)}<input type="number" step="any" data-budget-kind="${kind}" data-budget-key="${key}" value="${escapeHtml(config.budget_defaults[kind]?.[key]??fields[key])}"></label>`).join('')}</div>`).join('');
}
function clearRowOverrides(row, newCommands) {
  if(newCommands!==undefined){
    const lost=RouterEditor.reconcile(config,row,newCommands);
    editingNotice=lost?`${lost} changed or ambiguous optic assignment${lost===1?'':'s'} reset; other assignments retained.`:'';
  }else{
    Object.keys(config.optic_overrides).forEach(k=>{if(k.startsWith(row.id+':'))delete config.optic_overrides[k];});
    delete row.step_ids;delete row.step_labels;delete row.starter_step_id;
  }
  opticSignature='';
}
function renderRows() {
  const opened=new Map([...document.querySelectorAll('.command-editor')].map(e=>[e.dataset.commandsFor,e.open]));
  studioFind();
  $('rows').innerHTML = config.rows.map((row,i) => `<article class="route-row" data-row="${i}">
    <div class="row-head"><span class="row-number">${i+1}</span><input id="row-name-${row.id}" class="row-name" aria-label="Path ${i+1} name" data-row-name="${i}" value="${escapeHtml(row.name)}"><button class="remove-row" data-remove-row="${i}" aria-label="Remove path ${i+1}" ${config.rows.length===1?'disabled':''}>×</button></div>
    <div class="row-start"><span>Start</span><select data-start-mode="${i}" aria-label="Path ${i+1} start"><option value="source" ${row.start_mode==='source'?'selected':''}>Source settings</option><option value="previous" ${row.start_mode==='previous'?'selected':''} ${i===0?'disabled':''}>Previous line end</option><option value="snapshot" ${row.start_mode==='snapshot'?'selected':''}>Copied endpoint</option></select><button data-paste-row="${i}">Paste endpoint…</button></div>
    ${row.start_mode==='snapshot'?`<div class="snapshot-info">${escapeHtml(row.endpoint_name || 'Endpoint snapshot · beam state retained')}</div>`:''}
    <div id="sequence-${row.id}">${studioStepsHtml(row,i)}</div>
    <details class="command-editor" data-commands-for="${row.id}" ${opened.get(row.id)!==false?'open':''}><summary>Commands <span class="summary-note">edit the same sequence as text</span></summary><textarea id="commands-${row.id}" class="commands" data-commands="${i}" spellcheck="false" rows="2" aria-label="Path ${i+1} commands">${escapeHtml(row.commands)}</textarea></details>
    <div id="output-${row.id}" class="row-output"></div>
  </article>`).join('');
  if (plan) renderOutputs();studioInspector();
}
function statsHtml(s, rowLength) {
  const state = `${s.status}${s.model==='gaussian'?' · Gaussian':''}`;
  let entries = [
    ['Endpoint XYZ · mm', s.position.map(n => fmt(n)).join(', ')],
    ['Azimuth / elevation · °', (s.azimuth_defined?fmt(s.azimuth):'undefined ('+fmt(s.azimuth)+' retained)')+' / '+fmt(s.elevation)],
    ['Direction · unit XYZ', s.direction.map(n => fmt(n)).join(', ')],
    ['Diameter · mm',fmt(s.diameter_mm)],
    ['Geometric from source · mm',fmt(s.path_mm)],
    ['Glass-adjusted path · mm',fmt(s.optical_path_mm)],
    ['Cumulative loss · %',fmt(s.loss_pct)],
    ['Accumulated GDD · fs²',fmt(s.gdd_fs2)]];
  if (rowLength !== undefined) entries.push(['This line · mm',fmt(rowLength)]);
  entries.push(['Wavelength · nm',fmt(s.wavelength_nm)]);
  if(s.diameter_h_mm!==undefined)entries.push(['Diameter H × V · mm',fmt(s.diameter_h_mm)+' × '+fmt(s.diameter_v_mm)],['Major × minor · mm',fmt(s.diameter_major_mm)+' × '+fmt(s.diameter_minor_mm)],['H / V waist distance · mm',fmt(s.waist_distance_h_mm)+' / '+fmt(s.waist_distance_v_mm)]);
  if(s.spectral_weight!==undefined&&s.spectral_weight!==1)entries.push(['Relative spectral density',fmt(s.spectral_weight)]);
  if(s.spectral_ray_count)entries.push(['Spectral samples carried',String(s.spectral_ray_count+1)+' including centre']);
  if (s.model === 'gaussian'&&s.diameter_h_mm===undefined) entries.push(['Waist diameter · mm',fmt(s.waist_diameter_mm)],['Waist distance · mm',fmt(s.waist_distance_mm)],['Far-field half-angle · mrad',fmt(s.far_half_angle_mrad)]);
  return `<div class="state-line">${escapeHtml(state)}</div><dl class="stat-grid">${entries.map(([label,value])=>`<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>`;
}
function renderOutputs() {
  if (!plan) return;
  plan.rows.forEach((row,i) => {
    const box = $('output-'+row.id); if (!box) return;
    box.innerHTML = `<details class="endpoint-detail"><summary>End · Ø ${fmt(row.endpoint.stats.diameter_mm)} mm · ${fmt(row.length_mm)} mm this line</summary>`+statsHtml(row.endpoint.stats,row.length_mm)+'</details>'+
      row.ports.map((p,pi) => `<div class="port"><div class="port-head"><span>${escapeHtml(p.name)}</span><button data-live-endpoint data-copy-port="${i}:${pi}">Copy ${p.kind==='reflected'?'reflected':'endpoint'}</button><button data-live-endpoint data-use-port="${i}:${pi}">New line</button></div><div class="hint">XYZ ${p.stats.position.map(n=>fmt(n)).join(', ')} mm · Az ${fmt(p.stats.azimuth)}° · El ${fmt(p.stats.elevation)}° · Ø ${fmt(p.stats.diameter_mm)} mm</div></div>`).join('')+
      `<div class="end-actions"><button data-live-endpoint data-copy-end="${i}">Copy endpoint</button><button data-live-endpoint data-use-end="${i}">Continue in new line</button></div><details class="steps"><summary>Command details</summary><div class="table-wrap"><table><thead><tr><th>Command</th><th>XYZ · mm</th><th>Diameter · mm</th></tr></thead><tbody>${row.steps.map(s=>`<tr><td><code>${escapeHtml(s.command)}</code></td><td>${s.position.map(n=>fmt(n,4)).join(', ')}</td><td>${fmt(s.diameter_mm)}</td></tr>`).join('')}</tbody></table></div></details>`;
  });
  setValid(valid);
}
function override(optic) {
  const existing = config.optic_overrides[optic.id];
  if (existing?.token === optic.token) return existing;
  return config.optic_overrides[optic.id] = {...JSON.parse(JSON.stringify(optic.settings)), token:optic.token};
}
function cardSettings(o) {
  const existing=config.optic_overrides[o.id];
  const local = existing&&existing.token===o.token ? existing : {};
  const mode = local.representation || o.settings?.representation || 'default';
  const base = mode === 'default' ? config.component_defaults[o.default_key] || {} : {...o.settings,...local};
  return {shift:[0,0,0], rotation:[0,0,0], reference:[0,0,0], ...base,
    representation:mode, custom:mode==='default'?(base.custom??!!(base.component_token||base.component_ref_token)):mode==='custom'};
}
function editableOverride(o) {
  const s = {...JSON.parse(JSON.stringify(cardSettings(o))), token:o.token};
  if (s.representation === 'default') {s.representation = s.custom?'custom':'builtin';s.budget??=JSON.parse(JSON.stringify(o.budget||{}));}
  config.optic_overrides[o.id] = s;
  return s;
}
const templateFields = ['custom','component_token','component_ref_token','component_name','component_linked','diameter_mm','design_bend_deg','roll_deg','budget','tube_length_mm','crystal_width_mm','shape','depth_mm','beam_color','displacement_mm','component_rotation_deg','assembly_offset_mm'];
function colorOptions(current,inherit=false){return (inherit?'<option value="inherit">Keep incoming color</option>':'')+Object.keys(RouterSchematic.colors).map(c=>`<option value="${c}" ${c===current?'selected':''}>${c[0].toUpperCase()+c.slice(1)}</option>`).join('');}
function componentTemplate(s) { return Object.fromEntries(templateFields.filter(k=>s[k]!==undefined).map(k=>[k,s[k]])); }
function opticInput(o, key, label, value, extra='') {
  return `<label>${label}<input id="optic-${o.id.replace(':','-')}-${key}" data-optic="${escapeHtml(o.id)}" data-optic-field="${key}" type="number" step="any" value="${escapeHtml(value)}" ${cardSettings(o).representation==='default'?'disabled':''} ${extra}></label>`;
}
function componentAdjustmentHtml(s,input){
  return `<details class="spaced"><summary>Component rotation &amp; assembly offsets</summary><p class="hint">Corrections about fixed component-origin X, then Y, then Z, before alignment. −90° about Z maps the original +Y normal onto the target +X normal. Offsets use Hybrid assembly X/Y/Z even when the route is rotated. They affect CAD placement only. Preparing the source file is preferred.</p><div class="grid three">${['X','Y','Z'].map((axis,i)=>input('component_rotation_deg.'+i,'Component R'+axis.toLowerCase()+' · °',s.component_rotation_deg?.[i]??0)).join('')}</div><div class="grid three spaced">${['X','Y','Z'].map((axis,i)=>input('assembly_offset_mm.'+i,'Assembly Δ'+axis+' · mm',s.assembly_offset_mm?.[i]??0)).join('')}</div></details>`;
}
function physicalKey(raw){
  const t=RouterEditor.parse(raw),prefix={small:'-',large:'+'}[t.size]||'';
  if(['bs','tp','laha','laqu','nd','pol','bsc'].includes(t.kind))return prefix+t.kind;
  if(t.kind==='generic')return prefix+'g';
  if(t.kind==='lens')return prefix+'l'+t.focal;
  if(t.kind==='cyl')return prefix+'cyl'+t.focal+'h';
  if(t.kind==='grating')return prefix+'gr'+t.grooves+'a0m1h';
  if(t.kind==='reset')return prefix+'resetd5finf';
  if(['wp','rp','bd'].includes(t.kind))return prefix+t.kind+t.amount;
  if(t.kind==='oap'){const angle=Math.acos(Math.max(-1,Math.min(1,Math.cos(t.horizontal*Math.PI/180)*Math.cos(t.vertical*Math.PI/180))))*180/Math.PI;return prefix+'r'+Number(angle.toFixed(8))+'f'+t.focal;}
  if(t.kind==='mirror')return prefix+'r'+t.horizontal+(t.vertical?'v'+t.vertical:'');
  throw Error('Enter one optic command, for example l75, +bs30 or r90f100.');
}
function defaultKind(key){return RouterEditor.parse(key.replace(/^([+-]?)bs$/,'$1bs90').replace(/^([+-]?)tp$/,'$1tp0d0')).kind;}
function defaultDraft(){
  return componentDefaultDrafts[componentDefaultKey]??=JSON.parse(JSON.stringify(config.component_defaults[componentDefaultKey]||{custom:false,shift:[0,0,0],rotation:[0,0,0],reference:[0,0,0]}));
}
function renderComponentDefaults(){
  const host=$('component-default-editor');if(!host||!config)return;
  const base=['l50','l100','l-50','l-100','cyl100h','r90','r-90','r90f50','pol','bs','bsc','laha','laqu','nd','tp','wp20','rp10.6','bd4','gr600a0m1h','g'];
  const keys=[...new Set([...base,...Object.keys(config.component_defaults),...Object.keys(componentDefaultDrafts),...(plan?.optics||[]).map(o=>o.default_key),componentDefaultKey])];
  $('component-default-key').innerHTML=keys.filter(k=>defaultKind(k)!=='unknown').map(k=>`<option value="${escapeHtml(k)}" ${k===componentDefaultKey?'selected':''}>${escapeHtml(familyNames[defaultKind(k)]||k)} · ${escapeHtml(k)}</option>`).join('');
  const s=defaultDraft(),kind=defaultKind(componentDefaultKey),custom=s.custom??!!(s.component_token||s.component_ref_token);
  const field=(key,label,value,extra='')=>`<label>${label}<input id="default-${key}" data-default-field="${key}" type="number" step="any" value="${escapeHtml(value)}" ${extra}></label>`;
  const split=['bs','bsc','wp','rp','bd'].includes(kind),fields=split?['transmission_pct','reflection_pct','gdd_t_fs2','gdd_r_fs2','n_t','thickness_t_mm','n_r','thickness_r_mm',...(kind==='bd'?['loss_pct','gdd_fs2','n','thickness_mm']:[])]:['loss_pct','gdd_fs2','n','thickness_mm'];
  const values={...(custom?(split?{transmission_pct:50,reflection_pct:50}:{}):budgetDefaults[kind]),...(!custom?config.budget_defaults?.[kind]:{}),...s.budget};
  host.innerHTML=`<div class="default-title"><h3>${escapeHtml(familyNames[kind])} <code>${escapeHtml(componentDefaultKey)}</code></h3><span id="component-default-status" class="hint">${savingDefaultKey===componentDefaultKey?'Saving…':componentDefaultDirty.has(componentDefaultKey)?'Unsaved default edits':config.component_defaults[componentDefaultKey]?'Saved in this document':'Built-in fallback'}</span></div>
    <label>Default representation<select id="default-representation"><option value="builtin" ${custom?'':'selected'}>Built-in optic</option><option value="custom" ${custom?'selected':''}>Assigned component</option></select></label>
    ${custom?`<div class="selection"><span>${escapeHtml(s.component_name||'No component selected')}</span><button id="default-pick-component">Choose component…</button></div><p class="axis-note">${preparedAxesNote({kind})}</p><button data-component-guide>Component preparation guide</button>${componentAdjustmentHtml(s,field)}`:''}
    <div class="grid two spaced">${field('diameter_mm',kind==='bsc'?'Nominal edge · mm':'Nominal diameter · mm',s.diameter_mm||config.sizes[kind]?.[componentDefaultKey[0]==='+'?'large':componentDefaultKey[0]==='-'?'small':'normal']||25.4,'min="0.01"')}${['bs','bsc'].includes(kind)?field('displacement_mm','Transmitted displacement · mm',s.displacement_mm||0,'min="-10000" max="10000"'):''}${kind==='bsc'?field('roll_deg','Reflected port roll · °',s.roll_deg||0):''}${kind==='oap'?field('design_bend_deg','Part design bend · °',s.design_bend_deg??Number(componentDefaultKey.match(/r([\d.]+)f/)?.[1]||90),'min="0.01" max="180"'):''}</div>
    ${kind==='bs'?'<p class="hint">All plate-splitter angles and turn signs share this component for the selected size. Positive displacement moves transmission away from the reflected branch; reflection stays at the incoming hit point.</p>':''}
    ${kind==='tp'?'<p class="hint">Every tilt/displacement of the same size shares this physical plate. The tp command specifies the incidence and displacement for each encounter.</p>':''}
    <details class="budget-card"><summary>Default reference loss, GDD &amp; glass</summary><p class="hint">Manual reference values. Built-in fallback values come from Reference budget defaults below; assigned components start at zero (splitters: 50/50). Saving freezes the values you enter here.</p><div class="grid two">${fields.map(key=>field('budget.'+key,defaultBudgetLabel(kind,key),values[key]??0)).join('')}</div></details>
    <div class="button-row"><button id="default-save" class="primary">Save default</button><button id="default-discard">Discard edits</button><button id="default-remove" ${config.component_defaults[componentDefaultKey]?'':'disabled'}>Restore built-in fallback</button></div><p class="hint">Applies to optics with Use default checked. Rebuilt routes use the prepared X-normal component convention. Save the Fusion document to retain these defaults.</p>`;
}
function markDefaultDirty(){componentDefaultDirty.add(componentDefaultKey);$('component-default-status').textContent='Unsaved default edits';}
function changeDefaultField(e){
  const s=defaultDraft(),parts=e.dataset.defaultField.split('.');
  if(parts.length===2){s[parts[0]]??=parts[0]==='budget'?{}:[0,0,0];s[parts[0]][parts[0]==='budget'?parts[1]:Number(parts[1])]=Number(e.value);}else s[parts[0]]=Number(e.value);
  markDefaultDirty();
}
function opticBudgetHtml(o, expanded=false) {
  const prism=['wp','rp','bd'].includes(o.kind),splitter=['bs','bsc','wp','rp','bd'].includes(o.kind)&&!o.combining;
  const fields=splitter?['transmission_pct','reflection_pct','gdd_t_fs2','gdd_r_fs2','n_t','thickness_t_mm','n_r','thickness_r_mm']:['loss_pct','gdd_fs2','n','thickness_mm'];
  const b=o.budget||{};
  const labels=prism?{transmission_pct:'Main output · %',reflection_pct:'Secondary output · %',gdd_t_fs2:'Main GDD · fs²',gdd_r_fs2:'Secondary GDD · fs²',n_t:'Main n',n_r:'Secondary n',thickness_t_mm:'Main glass thickness · mm',thickness_r_mm:'Secondary glass thickness · mm'}:{};
  return `<details class="budget-card" data-budget-id="${escapeHtml(o.id)}" ${expanded?'open':''}><summary>Reference loss, GDD &amp; glass length</summary><p class="hint">Approximate bookkeeping only; no change to the modeled beam. ${splitter?(prism?'Main + secondary ≤ 100%; enter the assumed power split.':'T + R ≤ 100%; the remainder is excess loss.'):'Loss is the percentage removed at this encounter.'} ${o.combining?'Combining applies this loss to each arm separately; it does not split power again.':''} GDD is signed. Glass correction is (n − 1) × effective thickness; enter the total distance travelled in glass, already included in the geometric path.</p><div class="grid two">${fields.map(key=>opticInput(o,'budget.'+key,labels[key]||budgetLabels[key],b[key]??0)).join('')}</div></details>`;
}
function renderOptics(force=false) {
  if (!plan) return;
  const visible=studioSelectedOptics();
  const active=document.activeElement;
  if(!force&&active?.dataset?.opticField&&visible.some(o=>o.id===active.dataset.optic))return;
  const signature = JSON.stringify([studioSelected,visible.map(o=>[o.id,o.token,o.label,o.diameter_mm,o.bend_deg,o.focal_mm,cardSettings(o),o.frame,o.budget,config.component_defaults[o.default_key]])]);
  if (signature===opticSignature && !force) return;
  opticSignature=signature;
  const focus=rememberFocus();
  const opened=new Set([...document.querySelectorAll('.optic-card[open]')].map(e=>e.dataset.opticId));
  const openBudgets=new Set([...document.querySelectorAll('.budget-card[open]')].map(e=>e.dataset.budgetId));
  $('optic-count').textContent = `${plan.optics.length} optic${plan.optics.length===1?'':'s'}`;
  $('optics').innerHTML=visible.length ? visible.map(o=>{
    if(o.kind==='reset')return `<div class="notice"><strong>Virtual reset plate</strong><p>Resets the spatial beam envelope to Ø ${fmt(o.reset_diameter_mm)} mm, ${o.reset_focus_mm==null?'collimated at this plane':'focus '+fmt(o.reset_focus_mm)+' mm ahead (negative: behind)'}. Position, direction, wavelength, color and accumulated budgets are retained. Gaussian beams retain M² and diffract after the plate. This is a user-imposed boundary condition, not a physical collimating optic.</p></div>`;
    const s=cardSettings(o), stored=config.component_defaults[o.default_key];
    const isDefault=s.representation==='default';
    const axis = preparedAxesNote(o);
    const values=[o.focal_mm!=null?'f = '+fmt(o.focal_mm)+' mm':null, ['mirror','oap','bs','bsc'].includes(o.kind)?'3D bend '+fmt(o.bend_deg)+'° · incidence '+fmt(o.incidence_deg)+'°':null, o.oap?'parent f '+fmt(o.oap.parent_focal_mm)+' mm':null, ['wp','rp','bd'].includes(o.kind)?(o.kind==='bd'?'Offset '+fmt(o.amount)+' mm':'Separation '+fmt(o.amount)+'°')+' · '+(o.axis==='v'?'vertical':'horizontal')+(o.combining?' · combining':''):null].filter(Boolean).join(' · ');
    return `<details class="optic-card" data-optic-id="${escapeHtml(o.id)}" open><summary><span class="optic-heading"><span class="optic-dot" style="background:${swatches[o.kind]}"></span>${escapeHtml(o.label)}</span><span class="summary-note">${familyNames[o.kind]} · ${o.kind==='bsc'?'edge':'Ø'} ${fmt(o.diameter_mm)} mm</span></summary><div class="optic-body"><div class="optic-meta">${escapeHtml(values)}</div>
      <label class="check default-check"><input type="checkbox" data-use-default="${escapeHtml(o.id)}" ${isDefault?'checked':''}>Use default · ${escapeHtml(o.default_key)}</label><p class="hint">${isDefault?'Reads the component, placement and reference properties from Defaults. Uncheck to customize this optic.':'Local settings for this optic. Check Use default to follow the global default again.'}</p><div class="selection"><span>${isDefault?escapeHtml(s.custom?s.component_name||'Assigned component':'Built-in optic'):''}</span><button data-open-default="${escapeHtml(o.default_key)}">Edit global default…</button></div>
      ${!isDefault?`<label class="representation-label">Local representation<select data-representation="${escapeHtml(o.id)}"><option value="builtin" ${!s.custom?'selected':''}>Built-in optic</option><option value="custom" ${s.custom?'selected':''}>Assigned component</option></select></label>`:''}
      ${o.visual_flip?'<p class="notice">f: CAD rotated 180° about its surface-normal X axis at the origin. Calculated beam direction is unchanged.</p>':''}
      <div class="grid two spaced">${opticInput(o,'diameter_mm',o.kind==='bsc'?'Nominal edge · mm':'Nominal diameter · mm',s.diameter_mm ?? o.diameter_mm,'min="0.01"')}${o.kind==='bsc'?opticInput(o,'roll_deg','Reflected port roll · °',s.roll_deg||0):''}</div>
      ${['bs','bsc'].includes(o.kind)?`<div class="grid two spaced">${opticInput(o,'displacement_mm','Transmitted displacement · mm',s.displacement_mm??0,'min="-10000" max="10000"')}</div><p class="hint">Reflection starts at the incoming hit point. Positive displacement shifts only transmission away from the reflected branch; negative reverses it. No internal glass propagation is calculated.</p>`:''}
      ${o.kind==='grating'?`<div class="notice">Reflection grating · β ${fmt(o.beta_deg)}° · width ratio ${fmt(o.anamorphic)}<br>mλ = d(sin α + sin β). Mode: ${escapeHtml(o.spectrum_mode||'central')}. Set wavelength and bandwidth under Source. Sampled rays intersect the fixed surfaces and continue through later optics, including return passes. Efficiency and GDD are manual estimates.${o.reuse_id?'<br>Return encounter: uses the physical grating placed at '+escapeHtml(o.reuse_id)+'.':''}</div>`:''}
      ${o.kind==='cyl'?'<p class="hint">h/v selects the powered transverse plane, not the cylinder axis. The perpendicular dimension remains unfocused. H/V and major/minor diameters are reported at endpoints.</p>':''}
      ${o.kind==='tp'?'<p class="hint">The angle tilts the plate normal toward local left (+Y for a +X beam). A positive displacement follows that tilt side; negative reverses it. At zero angle, positive displacement is local left. The explicit offset does not add path length or change beam diameter.</p>':''}
      ${o.kind==='generic'?`<div class="grid two spaced"><label>Placeholder shape<select data-generic-field="shape" data-generic-id="${escapeHtml(o.id)}" ${isDefault?'disabled':''}>${['disc','cube','ball'].map(shape=>`<option value="${shape}" ${(s.shape||'disc')===shape?'selected':''}>${shape[0].toUpperCase()+shape.slice(1)}</option>`).join('')}</select></label><label>Outgoing beam color<select data-generic-field="beam_color" data-generic-id="${escapeHtml(o.id)}" ${isDefault?'disabled':''}>${colorOptions(s.beam_color||'inherit',true)}</select></label>${(s.shape||'disc')==='disc'?opticInput(o,'depth_mm','Disc thickness · mm',s.depth_mm??3,'min="0.01"'):''}</div><p class="hint">Geometry and color are placeholders. Loss, GDD and glass values are manual references. This element does not focus, refract or change wavelength.</p>`:''}
      ${['wp','rp','bd'].includes(o.kind)?`<div class="grid two spaced">${opticInput(o,'tube_length_mm','Tube length · mm',o.tube_length_mm,'min="0.01"')}${opticInput(o,'crystal_width_mm','Crystal clear width · mm',o.crystal_width_mm,'min="0.01"')}</div><p class="hint">Built-in housing dimensions only; custom CAD stays at its original scale. Entered separation/offset is fixed and independent of wavelength. p advances both outputs; other optics affect the main beam. Use output endpoints for independent routing.</p>`:''}
      <div class="custom-panel" ${s.custom?'':'hidden'}><div class="selection"><span>${escapeHtml(s.component_name||'No component selected')}</span><button data-pick-component="${escapeHtml(o.id)}" ${isDefault?'disabled':''}>Choose component…</button></div>
        <div class="button-row"><button data-preview-component="${escapeHtml(o.id)}" ${s.component_token||s.component_ref_token?'':'disabled'}>Preview this CAD only</button><button data-component-guide>Component preparation guide</button></div>
        <p class="hint">${s.component_linked?'Linked reference component. Update its source file deliberately using Fusion.':'Insert the prepared source file as a linked component in Fusion, then choose it here. Local instances share their geometry.'}</p>
        <p class="axis-note">${axis}</p><p class="hint">Origin = beam hit. Z follows assembly up; it tilts when X has a vertical component. The component is not automatically rolled to follow h/v or _ modifiers. Use explicit rotation for a powered/groove/parent-axis orientation. Legacy Z-normal placement is not preserved.</p>${componentAdjustmentHtml(s,(key,label,value)=>opticInput(o,key,label,value))}
        ${o.kind==='oap'?`<div class="grid two spaced">${opticInput(o,'design_bend_deg','Part design bend · °',s.design_bend_deg??90,'min="0.01" max="180"')}</div>`:''}
      </div>${opticBudgetHtml(o,openBudgets.has(o.id))}</div></details>`;
  }).join(''):'';
  restoreFocus(focus);
}
function renderWarnings(warnings) {
  $('warnings').hidden=!warnings?.length;
  $('warnings').innerHTML=warnings?.length?`<div class="notice warning"><ul>${warnings.map(w=>`<li>${escapeHtml(w)}</li>`).join('')}</ul></div>`:'';
}
function schedule() {
  if (!config) return;
  studioChanged();
  setValid(false); sequence++;
  if(studioHasInvalid())return;
  clearTimeout(timer); timer=setTimeout(analyze,260);
  $('validation').className='notice'; $('validation').textContent='Checking commands…';
}
async function analyze() {
  if(!config||busy||studioHasInvalid())return;
  if(analysisRunning){analysisAgain=true;return;}
  analysisRunning=true;
  const revision=++sequence;
  try {
    const result=await request('analyze',{config,edit_token:editTarget?.token});
    if (revision!==sequence) return;
    plan=result; acceptBuildContext(result.build_context); globalError(null); if(studioTab==='calculator')renderCalculator();
    document.querySelectorAll('.commands').forEach(e=>e.classList.remove('invalid'));
    $('validation').className='notice good';
    $('validation').textContent=editingNotice || `Valid · ${plan.rows.length} path line${plan.rows.length===1?'':'s'} · ${plan.optics.length} optics`;
    const incomplete=plan.optics.find(o=>o.settings.custom&&!o.settings.component_token&&!o.settings.component_ref_token);
    setValid(!incomplete||config.options.use_assigned_components===false); renderOutputs(); renderOptics(); renderWarnings(plan.warnings);
    if(incomplete){$('validation').className='notice warning';$('validation').textContent=incomplete.label+': '+(config.options.use_assigned_components===false?'CAD not assigned yet; simple planning optics remain available.':'select a component or choose Built-in optic.');}
    status(incomplete&&config.options.use_assigned_components?'Select the missing custom component':config.options.use_assigned_components?'Ready · assigned CAD will be built':'Planning · simple optics; CAD assignments retained');
    studioAfterAnalysis();
  } catch (e) {
    if (revision!==sequence) return;
    setValid(false); $('validation').className='notice error';
    $('validation').textContent=(Number.isInteger(e.row)?`Path ${e.row+1}: `:'')+errorText(e);
    document.querySelectorAll('.commands').forEach(x=>x.classList.remove('invalid'));
    if (Number.isInteger(e.row) && config.rows[e.row]) {
      const el=$('commands-'+config.rows[e.row].id); el.classList.add('invalid');
      if(el.parentElement)el.parentElement.open=true;
      el.title=`${errorText(e)}${Number.isInteger(e.start)?' (characters '+(e.start+1)+'–'+e.end+')':''}`;
    }
    $('route-map').classList.add('outdated');
    status('Correct the highlighted path before building');
  } finally {
    analysisRunning=false;
    if(analysisAgain){analysisAgain=false;clearTimeout(timer);timer=setTimeout(analyze,0);}
  }
}
async function copyEndpoint(text, label='Endpoint') {
  if(typeof text!=='string'||!text)throw {message:'No text is available to copy.'};
  try {
    const result=await request('copy_text',{text});
    if(result.copied){status(label==='Endpoint'?'Endpoint copied: position, direction and divergence':label+' copied');return true;}
  } catch (_) {}
  // Embedded browser clipboard APIs can silently fail. Always offer visible,
  // selected text when native copying is unavailable; never claim success.
  $('copy-title').textContent='Copy '+label.toLowerCase();
  $('copy-text').value=text;$('copy-modal').hidden=false;$('copy-text').focus();$('copy-text').select();
  status('Text selected for manual copying: Ctrl+C / Command+C');
  return false;
}
async function newRow(endpoint, name) {
  if(endpoint && editTarget) endpoint=(await request('decode',{endpoint,edit_token:editTarget.token})).endpoint;
  const row={id:rowId(),name:'Path '+(config.rows.length+1),commands:'p100',start_mode:endpoint?'snapshot':'previous'};
  RouterEditor.markStarter(row);
  if(endpoint){row.endpoint=endpoint;row.endpoint_name=name;}
  config.rows.push(row);selectedRow=config.rows.length-1;studioSelected=null;renderRows();schedule();showTab('route');
  $('row-name-'+row.id)?.focus();
}
function newRun(endpoint, name) {
  studioCloseCatalogue();
  editTarget=null;renderEditState();
  config.rows=[{id:rowId(),name:'Path 1',commands:'p100',start_mode:endpoint?'snapshot':'source'}];
  RouterEditor.markStarter(config.rows[0]);
  if(endpoint){config.rows[0].endpoint=endpoint;config.rows[0].endpoint_name=name;}
  config.optic_overrides={};selectedRow=0;plan=null;opticSignature='';editingNotice='';studioSelected=null;
  config.run_name=name?name.slice(0,75)+' continuation':'Laser layout';renderSettings();
  config.route_id=rowId();calculatorSelection.clear();
  $('optics').innerHTML='';renderRows();schedule();showTab('route');
}
function openPaste(index) {
  pasteTarget=index;$('paste-modal').hidden=false;$('paste-error').hidden=true;
  $('paste-text').value='';$('paste-text').focus();
}
function routeStatus(run) {
  if(run.token==='draft')return '<p class="status-badge">Current draft · not built</p>';
  const kind=run.stale?'disconnected':run.upstream_pending?'upstream_pending':run.needs_refresh?'update_available':'current';
  const label={disconnected:'Disconnected · kept as a reference',upstream_pending:'Refresh upstream first',update_available:'Beam update available',current:'Connected / current'}[kind];
  return `<p class="status-badge ${kind}">${label}</p>${run.reasons?.length?`<p class="hint">${escapeHtml(run.reasons.join(' '))}</p>`:''}`;
}
function endpointContext(e) {
  const row=plan?.rows?.find(r=>r.id===(e.row_id||e.id.split(':')[0]));
  const commands=e.included_commands??e.commands??config.rows?.find(r=>r.id===row?.id)?.commands??'';
  const start=e.start_state;
  return `<p class="hint">${escapeHtml(e.kind==='reflected'?'Reflected splitter port':e.kind==='end'?'Path end':e.kind==='secondary'?'Secondary output':'Output endpoint')}</p>${commands?`<p class="endpoint-commands"><span class="hint">Included in this output</span><br><code>${escapeHtml(commands)}</code></p>`:''}${start?`<p class="hint">Start XYZ: ${start.position.map(n=>fmt(n)).join(', ')} mm · Az ${fmt(start.azimuth)}° / El ${fmt(start.elevation)}°</p>`:''}`;
}
function compactEndpointStats(s){
  if(!s)return '<p class="hint">Endpoint state unavailable.</p>';
  return `<div class="endpoint-summary"><span>Ø ${fmt(s.diameter_mm)} mm</span><span>${fmt(s.path_mm)} mm from source</span><span>${fmt(s.gdd_fs2)} fs²</span><span>${fmt(s.loss_pct)}% loss</span></div><details class="endpoint-detail"><summary>Position, direction &amp; full state</summary>${statsHtml(s)}</details>`;
}
function renderSaved() {
  $('saved-count').textContent=saved.length;
  const q=$('endpoint-filter').value.toLowerCase();
  const matches=saved.map((e,i)=>[e,i]).filter(([e])=>(e.name+' '+e.run).toLowerCase().includes(q));
  $('saved-list').innerHTML=matches.length?savedRuns.map((run,ri)=>{
    const endpoints=matches.filter(([e])=>e.run_token===run.token);if(!endpoints.length)return '';
    return `<section class="saved-group ${savedHighlight?.run_token===run.token?'highlighted-saved':''} ${run.stale?'stale':run.needs_refresh?'update-available':''}"><h3>${escapeHtml(run.name)}</h3>${routeStatus(run)}<div class="saved-actions"><button data-highlight-run="${ri}" aria-pressed="${savedHighlight?.run_token===run.token&&!savedHighlight?.endpoint_id}">Highlight route</button>${run.has_connections?`<button data-refresh-run="${ri}" ${run.editable?'':'disabled'}>Refresh beam…</button>`:''}<button data-edit-run="${ri}" ${run.editable?'':'disabled'}>Edit paths…</button><button data-rename-run="${ri}" ${run.editable?'':'disabled'}>Rename…</button><button data-delete-run="${ri}" class="danger" ${run.editable?'':'disabled'}>Delete route…</button></div>${run.editable?'':'<p class="hint">Nested route instance: endpoint copying is available; manage its route at the design root.</p>'}${endpoints.map(([e,i])=>`<article class="saved-card"><h3>${escapeHtml(e.name)}</h3>${endpointContext(e)}${compactEndpointStats(e.stats)}<div class="saved-actions"><button data-highlight-endpoint="${i}" aria-pressed="${savedHighlight?.endpoint_id===e.id}">Highlight path</button><button data-copy-saved="${i}">Copy endpoint</button><button data-use-saved="${i}" class="primary">Start new run here</button></div></article>`).join('')}</section>`;
  }).join(''):`<p class="empty">${saved.length?'No matching endpoints.':'Build a route to save its endpoints in this document.'}</p>`;
  savedMapRender();
}
function highlightSavedRun(token){if(!savedRuns.some(r=>r.token===token))return;savedHighlight={run_token:token};renderSaved();}
function savedMapRender(){
  if(!savedScene&&!savedScenePending&&studioTab==='saved')ensureSavedScene();
  const host=$('saved-map');if(!savedScene){host.innerHTML='<p class="empty">Reading saved path geometry…</p>';for(const id of ['saved-highlight-edit','saved-highlight-fit','saved-highlight-clear'])$(id).disabled=true;return;}
  const run=savedRuns.find(r=>r.token===savedHighlight?.run_token);
  const endpoint=saved.find(e=>e.id===savedHighlight?.endpoint_id);
  const event_ids=endpoint?(endpoint.state?.trace||[]).map(e=>e.id):[...savedScene.lines,...savedScene.optics].filter(e=>e.run_token===run?.token).flatMap(e=>e.event_ids||[]);
  const layers=run?[{run_token:run.token,event_ids,color:'#d46a20',name:endpoint?.name||run.name}]:[];
  if(!savedMapController)savedMapController=new RouterSchematic.Controller(host,()=>{},()=>busy,highlightSavedRun);
  savedMapController.update(savedScene,$('saved-projection').value||'XY',{layers,interactive:false,selectRuns:true,runNames:Object.fromEntries(savedRuns.map(r=>[r.token,r.name]))});
  $('saved-map-state').textContent=savedScene.warnings?.length?savedScene.warnings.join(' '):run?'Highlighted: '+run.name+(endpoint?' / '+endpoint.name:''):'Click a beam or optic, or use Highlight route / path below.';
  $('saved-highlight-edit').disabled=!run?.editable||busy;
  $('saved-highlight-fit').disabled=!run;
  $('saved-highlight-clear').disabled=!run;
  $('saved-map-detail').innerHTML=endpoint?compactEndpointStats(endpoint.stats):run?routeStatus(run):'';
}
function calculatorItems() { return $('calculator-source').value==='saved'?saved:(plan?.endpoints||[]); }
function calculatorColor(id){if(!calculatorColors.has(id))calculatorColors.set(id,selectionPalette[calculatorColors.size%selectionPalette.length]);return calculatorColors.get(id);}
function calculatorAutoKey(s){return 'auto|'+s.run_token+'|'+s.resolved_id;}
function calculatorLayers(){
  const selected=calculatorItems().filter(e=>calculatorSelection.has(e.id));
  return selected.map(entry=>{
    const used=calculatorResult?.selections?.find(s=>s.requested_id===entry.id);
    return {name:used?.name||entry.name,run_token:used?.run_token||entry.run_token||'draft',
      color:calculatorColor(entry.id),event_ids:used?.event_ids||(entry.state?.trace||[]).slice(entry.trace_start||0).map(e=>e.id)};
  }).concat((calculatorResult?.selections||[]).filter(s=>s.automatic).map(s=>({...s,color:calculatorColor(calculatorAutoKey(s)),name:'Connecting path · '+(s.route_name?s.route_name+' / ':'')+s.name})));
}
function ensureSavedScene(){
  if(savedScene||savedScenePending)return;
  savedScenePending=true;const epoch=savedSceneEpoch;
  request('schematic').then(scene=>{if(epoch===savedSceneEpoch){savedScene=scene;savedScenePending=false;calculatorMapRender();savedMapRender();if(plan)studioMap();}})
    .catch(e=>{if(epoch===savedSceneEpoch){savedScene={lines:[],optics:[],warnings:['Schematic unavailable: '+errorText(e)]};savedScenePending=false;calculatorMapRender();savedMapRender();}});
}
function calculatorMapRender(){
  const source=$('calculator-source').value;
  if(source==='saved'&&!savedScene&&!savedScenePending&&studioTab==='calculator'){
    ensureSavedScene();
  }
  const scene=source==='saved'?savedScene:plan;
  const host=$('calculator-map');if(!scene){host.innerHTML='<p class="empty">'+(source==='saved'?'Reading saved path geometry…':'A valid route will appear here.')+'</p>';return;}
  if(!calculatorMapController)calculatorMapController=new RouterSchematic.Controller(host,()=>{},()=>busy);
  const layers=calculatorLayers();
  calculatorMapController.update(scene,$('calculator-projection').value||'XY',{layers,interactive:false});
  $('calculator-map-state').textContent=scene.warnings?.length?scene.warnings.join(' '):calculatorResult?'Colored sections match the calculated contributions.':layers.length?'Selected local sections · calculate to resolve a reflected continuation.':'Choose endpoints below. Scroll to zoom; drag to pan.';
  $('calculator-map-legend').innerHTML=layers.map(l=>`<span class="path-key"><i style="background:${escapeHtml(l.color)}"></i>${escapeHtml(l.name)}</span>`).join('');
}
function calculatorQueue(){
  clearTimeout(calculatorTimer);calculatorRevision++;calculatorResult=null;
  if(studioTab==='calculator'&&calculatorSelection.size&&($('calculator-source').value==='saved'||valid)){
    const revision=calculatorRevision;
    calculatorTimer=setTimeout(()=>calculateSelected().catch(e=>{if(revision===calculatorRevision){$('calculator-result').hidden=false;$('calculator-result').textContent=errorText(e);$('calculator-map-state').textContent='Selection is not one complete connected arm; no combined total.';}}),150);
  }
}
function calculatorIncluded(e){
  const resolved=calculatorResult?.selections?.find(s=>s.requested_id===e.id);
  const included=resolved?.included||e.included||[];
  const used=resolved?.included_commands;
  return (used&&resolved.resolved_id!==e.id?`<p class="notice good">Used in this sum: <code>${escapeHtml(used)}</code><br>${escapeHtml(resolved.name)}</p>`:'')+
    (included.length?`<details class="included-optics"><summary>${included.filter(x=>x.kind!=='propagate').length} optical encounters · ${included.length} contributions</summary><table><thead><tr><th>Included step</th><th>Port</th><th>Length · mm</th><th>Loss · %</th><th>GDD · fs²</th></tr></thead><tbody>${included.map(x=>`<tr><td>${escapeHtml(x.label||x.command)} <code>${escapeHtml(x.command)}</code></td><td>${escapeHtml(x.port||'—')}</td><td>${fmt(x.geometric_mm)}</td><td>${fmt(x.loss_pct)}</td><td>${fmt(x.gdd_fs2)}</td></tr>`).join('')}</tbody></table></details>`:'');
}
function renderCalculator(preserveResult=false) {
  const items=calculatorItems();
  const ids=new Set(items.map(e=>e.id));calculatorSelection=new Set([...calculatorSelection].filter(id=>ids.has(id)));
  if(!preserveResult)calculatorQueue();
  const q=$('calculator-filter').value.toLowerCase();
  const groups=$('calculator-source').value==='saved'?savedRuns:[{token:'draft',name:(config?.run_name||'Current route')+' · draft'}];
  $('calculator-paths').innerHTML=groups.map(run=>{
    const entries=items.filter(e=>(e.run_token||'draft')===run.token&&[run.name,e.name,e.commands].join(' ').toLowerCase().includes(q));
    if(!entries.length)return '';
    return `<section class="saved-group ${run.stale?'stale':run.needs_refresh?'update-available':''}"><h3>${escapeHtml(run.name)}</h3>${routeStatus(run)}${entries.map(e=>`<article class="saved-card calculator-card ${calculatorSelection.has(e.id)?'selected':''}"><label class="check calculator-choice"><input type="checkbox" data-calc-id="${escapeHtml(e.id)}" ${calculatorSelection.has(e.id)?'checked':''}><strong>${escapeHtml(e.name)}</strong></label>${calculatorSelection.has(e.id)?`<label class="path-color">Selection color<input type="color" data-calc-color="${escapeHtml(e.id)}" value="${calculatorColor(e.id)}" aria-label="Color for ${escapeHtml(e.name)}"></label>`:''}${endpointContext(e)}${calculatorIncluded(e)}${compactEndpointStats(e.stats)}</article>`).join('')}</section>`;
  }).join('')||'<p class="empty">No matching endpoints. Build a route or choose Current route.</p>';
  $('calculator-count').textContent=`${calculatorSelection.size} selected`;
  const automatic=(calculatorResult?.selections||[]).filter(s=>s.automatic);
  $('calculator-connectors').innerHTML=automatic.length?`<h3>Included connecting paths</h3><p class="hint">These intermediate contributions complete the unique continuous arm. Their lengths and optics are included in the total.</p>`+automatic.map(s=>`<article class="saved-card"><strong>${escapeHtml(s.route_name?s.route_name+' / ':'')}${escapeHtml(s.name)}</strong><label class="path-color">Selection color<input type="color" data-calc-color="${escapeHtml(calculatorAutoKey(s))}" value="${calculatorColor(calculatorAutoKey(s))}" aria-label="Color for connecting path"></label><p class="endpoint-commands"><code>${escapeHtml(s.included_commands)}</code></p>${calculatorIncluded({included:s.included||[]})}</article>`).join(''):'';
  if(!preserveResult)$('calculator-result').hidden=true;
  calculatorMapRender();
}
async function beginRefresh(run) {
  const data=await request('refresh_candidates',{token:run.token});
  if(!data.rows.length)throw {message:'This route has no connection in this document to refresh.'};
  refreshTarget=data;
  $('refresh-description').textContent=`Refresh “${data.name}” from matching endpoints (within ${data.position_tolerance_mm} mm / ${data.angle_tolerance_deg}°). Existing optics stay in place; the beam and reference totals are rebuilt.`;
  $('refresh-choices').innerHTML=data.rows.map(row=>`<label class="refresh-choice">${escapeHtml(row.name)}<select data-refresh-row="${escapeHtml(row.id)}"><option value="">${row.candidates.length?'Choose a source endpoint':'No matching position and direction'}</option>${row.candidates.map(e=>`<option value="${escapeHtml(e.id)}" ${e.id===row.selected?'selected':''} ${e.usable?'':'disabled'}>${escapeHtml(e.name)} · Ø ${fmt(e.stats.diameter_mm)} mm${e.usable?'':' · refresh source first'}</option>`).join('')}</select></label>`).join('');
  $('refresh-error').hidden=true;$('refresh-modal').hidden=false;
}
async function submitRefresh() {
  if(!refreshTarget)return;
  const choices={};document.querySelectorAll('[data-refresh-row]').forEach(e=>choices[e.dataset.refreshRow]=e.value);
  if(refreshTarget.rows.some(row=>!choices[row.id])){$('refresh-error').hidden=false;$('refresh-error').textContent='Choose a usable endpoint for each line. If none matches, correct the connection or edit the route manually.';return;}
  clearTimeout(timer);sequence++;setBusy(true);$('refresh-confirm').disabled=true;status('Refreshing beam; preserving optics…');
  try{await request('refresh_route',{token:refreshTarget.token,choices});}catch(e){setBusy(false);$('refresh-confirm').disabled=false;throw e;}
}
async function calculateSelected() {
  if($('calculator-source').value==='current'&&!valid)throw {message:'Correct the current route before calculating.'};
  const entries=calculatorItems().filter(e=>calculatorSelection.has(e.id));
  const revision=calculatorRevision;
  const r=await request('calculate',{entries,available:calculatorItems()});
  if(revision!==calculatorRevision)return;
  calculatorResult=r;renderCalculator(true);
  $('calculator-result').hidden=false;
  $('calculator-result').textContent=`Geometric length: ${fmt(r.geometric_mm,8)} mm\nGlass-adjusted length: ${fmt(r.optical_path_mm,8)} mm\nTotal loss: ${fmt(r.loss_pct,6)}%\nAccumulated GDD: ${fmt(r.gdd_fs2,8)} fs²\n${r.notes?.length?r.notes.join('\n')+'\n':''}Simple approximation for reference; not a quantitative optical calculation.${entries.some(e=>e.stale||e.needs_refresh)?'\nIncludes saved snapshots needing attention. Refresh their beams for current values.':''}`;
}
async function exchangeFile(id) {
  const format=id.startsWith('export-document')?'document':id==='import-csv'?'import':id==='export-svg'?'svg':'csv';
  if(!['import','document'].includes(format)&&!valid)throw {message:'Correct the current route before exporting.'};
  const r=await request('file',{format,config,document_id:config.document_id,edit_token:editTarget?.token,projection:$('svg-projection').value});
  if(r.cancelled)return;
  if(format==='import'){
    studioSelected=null;config=r.config;editTarget=null;plan=null;opticSignature='';selectedRow=0;calculatorSelection.clear();
    editingNotice='CSV imported as a draft. Recheck component references and optical properties before building.';
    renderEditState();renderSettings();renderRows();showTab('route');schedule();
  }else status('Exported '+(r.route_count!==undefined?r.route_count+' saved routes: ':'')+r.path);
}
async function refreshSaved(){try{const r=await request('saved');acceptSaved(r);if(r.warnings.length)globalError({message:r.warnings.join('\n')});}catch(e){globalError(e);}}
function openManage(operation, run) {
  manageTarget={operation,run};$('manage-title').textContent=operation==='delete_run'?'Delete saved route':'Rename saved route';
  $('manage-description').textContent=operation==='delete_run'?`Delete “${run.name}”, its geometry and saved endpoints? Copied continuations stay where they are.`:`Rename “${run.name}”. To rename individual path lines, choose Edit paths instead.`;
  $('manage-name-label').hidden=operation==='delete_run';$('manage-name').value=run.name;
  $('manage-confirm').textContent=operation==='delete_run'?'Delete route':'Rename';
  $('manage-modal').hidden=false;if(operation==='rename_run')$('manage-name').focus();
}
async function editRun(run) {
  const data=await request('load_run',{token:run.token});
  config=data.config;config.component_defaults??={};editTarget={token:data.token,name:data.name,run_id:data.config.route_id};
  plan=null;opticSignature='';editingNotice='';selectedRow=0;studioSelected=null;
  renderEditState();renderSettings();renderRows();$('optics').innerHTML='';showTab('route');schedule();
}
async function load() {
  const epoch=++loadEpoch;
  clearTimeout(timer);clearTimeout(studioSaveTimer);clearTimeout(studioLiveTimer);
  sequence++;docKey='';setValid(false);setBusy(true);globalError(null);
  try {
    const data=await request('bootstrap');if(epoch!==loadEpoch)return;
    config=data.config;config.component_defaults??={};componentDefaultDrafts={};componentDefaultDirty.clear();componentDefaultKey='bs';savingDefaultKey=null;docKey=data.doc_key;calculatorColors.clear();calculatorSelection.clear();calculatorMapController?.reset();savedMapController?.reset();savedHighlight=null;acceptSaved(data.saved);
    acceptBuildContext(data.build_context||{intent:'legacy',can_build:true,requires_hybrid:false,message:''});
    editTarget=null;manageTarget=null;$('manage-modal').hidden=true;renderEditState();
    plan=null;opticSignature='';editingNotice='';selectedRow=0;
    $('document').textContent='by A. P. Lanz';
    renderSettings();renderRows();renderSaved();studioReset();studioRecoveryOffer(data);setBusy(false);await analyze();
    if(epoch===loadEpoch&&(data.saved?.runs||[]).some(r=>r.display_repair_needed)){
      setBusy(true);await request('manage',{operation:'refresh_status'});
    }
  }catch(e){if(epoch===loadEpoch){setBusy(false);globalError(e);status('Open a design in Fusion’s Design workspace');}}
}

window.fusionJavaScriptHandler={handle(action,raw){
  try{
    const data=JSON.parse(raw||'{}');
    if(action==='reload')load();
    else if(action==='built'){
      acceptBuildContext(data.build_context);
      setBusy(false);acceptSaved(data.saved);renderWarnings(data.warnings);
      if(data.config){config=data.config;renderSettings();renderRows();renderOptics(true);}
      editTarget=data.token?{token:data.token,name:data.name,run_id:data.run_id||config.route_id}:null;renderEditState();
      studioReset();studioRestoring=true;schedule();studioRestoring=false;
      if(!studioRecovery)request('discard_draft').catch(globalError);$('draft-status').textContent='Built · save the Fusion document';
      status(`${data.replaced?'Replaced':'Created'} ${data.name} · ${data.endpoint_count} endpoints saved`);
    }else if(action==='managed'){
      setBusy(false);acceptSaved(data.saved);$('manage-modal').hidden=true;$('refresh-modal').hidden=true;$('refresh-confirm').disabled=false;
      if(data.operation==='refresh_route'){
        if(editTarget?.token===data.token){config=data.config;plan=null;opticSignature='';renderSettings();renderRows();schedule();}
        renderWarnings(data.warnings||[]);refreshTarget=null;
      }
      if(data.component_defaults){
        config.component_defaults=data.component_defaults;
        if(savingDefaultKey){delete componentDefaultDrafts[savingDefaultKey];componentDefaultDirty.delete(savingDefaultKey);}savingDefaultKey=null;renderComponentDefaults();renderOptics(true);schedule();
      }else if(editTarget && manageTarget?.run?.token===editTarget.token && ['rename_run','delete_run'].includes(data.operation)){if(data.operation==='delete_run')newRun();else{editTarget.name=data.name;config.run_name=data.name;renderSettings();renderEditState();}}
      manageTarget=null;status(data.operation==='refresh_route'?'Beam refreshed; existing optics preserved':data.operation==='save_default'?'Component defaults saved in this document':data.operation==='delete_run'?'Route deleted':data.operation==='refresh_status'?'Endpoint status refreshed; built colors retained':'Route renamed');
    }else if(action==='manage_failed'){savingDefaultKey=null;setBusy(false);globalError(data);$('manage-modal').hidden=true;$('refresh-modal').hidden=true;$('refresh-confirm').disabled=false;
    }else if(action==='build_failed'){setBusy(false);globalError(data);status('Build failed; see the error above');}
    return 'OK';
  }catch(e){globalError(e);return 'FAILED';}
}};

document.addEventListener('input',event=>{
  const e=event.target;
  if(!config||busy)return;
  if(!studioValidateNumber(e))return;
  if(e.id==='component-search'){renderComponentPicker();return;}
  if(studioInput(e))return;
  if(e.id.startsWith('src-'))sourceChanged();
  else if(e.id==='run-name'){config.run_name=e.value;studioChanged();}
  else if(e.dataset.commands!==undefined){const row=config.rows[Number(e.dataset.commands)];clearRowOverrides(row,e.value);row.commands=e.value;selectedRow=Number(e.dataset.commands);if(studioSelected?.row!==row.id)studioSelected=null;studioRows();renderOptics(true);schedule();}
  else if(e.dataset.rowName!==undefined){config.rows[Number(e.dataset.rowName)].name=e.value;schedule();}
  else if(e.dataset.sizeKind){config.sizes[e.dataset.sizeKind][e.dataset.size]=Number(e.value);schedule();}
  else if(e.id.startsWith('opt-')){config.options[e.id.slice(4)]=e.type==='checkbox'?e.checked:Number(e.value);schedule();}
  else if(e.dataset.defaultField){changeDefaultField(e);}
  else if(e.dataset.opticField){const o=plan?.optics.find(x=>x.id===e.dataset.optic);if(!o)return;const s=editableOverride(o);const bits=e.dataset.opticField.split('.');if(bits.length===2){s[bits[0]]??=bits[0]==='budget'?{}:[0,0,0];s[bits[0]][bits[0]==='budget'?bits[1]:Number(bits[1])]=Number(e.value);}else s[bits[0]]=Number(e.value);schedule();}
  else if(e.dataset.budgetKind){config.budget_defaults[e.dataset.budgetKind]??={};config.budget_defaults[e.dataset.budgetKind][e.dataset.budgetKey]=Number(e.value);schedule();}
  else if(e.id==='endpoint-filter')renderSaved();
  else if(e.id==='calculator-filter')renderCalculator();
});
document.addEventListener('change',async event=>{
  const e=event.target;if(!config||busy)return;
  try {
  if(studioChange(e))return;
  if(['src-model','src-color','src-spectrum-mode'].includes(e.id)){sourceChanged();return;}
  if(e.id==='component-default-key'){componentDefaultKey=e.value;renderComponentDefaults();return;}
  if(e.id==='default-representation'){defaultDraft().custom=e.value==='custom';renderComponentDefaults();markDefaultDirty();return;}
  if(e.id==='calculator-projection'){calculatorMapRender();return;}
  if(e.id==='saved-projection'){savedMapRender();return;}
  if(e.dataset.calcColor){calculatorColors.set(e.dataset.calcColor,e.value);renderCalculator(true);return;}
  if(e.dataset.genericField){const o=plan?.optics.find(o=>o.id===e.dataset.genericId);if(o){editableOverride(o)[e.dataset.genericField]=e.value;renderOptics(true);schedule();}return;}
  if(e.id==='calculator-source'){calculatorSelection.clear();calculatorMapController?.reset();if(e.value==='saved')await refreshSaved();renderCalculator();}
  else if(e.dataset.calcId){if(e.checked)calculatorSelection.add(e.dataset.calcId);else calculatorSelection.delete(e.dataset.calcId);renderCalculator();}
  else if(e.dataset.startMode!==undefined){const i=Number(e.dataset.startMode);config.rows[i].start_mode=e.value;renderRows();schedule();if(e.value==='snapshot'&&!config.rows[i].endpoint)openPaste(i);}
  else if(e.dataset.representation){
    const o=plan.optics.find(x=>x.id===e.dataset.representation);
    config.optic_overrides[o.id]={token:o.token,representation:e.value,custom:e.value!=='builtin'};
    if(e.value==='custom')Object.assign(config.optic_overrides[o.id],{component_token:'',component_ref_token:'',component_name:'',shift:[0,0,0],rotation:[0,0,0],reference:[0,0,0],reference_name:'Component origin'});
    renderOptics(true);schedule();
  }else if(e.dataset.useDefault){
    const o=plan.optics.find(x=>x.id===e.dataset.useDefault);
    if(e.checked)config.optic_overrides[o.id]={token:o.token,representation:'default'};
    else editableOverride(o);
    renderOptics(true);schedule();
  }
  }catch(error){setBusy(false);globalError(error);renderOptics(true);}
});
document.addEventListener('focusin',e=>{const row=e.target.closest('[data-row]');if(row)selectedRow=Number(row.dataset.row);});
document.addEventListener('click',async event=>{
  if(studioMapClick(event))return;
  const b=event.target.closest('button');if(!b || b.disabled||busy)return;
  try{
    if(await studioClick(b))return;
    if(b.id==='component-picker-cancel'){closeComponentPicker();return;}
    if(b.id==='component-picker-use'){await applyComponentChoice();return;}
    if(b.id==='about-open'){$('about-modal').hidden=false;$('about-close').focus();}
    else if(b.id==='about-close'){$('about-modal').hidden=true;$('about-open').focus();}
    else if(b.id==='cite-text'||b.id==='cite-bibtex')await copyEndpoint(b.id==='cite-text'?softwareCitation:softwareBibtex,'Software citation');
    else if(b.dataset.componentGuide!==undefined){$('component-guide-modal').hidden=false;$('component-guide-close').focus();}
    else if(b.id==='component-guide-close')$('component-guide-modal').hidden=true;
    else if(b.dataset.tab){showTab(b.dataset.tab);if(b.dataset.tab==='saved'||b.dataset.tab==='calculator')await refreshSaved();}
    else if(b.id==='add-row')await newRow();
    else if(b.id==='new-run')newRun();
    else if(b.dataset.removeRow!==undefined){const i=Number(b.dataset.removeRow);clearRowOverrides(config.rows[i]);config.rows.splice(i,1);if(config.rows[0].start_mode==='previous')config.rows[0].start_mode='source';selectedRow=Math.min(selectedRow,config.rows.length-1);renderRows();schedule();}
    else if(b.dataset.pasteRow!==undefined)openPaste(Number(b.dataset.pasteRow));
    else if(b.id==='paste-cancel')$('paste-modal').hidden=true;
    else if(b.id==='paste-use'){
      try{const data=await request('decode',{endpoint:$('paste-text').value,edit_token:editTarget?.token});const row=config.rows[pasteTarget];row.start_mode='snapshot';row.endpoint=data.endpoint;row.endpoint_name=data.name;$('paste-modal').hidden=true;renderRows();schedule();}catch(e){$('paste-error').hidden=false;$('paste-error').textContent=errorText(e);}
    }else if(b.id==='copy-close')$('copy-modal').hidden=true;
    else if(b.dataset.copyEnd!==undefined)await copyEndpoint(plan.rows[Number(b.dataset.copyEnd)].endpoint.endpoint);
    else if(b.dataset.useEnd!==undefined){const row=plan.rows[Number(b.dataset.useEnd)];await newRow(row.endpoint.endpoint,row.endpoint.name);}
    else if(b.dataset.copyPort!==undefined||b.dataset.usePort!==undefined){const use=b.dataset.usePort!==undefined;const [ri,pi]=(use?b.dataset.usePort:b.dataset.copyPort).split(':').map(Number);const port=plan.rows[ri].ports[pi];if(use)await newRow(port.endpoint,port.name);else await copyEndpoint(port.endpoint);}
    else if(b.dataset.openDefault){componentDefaultKey=b.dataset.openDefault;showTab('settings');$('component-default-key').focus();}
    else if(b.id==='default-add'){
      const raw=$('component-default-command').value.trim();componentDefaultKey=physicalKey(raw);renderComponentDefaults();
    }else if(b.id==='default-discard'){delete componentDefaultDrafts[componentDefaultKey];componentDefaultDirty.delete(componentDefaultKey);renderComponentDefaults();}
    else if(b.id==='default-pick-component'){await openComponentPicker({defaultKey:componentDefaultKey});}
    else if(b.id==='default-pick-reference'){
      const s=defaultDraft(),key=componentDefaultKey,result=await request(b.id==='default-pick-component'?'pick_component':'pick_reference',{component_token:s.component_token});
      if(!result.cancelled){Object.assign(s,result);componentDefaultKey=key;renderComponentDefaults();markDefaultDirty();}
    }else if(b.id==='default-origin'){Object.assign(defaultDraft(),{reference:[0,0,0],reference_name:'Component origin'});renderComponentDefaults();markDefaultDirty();}
    else if(b.id==='default-save'||b.id==='default-remove'){
      if(studioHasInvalid())throw Error('Complete the highlighted numeric field first.');
      clearTimeout(timer);sequence++;savingDefaultKey=componentDefaultKey;setBusy(true);status('Saving component default…');
      try{await request('manage',{operation:'save_default',key:componentDefaultKey,settings:b.id==='default-remove'?null:componentTemplate(defaultDraft())});}catch(e){savingDefaultKey=null;setBusy(false);throw e;}
    }
    else if(b.dataset.pickComponent){await openComponentPicker({opticId:b.dataset.pickComponent});}
    else if(b.dataset.previewComponent){clearTimeout(timer);sequence++;setBusy(true);globalError(null);status('Inspecting selected CAD…');try{const r=await request('preview',{config,edit_token:editTarget?.token,quality:'selected',optic_id:b.dataset.previewComponent});renderWarnings(r.warnings);status('Selected CAD preview · datum axes X red, Y green, Z blue · source unchanged');}finally{setBusy(false);}}
    else if(b.dataset.resetReference){const s=editableOverride(plan.optics.find(x=>x.id===b.dataset.resetReference));s.reference=[0,0,0];s.reference_name='Component origin';renderOptics(true);schedule();}
    else if(b.id==='refresh-saved'){globalError(null);manageTarget=null;setBusy(true);await request('manage',{operation:'refresh_status'});}
    else if(b.dataset.highlightRun!==undefined)highlightSavedRun(savedRuns[Number(b.dataset.highlightRun)].token);
    else if(b.dataset.highlightEndpoint!==undefined){const e=saved[Number(b.dataset.highlightEndpoint)];savedHighlight={run_token:e.run_token,endpoint_id:e.id};renderSaved();}
    else if(b.id==='saved-highlight-clear'){savedHighlight=null;renderSaved();}
    else if(b.id==='saved-highlight-fit'){const scene={lines:savedScene.lines.filter(e=>e.run_token===savedHighlight?.run_token),optics:savedScene.optics.filter(e=>e.run_token===savedHighlight?.run_token)};savedMapController.view.fit(scene);savedMapController.draw();}
    else if(b.id==='saved-highlight-edit'){const run=savedRuns.find(r=>r.token===savedHighlight?.run_token);if(run?.editable)await editRun(run);}
    else if(b.id==='calculate')await calculateSelected();
    else if(b.id==='calculator-clear'){calculatorSelection.clear();renderCalculator();}
    else if(b.dataset.refreshRun!==undefined)await beginRefresh(savedRuns[Number(b.dataset.refreshRun)]);
    else if(b.id==='refresh-cancel'){$('refresh-modal').hidden=true;refreshTarget=null;}
    else if(b.id==='refresh-confirm')await submitRefresh();
    else if(['export-csv','export-svg','import-csv','export-document','export-document-saved'].includes(b.id))await exchangeFile(b.id);
    else if(b.id==='copy-diagnostic'){const data=await request('diagnostic');await copyEndpoint(data.text,'Build traceback');}
    else if(b.dataset.copySaved!==undefined)await copyEndpoint(saved[Number(b.dataset.copySaved)].endpoint);
    else if(b.dataset.useSaved!==undefined){const e=saved[Number(b.dataset.useSaved)];newRun(e.endpoint,e.run+' / '+e.name);}
    else if(b.dataset.editRun!==undefined)await editRun(savedRuns[Number(b.dataset.editRun)]);
    else if(b.dataset.renameRun!==undefined)openManage('rename_run',savedRuns[Number(b.dataset.renameRun)]);
    else if(b.dataset.deleteRun!==undefined)openManage('delete_run',savedRuns[Number(b.dataset.deleteRun)]);
    else if(b.id==='manage-cancel'){$('manage-modal').hidden=true;manageTarget=null;}
    else if(b.id==='manage-confirm'){
      if(!manageTarget)return;
      if(manageTarget.operation==='rename_run'&&!$('manage-name').value.trim())throw {message:'Enter a route name.'};
      setBusy(true);await request('manage',{operation:manageTarget.operation,token:manageTarget.run.token,name:$('manage-name').value});
    }
    else if(b.dataset.example){const row=config.rows[selectedRow]||config.rows[0];clearRowOverrides(row);row.commands=b.dataset.example;
      if(b.dataset.exampleSource==='compressor'){
        Object.assign(config.source,{position:[0,0,0],azimuth:0,elevation:0,diameter_mm:5,half_angle_mrad:0,wavelength_nm:800,m2:1,model:'geometric',spectrum:{mode:'sidebands',width_nm:20}});
        row.start_mode='source';row.endpoint='';renderSettings();
      }
      renderRows();schedule();showTab('route');}
    else if(b.id==='preview'){clearTimeout(timer);sequence++;setBusy(true);status('Generating 3D preview…');try{const r=await request('preview',{config,edit_token:editTarget?.token,quality:$('preview-quality').value||'draft'});renderWarnings(r.warnings);status($('preview-quality').value==='solid'?'Solid preview shown · build to keep this route':'Draft preview · nominal planes, no CAD geometry');}finally{setBusy(false);}}
    else if(b.id==='build'||b.id==='build-close'){
      if(!buildContext.can_build)throw {message:buildContext.message};
      clearTimeout(studioSaveTimer);clearTimeout(studioLiveTimer);clearTimeout(timer);sequence++;setBusy(true);globalError(null);
      status(buildContext.requires_hybrid?'Switching document to Hybrid and building…':editTarget?'Replacing selected route…':'Building route…');
      await request('build',{config,edit_token:editTarget?.token,close:b.id==='build-close',
        convert_from:buildContext.requires_hybrid?buildContext.intent:null});
    }
  }catch(e){setBusy(false);globalError(e);}
});
document.addEventListener('keydown',e=>{studioKey(e);if(e.key==='Escape'&&!busy){if(componentPickerTarget)closeComponentPicker();$('component-guide-modal').hidden=true;$('about-modal').hidden=true;$('paste-modal').hidden=true;$('copy-modal').hidden=true;$('manage-modal').hidden=true;$('refresh-modal').hidden=true;}});

// Do not recreate numeric inputs while the user is entering signs/decimals/exponents.
document.addEventListener('focusout',event=>{
  if(event.target?.dataset?.opticField)setTimeout(()=>{
    if(!studioHasInvalid()&&!document.activeElement?.dataset?.opticField)renderOptics(true);
  },0);
});
let componentPickerTarget=null,componentPickerItems=[];
function closeComponentPicker(){
  $('component-picker-modal').hidden=true;componentPickerTarget=null;
  if(!valid&&!studioHasInvalid())schedule();
}
function preparedAxesNote(o){
  let extra='Local +Y and +Z span the surface; +X follows transmission for a lens or passive plate.';
  if(['mirror','bs','oap'].includes(o.kind))extra='Local +X is the front-surface normal toward the incoming beam, with backing toward −X. A beam along −X reflects along +X at normal incidence.';
  if(o.kind==='oap')extra+=' Use the tangent surface normal at the hit, not the parent axis. Set component Rx deliberately to match its off-axis orientation; _ does not roll assigned CAD.';
  if(o.kind==='cyl')extra='Local +X follows transmission. For a part powered in Y with cylinder axis Z, h is upright; a vertical powered plane requires an explicit 90° Rx correction.';
  if(o.kind==='grating')extra='Local +X is the front-surface normal. Prepare grooves along Z for horizontal dispersion; set component Rx for vertical dispersion.';
  if(o.kind==='bsc')extra='Local +X follows the transmitted beam and +Y the reflected branch. Use the internal splitting-plane hit as the origin.';
  if(['wp','rp','bd'].includes(o.kind))extra='Local +X follows the incoming beam; +Y points toward secondary separation / walk-off. +Z = X × Y.';
  return 'Prepare the part in its own file: origin at the beam hit and X perpendicular to the reference surface. Z stays parallel to assembly Z for a horizontal normal, and follows projected assembly up for a tilted normal. '+extra;
}
async function openComponentPicker(target){
  clearTimeout(timer);clearTimeout(studioLiveTimer);sequence++;
  const result=await request('list_components');
  componentPickerTarget=target;componentPickerItems=result.items||[];
  $('component-search').value='';$('component-picker-error').hidden=true;
  renderComponentPicker();$('component-picker-modal').hidden=false;$('component-search').focus();
}
function renderComponentPicker(){
  const q=$('component-search').value.toLowerCase(),items=componentPickerItems.filter(c=>c.component_name.toLowerCase().includes(q));
  const previous=$('component-choices').value;
  $('component-choices').innerHTML=items.map(c=>`<option value="${escapeHtml(c.component_token)}">${escapeHtml(c.component_name)}${c.component_linked?' · linked':''}</option>`).join('');
  $('component-choices').value=items.some(c=>c.component_token===previous)?previous:items[0]?.component_token||'';
  $('component-picker-use').disabled=!items.length;
  $('component-picker-count').textContent=items.length?`${items.length} reference components`:'No matching reference component. Insert the prepared file into this design first. Generated routes are excluded.';
}
async function applyComponentChoice(){
  const target=componentPickerTarget,token=$('component-choices').value;if(!target||!token)return;
  try{
    const result=await request('choose_component',{component_token:token});
    if(target.defaultKey){componentDefaultKey=target.defaultKey;Object.assign(defaultDraft(),result,{custom:true});renderComponentDefaults();markDefaultDirty();}
    else {const o=plan?.optics.find(o=>o.id===target.opticId);if(!o)throw Error('The selected optic changed. Choose it again.');Object.assign(editableOverride(o),result);renderOptics(true);schedule();}
    $('component-picker-modal').hidden=true;componentPickerTarget=null;
  }catch(e){$('component-picker-error').hidden=false;$('component-picker-error').textContent=errorText(e);}
}


(async()=>{
  for(let i=0;i<60&&!window.adsk?.fusionSendData;i++)await new Promise(r=>setTimeout(r,100));
  if(!window.adsk?.fusionSendData){globalError({message:'Open this interface using the LaserOpticsRouter add-in inside Autodesk Fusion.'});setValid(false);return;}
  await load();
})();
