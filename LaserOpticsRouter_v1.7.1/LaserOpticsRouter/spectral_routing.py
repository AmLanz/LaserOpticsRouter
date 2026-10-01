"""Wavelength rays through the fixed surfaces of a planned central-ray route.

Central planning remains unchanged. Distances specify central-ray stations;
side rays intersect those stations and the actual optical interaction planes.
Reflection/grating directions are exact; lens/OAP power is ideal paraxial.
"""
import copy
import math
from dataclasses import asdict, replace
try:
    from . import core, beam_matrix
except ImportError:
    import core, beam_matrix


def rotation_between(a, b):
    c=max(-1,min(1,core.dot(a,b)))
    if c < -1+1e-10:
        axis=core.frame(a)[0]
        return tuple(core.sub(core.mul(axis,2*core.dot(axis,v)),v) for v in ((1,0,0),(0,1,0),(0,0,1)))
    k=core.cross(a,b)
    return tuple(core.add(core.add(v,core.cross(k,v)),core.mul(core.cross(k,core.cross(k,v)),1/(1+c)))
                 for v in ((1,0,0),(0,1,0),(0,0,1)))


def turned(ray, direction, normal=None):
    az,el=core.angles(direction,ray.azimuth)
    return core.transport_beam(ray,replace(ray,azimuth=az,elevation=el),normal=normal)


def reflected(ray, normal):
    direction=core.sub(ray.d,core.mul(normal,2*core.dot(ray.d,normal)))
    out=turned(ray,direction,normal)
    return replace(out,boundary_normal=normal,boundary_kind='mirror',
                   boundary_bend=math.degrees(math.acos(max(-1,min(1,core.dot(ray.d,out.d))))))


def grating(ray, optic):
    """Conserve groove-parallel momentum and add mλG along a fixed tangent."""
    n=tuple(optic['normal']);t=tuple(optic['frame'][0]);g=tuple(optic['frame'][1])
    tangential=core.dot(ray.d,t)+optic['order']*ray.wavelength_nm*optic['grooves_per_mm']*1e-6
    groove=core.dot(ray.d,g)
    disc=1-tangential*tangential-groove*groove
    if disc <= 1e-10:
        raise core.LayoutError(f"Grating order {optic['order']} at {ray.wavelength_nm:g} nm is evanescent or grazing. Reduce bandwidth or change the grating.")
    incoming_normal=core.dot(ray.d,n)
    if abs(incoming_normal)<1e-10: raise core.LayoutError('A spectral ray is tangent to the grating.')
    outgoing_normal=-math.copysign(math.sqrt(disc),incoming_normal)
    d=core.add(core.add(core.mul(t,tangential),core.mul(g,groove)),core.mul(n,outgoing_normal))
    az,el=core.angles(d,ray.azimuth)
    out=replace(ray,azimuth=az,elevation=el,boundary_normal=n,boundary_kind='grating',
                boundary_bend=math.degrees(math.acos(max(-1,min(1,core.dot(ray.d,d))))))
    incoming,outgoing=core.beam_frame(ray),core.beam_frame(out)
    hit=[core.sub(v,core.mul(ray.d,core.dot(n,v)/incoming_normal)) for v in incoming[:2]]
    position=[[core.dot(outgoing[i],hit[j]) for j in range(2)] for i in range(2)]
    derivatives=[]
    for v in incoming[:2]:
        dt,dg=core.dot(v,t),core.dot(v,g)
        dn=-(tangential*dt+groove*dg)/outgoing_normal
        derivatives.append(core.add(core.add(core.mul(t,dt),core.mul(g,dg)),core.mul(n,dn)))
    slope=[[core.dot(outgoing[i],derivatives[j]) for j in range(2)] for i in range(2)]
    out.moments=beam_matrix.axes_transform(beam_matrix.seed(ray),position,slope)
    beta=math.degrees(math.atan2(tangential,abs(outgoing_normal)))
    return out,beta


def focused(ray, optic, center_before, center_after):
    """Off-axis chief-ray power around the central optical axis, plus envelope power."""
    axis=tuple(center_after.d)
    h,v=core.beam_frame(center_after)[:2]
    height=core.sub(ray.position,tuple(optic['position']))
    longitudinal=core.dot(ray.d,axis)
    if longitudinal<=1e-8: raise core.LayoutError('Spectral ray approaches the focusing optic from an incompatible direction.')
    powers=(h,v) if optic['kind']!='cyl' else (core.beam_frame(center_before)[0 if optic['axis']=='h' else 1],)
    d=core.mul(ray.d,1/longitudinal)
    for powered in powers:
        transverse=core.sub(powered,core.mul(axis,core.dot(powered,axis)))
        if core.norm(transverse)>1e-10:
            transverse=core.unit(transverse)
            d=core.sub(d,core.mul(transverse,core.dot(height,transverse)/optic['focal_mm']))
    out=turned(ray,core.unit(d))
    s=beam_matrix.seed(out);basis=core.beam_frame(out)
    matrix=beam_matrix.identity()
    for powered in powers:
        for i in range(2):
            for j in range(2):
                matrix[i+2][j]-=core.dot(basis[i],powered)*core.dot(basis[j],powered)/optic['focal_mm']
    return replace(out,moments=beam_matrix.transform(s,matrix))


def interaction(ray, optic, before, after, token, secondary=False):
    kind=optic['kind']
    if kind=='grating': return grating(ray,optic)[0]
    if kind in ('mirror','oap','bs','bsc'):
        out=reflected(ray,tuple(optic['normal']))
        if kind=='oap': out=focused(out,optic,before,after)
        return out
    if kind in ('lens','cyl'): return focused(ray,optic,before,after)
    if kind=='reset': return core.reset_beam(ray,optic['reset_diameter_mm'],optic['reset_focus_mm'])
    if kind in core.PRISMS:
        if kind=='bd':
            offset=core.mul(core.prism_axis(before,token),token['amount']*(1 if secondary else 0))
            return core.displaced(ray,offset)
        nominal=core.prism_output(before,token,secondary)
        rotation=rotation_between(before.d,nominal.d)
        return core.moved_state(ray,core.sub(ray.position,core.world(rotation,ray.position)),rotation)
    if kind=='tp': return core.displaced(ray,tuple(optic['transmission_offset']))
    if kind=='generic' and optic['settings'].get('beam_color','inherit')!='inherit':
        return replace(ray,color=optic['settings']['beam_color'])
    return ray


def plane_distance(ray, point, normal):
    denom=core.dot(ray.d,normal)
    if abs(denom)<1e-10: raise core.LayoutError(f'Spectral ray at {ray.wavelength_nm:g} nm cannot reach the next optical plane.')
    return core.dot(core.sub(point,ray.position),normal)/denom


def segment(ray, distance, transition, lane, suffix=''):
    event=transition['event']+':p:'+lane['id']+suffix
    result=dict(name=f"{ray.wavelength_nm:g} nm · {transition['token']['raw']}",state=replace(ray),
                length=distance,trim_start=None,trim_end=None,row=transition['row'],secondary=True,spectral=True,
                event_ids=[event],spectral_lane=lane['id']+suffix)
    return result,core.budget_event(ray.propagated(distance),event,geometric_mm=distance)


def advance(lane, point, normal, transition, segments):
    ray=lane['state'];distance=plane_distance(ray,point,normal)
    if distance < -1e-7:
        raise core.LayoutError(f'Spectral ray at {ray.wavelength_nm:g} nm would propagate backwards. Review the distances and optical planes.')
    if distance>1e-9:
        item,out=segment(ray,distance,transition,lane)
        segments.append(item);lane['last_segment']=item;lane['state']=out


def intersect(lane, optic, transition, segments):
    ray=lane['state'];distance=plane_distance(ray,tuple(optic['position']),tuple(optic['normal']))
    last=lane.get('last_segment')
    if abs(distance)<1e-9:return
    if last is not None:
        length=last['length']+distance
        if length < -1e-7:
            raise core.LayoutError(f'{ray.wavelength_nm:g} nm reaches the tilted optic before the last propagation station. Reduce the last distance or bandwidth.')
        last['length']=max(0,length)
        lane['state']=core.budget_event(last['state'].propagated(last['length']),last['event_ids'][0],geometric_mm=last['length'])
    elif distance>0:
        item,out=segment(ray,distance,transition,lane,':hit')
        segments.append(item);lane['last_segment']=item;lane['state']=out
    else:
        raise core.LayoutError(f'{ray.wavelength_nm:g} nm reaches the optic behind the saved spectral start. Add propagation before this optic or shorten the upstream route.')


def bundled(state, lanes):
    return replace(state,spectral_rays=[asdict(replace(lane['state'],spectral_rays=[])) for lane in lanes])


def write_bundle(endpoint, lanes):
    state=bundled(core.state_from_dict(endpoint['state']),lanes)
    endpoint.update(state=asdict(state),endpoint=core.encode_endpoint(state,endpoint['name']),stats=state.stats())


def endpoints(lanes, key, label, kind='spectral'):
    result=[]
    for lane in lanes:
        ray=replace(lane['state'],spectral_rays=[])
        name=f'{label} · {ray.wavelength_nm:g} nm · relative weight {ray.spectral_weight:.3g}'
        result.append(dict(id=key+':'+lane['id'],name=name,state=asdict(ray),endpoint=core.encode_endpoint(ray,name),
                           stats=ray.stats(),kind=kind,trace_start=lane['trace_start'],start_state=lane['start_state']))
    return result


def copied_lane(lane):
    return dict(id=lane['id'],state=copy.deepcopy(lane['state']),trace_start=lane['trace_start'],
                start_state=copy.deepcopy(lane['start_state']),companions=copy.deepcopy(lane.get('companions',[])),last_segment=None)


def attach(plan, trajectory):
    previous=[];config=plan['config'];segments=plan['segments'];all_endpoints=plan['endpoints']
    for ri,row in enumerate(plan['rows']):
        raw=config['rows'][ri];start=core.state_from_dict(row['start_state'])
        if raw.get('start_mode')=='previous':
            lanes=[copied_lane(lane) for lane in previous]
            for lane in lanes:
                lane.update(trace_start=len(lane['state'].trace),start_state=asdict(lane['state']))
                for child in lane.get('companions',[]):child['last_segment']=None
        else:
            lanes=[dict(id='S'+str(i),state=core.state_from_dict(ray),trace_start=len(ray.get('trace',[])),
                        start_state=copy.deepcopy(ray),companions=[],last_segment=None) for i,ray in enumerate(start.spectral_rays)]
        extra=[]
        for transition in (x for x in trajectory if x['row']==ri):
            before,after=transition['before'],transition['after'];token=transition['token'];optic=transition['optic']
            transition['event']=str(config.get('route_id','draft'))+':'+transition['id']
            try:
                if token['kind']=='propagate':
                    if token['length']<=0:continue
                    for lane in lanes:
                        advance(lane,after.position,before.d,transition,segments)
                        for child in lane.get('companions',[]):
                            nominal=next((x['state'] for x in transition['paired_after'] if x['id']==child['center_id']),None)
                            if nominal is not None:advance(child,nominal.position,nominal.d,transition,segments)
                    continue
                if optic['kind']=='grating' and not lanes:
                    for i,(wavelength,weight) in enumerate(core.spectral_samples(before)):
                        if abs(wavelength-before.wavelength_nm)<1e-9:continue
                        ray=replace(core.with_wavelength(before,wavelength),spectral_weight=weight,
                                    color='blue' if wavelength<before.wavelength_nm else 'green')
                        lanes.append(dict(id='S'+str(i),state=ray,trace_start=row['endpoint']['trace_start'],
                                          start_state=copy.deepcopy(row['start_state']),companions=[],last_segment=None))
                reflected_lanes=[];secondary_lanes=[]
                for lane in lanes:
                    intersect(lane,optic,transition,segments)
                    ray=lane['state'];event=transition['event']+':'+lane['id'];kind=optic['kind']
                    if kind in ('bs','bsc'):
                        reflected_ray=core.optic_budget(interaction(ray,optic,before,after,token),optic,event,'R')
                        reflected_lanes.append(dict(lane,state=reflected_ray,last_segment=None))
                        out=core.optic_budget(core.displaced(ray,tuple(optic['transmission_offset'])),optic,event,'T')
                    elif kind in core.PRISMS and not token['flip']:
                        child=core.optic_budget(interaction(ray,optic,before,after,token,True),optic,event,'R')
                        center_id=transition['id']+':B'
                        child_lane=dict(id=lane['id']+':B',center_id=center_id,state=child,combined=False,
                                        last_segment=None,trace_start=lane['trace_start'],start_state=lane['start_state'])
                        lane['companions'].append(child_lane);secondary_lanes.append(child_lane)
                        out=core.optic_budget(interaction(ray,optic,before,after,token),optic,event,'T')
                    else:
                        out=interaction(ray,optic,before,after,token)
                        combined_ids={x['id'] for x in transition['paired_after'] if x['combined'] and
                                      not any(y['id']==x['id'] and y['combined'] for y in transition['paired_before'])}
                        valid_combiner=kind!='bd' or not token['flip'] or bool(combined_ids)
                        if valid_combiner:out=core.optic_budget(out,optic,event)
                        if kind=='bd' and token['flip'] and combined_ids:
                            for child in lane.get('companions',[]):
                                if child['center_id'] not in combined_ids:continue
                                child['state']=core.optic_budget(replace(child['state'],position=out.position,
                                    azimuth=out.azimuth,elevation=out.elevation),optic,event+':B')
                                child['combined']=True
                    if kind not in core.PRISMS:
                        for child in lane.get('companions',[]):
                            if not child.get('combined'):continue
                            intersect(child,optic,transition,segments)
                            child_out=(core.displaced(child['state'],tuple(optic['transmission_offset'])) if kind in ('bs','bsc') else
                                       interaction(child['state'],optic,before,after,token))
                            child['state']=core.optic_budget(child_out,optic,event+':B','T' if kind in ('bs','bsc') else '')
                            child['last_segment']=None
                    # No ray-to-plane correction may be applied across a preceding optic.
                    lane['state']=core.state_from_dict(asdict(out));lane['last_segment']=None
                    if core.norm(core.sub(out.position,tuple(optic.get('physical_position',optic['position']))))+out.radius>optic.get('crystal_width_mm',optic['diameter_mm'])/2:
                        plan['warnings'].append(f'{optic["label"]}: a spectral ray/envelope extends outside the nominal aperture; rays are not clipped.')
                if optic['kind']=='grating':
                    samples=[dict(wavelength_nm=after.wavelength_nm,weight=after.spectral_weight,beta_deg=optic['beta_deg'],direction=list(after.d))]
                    samples.extend(dict(wavelength_nm=lane['state'].wavelength_nm,weight=lane['state'].spectral_weight,
                                        beta_deg=math.degrees(math.atan2(core.dot(lane['state'].d,optic['frame'][0]),abs(core.dot(lane['state'].d,optic['normal'])))),
                                        direction=list(lane['state'].d)) for lane in lanes)
                    optic['spectral_samples']=sorted(samples,key=lambda x:x['wavelength_nm'])
                if reflected_lanes:
                    port=next((p for p in row['ports'] if p['id']==transition['id']+':R'),None)
                    if port:write_bundle(port,reflected_lanes)
                    extra.extend(endpoints(reflected_lanes,transition['id']+':R',optic['label']+' · reflected','spectral_reflected'))
                if secondary_lanes:
                    main_port=next((p for p in row['ports'] if p['id']==transition['id']+':A'),None)
                    second_port=next((p for p in row['ports'] if p['id']==transition['id']+':B'),None)
                    if main_port:write_bundle(main_port,lanes)
                    if second_port:write_bundle(second_port,secondary_lanes)
                    extra.extend(endpoints(secondary_lanes,transition['id']+':B',optic['label']+' · secondary'))
            except core.LayoutError as exc:
                raise core.LayoutError(str(exc),ri,None,token['start'],token['end']) from exc
        write_bundle(row['endpoint'],lanes)
        extra.extend(endpoints(lanes,row['id']+':end',row['name']+' · spectral end'))
        for index,central in enumerate(e for e in row['ports'] if e['id'].startswith(row['id']+':end:B')):
            children=[lane['companions'][index] for lane in lanes if len(lane.get('companions',[]))>index]
            if children:
                write_bundle(central,children)
                extra.extend(endpoints(children,central['id'],row['name']+' · secondary spectral end'))
        row['ports'].extend(extra);all_endpoints.extend(extra)
        previous=lanes
    # Corrections to a tilted plane may reduce the last interval to zero.
    plan['segments']=[s for s in segments if s['length']>1e-9]
    if any(e['state'].get('spectral_rays') for e in all_endpoints):
        plan['warnings'].append('Spectral samples follow fixed optical planes throughout the route. Grating/mirror directions are geometric; lens/OAP focusing is paraxial. Weights are relative spectral intensity, not independent full-power beams. Pulse duration and material phase are not calculated.')
