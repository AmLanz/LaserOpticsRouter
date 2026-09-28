'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const Editor=require('../editor.js');
const root=path.join(__dirname,'..');
function fixture(commands='p100 l50 p50 r90 p20'){
  const row={id:'arm',name:'Arm',commands,start_mode:'source'};
  const config={rows:[row],optic_overrides:{}};Editor.ensure(row);
  return {row,config};
}
function python(code,input){
  const result=spawnSync(process.env.LOR_TEST_PYTHON||(process.platform==='win32'?'python':'python3'),['-c',code],{cwd:root,input:JSON.stringify(input),encoding:'utf8',maxBuffer:8e6});
  assert.equal(result.status,0,result.stderr);return JSON.parse(result.stdout);
}
test('every visual token round-trips to the same Python optical command',()=>{
  const commands=['p0','p1e-3','l-50','+l150','f-l50','pol','f+pol','r90v30','r-90v-30','r0v60',
    'r90f50','_r-90f50','+f_r90v20f75','bs30v10','bsc','bsc-','-bsc-','wp20h','wp20v-',
    'rp10.6','rp1e-2v','bd2.7h','f_bd4v-','g','+g','fg'];
  const pairs=commands.map(command=>[command,Editor.serialize(Editor.parse(command))]);
  const result=python(`import sys,json,core
pairs=json.load(sys.stdin)
def parsed(s):
 d=core.parse_commands(s)[0]
 for k in ('raw','start','end'):d.pop(k)
 return d
print(json.dumps([parsed(a)==parsed(b) for a,b in pairs]))`,pairs);
  assert.ok(result.every(Boolean));
});
test('invalid prefixes and splitter focal commands stay unrecognized',()=>{
  for(const raw of ['ffl50','+-l50','_l50','__r90f50','_r90','bs90f50','fp50'])
    assert.equal(Editor.parse(raw).kind,'unknown',raw);
});
test('distance edits preserve optic and propagation identity',()=>{
  const {row,config}=fixture();config.optic_overrides['arm:1']={token:'l50',component_token:'lens-A'};
  const before=[...row.step_ids];Editor.reconcile(config,row,'p110 l50 p70 r90 p40');
  assert.deepEqual(row.step_ids,before);assert.equal(config.optic_overrides['arm:1'].component_token,'lens-A');
});
test('inserting a propagation preserves existing component identity and budget',()=>{
  const {row,config}=fixture();config.optic_overrides['arm:1']={token:'l50',component_token:'lens-A',budget:{gdd_fs2:20}};
  Editor.operate(config,row,1,'insert','p25');
  assert.equal(row.step_ids[2],'1');assert.equal(config.optic_overrides['arm:1'].budget.gdd_fs2,20);
  assert.equal(new Set(row.step_ids).size,row.step_ids.length);
});
test('moving an optic retains its unique assignment and label',()=>{
  const {row,config}=fixture();config.optic_overrides['arm:1']={token:'l50',component_token:'lens-A'};row.step_labels['1']='Input lens';
  Editor.operate(config,row,1,'down');
  assert.equal(row.step_ids[2],'1');assert.equal(Editor.ensure(row)[2].label,'Input lens');
  assert.equal(config.optic_overrides['arm:1'].component_token,'lens-A');
});
test('duplicated optics have independent calibration objects',()=>{
  const {row,config}=fixture('l50 p50');config.optic_overrides['arm:0']={token:'l50',reference:[1,2,3],budget:{loss_pct:7}};
  row.step_labels['0']='Lens';Editor.operate(config,row,0,'duplicate');const newId=row.step_ids[1];
  config.optic_overrides['arm:'+newId].reference[0]=99;
  assert.equal(config.optic_overrides['arm:0'].reference[0],1);assert.equal(row.step_labels[newId],'Lens copy');
});
test('all OAP sign and parent-axis variants reuse local calibration',()=>{
  const {row,config}=fixture('r90f50');config.optic_overrides['arm:0']={token:'r90f50',component_token:'oap',rotation:[1,2,3]};
  for(const raw of ['_r90f50','_r-90f50','r-90f50','r90f50']){
    assert.equal(Editor.update(config,row,0,Editor.parse(raw)),false);
    assert.equal(config.optic_overrides['arm:0'].component_token,'oap');
    assert.equal(config.optic_overrides['arm:0'].token,raw);
  }
});
test('unique orientation edits in command text also preserve local calibration',()=>{
  const {row,config}=fixture('p50 r90f50 p50');config.optic_overrides['arm:1']={token:'r90f50',component_token:'oap'};
  Editor.reconcile(config,row,'p50 _r-90f50 p50');
  assert.equal(config.optic_overrides['arm:1'].component_token,'oap');
  assert.equal(config.optic_overrides['arm:1'].token,'_r-90f50');
});
test('changing a physical focal length resets only that optic assignment',()=>{
  const {row,config}=fixture();config.optic_overrides={'arm:1':{token:'l50',component_token:'lens'},'arm:3':{token:'r90',component_token:'mirror'}};
  assert.equal(Editor.update(config,row,1,Editor.parse('l100')),true);
  assert.equal(config.optic_overrides['arm:1'],undefined);assert.equal(config.optic_overrides['arm:3'].component_token,'mirror');
});
test('ambiguous repeated optics in a rewritten sequence are not guessed',()=>{
  const {row,config}=fixture('l50 p20 l50 r90');config.optic_overrides={'arm:0':{token:'l50',component_token:'first'},'arm:2':{token:'l50',component_token:'second'},'arm:3':{token:'r90',component_token:'mirror'}};
  const lost=Editor.reconcile(config,row,'l50 r90');assert.equal(lost,2);
  assert.equal(Object.keys(config.optic_overrides).length,1);assert.equal(config.optic_overrides['arm:3'].component_token,'mirror');
});
test('unchanged repeated optics retain their ordered assignments during distance edits',()=>{
  const {row,config}=fixture('l50 p20 l50');config.optic_overrides={'arm:0':{token:'l50',component_token:'first'},'arm:2':{token:'l50',component_token:'second'}};
  Editor.reconcile(config,row,'l50 p25 l50');assert.equal(config.optic_overrides['arm:2'].component_token,'second');
  assert.deepEqual(row.step_ids,['0','1','2']);
});
test('text edits preserve exact whitespace/comments and structural edits preserve comments',()=>{
  const {row,config}=fixture('p100 l50 # input');const raw='  p100\t L50   # λ note';
  Editor.reconcile(config,row,raw);assert.equal(row.commands,raw);
  Editor.operate(config,row,1,'duplicate');assert.match(row.commands,/# λ note$/);
});
test('empty line can be repaired by insertion but the last remaining step cannot be removed',()=>{
  const {row,config}=fixture('');Editor.operate(config,row,0,'insert','p100');assert.equal(row.commands,'p100');
  assert.throws(()=>Editor.operate(config,row,0,'remove'),/at least one step/);
});
test('draft history coalesces typing, supports redo, and discards the redo branch after an edit',()=>{
  const h=new Editor.History();h.reset({n:0});h.record({n:1},'field',1000);h.record({n:12},'field',1100);
  assert.equal(h.items.length,2);assert.deepEqual(h.travel(-1),{n:0});assert.deepEqual(h.travel(1),{n:12});
  h.travel(-1);h.record({n:2},'',1500);assert.equal(h.travel(1),null);
});
test('the undo history has both a state-count and memory bound',()=>{
  const h=new Editor.History(4);h.reset({n:0});for(let n=1;n<10;n++)h.record({n});assert.equal(h.items.length,4);
  const text='x'.repeat(3e6);for(let n=10;n<20;n++)h.record({n,text});
  assert.ok(h.items.reduce((n,x)=>n+x.length,0)<=12e6);
});
test('an edited sequence is accepted by the real Python planner with the intended CAD and budgets',()=>{
  const {row,config}=fixture();config.optic_overrides={'arm:1':{token:'l50',representation:'custom',component_token:'lens-A',reference:[1,2,3],budget:{loss_pct:5,gdd_fs2:30}}};
  row.step_labels['1']='Pump lens';Editor.operate(config,row,1,'duplicate');Editor.operate(config,row,1,'insert','p25');
  const result=python(`import json,sys,core
c=core.default_config();c.update(json.load(sys.stdin));p=core.plan_layout(c)
print(json.dumps({'ids':[o['id'] for o in p['optics']], 'names':[o['label'] for o in p['optics']], 'components':[o['settings'].get('component_token') for o in p['optics']], 'loss':p['rows'][0]['endpoint']['stats']['loss_pct']}))`,config);
  assert.equal(result.components[0],'lens-A');assert.equal(result.components[1],'lens-A');
  assert.match(result.names[0],/Pump lens/);assert.match(result.names[1],/copy/);
  assert.ok(Math.abs(result.loss-(1-.95*.95*.99)*100)<1e-8);
});

test('passive plate and tweaker commands round-trip with signed displacement and size modifiers',()=>{
  for(const raw of ['laha','laqu','nd','+laha','f-laqu','tp30d0.5','tp-30d-0.5','f+tp0d0']){
    const a=Editor.parse(raw),b=Editor.parse(Editor.serialize(a));assert.equal(a.kind,b.kind);assert.equal(a.size,b.size);
    if(a.kind==='tp'){assert.equal(a.angle,b.angle);assert.equal(a.displacement,b.displacement);}
  }
});

test('starter identity is explicit and a duplicated p100 is an ordinary step',()=>{
  const {row,config}=fixture('p100');assert.equal(Editor.isStarter(row,Editor.ensure(row)[0]),false);
  Editor.markStarter(row);Editor.operate(config,row,0,'duplicate');
  const steps=Editor.ensure(row);assert.equal(Editor.isStarter(row,steps[0]),true);assert.equal(Editor.isStarter(row,steps[1]),false);
  Editor.operate(config,row,0,'replace','l50');assert.equal(row.commands,'l50 p100');assert.equal(row.starter_step_id,undefined);
});
test('editing or replacing an automatic p100 consumes its starter identity',()=>{
  for(const method of ['text','same-text','inspector','replace']){
    const {row,config}=fixture('p100');Editor.markStarter(row);
    if(method==='text'){Editor.reconcile(config,row,'p50');Editor.reconcile(config,row,'p100');}
    else if(method==='same-text')Editor.reconcile(config,row,'p100');
    else if(method==='inspector'){Editor.update(config,row,0,{...Editor.ensure(row)[0],length:50});Editor.update(config,row,0,{...Editor.ensure(row)[0],length:100});}
    else Editor.operate(config,row,0,'replace','p100');
    assert.equal(Editor.isStarter(row,Editor.ensure(row)[0]),false,method);
  }
});
test('adding or moving steps retains the original starter identity until it is removed',()=>{
  const {row,config}=fixture('p100');Editor.markStarter(row);const starter=row.starter_step_id;
  Editor.operate(config,row,0,'insert','p100');Editor.operate(config,row,1,'up');
  assert.equal(row.starter_step_id,starter);assert.equal(Editor.isStarter(row,Editor.ensure(row)[0]),true);
  Editor.operate(config,row,0,'remove');assert.equal(row.starter_step_id,undefined);
});
