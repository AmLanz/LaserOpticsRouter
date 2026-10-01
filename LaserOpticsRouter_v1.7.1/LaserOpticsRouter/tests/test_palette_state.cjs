/* Controller unit tests with DOM/bridge doubles; no browser is launched. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname,'..','palette.js'),'utf8');
const controller = source.slice(0, source.lastIndexOf('\n(async()=>{'));
function setup() {
  const elements = new Map(), listeners = {}, requests = [], responses = {};
  function element(id) {
    if(!elements.has(id))elements.set(id,{id,value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,
      style:{},classList:{add(){},remove(){},toggle(){}},focus(){},select(){},remove(){}});
    return elements.get(id);
  }
  const context = vm.createContext({
    document:{getElementById:element,activeElement:null,querySelector:element,querySelectorAll:()=>[],
      addEventListener:(name,fn)=>listeners[name]=fn},
    window:{adsk:{fusionSendData:async(action,raw)=>{
      const data=JSON.parse(raw);requests.push({action,data});
      return JSON.stringify({ok:true,result:responses[action]??(action==='decode'?{endpoint:'local-packet',name:'Converted'}:{queued:true})});
    }}}, navigator:{}, setTimeout:()=>123,clearTimeout(){}, console
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'..','editor.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'..','schematic.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'..','studio.js'),'utf8'),context);
  vm.runInContext(controller,context);
  const evaluate = code => vm.runInContext(code,context);
  evaluate(`config={component_defaults:{l50:{component_token:'occ-A',component_ref_token:'part-A',component_name:'Lens A',
    reference:[1,2,3],reference_name:'Circle centre',shift:[0,0,0],rotation:[0,0,0]}},optic_overrides:{},
    rows:[{id:'line1',name:'Path 1',commands:'l50',start_mode:'source'}]};
    config.source={position:[0,0,0],azimuth:0,elevation:0,diameter_mm:5,model:'geometric',half_angle_mrad:3,wavelength_nm:800,m2:1};
    config.options={};config.sizes=Object.fromEntries(Object.keys(familyNames).map(k=>[k,{small:12.7,normal:25.4,large:50.8}]));
    plan={optics:[{id:'line1:0',token:'l50',default_key:'l50',kind:'lens',label:'Path 1 · l50',diameter_mm:25.4,
      focal_mm:50,frame:[[0,1,0],[0,0,1],[1,0,0]],settings:{...config.component_defaults.l50,representation:'default',custom:true}}],
      rows:[],warnings:[]};`);
  return {elements,listeners,requests,responses,evaluate,context};
}
const value = x => JSON.parse(JSON.stringify(x));
async function click(ui,id,dataset={}) {
  const button={id,dataset,disabled:false};
  await ui.listeners.click({target:{closest:()=>button}});
}
const emptySaved = {items:[],runs:[],warnings:[]};

function savedFixture(ui) {
  ui.evaluate(`$('calculator-source').value='saved';
    const sampleStats={position:[100,4,0],direction:[1,0,0],azimuth:0,elevation:0,azimuth_defined:true,diameter_mm:5,path_mm:100,optical_path_mm:102,loss_pct:51,gdd_fs2:300,status:'near collimated',model:'geometric'};
    saved=[{id:'a|line1:end',run_token:'a',run:'Pump arm',name:'Pump · end',commands:'p100 bsc p200',kind:'end',stats:sampleStats,start_state:{position:[0,0,0],azimuth:0,elevation:0}},
      {id:'b|line1:end',run_token:'b',run:'Reference <arm>',name:'Reference · end',commands:'p40 l50',kind:'end',stats:sampleStats}];
    savedRuns=[{token:'a',name:'Pump arm',editable:true,has_connections:false},{token:'b',name:'Reference <arm>',editable:true,has_connections:true,needs_refresh:true,reasons:['Beam diameter changed.']}];`);
}

test('calculator groups named routes with commands, start geometry and endpoint statistics',()=>{
  const ui=setup();savedFixture(ui);ui.evaluate('renderCalculator()');
  const html=ui.elements.get('calculator-paths').innerHTML;
  for(const text of ['saved-group','Pump arm','Reference &lt;arm&gt;','p100 bsc p200','Start XYZ: 0, 0, 0','Direction · unit XYZ','Accumulated GDD','Beam update available'])assert.ok(html.includes(text),text);
  assert.equal(ui.elements.get('calculator-count').textContent,'0 selected');
});
test('calculator filtering keeps hidden selections and clear selection resets them',async()=>{
  const ui=setup();savedFixture(ui);ui.evaluate(`calculatorSelection.add('a|line1:end');$('calculator-filter').value='Reference';renderCalculator()`);
  assert.equal(ui.evaluate('calculatorSelection.size'),1);
  assert.equal(ui.elements.get('calculator-count').textContent,'1 selected');
  assert.ok(!ui.elements.get('calculator-paths').innerHTML.includes('Pump arm'));
  await click(ui,'calculator-clear');assert.equal(ui.evaluate('calculatorSelection.size'),0);
});
test('saved cards distinguish a changed beam from a disconnected route and expose per-route refresh',()=>{
  const ui=setup();savedFixture(ui);ui.evaluate('renderSaved()');
  const html=ui.elements.get('saved-list').innerHTML;
  assert.match(html,/data-refresh-run="1"/);assert.match(html,/Beam update available/);assert.doesNotMatch(html,/Disconnected/);
  ui.evaluate(`savedRuns[1].stale=true;renderSaved()`);assert.match(ui.elements.get('saved-list').innerHTML,/Disconnected/);
});
test('refresh shows candidate identities and requires a usable choice before requesting mutation',async()=>{
  const ui=setup();savedFixture(ui);
  ui.responses.refresh_candidates={token:'b',name:'Reference arm',position_tolerance_mm:.001,angle_tolerance_deg:.001,
    rows:[{id:'line1',name:'Branch',selected:'',candidates:[{id:'a|port',name:'Pump arm / reflected',stats:{diameter_mm:8},usable:true},{id:'old|port',name:'Other arm / end',stats:{diameter_mm:5},usable:false}]}]};
  await click(ui,'',{refreshRun:'1'});
  const html=ui.elements.get('refresh-choices').innerHTML;assert.match(html,/Pump arm \/ reflected/);assert.match(html,/refresh source first/);
  await click(ui,'refresh-confirm');assert.equal(ui.requests.filter(r=>r.action==='refresh_route').length,0);assert.equal(ui.elements.get('refresh-error').hidden,false);
  ui.context.document.querySelectorAll=selector=>selector==='[data-refresh-row]'?[{dataset:{refreshRow:'line1'},value:'a|port'}]:[];
  await click(ui,'refresh-confirm');const req=ui.requests.find(r=>r.action==='refresh_route');
  assert.deepEqual(req.data.choices,{line1:'a|port'});assert.equal(req.data.token,'b');assert.equal(ui.evaluate('busy'),true);
});
test('refresh completion keeps edit identity and loads new beam settings without a null target error',()=>{
  const ui=setup();ui.evaluate(`editTarget={token:'b',name:'Reference arm'};manageTarget=null;busy=true;`);
  const config=value(ui.evaluate('config'));config.source.diameter_mm=8;
  const answer=ui.context.window.fusionJavaScriptHandler.handle('managed',JSON.stringify({operation:'refresh_route',token:'b',name:'Reference arm',config,saved:emptySaved,warnings:[]}));
  assert.equal(answer,'OK');assert.equal(ui.evaluate('busy'),false);assert.equal(ui.evaluate('config.source.diameter_mm'),8);
  assert.equal(ui.evaluate('editTarget.token'),'b');assert.equal(ui.elements.get('refresh-modal').hidden,true);
});
test('old settings gain prism size families and a custom prism card has dimensions and alignment help',()=>{
  const ui=setup();ui.evaluate(`delete config.sizes.wp;delete config.sizes.rp;delete config.sizes.bd;renderSettings();
    config.rows[0].commands='wp20h';plan.optics=[{...plan.optics[0],kind:'wp',token:'wp20h',default_key:'wp20',amount:20,axis:'h',tube_length_mm:14,crystal_width_mm:10,budget:{},settings:{custom:false,representation:'builtin'}}];renderOptics(true);`);
  assert.deepEqual(value(ui.evaluate('config.sizes.bd')),{small:12.7,normal:25.4,large:50.8});
  const html=ui.elements.get('optics').innerHTML;
  for(const text of ['Wollaston prism','Tube length · mm','Crystal clear width · mm','+Y points toward secondary separation','Main output · %','Secondary output · %'])assert.ok(html.includes(text),text);
});
test('combining displacer has per-arm loss controls and no second power split',()=>{
  const ui=setup();const html=ui.evaluate(`opticBudgetHtml({id:'line1:2',kind:'bd',combining:true,budget:{loss_pct:1}})`);
  assert.match(html,/does not split power again/);assert.match(html,/Loss · %/);assert.doesNotMatch(html,/Secondary output · %/);
});

test('default card reads globals and exposes the checked Use default box',()=>{
  const {evaluate,elements}=setup();evaluate('renderOptics(true)');
  const html=elements.get('optics').innerHTML;
  for(const expected of ['Use default · l50','Edit global default','Component rotation','assembly up','X perpendicular','Uncheck to customize'])assert.ok(html.includes(expected));
  assert.match(html,/data-use-default="line1:0" checked/);
});
test('changing default placement creates an independent custom choice',()=>{
  const {evaluate}=setup();evaluate('editableOverride(plan.optics[0]).rotation[2]=90');
  assert.equal(evaluate('config.optic_overrides["line1:0"].representation'),'custom');
  assert.equal(evaluate('config.component_defaults.l50.rotation[2]'),0);
  assert.equal(evaluate('cardSettings(plan.optics[0]).rotation[2]'),90);
});
test('new component choice clears inherited identity and datum',async()=>{
  const {evaluate,listeners}=setup();
  await listeners.change({target:{dataset:{representation:'line1:0'},value:'custom'}});
  assert.equal(evaluate('cardSettings(plan.optics[0]).component_token'),'');
  assert.deepEqual(value(evaluate('cardSettings(plan.optics[0]).reference')),[0,0,0]);
  assert.equal(evaluate('cardSettings(plan.optics[0]).reference_name'),'Component origin');
});
test('built-in choice overrides automatic default',async()=>{
  const {evaluate,listeners,elements}=setup();
  await listeners.change({target:{dataset:{representation:'line1:0'},value:'builtin'}});
  assert.equal(evaluate('cardSettings(plan.optics[0]).custom'),false);
  assert.match(elements.get('optics').innerHTML,/value="builtin" selected/);
});
test('Defaults page saves a component snapshot through the native document command',async()=>{
  const ui=setup();ui.evaluate("componentDefaultKey='l50';renderComponentDefaults()");
  await click(ui,'default-save');
  assert.equal(ui.requests[0].action,'manage');assert.equal(ui.requests[0].data.operation,'save_default');
  assert.equal(ui.requests[0].data.settings.component_ref_token,'part-A');
  assert.equal(ui.evaluate('busy'),true);
  const result=ui.context.window.fusionJavaScriptHandler.handle('managed',JSON.stringify({operation:'save_default',
    component_defaults:{l50:ui.requests[0].data.settings},saved:{items:[],runs:[],warnings:[]}}));
  assert.equal(result,'OK');assert.equal(ui.evaluate('busy'),false);
  assert.equal(ui.evaluate('config.component_defaults.l50.component_token'),'occ-A');
});
test('removing a live default restores builtin fallback without pinning stale component data',()=>{
  const {evaluate,context}=setup();evaluate('config.optic_overrides["line1:0"]={token:"l50",representation:"default"}');
  const result=context.window.fusionJavaScriptHandler.handle('managed',JSON.stringify({operation:'save_default',
    component_defaults:{},saved:{items:[],runs:[],warnings:[]}}));
  assert.equal(result,'OK');assert.equal(evaluate('cardSettings(plan.optics[0]).custom'),false);
  assert.equal(evaluate('config.optic_overrides["line1:0"].representation'),'default');
});
test('continuing while editing converts world endpoint to route coordinates',async()=>{
  const {evaluate,requests}=setup();evaluate('editTarget={token:"moved-run",name:"Moved"}');
  await evaluate('newRow("world-packet","Branch")');
  assert.equal(requests[0].action,'decode');assert.equal(requests[0].data.edit_token,'moved-run');
  assert.equal(evaluate('config.rows[1].endpoint'),'local-packet');
});
test('starting a separate run uses the world packet unchanged',()=>{
  const {evaluate,requests}=setup();evaluate('editTarget={token:"old",name:"Old"}; newRun("world-packet","End")');
  assert.equal(evaluate('editTarget'),null);assert.equal(evaluate('config.rows[0].endpoint'),'world-packet');
  assert.equal(requests.length,0);
});
test('endpoint display explicitly shows unit direction and both angles',()=>{
  const {evaluate}=setup();const html=evaluate(`statsHtml({position:[0,0,0],direction:[0,0.866,0.5],azimuth:90,elevation:30,
    azimuth_defined:true,diameter_mm:5,half_angle_mrad:1,path_mm:100,status:'diverging',model:'geometric'})`);
  assert.ok(html.includes('Direction · unit XYZ'));assert.ok(html.includes('90 / 30'));assert.ok(html.includes('0, 0.866, 0.5'));
});
test('budget inputs store named fields and remain separate from CAD shifts',()=>{
  const {evaluate,listeners}=setup();
  listeners.input({target:{id:'budget-loss',dataset:{optic:'line1:0',opticField:'budget.loss_pct'},value:'7.5'}});
  assert.equal(evaluate('config.optic_overrides["line1:0"].budget.loss_pct'),7.5);
  assert.deepEqual(value(evaluate('config.optic_overrides["line1:0"].shift')),[0,0,0]);
});
test('propagation edits preserve matching component assignments',()=>{
  const {evaluate,listeners}=setup();
  evaluate('config.optic_overrides["line1:0"]={token:"l50",component_token:"kept",budget:{loss_pct:3}}');
  listeners.input({target:{id:'commands-line1',dataset:{commands:'0'},value:'p25 l50 p100'}});
  assert.equal(evaluate('config.optic_overrides["line1:0"].component_token'),'kept');
  assert.equal(evaluate('config.optic_overrides["line1:0"].budget.loss_pct'),3);
  assert.equal(evaluate('config.rows[0].step_ids[1]'),'0');
});
test('optic-specification edits clear ambiguous assignments',()=>{
  const {evaluate,listeners}=setup();
  evaluate('config.optic_overrides["line1:0"]={token:"l50",component_token:"old"}');
  listeners.input({target:{id:'commands-line1',dataset:{commands:'0'},value:'l100'}});
  assert.deepEqual(value(evaluate('config.optic_overrides')),{});
});
test('reference controls exist for built-in and custom representations',()=>{
  const {evaluate,elements}=setup();
  for(const mode of ['builtin','custom']){
    evaluate(`config.optic_overrides['line1:0']={token:'l50',representation:'${mode}'}; renderOptics(true)`);
    for(const label of ['Reference loss','budget.loss_pct','budget.gdd_fs2','budget.thickness_mm'])
      assert.ok(elements.get('optics').innerHTML.includes(label));
  }
});

test('Refresh completes with no selected edit or management target',async()=>{
  const ui=setup();
  await click(ui,'refresh-saved');
  assert.equal(ui.requests[0].data.operation,'refresh_status');
  assert.equal(ui.evaluate('busy'),true);
  const reply=ui.context.window.fusionJavaScriptHandler.handle('managed',JSON.stringify({operation:'refresh_status',saved:emptySaved}));
  assert.equal(reply,'OK');assert.equal(ui.evaluate('busy'),false);
  assert.equal(ui.evaluate('editTarget'),null);
  assert.match(ui.elements.get('footer-status').textContent,/refreshed/);
});
test('Refresh preserves an active route edit and its name',()=>{
  const ui=setup();ui.evaluate('editTarget={token:"editing",name:"Keep me"};config.run_name="Keep me"');
  const reply=ui.context.window.fusionJavaScriptHandler.handle('managed',JSON.stringify({operation:'refresh_status',saved:emptySaved}));
  assert.equal(reply,'OK');assert.equal(ui.evaluate('editTarget.name'),'Keep me');
  assert.equal(ui.evaluate('config.run_name'),'Keep me');
});
test('native clipboard receives exact endpoint data and reports success',async()=>{
  const ui=setup();ui.responses.copy_text={copied:true};
  const packet='LOR2: exact Unicode λ and direction';
  ui.context.packet=packet;
  assert.equal(await ui.evaluate('copyEndpoint(packet)'),true);
  assert.equal(ui.requests[0].action,'copy_text');assert.equal(ui.requests[0].data.text,packet);
  assert.match(ui.elements.get('footer-status').textContent,/Endpoint copied/);
});
test('clipboard failure shows selectable text without a false copied message',async()=>{
  const ui=setup();ui.responses.copy_text={copied:false,message:'busy'};
  assert.equal(await ui.evaluate('copyEndpoint("traceback", "Build traceback")'),false);
  assert.equal(ui.elements.get('copy-modal').hidden,false);
  assert.equal(ui.elements.get('copy-text').value,'traceback');
  assert.match(ui.elements.get('copy-title').textContent,/build traceback/);
  assert.match(ui.elements.get('footer-status').textContent,/manual copying/);
});
test('all endpoint and diagnostic copy buttons use the native copy bridge',async()=>{
  for(const [id,dataset,packet] of [
    ['',{copyEnd:'0'},'line-end'],['',{copyPort:'0:0'},'reflected'],
    ['',{copySaved:'0'},'saved-end'],['copy-diagnostic',{},'traceback']]){
    const ui=setup();ui.responses.copy_text={copied:true};ui.responses.diagnostic={text:'traceback'};
    ui.evaluate('plan.rows=[{endpoint:{endpoint:"line-end"},ports:[{endpoint:"reflected"}]}];saved=[{endpoint:"saved-end"}]');
    await click(ui,id,dataset);
    assert.equal(ui.requests.at(-1).action,'copy_text');assert.equal(ui.requests.at(-1).data.text,packet);
  }
});
test('Build keeps window open and the next build targets the just-built route',async()=>{
  const ui=setup();ui.evaluate('setValid(true)');
  await click(ui,'build');
  assert.equal(ui.requests[0].data.close,false);
  const config=value(ui.evaluate('config'));
  const reply=ui.context.window.fusionJavaScriptHandler.handle('built',JSON.stringify({token:'new-route',name:'Built route',config,
    saved:emptySaved,warnings:[],endpoint_count:1}));
  assert.equal(reply,'OK');assert.equal(ui.evaluate('editTarget.token'),'new-route');
  assert.equal(ui.elements.get('build').textContent,'Replace route');
  ui.evaluate('setValid(true)');await click(ui,'build');
  const builds=ui.requests.filter(r=>r.action==='build');
  assert.equal(builds[1].data.edit_token,'new-route');assert.equal(builds[1].data.close,false);
});
test('Build & close requests close and both build buttons follow busy/valid state',async()=>{
  const ui=setup();ui.evaluate('setValid(false)');
  assert.equal(ui.elements.get('build').disabled,true);assert.equal(ui.elements.get('build-close').disabled,true);
  ui.evaluate('setValid(true)');assert.equal(ui.elements.get('build-close').disabled,false);
  await click(ui,'build-close');assert.equal(ui.requests[0].data.close,true);
  assert.equal(ui.elements.get('build').disabled,true);assert.equal(ui.elements.get('build-close').disabled,true);
});
test('calculator includes available splitter ports for automatic parent truncation',async()=>{
  const ui=setup();ui.responses.calculate={geometric_mm:140,optical_path_mm:140,loss_pct:51,gdd_fs2:300,
    notes:['Parent counted up to its reflected port.']};
  ui.evaluate('setValid(true);plan.endpoints=[{id:"parent"},{id:"port"},{id:"child"}];calculatorSelection=new Set(["parent","child"])');
  await click(ui,'calculate');
  assert.deepEqual(ui.requests[0].data.entries.map(x=>x.id),['parent','child']);
  assert.deepEqual(ui.requests[0].data.available.map(x=>x.id),['parent','port','child']);
  assert.match(ui.elements.get('calculator-result').textContent,/Parent counted up to its reflected port/);
});
test('all-document export works even while the current draft is invalid',async()=>{
  const ui=setup();ui.responses.file={path:'document.zip',route_count:2};ui.evaluate('setValid(false)');
  await click(ui,'export-document');
  assert.equal(ui.requests[0].action,'file');assert.equal(ui.requests[0].data.format,'document');
  assert.match(ui.elements.get('footer-status').textContent,/2 saved routes/);
});
test('source edits retain hidden divergence without printing a local half-angle',()=>{
  const ui=setup();ui.evaluate('renderSettings();sourceChanged()');
  assert.equal(ui.evaluate('config.source.half_angle_mrad'),3);
  assert.equal(ui.elements.has('src-half_angle_mrad'),false);
  assert.doesNotMatch(ui.elements.get('source-summary').textContent,/mrad/);
  const html=ui.evaluate(`statsHtml({position:[0,0,0],direction:[1,0,0],azimuth:0,elevation:0,
    azimuth_defined:true,diameter_mm:5,half_angle_mrad:3,path_mm:100,status:'diverging',model:'geometric'})`);
  assert.doesNotMatch(html,/half.angle|mrad/i);assert.match(html,/diverging/);
  assert.doesNotMatch(fs.readFileSync(path.join(__dirname,'..','palette.html'),'utf8'),/local half.angle|src-half_angle_mrad/i);
});

test('only the selected optic is rendered in the inspector',async()=>{
  const ui=setup();ui.evaluate(`config.rows[0].commands='l50 r90';
    plan.optics.push({...plan.optics[0],id:'line1:1',token:'r90',kind:'mirror',label:'Mirror two',default_key:'r90'});
    renderRows();renderOptics(true);`);
  assert.ok(!ui.elements.get('optics').innerHTML.includes('Mirror two'));
  await click(ui,'',{selectStep:'0:1'});
  assert.ok(ui.elements.get('optics').innerHTML.includes('Mirror two'));
  assert.equal(ui.evaluate('studioSelected.id'),'1');
});
test('blank numeric fields block Build and retain the last committed parameter',()=>{
  const ui=setup();ui.evaluate('setValid(true)');
  const e={id:'step-focal',type:'number',value:'',dataset:{stepField:'focal'},classList:{add(){},remove(){}}};
  ui.listeners.input({target:e});
  assert.equal(ui.evaluate('valid'),false);assert.equal(ui.elements.get('build').disabled,true);
  assert.equal(ui.evaluate('config.rows[0].commands'),'l50');
  e.value='60';ui.listeners.input({target:e});
  assert.equal(ui.evaluate('studioHasInvalid()'),false);assert.equal(ui.evaluate('config.rows[0].commands'),'l60');
});
test('analysis started before an invalid numeric edit cannot re-enable Build',async()=>{
  const ui=setup();let resolve;
  const result=value(ui.evaluate('plan'));
  ui.context.window.adsk.fusionSendData=()=>new Promise(r=>resolve=r);
  const pending=ui.evaluate('analyze()');
  ui.listeners.input({target:{id:'step-focal',type:'number',value:'',dataset:{stepField:'focal'},classList:{add(){},remove(){}}}});
  resolve(JSON.stringify({ok:true,result}));await pending;
  assert.equal(ui.evaluate('valid'),false);assert.equal(ui.elements.get('build').disabled,true);
});
test('analysis requests are coalesced while a previous calculation is running',async()=>{
  const ui=setup();const pending=[];
  ui.context.window.adsk.fusionSendData=(action,raw)=>new Promise(resolve=>pending.push({action,raw,resolve}));
  const a=ui.evaluate('analyze()');
  ui.evaluate(`config.rows[0].commands='l100';schedule()`);await ui.evaluate('analyze()');
  assert.equal(pending.length,1);
  pending[0].resolve(JSON.stringify({ok:true,result:value(ui.evaluate('plan'))}));await a;
  const b=ui.evaluate('analyze()');assert.equal(pending.length,2);
  assert.equal(JSON.parse(pending[1].raw).config.rows[0].commands,'l100');
  pending[1].resolve(JSON.stringify({ok:true,result:{rows:[],optics:[],endpoints:[],warnings:[],lines:[]}}));await b;
  assert.equal(ui.evaluate('valid'),true);
});
test('bridge responses from a previous document are rejected',async()=>{
  const ui=setup();let resolve;ui.evaluate(`docKey='first'`);
  ui.context.window.adsk.fusionSendData=()=>new Promise(r=>resolve=r);
  const pending=ui.evaluate(`request('saved')`);ui.evaluate(`docKey='second'`);
  resolve(JSON.stringify({ok:true,result:emptySaved}));
  await assert.rejects(pending,e=>e.stale===true);
});
test('recovery drafts are not overwritten until Restore or Discard is chosen',async()=>{
  const ui=setup();ui.evaluate(`studioRecovery={config:{},saved_at:1}`);
  await ui.evaluate('studioSaveDraft()');assert.equal(ui.requests.length,0);
  await click(ui,'discard-recovery');
  assert.equal(ui.requests[0].action,'discard_draft');assert.equal(ui.requests[1].action,'save_draft');
});
test('recovery uses current document defaults while keeping occurrence overrides',async()=>{
  const ui=setup();ui.evaluate(`studioRecovery={config:JSON.parse(JSON.stringify(config)),saved_at:1};
    studioRecovery.config.component_defaults={obsolete:{}};
    studioRecovery.config.optic_overrides['line1:0']={token:'l50',representation:'custom',component_token:'retained'};`);
  await click(ui,'restore-recovery');
  assert.equal(ui.evaluate('config.component_defaults.l50.component_token'),'occ-A');
  assert.equal(ui.evaluate(`config.optic_overrides['line1:0'].component_token`),'retained');
  assert.equal(ui.evaluate('studioRecovery'),null);
});
test('recovery matches a changed occurrence token using the stable route identity',async()=>{
  const ui=setup();ui.evaluate(`config.route_id='stable';studioRecovery={config:JSON.parse(JSON.stringify(config)),saved_at:1,edit_target:{token:'old',run_id:'stable'}};
    savedRuns=[{token:'new',run_id:'stable',name:'Pump',editable:true}];`);
  await click(ui,'restore-recovery');assert.equal(ui.evaluate('editTarget.token'),'new');
  assert.equal(ui.evaluate('config.route_id'),'stable');
});
test('ambiguous recovery never chooses one of two saved route instances silently',async()=>{
  const ui=setup();ui.evaluate(`config.route_id='stable';studioRecovery={config:JSON.parse(JSON.stringify(config)),saved_at:1,edit_target:{token:'missing',run_id:'stable'}};
    savedRuns=[{token:'a',run_id:'stable',editable:true},{token:'b',run_id:'stable',editable:true}];`);
  await click(ui,'restore-recovery');assert.equal(ui.evaluate('editTarget'),null);
  assert.notEqual(ui.evaluate('config.route_id'),'stable');assert.match(ui.evaluate('editingNotice'),/ambiguous/);
});
test('visual step edits can be undone and redone without requesting model mutations',async()=>{
  const ui=setup();ui.evaluate('studioReset()');
  ui.listeners.input({target:{id:'step-focal',type:'number',value:'75',dataset:{stepField:'focal'},classList:{add(){},remove(){}}}});
  assert.equal(ui.evaluate('config.rows[0].commands'),'l75');
  await click(ui,'undo-draft');assert.equal(ui.evaluate('config.rows[0].commands'),'l50');
  await click(ui,'redo-draft');assert.equal(ui.evaluate('config.rows[0].commands'),'l75');
  assert.ok(ui.requests.every(r=>r.action==='save_draft'));
});
test('selected step labels are persisted and scheduled for backend naming',()=>{
  const ui=setup();ui.listeners.input({target:{id:'step-label',value:'Pump lens',dataset:{stepLabel:''}}});
  assert.equal(ui.evaluate(`config.rows[0].step_labels['0']`),'Pump lens');
  assert.equal(ui.evaluate('valid'),false);
});
test('new lines select their own first step and keep existing assignments',async()=>{
  const ui=setup();ui.evaluate(`studioSelected={row:'line1',id:'0'};override(plan.optics[0]);`);
  await click(ui,'add-row');
  assert.equal(ui.evaluate('studioSelected.row'),ui.evaluate('config.rows[1].id'));
  assert.equal(ui.evaluate(`config.optic_overrides['line1:0'].component_token`),'occ-A');
});
test('preview quality is explicit and busy operations disable all footer controls',async()=>{
  const ui=setup();ui.elements.set('preview-quality',{value:'draft'});ui.evaluate('setValid(true)');
  await click(ui,'preview');assert.equal(ui.requests[0].data.quality,'draft');
  ui.evaluate('setBusy(true)');
  for(const id of ['preview-quality','clear-preview','live-preview'])assert.equal(ui.elements.get(id).disabled,true);
});

test('Part build visibly requests Hybrid and carries the displayed document type',async()=>{
  const ui=setup();ui.evaluate(`acceptBuildContext({intent:'part',can_build:true,requires_hybrid:true,message:'Part documents allow only one component.'});setValid(true);`);
  assert.equal(ui.elements.get('build').textContent,'Switch to Hybrid & build');
  assert.equal(ui.elements.get('build-close').textContent,'Switch, build & close');
  assert.equal(ui.elements.get('document-type-notice').hidden,false);
  assert.equal(ui.elements.get('preview').disabled,false);
  await click(ui,'build');
  assert.equal(ui.requests[0].data.convert_from,'part');
  assert.equal(ui.requests[0].data.close,false);
  assert.equal(ui.requests[0].data.config.convert_from,undefined);
});
test('restricted document preview never requests a type conversion',async()=>{
  const ui=setup();ui.evaluate(`acceptBuildContext({intent:'assembly',can_build:true,requires_hybrid:true,message:'Assembly'});setValid(true);`);
  await click(ui,'preview');
  assert.equal(ui.requests.length,1);
  assert.equal(ui.requests[0].action,'preview');
  assert.equal(ui.requests[0].data.convert_from,undefined);
});
test('successful conversion removes the notice and restores normal replacement controls',()=>{
  const ui=setup();ui.evaluate(`acceptBuildContext({intent:'part',can_build:true,requires_hybrid:true,message:'Part'});setBusy(true);`);
  ui.context.window.fusionJavaScriptHandler.handle('built',JSON.stringify({name:'Route',token:'created',run_id:'route',
    endpoint_count:1,saved:emptySaved,warnings:[],build_context:{intent:'hybrid',can_build:true,requires_hybrid:false,message:''}}));
  assert.equal(ui.elements.get('document-type-notice').hidden,true);
  assert.equal(ui.elements.get('build').textContent,'Replace route');
  assert.equal(ui.elements.get('build-close').textContent,'Replace & close');
  assert.equal(ui.evaluate('busy'),false);
});
test('failed native build uses document type reported after rollback for the next action',async()=>{
  const ui=setup();ui.evaluate(`acceptBuildContext({intent:'hybrid',can_build:true,requires_hybrid:false,message:''});setValid(true);setBusy(true);`);
  ui.context.window.fusionJavaScriptHandler.handle('build_failed',JSON.stringify({message:'Build failed',
    build_context:{intent:'part',can_build:true,requires_hybrid:true,message:'Part'}}));
  assert.equal(ui.elements.get('build').textContent,'Switch to Hybrid & build');
  assert.equal(ui.elements.get('build').disabled,false);
  await click(ui,'build-close');
  assert.equal(ui.requests[0].data.convert_from,'part');
  assert.equal(ui.requests[0].data.close,true);
});
test('unknown document type blocks build while retaining preview and the draft',async()=>{
  const ui=setup();ui.evaluate(`acceptBuildContext({intent:'unavailable',can_build:false,requires_hybrid:false,message:'Unsupported document type'});setValid(true);`);
  assert.equal(ui.elements.get('build').disabled,true);
  assert.equal(ui.elements.get('build-close').disabled,true);
  assert.equal(ui.elements.get('preview').disabled,false);
  const before=value(ui.evaluate('config'));
  await click(ui,'build');
  assert.equal(ui.requests.length,0);
  assert.deepEqual(value(ui.evaluate('config')),before);
});
test('analysis refreshes changed document intent without resetting the route',async()=>{
  const ui=setup();ui.evaluate('config.rows.forEach(RouterEditor.ensure)');const before=value(ui.evaluate('config'));
  ui.responses.analyze={rows:[],optics:[],endpoints:[],warnings:[],lines:[],
    build_context:{intent:'assembly',can_build:true,requires_hybrid:true,message:'Assembly needs Hybrid'}};
  await ui.evaluate('analyze()');
  assert.equal(ui.evaluate('buildContext.intent'),'assembly');
  assert.equal(ui.elements.get('build').textContent,'Switch to Hybrid & build');
  assert.equal(ui.evaluate('valid'),true);
  assert.deepEqual(value(ui.evaluate('config')),before);
});

test('overview metrics use the labelled endpoint and distinguish an ideal focus',()=>{
  const ui=setup();ui.evaluate(`plan.lines=[{start:[0,0,0],end:[50,0,0],event_ids:['p']}];
    plan.rows=[{id:'line1',ports:[],steps:[{diameter_mm:0,status:'geometric focus'}],endpoint:{id:'line1:end',name:'Path 1 · end',state:{trace:[{id:'p'}]},stats:{diameter_mm:5,path_mm:50,gdd_fs2:100,status:'near collimated'}}}];setValid(true);studioMap();`);
  let html=ui.elements.get('route-metrics').innerHTML;
  assert.match(html,/Diameter at this endpoint/);assert.match(html,/5 mm/);assert.doesNotMatch(html,/<strong>0 mm<\/strong>/);
  assert.match(ui.elements.get('route-map').innerHTML,/selected-path/);
  ui.evaluate(`plan.rows[0].endpoint.stats.diameter_mm=0;plan.rows[0].endpoint.stats.status='geometric focus';studioMap()`);
  assert.match(ui.elements.get('route-metrics').innerHTML,/0 mm · ideal geometric focus/);
});

test('planning representation toggle keeps calibrated CAD assignments',async()=>{
  const ui=setup();ui.evaluate(`config.optic_overrides['line1:0']={token:'l50',custom:true,component_token:'part',reference:[1,2,3],rotation:[0,45,0],component_linked:true};`);
  const before=value(ui.evaluate('config.optic_overrides'));
  ui.listeners.input({target:{id:'opt-use_assigned_components',type:'checkbox',checked:false,dataset:{}}});
  assert.equal(ui.evaluate('config.options.use_assigned_components'),false);
  assert.deepEqual(value(ui.evaluate('config.optic_overrides')),before);
  assert.equal(ui.evaluate("componentTemplate(config.optic_overrides['line1:0']).component_linked"),true);
});

test('selected CAD preview requests exactly one optic without enabling full CAD',async()=>{
  const ui=setup();ui.evaluate('config.options.use_assigned_components=false');
  const before=value(ui.evaluate('config'));ui.responses.preview={warnings:[]};
  await click(ui,'',{previewComponent:'line1:0'});
  const request=ui.requests.find(x=>x.action==='preview');
  assert.equal(request.data.quality,'selected');assert.equal(request.data.optic_id,'line1:0');
  assert.deepEqual(value(ui.evaluate('config')),before);assert.equal(ui.evaluate('busy'),false);
});

test('unassigned CAD does not block a valid simple planning build',async()=>{
  const ui=setup();ui.evaluate('config.options.use_assigned_components=false');
  const optic=value(ui.evaluate('plan.optics[0]'));optic.settings={custom:true,representation:'custom'};
  ui.responses.analyze={rows:[],optics:[optic],endpoints:[],warnings:[],lines:[]};
  await ui.evaluate('analyze()');
  assert.equal(ui.evaluate('valid'),true);
  assert.match(ui.elements.get('validation').textContent,/simple planning optics remain available/);
});

test('component guide opens independently of model changes',async()=>{
  const ui=setup();const before=value(ui.evaluate('config'));
  await click(ui,'',{componentGuide:''});assert.equal(ui.elements.get('component-guide-modal').hidden,false);
  await click(ui,'component-guide-close');assert.equal(ui.elements.get('component-guide-modal').hidden,true);
  assert.deepEqual(value(ui.evaluate('config')),before);assert.equal(ui.requests.length,0);
});
test('calculator highlights the resolved prefix using the requested entry color',async()=>{
  const ui=setup();savedFixture(ui);
  ui.evaluate(`calculatorSelection.add('a|line1:end');savedScene={lines:[{start:[0,0,0],end:[100,0,0],run_token:'a',event_ids:['prefix']},{start:[100,0,0],end:[300,0,0],run_token:'a',event_ids:['excluded']}],optics:[]};`);
  ui.responses.calculate={geometric_mm:100,optical_path_mm:100,loss_pct:51,gdd_fs2:300,notes:[],selections:[{
    requested_id:'a|line1:end',resolved_id:'a|line1:1:R',run_token:'a',name:'Reflected port',event_ids:['prefix'],included_commands:'p100 bsc [R]',included:[]}]};
  await click(ui,'calculate');
  assert.match(ui.elements.get('calculator-paths').innerHTML,/Used in this sum/);
  assert.match(ui.elements.get('calculator-paths').innerHTML,/p100 bsc \[R\]/);
  assert.equal((ui.elements.get('calculator-map').innerHTML.match(/class="selected-path"/g)||[]).length,1);
  const before=value(ui.evaluate('config'));
  await ui.listeners.change({target:{id:'',dataset:{calcColor:'a|line1:end'},value:'#992244'}});
  assert.match(ui.elements.get('calculator-map').innerHTML,/#992244/);assert.deepEqual(value(ui.evaluate('config')),before);
});
test('generic shape and outgoing color edits remain per-optic settings',async()=>{
  const ui=setup();ui.evaluate(`config.rows[0].commands='g';plan.optics[0]={...plan.optics[0],token:'g',kind:'generic',default_key:'g',shape:'disc',depth_mm:3,settings:{custom:false,representation:'builtin'}};`);
  await ui.listeners.change({target:{id:'',dataset:{genericField:'shape',genericId:'line1:0'},value:'ball'}});
  await ui.listeners.change({target:{id:'',dataset:{genericField:'beam_color',genericId:'line1:0'},value:'purple'}});
  assert.equal(ui.evaluate("config.optic_overrides['line1:0'].shape"),'ball');
  assert.equal(ui.evaluate("config.optic_overrides['line1:0'].beam_color"),'purple');
  assert.equal(ui.evaluate('config.rows[0].commands'),'g');
});
test('catalogue presents meaningful presets and inserts the chosen generic shape',async()=>{
  const ui=setup();ui.evaluate(`$('insert-filter').value='';studioCatalogueRender()`);
  const html=ui.elements.get('insert-catalogue').innerHTML;
  for(const text of ['p10','p50','p100','l-100','l-50','r-90','_r90f50','Custom…','Outgoing parent axis','data-generic-shape="cube"'])assert.ok(html.includes(text),text);
  await click(ui,'',{addCommand:'g',genericShape:'cube'});
  assert.equal(ui.evaluate('config.rows[0].commands'),'l50 g');
  assert.equal(ui.evaluate('Object.values(config.optic_overrides)[0].shape'),'cube');
});
test('About offers author credit and both citation formats through the native clipboard',async()=>{
  const ui=setup();ui.responses.copy_text={copied:true};
  await click(ui,'about-open');assert.equal(ui.elements.get('about-modal').hidden,false);
  await click(ui,'cite-text');await click(ui,'cite-bibtex');
  assert.match(ui.requests[0].data.text,/Amon P\. Lanz/);assert.match(ui.requests[1].data.text,/@software/);
  assert.match(ui.requests[1].data.text,/Apache-2.0/);
  for(const r of ui.requests)assert.ok(r.data.text.includes('https://github.com/AmLanz/LaserOpticsRouter'));
  assert.equal(ui.requests[1].data.text.trim(),fs.readFileSync(path.join(__dirname,'..','CITATION.bib'),'utf8').trim());
  await click(ui,'about-close');assert.equal(ui.elements.get('about-modal').hidden,true);
});
test('full-path overview resolves an upstream occurrence by position and direction',()=>{
  const ui=setup();ui.evaluate(`plan.lines=[{start:[0,0,0],end:[20,0,0],event_ids:['child:p']}];plan.optics=[];
    saved=[{run_id:'parent',endpoint_id:'end',run_token:'right',state:{position:[0,0,0],azimuth:0,elevation:0}},
           {run_id:'parent',endpoint_id:'end',run_token:'opposite',state:{position:[0,0,0],azimuth:180,elevation:0}}];
    savedScene={lines:[{run_token:'right',event_ids:['parent:p'],start:[-50,0,0],end:[0,0,0]},{run_token:'opposite',event_ids:['parent:p'],start:[50,0,0],end:[0,0,0]}],optics:[]};
    globalThis.contextEnd={trace_start:1,state:{trace:[{id:'parent:p'},{id:'child:p'}]},start_state:{position:[0,0,0],azimuth:0,elevation:0,link:{run_id:'parent',endpoint_id:'end'}}};`);
  const result=value(ui.evaluate('studioContextScene(contextEnd)'));
  assert.equal(result.complete,true);assert.equal(result.scene.lines.length,2);assert.equal(result.scene.lines[0].run_token,'right');
});
test('ambiguous upstream instances are not silently displayed as the measured source',()=>{
  const ui=setup();ui.evaluate(`plan.lines=[{event_ids:['child:p']}];plan.optics=[];
    saved=['a','b'].map(run_token=>({run_id:'parent',endpoint_id:'end',run_token,state:{position:[0,0,0],azimuth:0,elevation:0}}));
    savedScene={lines:[],optics:[]};globalThis.contextEnd={trace_start:1,state:{trace:[{id:'parent:p'},{id:'child:p'}]},start_state:{position:[0,0,0],azimuth:0,elevation:0,link:{run_id:'parent',endpoint_id:'end'}}};`);
  assert.equal(ui.evaluate('studioContextScene(contextEnd).complete'),false);
  assert.equal(ui.evaluate('studioContextScene(contextEnd).key'),'');
});

test('Use default is a local reference switch and never writes document defaults',async()=>{
  const ui=setup();
  await ui.listeners.change({target:{dataset:{useDefault:'line1:0'},checked:false}});
  assert.equal(ui.evaluate('cardSettings(plan.optics[0]).representation'),'custom');
  ui.evaluate("config.optic_overrides['line1:0'].rotation[2]=70");
  assert.equal(ui.evaluate('config.component_defaults.l50.rotation[2]'),0);
  await ui.listeners.change({target:{dataset:{useDefault:'line1:0'},checked:true}});
  assert.equal(ui.evaluate('cardSettings(plan.optics[0]).rotation[2]'),0);
  assert.equal(ui.evaluate('cardSettings(plan.optics[0]).representation'),'default');
  assert.equal(ui.requests.length,0);
});
test('default dimension edits stay separate and calibration controls are absent',()=>{
  const ui=setup();ui.evaluate("componentDefaultKey='l50';renderComponentDefaults()");
  const html=ui.elements.get('component-default-editor').innerHTML;
  assert.doesNotMatch(html,/data-default-field="(?:shift|rotation)/);
  ui.listeners.input({target:{id:'default-diameter_mm',dataset:{defaultField:'diameter_mm'},type:'number',value:'30.5',min:'0.01',max:''}});
  assert.equal(ui.evaluate('defaultDraft().diameter_mm'),30.5);
  assert.equal(ui.evaluate('config.component_defaults.l50.diameter_mm'),undefined);
  assert.equal(ui.elements.get('component-default-status').textContent,'Unsaved default edits');
});
test('angle-independent splitter default exposes transmission displacement',()=>{
  const ui=setup();ui.evaluate("componentDefaultKey='bs';renderComponentDefaults()");
  assert.equal(ui.evaluate("physicalKey('bs30')"),'bs');assert.equal(ui.evaluate("physicalKey('bs-90')"),'bs');
  assert.equal(ui.evaluate("physicalKey('+bs-90')"),'+bs');
  const html=ui.elements.get('component-default-editor').innerHTML;
  assert.match(html,/data-default-field="displacement_mm"/);assert.match(html,/reflection stays at the incoming hit point/);
});
test('saved schematic highlights the chosen route without opening an editor',async()=>{
  const ui=setup();savedFixture(ui);
  ui.evaluate(`savedScene={lines:[{start:[0,0,0],end:[100,0,0],run_token:'a',event_ids:['a:p'],color:'red'},
    {start:[0,4,0],end:[100,4,0],run_token:'b',event_ids:['b:p'],color:'blue'}],optics:[],warnings:[]};studioTab='saved';renderSaved()`);
  await click(ui,'',{highlightRun:'1'});
  assert.equal(ui.evaluate('savedHighlight.run_token'),'b');assert.equal(ui.requests.length,0);
  assert.equal(ui.evaluate('editTarget'),null);
  const html=ui.elements.get('saved-map').innerHTML;
  assert.match(html,/data-map-run="a"/);assert.match(html,/data-map-run="b"/);assert.match(html,/selected-path/);
  assert.equal(ui.elements.get('saved-highlight-edit').disabled,false);
});
test('automatic budget bridges are listed and use their editable selection color',()=>{
  const ui=setup();savedFixture(ui);
  ui.evaluate(`calculatorResult={selections:[{automatic:true,run_token:'b',resolved_id:'b|line1:end',name:'Connector',route_name:'Reference',event_ids:['b:p'],included_commands:'p40 l50',included:[]}]};renderCalculator(true)`);
  assert.match(ui.elements.get('calculator-connectors').innerHTML,/Included connecting paths/);
  assert.match(ui.elements.get('calculator-connectors').innerHTML,/p40 l50/);
  assert.equal(ui.evaluate('calculatorLayers()[0].run_token'),'b');
  assert.match(ui.elements.get('calculator-connectors').innerHTML,/data-calc-color="auto\|b\|b\|line1:end"/);
});
test('passive elements and tweaker parameters are available in the visual editor',()=>{
  const ui=setup();
  for(const kind of ['laha','laqu','nd','tp'])assert.equal(ui.evaluate(`studioCatalogue.some(c=>c[0]==='${kind}')`),true);
  ui.evaluate("config.rows[0].commands='tp30d0.5';delete config.rows[0].step_ids;studioSelected=null;studioInspector()");
  assert.match(ui.elements.get('step-editor').innerHTML,/Incidence from normal/);
  assert.match(ui.elements.get('step-editor').innerHTML,/Signed displacement/);
});

test('automatic first step opens the catalogue and replaces in one undoable edit',async()=>{
  const ui=setup();ui.evaluate('newRun();studioReset()');
  await click(ui,'',{selectStep:'0:0'});
  assert.equal(ui.elements.get('insert-modal').hidden,false);
  assert.match(ui.elements.get('insert-hint').textContent,/Replace the starter p100/);
  await click(ui,'',{addCommand:'l-100'});
  assert.equal(ui.evaluate('config.rows[0].commands'),'l-100');
  assert.equal(ui.evaluate('config.rows[0].starter_step_id'),undefined);
  assert.equal(ui.elements.get('insert-modal').hidden,true);
  await click(ui,'undo-draft');assert.equal(ui.evaluate('config.rows[0].commands'),'p100');
  assert.equal(ui.evaluate('RouterEditor.isStarter(config.rows[0],RouterEditor.ensure(config.rows[0])[0])'),true);
  await click(ui,'redo-draft');assert.equal(ui.evaluate('config.rows[0].commands'),'l-100');
});
test('cancel keeps a starter unchanged and a manually chosen p100 opens Inspector',async()=>{
  const ui=setup();ui.evaluate('newRun();studioReset()');
  await click(ui,'',{selectStep:'0:0'});await click(ui,'insert-cancel');
  assert.equal(ui.evaluate('studioHistory.items.length'),1);
  assert.equal(ui.evaluate('config.rows[0].commands'),'p100');
  await click(ui,'',{selectStep:'0:0'});await click(ui,'',{addCommand:'p100'});
  await click(ui,'',{selectStep:'0:0'});assert.equal(ui.elements.get('insert-modal').hidden,true);
  assert.match(ui.elements.get('step-editor').innerHTML,/Distance · mm/);
});
test('continuation starter replacement preserves its endpoint and generic shape',async()=>{
  const ui=setup();await ui.evaluate("newRow('endpoint-packet','Parent end')");
  await click(ui,'',{selectStep:'1:0'});await click(ui,'',{addCommand:'g',genericShape:'ball'});
  assert.equal(ui.evaluate('config.rows[1].commands'),'g');
  assert.equal(ui.evaluate('config.rows[1].endpoint'),'endpoint-packet');
  assert.equal(ui.evaluate('config.rows[1].start_mode'),'snapshot');
  assert.equal(ui.evaluate("config.optic_overrides[config.rows[1].id+':'+config.rows[1].step_ids[0]].shape"),'ball');
  await click(ui,'',{insertStep:'1'});await click(ui,'',{addCommand:'p50'});
  assert.equal(ui.evaluate('config.rows[1].commands'),'g p50');
});
test('a stale replacement target cannot replace another row',async()=>{
  const ui=setup();ui.evaluate('newRun()');await click(ui,'',{selectStep:'0:0'});
  ui.evaluate("config.rows[0].id='changed'");
  await assert.rejects(ui.evaluate("studioClick({dataset:{addCommand:'l50'}})"),/starter step changed/);
  assert.equal(ui.evaluate('config.rows[0].commands'),'p100');
});
test('Commands starts expanded and retains explicit collapse when paths rerender',async()=>{
  const ui=setup();ui.evaluate('renderRows()');
  assert.match(ui.elements.get('rows').innerHTML,/data-commands-for="line1" open/);
  ui.context.document.querySelectorAll=selector=>selector==='.command-editor'?[{dataset:{commandsFor:'line1'},open:false}]:[];
  await ui.evaluate('newRow()');
  const html=ui.elements.get('rows').innerHTML;
  assert.doesNotMatch(html,/data-commands-for="line1" open/);
  assert.match(html,new RegExp('data-commands-for="'+ui.evaluate('config.rows[1].id')+'" open'));
});
test('palette load queues native color repair only for legacy clear beams',async()=>{
  for(const legacy of [false,true]){
    const ui=setup();
    ui.responses.bootstrap={config:value(ui.evaluate('config')),doc_key:'doc',saved:{...emptySaved,runs:legacy?[{token:'a',name:'Saved arm',display_repair_needed:true}]:[]}};
    ui.responses.analyze={rows:[],optics:[],endpoints:[],warnings:[],lines:[]};
    await ui.evaluate('load()');
    const repairs=ui.requests.filter(r=>r.action==='manage');
    assert.equal(repairs.length,Number(legacy));
    if(legacy)assert.equal(repairs[0].data.operation,'refresh_status');
  }
});

test('custom numeric input survives an asynchronous analysis repaint',async()=>{
  const ui=setup();ui.evaluate(`config.rows[0].commands='g';studioSelected={row:'line1',id:'0'};
    plan.optics[0]={...plan.optics[0],kind:'generic',token:'g',default_key:'g',settings:{representation:'builtin'}};
    renderOptics(true);`);
  const input={id:'optic-number',type:'number',tagName:'INPUT',min:'0.01',max:'',value:'2.50',dataset:{opticField:'depth_mm',optic:'line1:0'},classList:{add(){},remove(){}}};
  ui.context.document.activeElement=input;
  ui.listeners.input({target:input});
  const before=ui.elements.get('optics').innerHTML;
  ui.responses.analyze={rows:[],optics:[{...value(ui.evaluate('plan.optics[0]')),diameter_mm:40}],endpoints:[],warnings:[],lines:[]};
  await ui.evaluate('analyze()');
  assert.equal(ui.elements.get('optics').innerHTML,before);
  assert.equal(input.value,'2.50');
  assert.equal(ui.evaluate("config.optic_overrides['line1:0'].depth_mm"),2.5);
  ui.context.document.activeElement=null;ui.evaluate('renderOptics()');
  assert.notEqual(ui.elements.get('optics').innerHTML,before);
});
test('incomplete custom GDD leaves prior value intact and blocks stale analysis',async()=>{
  const ui=setup();
  ui.evaluate(`config.optic_overrides['line1:0']={token:'l50',representation:'builtin',budget:{gdd_fs2:4}};setValid(true)`);
  const e={id:'gdd-entry',type:'number',tagName:'INPUT',min:'',max:'',value:'',dataset:{opticField:'budget.gdd_fs2',optic:'line1:0'},classList:{add(){},remove(){}}};
  ui.context.document.activeElement=e;ui.listeners.input({target:e});await ui.evaluate('analyze()');
  assert.equal(ui.evaluate('valid'),false);assert.equal(ui.requests.length,0);
  assert.equal(ui.evaluate("config.optic_overrides['line1:0'].budget.gdd_fs2"),4);
  for(const [raw,expected] of [['-2.5',-2.5],['-2.5e2',-250]]){
    e.value=raw;ui.listeners.input({target:e});
    assert.equal(ui.evaluate("config.optic_overrides['line1:0'].budget.gdd_fs2"),expected);
    assert.equal(ui.evaluate('studioHasInvalid()'),false);
  }
});
test('step number input retains partial spelling while analysis updates Inspector',()=>{
  const ui=setup();ui.evaluate(`config.rows[0].commands='cyl100h';studioSelected={row:'line1',id:'0'};studioInspector()`);
  const before=ui.elements.get('step-editor').innerHTML;
  const e={id:'step-focal',type:'number',tagName:'INPUT',min:'',max:'',value:'-50.0',dataset:{stepField:'focal'},classList:{add(){},remove(){}}};
  ui.context.document.activeElement=e;ui.listeners.input({target:e});ui.evaluate('studioInspector()');
  assert.equal(ui.elements.get('step-editor').innerHTML,before);assert.equal(e.value,'-50.0');
  assert.equal(ui.evaluate('config.rows[0].commands'),'cyl-50h');
});
test('reference chooser filters full paths, escapes names, and stages defaults',async()=>{
  const ui=setup();const before=value(ui.evaluate('config.component_defaults'));
  ui.responses.list_components={items:[{component_token:'a&b',component_name:'Bench+Mirror <A>',component_linked:true},{component_token:'lens',component_name:'Lens:1'}]};
  ui.responses.choose_component={component_token:'a&b',component_ref_token:'def-a',component_name:'Bench+Mirror <A>',component_linked:true};
  await ui.evaluate("openComponentPicker({defaultKey:'l50'})");
  assert.equal(ui.requests[0].action,'list_components');
  assert.match(ui.elements.get('component-choices').innerHTML,/Mirror &lt;A&gt;/);
  assert.equal(ui.elements.get('component-choices').value,'a&b');
  ui.elements.get('component-search').value='bench+';ui.evaluate('renderComponentPicker()');
  assert.doesNotMatch(ui.elements.get('component-choices').innerHTML,/Lens:1/);
  ui.elements.get('component-choices').value='a&b';await click(ui,'component-picker-use');
  assert.equal(ui.requests[1].action,'choose_component');assert.equal(ui.requests[1].data.component_token,'a&b');
  assert.equal(ui.evaluate("componentDefaultDrafts.l50.component_token"),'a&b');
  assert.equal(ui.evaluate("componentDefaultDirty.has('l50')"),true);
  assert.deepEqual(value(ui.evaluate('config.component_defaults')),before);
});
test('reference chooser writes a local assignment and cancellation resumes analysis',async()=>{
  const ui=setup();ui.responses.list_components={items:[{component_token:'ref',component_name:'Prepared'}]};
  ui.responses.choose_component={component_token:'ref',component_name:'Prepared'};
  await ui.evaluate("openComponentPicker({opticId:'line1:0'})");
  ui.elements.get('component-choices').value='ref';await click(ui,'component-picker-use');
  assert.equal(ui.evaluate("config.optic_overrides['line1:0'].component_token"),'ref');
  assert.equal(ui.elements.get('component-picker-modal').hidden,true);
  await ui.evaluate("openComponentPicker({opticId:'line1:0'})");
  ui.evaluate("$('component-search').value='no-such-component';renderComponentPicker()");
  assert.equal(ui.elements.get('component-picker-use').disabled,true);
  const seq=ui.evaluate('sequence');await click(ui,'component-picker-cancel');
  assert.ok(ui.evaluate('sequence')>seq);assert.equal(ui.evaluate('componentPickerTarget'),null);
});
test('wavelength modes are independent from the spatial Gaussian model',async()=>{
  const ui=setup();ui.evaluate('renderSettings()');
  ui.elements.get('src-spectrum-mode').value='gaussian';ui.elements.get('src-spectrum-width').value='20';ui.elements.get('src-spectrum-samples').value='9';
  await ui.listeners.change({target:{id:'src-spectrum-mode',dataset:{}}});
  assert.equal(ui.evaluate('config.source.model'),'geometric');
  assert.deepEqual(value(ui.evaluate('config.source.spectrum')),{mode:'gaussian',width_nm:20,samples:9});
  assert.match(ui.elements.get('spectrum-width-label').textContent,/FWHM/);
  ui.elements.get('src-spectrum-mode').value='sidebands';await ui.listeners.change({target:{id:'src-spectrum-mode',dataset:{}}});
  assert.equal(ui.elements.get('spectrum-samples-label').hidden,true);
  ui.elements.get('src-spectrum-mode').value='central';await ui.listeners.change({target:{id:'src-spectrum-mode',dataset:{}}});
  assert.deepEqual(value(ui.evaluate('config.source.spectrum')),{});
});
test('reset inspector toggles finite focus and collimation without changing diameter',async()=>{
  const ui=setup();ui.evaluate(`config.rows[0].commands='resetd5finf';studioSelected={row:'line1',id:'0'};studioInspector()`);
  assert.match(ui.elements.get('step-editor').innerHTML,/Collimated \(finf\)/);
  await ui.listeners.change({target:{dataset:{resetCollimated:''},checked:false}});
  assert.equal(ui.evaluate('config.rows[0].commands'),'resetd5f50');
  await ui.listeners.change({target:{dataset:{resetCollimated:''},checked:true}});
  assert.equal(ui.evaluate('config.rows[0].commands'),'resetd5finf');
});

test('catalogue places cylinder after lens and grating just before generic',()=>{
  const ui=setup();const kinds=value(ui.evaluate('studioCatalogue.map(x=>x[0])'));
  assert.equal(kinds[kinds.indexOf('lens')+1],'cyl');
  assert.deepEqual(kinds.slice(-2),['grating','generic']);
  assert.deepEqual(value(ui.evaluate('Object.keys(familyNames).slice(-2)')),['grating','generic']);
});
test('component corrections have reproducible axes and assembly-coordinate labels',()=>{
  const ui=setup();ui.evaluate(`studioSelected={row:'line1',id:'0'};renderOptics(true)`);
  const html=ui.elements.get('optics').innerHTML;
  for(const text of ['Component Rx','Component Rz','Assembly ΔX','Assembly ΔZ','−90° about Z','component_rotation_deg.2','assembly_offset_mm.0'])assert.ok(html.includes(text),text);
});
test('component correction number input keeps raw spelling during analysis',async()=>{
  const ui=setup();ui.evaluate(`config.optic_overrides['line1:0']={token:'l50',representation:'custom',component_token:'source'};
    studioSelected={row:'line1',id:'0'};renderOptics(true)`);
  const e={id:'rotation-entry',type:'number',tagName:'INPUT',min:'',max:'',value:'-90.0',dataset:{opticField:'component_rotation_deg.2',optic:'line1:0'},classList:{add(){},remove(){}}};
  ui.context.document.activeElement=e;ui.listeners.input({target:e});
  const html=ui.elements.get('optics').innerHTML;
  ui.responses.analyze={rows:[],optics:[value(ui.evaluate('plan.optics[0]'))],endpoints:[],warnings:[],lines:[]};
  await ui.evaluate('analyze()');
  assert.equal(ui.elements.get('optics').innerHTML,html);assert.equal(e.value,'-90.0');
  assert.deepEqual(value(ui.evaluate("config.optic_overrides['line1:0'].component_rotation_deg")),[0,0,-90]);
  e.dataset.opticField='assembly_offset_mm.1';e.value='-1.25e1';ui.listeners.input({target:e});
  assert.deepEqual(value(ui.evaluate("config.optic_overrides['line1:0'].assembly_offset_mm")),[0,-12.5,0]);
});
test('default corrections are staged and retained in the component template',()=>{
  const ui=setup();ui.evaluate("componentDefaultKey='l50'");
  for(const [field,raw] of [['component_rotation_deg.2','-90'],['assembly_offset_mm.0','3.5']]){
    ui.listeners.input({target:{id:'default-field',type:'number',tagName:'INPUT',min:'',max:'',value:raw,dataset:{defaultField:field},classList:{add(){},remove(){}}}});
  }
  const staged=value(ui.evaluate('componentTemplate(defaultDraft())'));
  assert.deepEqual(staged.component_rotation_deg,[0,0,-90]);assert.deepEqual(staged.assembly_offset_mm,[3.5,0,0]);
  assert.equal(ui.evaluate("config.component_defaults.l50.component_rotation_deg"),undefined);
});
test('compressor example sets the documented source and complete return route',async()=>{
  const ui=setup();const commands='p100 +gr600a-45m-1h p150 +gr600a13.126795470828m-1h p150 r0v90 p10 r180v-90 p150 +gr600a-45m-1h p150 +gr600a13.126795470828m-1h p100';
  await click(ui,'',{example:commands,exampleSource:'compressor'});
  assert.equal(ui.evaluate('config.rows[0].commands'),commands);
  assert.deepEqual(value(ui.evaluate('config.source.spectrum')),{mode:'sidebands',width_nm:20});
  assert.equal(ui.evaluate('config.source.wavelength_nm'),800);assert.equal(ui.evaluate('config.source.half_angle_mrad'),0);
  assert.equal(ui.evaluate('config.rows[0].start_mode'),'source');
});
