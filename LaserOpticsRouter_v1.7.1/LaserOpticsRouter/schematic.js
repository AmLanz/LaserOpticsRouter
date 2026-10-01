/* Shared, offline optical schematics. Coordinates are mm; symbols are schematic. */
'use strict';
const RouterSchematic=(()=>{
  const colors={red:'#d63b4e',blue:'#2878ce',green:'#258252',yellow:'#e2b426',orange:'#ef6b26',purple:'#8959bd',white:'#ffffff'};
  const axesFor=p=>({XY:[0,1],XZ:[0,2],YZ:[1,2]}[p]||[0,1]);
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n=x=>Number(x.toFixed(4));
  const xy=(p,axes)=>[p[axes[0]],-p[axes[1]]];
  const validPoint=p=>Array.isArray(p)&&p.length===3&&p.every(Number.isFinite);
  const angle=v=>Math.atan2(v[1],v[0])*180/Math.PI;
  const fmtSpectral=l=>`${Number(l.wavelength_nm).toPrecision(5)} nm · relative weight ${Number(l.spectral_weight??1).toPrecision(3)}`;
  const color=value=>colors[value]||(/^#[0-9a-f]{6}$/i.test(value||'')?value:colors.red);
  function labelPosition(point,text,width,height,occupied){
    const [x,y]=point,size=6*text.length,sides=x+16+size>width-5?[-1,1]:[1,-1];
    for(const side of sides)for(const offset of [-19,24,-36,41,-53,58]){
      const anchor=x+side*16,baseline=y+offset,box=[side<0?anchor-size:anchor,baseline-11,side<0?anchor:anchor+size,baseline+2];
      if(box[0]<5||box[2]>width-5||box[1]<5||box[3]>height-30)continue;
      if(occupied.some(b=>box[0]<b[2]+3&&box[2]>b[0]-3&&box[1]<b[3]+3&&box[3]>b[1]-3))continue;
      occupied.push(box);return [side*16,offset,side<0];
    }
    return [x>width-95?-16:16,-19,x>width-95];
  }
  function surfaceAngle(optic,axes){
    const normal=xy(optic.normal||optic.input_direction||[1,0,0],axes);
    return angle([-normal[1],normal[0]]);
  }
  function symbol(o,axes,polarization=true){
    const a=angle(xy(o.input_direction||[1,0,0],axes)),t=surfaceAngle(o,axes);
    const rotate=(d,body)=>`<g transform="rotate(${n(d)})">${body}</g>`;
    const base='stroke="#344e61" stroke-width="1.7" stroke-linejoin="round"';
    const line=(d,w=2)=>rotate(d,`<path d="M-15 0 H15" fill="none" stroke="#344e61" stroke-width="${w}"/>`);
    if(o.kind==='lens')return rotate(a,`<path d="${o.focal_mm<0?'M-6 -15 Q2 0 -6 15 L6 15 Q-2 0 6 -15 Z':'M0 -15 Q13 0 0 15 Q-13 0 0 -15 Z'}" fill="#d8edf2" ${base}/>`);
    if(o.kind==='cyl')return rotate(a,`<rect x="-6" y="-15" width="12" height="30" rx="5" fill="#d8edf2" ${base}/><path d="M-3 -10 V10 M3 -10 V10" stroke="#5b92a2"/><text x="8" y="-7" font-size="9">${esc(o.axis||'h')}</text>`);
    if(o.kind==='grating')return rotate(t,`<rect x="-16" y="-3" width="32" height="6" fill="#d8bc82" ${base}/><path d="M-12 -3 V3 M-8 -3 V3 M-4 -3 V3 M0 -3 V3 M4 -3 V3 M8 -3 V3 M12 -3 V3" stroke="#725829"/>`);
    if(o.kind==='reset')return rotate(a,`<rect x="-3" y="-15" width="6" height="30" fill="#c0e2d4" ${base}/><path d="M-8 -9 L-3 -4 L-8 1 M3 -1 L8 4 L3 9" fill="none" stroke="#2a6954"/>`);
    if(o.kind==='mirror')return rotate(t,`<rect x="-15" y="-2.5" width="30" height="5" rx=".5" fill="#8c9ba7" ${base}/><path d="M-15 -3 H15" stroke="#162f43" stroke-width="1.7"/>`);
    // Local -Y faces the optical normal. The concave face meets the ray at (0,0).
    if(o.kind==='oap')return rotate(t,`<path d="M-15 -5 Q0 5 15 -5 L15 -2 Q0 8 -15 -2 Z" fill="#d7b373" ${base}/>`);
    if(o.kind==='bs')return line(t,1.8);
    if(o.kind==='tp')return rotate(t,`<rect x="-15" y="-2" width="30" height="4" fill="#d8e8ef" ${base}/>`);
    if(['laha','laqu','nd'].includes(o.kind))return rotate(a,`<rect x="${o.kind==='nd'?-3:-1.5}" y="-14" width="${o.kind==='nd'?6:3}" height="28" rx=".6" fill="${o.kind==='nd'?'#8997a5':'#c6dfe4'}" ${base}/>`);
    if(o.kind==='bsc'){
      const r=(t-a)*Math.PI/180,c=Math.cos(r),s=Math.sin(r),m=13/Math.max(Math.abs(c),Math.abs(s));
      return rotate(a,`<rect x="-13" y="-13" width="26" height="26" fill="#e0edfa" ${base}/><path d="M${n(-c*m)} ${n(-s*m)} L${n(c*m)} ${n(s*m)}" stroke="#326d9f" stroke-width="1.8"/>`);
    }
    if(['wp','rp','bd'].includes(o.kind)){
      const transverse=xy(o.frame?.[0]||[0,1,0],axes),forward=xy(o.input_direction||[1,0,0],axes);
      const side=Math.sign(forward[0]*transverse[1]-forward[1]*transverse[0])||-1;
      const shape=o.kind==='bd'?'<path d="M-18 -12 H10 L18 12 H-10 Z"/>':'<rect x="-17" y="-12" width="34" height="24"/>';
      const seam=o.kind==='bd'?'<path d="M-12 -4 H1 L9 4 H14" stroke="#567d86"/>':'<path d="M-17 12 L17 -12" stroke="#567d86"/>';
      const marks=polarization?(o.kind==='wp'?'<circle cx="-7" cy="-5" r="3"/><circle cx="-7" cy="-5" r=".7" fill="#344e61"/><path d="M7 0 V9 M4 3 L7 0 L10 3 M4 6 L7 9 L10 6"/>':o.kind==='rp'?'<circle cx="-8" cy="-4" r="3"/><circle cx="-8" cy="-4" r=".7" fill="#344e61"/><path d="M8 0 V9 M5 3 L8 0 L11 3 M5 6 L8 9 L11 6"/>':'<circle cx="-7" cy="4" r="2.7"/><circle cx="-7" cy="4" r=".7" fill="#344e61"/><path d="M7 -9 V-1 M4 -6 L7 -9 L10 -6 M4 -4 L7 -1 L10 -4"/>'):'';
      return rotate(a,`<g transform="scale(1 ${side})" ${base}><g fill="#e1eee8">${shape}</g><g fill="none">${seam}${marks}</g></g>`);
    }
    if(o.kind==='generic'){
      const shape=o.shape||o.settings?.shape||'disc';
      if(shape==='ball')return `<circle r="12" fill="#eee7f4" ${base}/>`;
      if(shape==='cube')return rotate(a,`<rect x="-12" y="-12" width="24" height="24" fill="#eee7f4" ${base}/>`);
      return line(a+90,2.4);
    }
    if(o.kind==='pol')return rotate(a,`<rect x="-4" y="-14" width="8" height="28" fill="#e3e8ec" ${base}/><path d="M-4 -8 L4 -12 M-4 0 L4 -4 M-4 8 L4 4" stroke="#708493"/>`);
    return `<path d="M0 -10 L10 0 L0 10 L-10 0 Z" fill="white" ${base}/>`;
  }
  class View {
    constructor(width=900,height=320){this.width=width;this.height=height;this.projection='XY';this.scale=1;this.cx=0;this.cy=0;this.baseScale=1;this.fitted=false;}
    fit(scene,projection=this.projection){
      this.projection=projection;const axes=axesFor(projection),pts=[...(scene.lines||[]).flatMap(l=>[l.start,l.end]),...(scene.optics||[]).map(o=>o.position)];
      const usable=pts.filter(validPoint),ps=usable.length?usable.map(p=>xy(p,axes)):[[0,0]];
      let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
      for(const p of ps){x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1]);}
      this.cx=(x0+x1)/2;this.cy=(y0+y1)/2;
      this.scale=Math.min((this.width-100)/Math.max(x1-x0,30),(this.height-100)/Math.max(y1-y0,30));
      this.baseScale=this.scale;this.fitted=true;return this;
    }
    project(p){const q=xy(p,axesFor(this.projection));return [this.width/2+(q[0]-this.cx)*this.scale,this.height/2+(q[1]-this.cy)*this.scale];}
    at(p){return [this.cx+(p[0]-this.width/2)/this.scale,this.cy+(p[1]-this.height/2)/this.scale];}
    zoom(factor,p=[this.width/2,this.height/2]){
      const before=this.at(p);this.scale=Math.max(this.baseScale/1000,Math.min(this.baseScale*1000,this.scale*factor));
      const after=this.at(p);this.cx+=before[0]-after[0];this.cy+=before[1]-after[1];return this;
    }
    pan(dx,dy){this.cx-=dx/this.scale;this.cy-=dy/this.scale;return this;}
  }
  const members=(entry,events)=>entry.events.some(id=>events.has(id));
  function render(scene,view,options={}){
    const axes=axesFor(view.projection),width=view.width,height=view.height;
    const owners=(options.layers||[]).map(l=>({...l,set:new Set(l.event_ids||[])}));
    const matching=item=>owners.filter(l=>(!l.run_token||l.run_token===(item.run_token||'draft'))&&members({events:item.event_ids||[]},l.set));
    const highlighted=owners.length>0;
    const nice=raw=>{const power=10**Math.floor(Math.log10(raw));return ([1,2,5,10].find(v=>v*power>=raw)||10)*power;};
    const grid=nice(50/view.scale),gx=view.project([0,0,0]),step=grid*view.scale;
    let html=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Optical schematic in ${view.projection}; scroll to zoom, drag to pan" class="optical-map"><rect width="${width}" height="${height}" fill="#fbfcfd"/>`;
    for(let x=((gx[0]%step)+step)%step;x<width;x+=step)html+=`<path d="M${n(x)} 0 V${height}" stroke="#e8edf1" stroke-width="1"/>`;
    for(let y=((gx[1]%step)+step)%step;y<height;y+=step)html+=`<path d="M0 ${n(y)} H${width}" stroke="#e8edf1" stroke-width="1"/>`;
    for(const line of scene.lines||[]){
      if(!validPoint(line.start)||!validPoint(line.end))continue;
      const a=view.project(line.start),b=view.project(line.end),d=`M${a.map(n)} L${b.map(n)}`,owned=matching(line),paint=color(line.color||'red');
      const opacity=(highlighted&&!owned.length ? .24 : 1)*(line.spectral?Math.max(.14,Math.sqrt(line.spectral_weight??1)):1);
      html+=`<g opacity="${opacity}"><title>${line.spectral?esc(fmtSpectral(line)):"Beam path"}</title><path d="${d}" fill="none" stroke="${paint==='#ffffff'?'#53677a':'#fff'}" stroke-width="4.5"/><path d="${d}" fill="none" stroke="${paint}" stroke-width="2.2" ${line.secondary?'stroke-dasharray="6 3"':''}/>`;
      const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);
      if(len>32){const f=.68,x=a[0]+dx*f,y=a[1]+dy*f;html+=`<path d="M-5 -3 L2 0 L-5 3" transform="translate(${n(x)} ${n(y)}) rotate(${n(angle([dx,dy]))})" fill="none" stroke="${paint==='#ffffff'?'#53677a':paint}" stroke-width="1.8"/>`;}
      html+='</g>';
      for(let i=0;i<owned.length;i++){
        const offset=(i-(owned.length-1)/2)*4,ox=len?-dy/len*offset:0,oy=len?dx/len*offset:0;
        html+=`<path class="selected-path" d="M${n(a[0]+ox)} ${n(a[1]+oy)} L${n(b[0]+ox)} ${n(b[1]+oy)}" fill="none" stroke="${color(owned[i].color||'#164d70')}" stroke-width="${owned.length>1?2.5:4}" stroke-linecap="round" opacity=".8"><title>${esc(owned[i].name||'Included path')}</title></path>`;
      }
      if(owned.length)html+=`<path class="beam-center" d="${d}" fill="none" stroke="${paint}" stroke-width="1.2" ${line.secondary?'stroke-dasharray="6 3"':''}/>`;
      if(options.selectRuns&&line.run_token)html+=`<path class="map-run-hit" data-map-run="${esc(line.run_token)}" d="${d}" fill="none" stroke="#ffffff" stroke-opacity="0" stroke-width="14" pointer-events="stroke" tabindex="0" role="button" aria-label="Highlight ${esc(options.runNames?.[line.run_token]||'saved route')}"/>`;
    }
    const occupied=[];
    (scene.optics||[]).forEach((o,i)=>{
      if(!validPoint(o.position))return;
      const p=view.project(o.position);if(p[0]<-50||p[0]>width+50||p[1]<-50||p[1]>height+50)return;
      const owned=matching(o),selected=o.id===options.selectedOptic&&(!o.run_token||o.run_token==='draft');
      const inspect=options.interactive!==false&&(!o.run_token||o.run_token==='draft');
      html+=`<g transform="translate(${p.map(n)})" class="map-optic" ${options.selectRuns&&o.run_token?`data-map-run="${esc(o.run_token)}" tabindex="0" role="button" aria-label="Highlight ${esc(options.runNames?.[o.run_token]||'saved route')}"`:inspect?`data-map-optic="${esc(o.id)}" tabindex="0" role="button" aria-label="Inspect ${esc(o.label)}"`:''} opacity="${highlighted&&!owned.length&&!selected ? .38 : 1}">`;
      if(selected||owned.length)html+=`<rect x="-22" y="-22" width="44" height="44" rx="7" fill="${color(owned[0]?.color||'#164d70')}" fill-opacity=".09" stroke="${color(owned[0]?.color||'#164d70')}" stroke-width="${selected?2:1}" ${selected?'':'stroke-dasharray="3 3"'}/>`;
      const text=`${i+1} · ${o.token}`,[labelX,labelY,left]=labelPosition(p,text,width,height,occupied);
      html+=symbol(o,axes,options.polarization!==false)+`<rect x="-21" y="-21" width="42" height="42" fill="#ffffff" fill-opacity="0" pointer-events="all"/><text x="${labelX}" y="${labelY}" text-anchor="${left?'end':'start'}" font-size="10" font-family="sans-serif" fill="#23435a" paint-order="stroke" stroke="#fbfcfd" stroke-width="3">${esc(text)}</text><title>${esc(o.label)}${['wp','rp','bd'].includes(o.kind)?' — polarization marks are schematic references only':''}</title></g>`;
    });
    html+=`<rect x="0" y="${height-25}" width="${width}" height="25" fill="#fbfcfd" fill-opacity=".94"/><text x="12" y="${height-9}" font-size="11" font-family="sans-serif" fill="#516676">${view.projection} · grid ${Number(grid.toPrecision(4))} mm · ${Math.round(view.scale/view.baseScale*100)}% · symbols not to scale</text></svg>`;
    return html;
  }
  class Controller {
    constructor(host,onSelect=()=>{},disabled=()=>false,onRunSelect=()=>{}){
      this.host=host;this.view=new View();this.scene={lines:[],optics:[]};this.options={};this.disabled=disabled;this.onSelect=onSelect;this.onRunSelect=onRunSelect;this.pointers=new Map();this.suppressUntil=0;
      if(!host.addEventListener)return;
      host.addEventListener('wheel',e=>{if(this.disabled())return;e.preventDefault();this.view.zoom(Math.exp(-Math.max(-300,Math.min(300,e.deltaY))*.003),this.point(e));this.draw();},{passive:false});
      host.addEventListener('pointerdown',e=>{if(this.disabled()||e.button>0)return;this.pointers.set(e.pointerId,this.point(e));this.start=this.point(e);this.downOptic=e.target.closest?.('[data-map-optic]')?.dataset.mapOptic;this.downRun=e.target.closest?.('[data-map-run]')?.dataset.mapRun;this.dragged=this.pointers.size>1;host.setPointerCapture?.(e.pointerId);});
      host.addEventListener('pointermove',e=>{
        if(!this.pointers.has(e.pointerId)||this.disabled())return;
        const before=[...this.pointers.values()],old=this.pointers.get(e.pointerId),now=this.point(e);
        this.pointers.set(e.pointerId,now);
        if(before.length===1)this.view.pan(now[0]-old[0],now[1]-old[1]);
        else if(before.length===2){const after=[...this.pointers.values()],dist=p=>Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]),mid=p=>[(p[0][0]+p[1][0])/2,(p[0][1]+p[1][1])/2];const a=mid(before),b=mid(after);if(dist(before)>1)this.view.zoom(dist(after)/dist(before),a);this.view.pan(b[0]-a[0],b[1]-a[1]);}
        if(this.pointers.size>1||Math.hypot(now[0]-this.start[0],now[1]-this.start[1])>3){this.dragged=true;this.suppressUntil=Date.now()+180;}
        this.draw();
      });
      const end=e=>{if(this.dragged)this.suppressUntil=Date.now()+180;if(e.type==='pointerup'&&this.pointers.size===1&&!this.dragged&&!this.disabled()){if(this.downRun)this.onRunSelect(this.downRun);else if(this.downOptic)this.onSelect(this.downOptic);if(this.downRun||this.downOptic)this.suppressUntil=Date.now()+180;}this.pointers.delete(e.pointerId);};
      host.addEventListener('pointerup',end);host.addEventListener('pointercancel',end);host.addEventListener('lostpointercapture',end);
      host.addEventListener('click',e=>{if(Date.now()<this.suppressUntil){e.preventDefault();e.stopPropagation();}} ,true);
      host.addEventListener('keydown',e=>{const run=e.target.closest?.('[data-map-run]')?.dataset.mapRun;if(!this.disabled()&&run&&['Enter',' '].includes(e.key)){e.preventDefault();e.stopPropagation();this.onRunSelect(run);}});
      host.addEventListener('keydown',e=>{if(this.disabled()||e.target!==host)return;const shift=35;if(['+','=','-','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','0'].includes(e.key)){e.preventDefault();if(e.key==='0')this.fit();else if(['+','=','-'].includes(e.key))this.zoom(e.key==='-'?1/1.3:1.3);else {this.view.pan(e.key==='ArrowLeft'?shift:e.key==='ArrowRight'?-shift:0,e.key==='ArrowUp'?shift:e.key==='ArrowDown'?-shift:0);this.draw();}}});
    }
    point(e){const rect=this.host.querySelector('svg').getBoundingClientRect(),s=Math.min(rect.width/this.view.width,rect.height/this.view.height);return [(e.clientX-rect.left-(rect.width-this.view.width*s)/2)/s,(e.clientY-rect.top-(rect.height-this.view.height*s)/2)/s];}
    update(scene,projection,options={}){const reset=projection!==this.view.projection||!this.view.fitted;this.scene=scene;this.options=options;if(reset)this.view.fit(scene,projection);this.draw();}
    draw(){this.host.innerHTML=render(this.scene,this.view,this.options);}
    fit(){this.view.fit(this.scene);this.draw();}
    zoom(factor){this.view.zoom(factor);this.draw();}
    reset(){this.view.fitted=false;}
  }
  return {colors,color,axesFor,surfaceAngle,symbol,View,render,Controller};
})();
if(typeof module!=='undefined')module.exports=RouterSchematic;
