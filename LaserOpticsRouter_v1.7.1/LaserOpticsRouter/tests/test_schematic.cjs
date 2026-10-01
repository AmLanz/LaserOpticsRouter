'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const S=require('../schematic.js'),E=require('../editor.js');
const scene={lines:[{start:[0,0,0],end:[100,0,0],event_ids:['a:p'],color:'red'},
  {start:[100,0,0],end:[100,80,0],event_ids:['b:p'],color:'blue'}],optics:[]};
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);
test('zoom anchors the exact world point under the pointer',()=>{
  const v=new S.View().fit(scene),anchor=[201,110],before=v.at(anchor);
  v.zoom(3.7,anchor);v.at(anchor).forEach((n,i)=>close(n,before[i]));
});
test('pan moves by screen distance while keeping the scale unchanged',()=>{
  const v=new S.View().fit(scene),before=v.project([0,0,0]),scale=v.scale;
  v.pan(40,-20);const after=v.project([0,0,0]);close(after[0]-before[0],40);close(after[1]-before[1],-20);close(v.scale,scale);
});
test('fit contains all projected points and handles zero span',()=>{
  for(const projection of ['XY','XZ','YZ']){
    const v=new S.View().fit(scene,projection);
    for(const p of scene.lines.flatMap(l=>[l.start,l.end])){const q=v.project(p);assert.ok(q[0]>=40&&q[0]<=v.width-40);assert.ok(q[1]>=40&&q[1]<=v.height-40);}
  }
  const v=new S.View().fit({lines:[],optics:[]});assert.ok(Number.isFinite(v.scale));
});
test('mirror and plate planes follow the actual reflection angle',()=>{
  for(const degrees of [30,90,-30,-90]){
    const r=degrees*Math.PI/180,optic={normal:[Math.cos(r)-1,Math.sin(r),0]};
    let a=S.surfaceAngle(optic,[0,1]);while(a>90)a-=180;while(a<-90)a+=180;
    close(a,-degrees/2);
  }
});
test('cube diagonal follows the selected reflected side',()=>{
  const forward=S.symbol({kind:'bsc',normal:[-1,1,0],input_direction:[1,0,0]},[0,1]);
  const reverse=S.symbol({kind:'bsc',normal:[-1,-1,0],input_direction:[1,0,0]},[0,1]);
  assert.match(forward,/<rect/);assert.match(forward,/M-13 13 L13 -13/);assert.match(reverse,/M13 13 L-13 -13/);
});
test('generic disc cube and ball use distinct requested schematic shapes',()=>{
  const o={kind:'generic',input_direction:[1,0,0]};
  assert.match(S.symbol({...o,shape:'disc'},[0,1]),/rotate\(-?90\)/);
  assert.match(S.symbol({...o,shape:'cube'},[0,1]),/<rect/);
  assert.match(S.symbol({...o,shape:'ball'},[0,1]),/<circle/);
});
test('lenses show signed curvature and prism polarization reminders can be hidden',()=>{
  const lens={kind:'lens',input_direction:[1,0,0]};
  assert.notEqual(S.symbol({...lens,focal_mm:50},[0,1]),S.symbol({...lens,focal_mm:-50},[0,1]));
  for(const kind of ['wp','rp','bd'])assert.ok(S.symbol({kind},[0,1],true).length>S.symbol({kind},[0,1],false).length);
});
test('highlights use exact event identities and occurrence identity',()=>{
  const data={lines:[...scene.lines,{...scene.lines[0],run_token:'other'}],optics:[]},v=new S.View().fit(data);
  const svg=S.render(data,v,{layers:[{run_token:'draft',event_ids:['a:p'],color:'#258252'}]});
  assert.equal((svg.match(/class="selected-path"/g)||[]).length,1);
  assert.match(svg,/class="beam-center"[^>]*stroke="#d63b4e"/);
});
test('shared segments display both selected contribution colors',()=>{
  const svg=S.render(scene,new S.View().fit(scene),{layers:[{event_ids:['a:p'],color:'#258252'},{event_ids:['a:p'],color:'#8959bd'}]});
  assert.equal((svg.match(/class="selected-path"/g)||[]).length,2);
  assert.match(svg,/#258252/);assert.match(svg,/#8959bd/);
});
test('schematic escapes user labels and invalid colors do not become markup',()=>{
  const data={lines:scene.lines,optics:[{kind:'generic',shape:'ball',position:[10,0,0],id:'a',token:'g',label:'<script>oops</script>'}]};
  const svg=S.render(data,new S.View().fit(data),{layers:[{event_ids:['a:p'],color:'" onload="bad'}]});
  assert.doesNotMatch(svg,/<script>|onload=/);assert.match(svg,/&lt;script&gt;/);assert.doesNotMatch(svg,/NaN|Infinity/);
});
test('scene updates retain zoom and pan until Fit or a projection change',()=>{
  const host={innerHTML:''},c=new S.Controller(host);c.update(scene,'XY');c.zoom(2);c.view.pan(35,28);
  const before=[c.view.scale,c.view.cx,c.view.cy];c.update(scene,'XY');assert.deepEqual([c.view.scale,c.view.cx,c.view.cy],before);
  c.update(scene,'XZ');assert.notDeepEqual([c.view.scale,c.view.cx,c.view.cy],before);
});
test('pointer capture distinguishes selecting a symbol from dragging over one',()=>{
  const events={},picked=[],host={innerHTML:'',addEventListener:(name,fn)=>events[name]=fn,setPointerCapture(){},querySelector:()=>({getBoundingClientRect:()=>({left:0,top:0,width:900,height:320})})};
  const c=new S.Controller(host,id=>picked.push(id));c.update(scene,'XY');
  const event=(type,x,y)=>({type,button:0,pointerId:1,clientX:x,clientY:y,target:{closest:()=>({dataset:{mapOptic:'optic'}})}});
  events.pointerdown(event('pointerdown',100,100));events.pointerup(event('pointerup',100,100));assert.deepEqual(picked,['optic']);
  events.pointerdown(event('pointerdown',100,100));events.pointermove(event('pointermove',150,120));events.pointerup(event('pointerup',150,120));assert.deepEqual(picked,['optic']);
});
test('repeated setup values replace unused presets without changing the setup',()=>{
  const config={rows:[{commands:'p250 p100 p250 l75 l75 r90'}]},before=JSON.stringify(config);
  assert.deepEqual(E.presets(config,'propagate',['p10','p50','p100']).map(p=>p.raw),['p250','p10','p50']);
  assert.equal(E.presets(config,'lens',['l-100','l-50','l50','l100'])[0].raw,'l75');
  assert.equal(JSON.stringify(config),before);
});
test('combining displacers and OAP orientation variants keep separate useful presets',()=>{
  const config={rows:[{commands:'_bd4v _bd4v bd4h bd4h _r90f75 _r90f75'}]};
  assert.equal(E.presets(config,'bd-combine',['_bd4h','_bd4v'])[0].raw,'_bd4v');
  assert.equal(E.presets(config,'bd',['bd4h','bd2.7h'])[0].raw,'bd4h');
  assert.equal(E.presets(config,'oap',['r90f50','_r90f50'])[0].raw,'_r90f75');
});

test('saved route hit targets support click and keyboard but do not select during pan',()=>{
  const events={},picked=[],host={innerHTML:'',addEventListener:(name,fn)=>(events[name]??=[]).push(fn),setPointerCapture(){},querySelector:()=>({getBoundingClientRect:()=>({left:0,top:0,width:900,height:320})})};
  const c=new S.Controller(host,()=>assert.fail('Saved route must not inspect a draft optic'),()=>false,id=>picked.push(id));c.update(scene,'XY');
  const target={closest:selector=>selector==='[data-map-run]'?{dataset:{mapRun:'run-A'}}:null};
  const send=(type,x=100)=>events[type].forEach(fn=>fn({type,target,button:0,pointerId:1,clientX:x,clientY:100,key:'Enter',preventDefault(){},stopPropagation(){}}));
  send('pointerdown');send('pointerup');send('keydown');assert.deepEqual(picked,['run-A','run-A']);
  send('pointerdown');send('pointermove',150);send('pointerup',150);assert.equal(picked.length,2);
});
