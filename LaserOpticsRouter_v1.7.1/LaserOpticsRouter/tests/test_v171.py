"""Assembly-upright components and complete fixed-surface spectral trains."""
import copy
import json
import math
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core, exports, beam_matrix, spectral_routing
from test_adapter import backend, Design, Component, Occurrence, Matrix, Point, Attributes
import test_components as component_tests

USER_ROUTE = 'p100 l50 p25 r90 p75 _r90f50 p50 r90v45 p100 cyl100h p200 cyl100h p50 r-90v-45 p100 wp20h p50'
BETA = math.degrees(math.asin(-.48-math.sin(math.radians(-45))))
PAIR = f'p100 +gr600a-45m-1h p150 +gr600a{BETA:.14g}m-1h'
COMPRESSOR = PAIR+f' p150 r0v90 p10 r180v-90 p150 +gr600a-45m-1h p150 +gr600a{BETA:.14g}m-1h p100'


def layout(commands, model='geometric', mode='sidebands', width=20, **source):
    config = core.default_config()
    config['rows'][0]['commands'] = commands
    config['source'].update(model=model,spectrum=dict(mode=mode,width_nm=width,samples=9),**source)
    return core.plan_layout(config)


def end(plan): return core.state_from_dict(plan['rows'][-1]['endpoint']['state'])
def samples(plan): return [core.state_from_dict(ray) for ray in end(plan).spectral_rays]


class VectorChecks(unittest.TestCase):
    def vector(self, a, b, places=8):
        for x,y in zip(a,b): self.assertAlmostEqual(x,y,places=places)


class AssemblyPlacement(VectorChecks):
    def test_horizontal_normals_keep_positive_assembly_z(self):
        for commands in ('r90','r-90','r180','r45','_r90f50','cyl50v','gr600a30m1h','bd4v-'):
            with self.subTest(commands=commands):
                optic=layout('p10 '+commands,mode='central')['optics'][0]
                origin,axes=core.custom_transform(optic)
                self.vector(origin,(10,0,0));self.vector(axes[2],(0,0,1))
                self.vector(core.cross(axes[0],axes[1]),axes[2])

    def test_vertical_bends_use_projected_up_without_roll_inversion(self):
        for commands in ('r90v45','r90v90','r-90v-45','r0v90','r180v-90'):
            optic=layout(commands,mode='central')['optics'][0]
            _,axes=core.custom_transform(optic)
            n=axes[0]
            projected=core.unit(core.sub((0,0,1),core.mul(n,n[2])))
            self.vector(axes[2],projected)
            self.assertGreater(axes[2][2],0)
            for i in range(3):
                for j in range(3):self.assertAlmostEqual(core.dot(axes[i],axes[j]),int(i==j))

    def test_vertical_normal_fallback_is_finite_and_right_handed(self):
        for normal in ((0,0,1),(0,0,-1)):
            axes=core.level_frame(normal)
            self.vector(axes[0],normal);self.vector(axes[2],(-1,0,0))
            self.vector(core.cross(axes[0],axes[1]),axes[2])

    def test_local_z_rotation_maps_source_y_to_surface_normal(self):
        optic=layout('p10 r90',mode='central')['optics'][0]
        optic['settings']['component_rotation_deg']=[0,0,-90]
        _,axes=core.custom_transform(optic)
        self.vector(axes[1],optic['normal']);self.vector(axes[2],(0,0,1))

    def test_flip_rotates_around_target_normal_after_source_correction(self):
        optic=layout('p10 fr90',mode='central')['optics'][0]
        optic['settings']['component_rotation_deg']=[0,0,-90]
        _,axes=core.custom_transform(optic)
        self.vector(axes[1],optic['normal']);self.vector(axes[2],(0,0,-1))

    def test_offset_uses_assembly_axes_even_for_a_rotated_route(self):
        rotation=core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),25,40,70)
        optic=layout('p10 r90',mode='central')['optics'][0]
        optic['settings']['assembly_offset_mm']=[3,-7,12]
        origin,axes=core.custom_transform(optic,rotation)
        self.vector(core.sub(core.world(rotation,origin),core.world(rotation,optic['position'])),(3,-7,12))
        world_axes=[core.world(rotation,a) for a in axes]
        normal=world_axes[0]
        self.vector(world_axes[2],core.unit(core.sub((0,0,1),core.mul(normal,normal[2]))))

    def test_preview_and_build_agree_for_tilted_route_and_corrections(self):
        design=Design();source=Component(design,'Asymmetric source')
        source.bRepBodies=[NS(isVisible=True,points=[Point(.7,-.3,.2),Point(1.8,.4,-.5)])]
        source_occ=Occurrence(design,'source',source)
        design.entities['source']=source_occ;design.activeOccurrence=source_occ
        config=core.default_config();config['rows'][0]['commands']='p20 r90v45'
        config['options']['protect_components']=False
        config['optic_overrides']['line1:1']=dict(token='r90v45',custom=True,component_token='source',
            component_rotation_deg=[12,-23,90],assembly_offset_mm=[4,5,-6])
        plan=core.plan_layout(config);part=Component(design,'old')
        for key,value in [('run_id','old-id'),('settings',json.dumps(config)),('endpoints','[]')]:
            part.attributes.add(backend.GROUP,key,value)
        pose=Matrix(core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),30,20,70),(10,-20,5))
        old=Occurrence(design,'old',part,pose);design.entities['old']=old
        optic=plan['optics'][0];local=backend.custom_placement(optic,pose.axes)
        expected=backend.compose_placements(pose,local)
        geometry=dict(beam=[],optics=[],custom=[(optic,source)],warnings=[])
        backend.build(None,design,plan,'old',prepared=geometry)
        built=next(x for x in design.proxies.values() if x.component is source)
        self.vector(built.transform2.translation,expected.translation)
        for a,b in zip(built.transform2.axes,expected.axes):self.vector(a,b)
        self.assertFalse(old.isValid);self.assertIsNone(design.activeOccurrence)
        self.vector((source.bRepBodies[0].points[0].x,source.bRepBodies[0].points[0].y,source.bRepBodies[0].points[0].z),(.7,-.3,.2))

    def test_corrections_survive_csv_and_do_not_change_optical_geometry(self):
        original=layout('p30 r90 p20',mode='central');config=core.snapshot_config(original)
        config['optic_overrides']['line1:1'].update(custom=True,component_token='source',
            component_rotation_deg=[0,0,-90],assembly_offset_mm=[3,2,1])
        changed=core.plan_layout(config)
        self.assertEqual(end(original).stats(),end(changed).stats())
        restored=core.plan_layout(exports.import_csv(exports.export_csv(changed)))
        self.assertEqual(restored['optics'][0]['settings']['component_rotation_deg'],[0,0,-90])
        self.assertEqual(restored['optics'][0]['settings']['assembly_offset_mm'],[3,2,1])


class FixedSurfaceSpectra(VectorChecks):
    def test_parallel_grating_pair_cancels_angular_dispersion(self):
        plan=layout(PAIR+' p100');center=end(plan)
        self.vector(center.d,(1,0,0))
        for ray in samples(plan):self.vector(ray.d,center.d)
        positions=[ray.position for ray in samples(plan)]
        self.assertGreater(core.norm(core.sub(positions[0],positions[1])),1)
        for ray in samples(plan):
            grating=plan['optics'][1]
            first_leg=next(s for s in plan['segments'] if s.get('spectral') and s['state'].wavelength_nm==ray.wavelength_nm)
            hit=first_leg['state'].propagated(first_leg['length']).position
            self.assertAlmostEqual(core.dot(core.sub(hit,grating['position']),grating['normal']),0,places=9)

    def test_double_pass_recombines_all_samples_at_separated_output(self):
        for model,mode in (('geometric','sidebands'),('gaussian','gaussian')):
            plan=layout(COMPRESSOR,model,mode);center=end(plan)
            self.vector(center.position,(0,0,10));self.vector(center.d,(-1,0,0))
            rays=samples(plan);self.assertEqual(len(rays),2 if mode=='sidebands' else 8)
            for ray in rays:
                self.vector(ray.position,center.position);self.vector(ray.d,center.d)
                core.state_from_dict(asdict(ray))
            self.assertGreater(max(ray.path_mm for ray in rays)-min(ray.path_mm for ray in rays),3)
            for optic in (x for x in plan['optics'] if x['kind']=='grating'):
                self.assertEqual(len(optic['spectral_samples']),len(rays)+1)
            self.assertEqual(sum(bool(o.get('reuse_id')) for o in plan['optics']),2)

    def test_lens_corrects_decentered_spectral_chief_ray(self):
        incoming=layout('gr600a0m1h p100')
        focused=layout('gr600a0m1h p100 l100')
        nominal=end(incoming);axis=nominal.d;h,v=core.beam_frame(nominal)[:2]
        for before,after in zip(samples(incoming),samples(focused)):
            scaled=core.mul(before.d,1/core.dot(before.d,axis))
            height=core.sub(before.position,nominal.position)
            expected=core.unit(core.sub(scaled,core.mul(h,core.dot(height,h)/100)))
            self.vector(after.d,expected)
            self.assertLess(abs(core.dot(after.d,h)),abs(core.dot(before.d,h)))

    def test_multiple_optics_keep_samples_and_near_focus_moments_valid(self):
        commands='gr600a30m1h p100 r90v30 p50 cyl100h p100 l100 p100 resetd5finf p40 gr600a0m0h p30'
        for model in ('geometric','gaussian'):
            plan=layout(commands,model,'gaussian',10)
            self.assertEqual(len(samples(plan)),8)
            self.assertEqual([len(o['spectral_samples']) for o in plan['optics'] if o['kind']=='grating'],[9,9])
            for segment in plan['segments']:
                core.state_from_dict(asdict(segment['state'].propagated(segment['length'])))

    def test_fixed_mirror_preserves_spectral_angle_differences_in_3d(self):
        first=layout('gr600a0m1h p50');second=layout('gr600a0m1h p50 r90v45')
        normal=second['optics'][-1]['normal']
        for before,after in zip(samples(first),samples(second)):
            self.vector(after.d,core.sub(before.d,core.mul(normal,2*core.dot(before.d,normal))))
        self.assertGreater(core.norm(core.sub(samples(second)[0].d,samples(second)[1].d)),.02)

    def test_splitter_and_prism_endpoints_keep_full_spectral_bundles(self):
        for command,port in (('bsc','R'),('wp20h','B'),('rp10v','B'),('bd4h','B')):
            with self.subTest(command=command):
                plan=layout('gr600a0m1h p50 '+command+' p50')
                split=next(e for e in plan['endpoints'] if e['id']=='line1:2:'+port)
                self.assertEqual(len(split['state']['spectral_rays']),2)
                self.assertEqual(len(samples(plan)),2)
                if command!='bsc':
                    secondary=next(e for e in plan['endpoints'] if e['id']=='line1:end:B1')
                    self.assertEqual(len(secondary['state']['spectral_rays']),2)

    def test_invalid_displacer_combiner_does_not_apply_spectral_loss(self):
        first=layout('gr600a0m1h p50 bd4h p50')
        invalid=layout('gr600a0m1h p50 bd4h p50 _bd4h-')
        for before,after in zip(samples(first),samples(invalid)):
            self.assertEqual(before.throughput,after.throughput)
            self.assertEqual(before.gdd_fs2,after.gdd_fs2)

    def test_correct_displacer_combines_sample_positions_and_keeps_histories(self):
        plan=layout('gr600a0m1h p50 bd4h p50 _bd4h p50')
        secondary=next(e for e in plan['endpoints'] if e['id']=='line1:end:B1')
        for ray,child in zip(samples(plan),secondary['state']['spectral_rays']):
            self.vector(ray.position,child['position'])
            self.assertNotEqual(ray.trace,child['trace'])

    def test_previous_line_continues_the_same_rays(self):
        plan=layout(PAIR+' p50');config=core.snapshot_config(plan)
        config['rows'].append(dict(id='second',name='Continuation',commands='p50',start_mode='previous',endpoint=''))
        continued=core.plan_layout(config);single=layout(PAIR+' p100')
        for ray,expected in zip(samples(continued),samples(single)):
            self.vector(ray.position,expected.position);self.assertAlmostEqual(ray.path_mm,expected.path_mm)

    def test_snapshot_bundle_continues_after_compressor(self):
        plan=layout(COMPRESSOR);packet=plan['rows'][0]['endpoint']['endpoint']
        config=core.default_config();config['rows'][0].update(start_mode='snapshot',endpoint=packet,commands='p25 r90 p40 l100 p100')
        continued=core.plan_layout(config)
        self.assertEqual(len(samples(continued)),2)
        for ray in samples(continued):
            self.assertGreater(ray.path_mm,900);self.assertTrue(math.isfinite(ray.radius))

    def test_bundle_world_transform_moves_each_sample(self):
        state=end(layout(PAIR+' p100'))
        axes=core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),10,20,30);origin=(3,4,5)
        moved=core.moved_state(state,origin,axes)
        native=backend.transformed_state(asdict(state),Matrix(axes,core.mul(origin,.1)))
        for before,after,other in zip(state.spectral_rays,moved.spectral_rays,native.spectral_rays):
            self.vector(after['position'],core.add(origin,core.world(axes,before['position'])))
            self.vector(other['position'],after['position'])

    def test_csv_clone_rebinds_internal_bundle_histories(self):
        plan=layout('gr600a0m1h p50');config=core.snapshot_config(plan)
        old_id=config['route_id']
        config['rows'].append(dict(id='branch',name='Branch',commands='p50',start_mode='snapshot',endpoint=plan['rows'][0]['endpoint']['endpoint']))
        cloned=exports.import_csv(exports.export_csv(core.plan_layout(config)))
        state,_=core.decode_endpoint(cloned['rows'][1]['endpoint'])
        self.assertNotEqual(cloned['route_id'],old_id)
        for ray in [asdict(state)]+state.spectral_rays:
            self.assertFalse(any(e['id'].startswith(old_id+':') for e in ray['trace']))
            self.assertTrue(any(e['id'].startswith(cloned['route_id']+':') for e in ray['trace']))

    def test_bundle_rejects_nested_duplicate_and_oversized_packets(self):
        state=asdict(end(layout('gr600a0m1h p50')))
        for invalid in ('nested','duplicate','oversized'):
            data=copy.deepcopy(state)
            if invalid=='nested':data['spectral_rays'][0]['spectral_rays']=[copy.deepcopy(data['spectral_rays'][1])]
            if invalid=='duplicate':data['spectral_rays'][1]['wavelength_nm']=data['spectral_rays'][0]['wavelength_nm']
            if invalid=='oversized':data['spectral_rays']*=11
            with self.subTest(invalid=invalid),self.assertRaises(core.LayoutError):core.state_from_dict(data)

    def test_user_example_remains_an_ordinary_route(self):
        plan=layout(USER_ROUTE,mode='central');state=end(plan)
        self.assertEqual(state.path_mm,750);self.assertEqual(len(plan['optics']),8)
        self.vector(state.position,(-74.24038765061044,-163.80496453194513,247.4873734152916))
        self.assertEqual(len(state.spectral_rays),0)


class ReplacementAndReusedCad(VectorChecks):
    def test_final_colors_are_assigned_after_old_route_is_deleted(self):
        design=Design();old_part=Component(design,'old');old_part.attributes.add(backend.GROUP,'run_id','id')
        old=Occurrence(design,'old',old_part);design.entities['old']=old
        old.activate();plan=layout('p20 r90 p10',mode='central');plan['config']['options']['protect_components']=False
        body=NS(attributes=Attributes(),appearance=None)
        body.attributes.add(backend.GROUP,'router_style','beam')
        geometry=dict(beam=[('beam',object(),'beam')],optics=[],custom=[],warnings=[])
        def add(component,design,entries):component.bRepBodies=[body];return [(NS(),'beam')]
        colored=object()
        def appearance(app,design,kind):
            self.assertFalse(old.isValid);self.assertEqual(kind,'beam');return colored
        with patch.object(backend,'add_bodies',side_effect=add),patch.object(backend,'appearance',side_effect=appearance):
            result=backend.build(None,design,plan,'old',prepared=geometry)
        self.assertIs(body.appearance,colored);self.assertTrue(result['replaced'])
        self.assertIsNone(design.activeOccurrence)
        self.assertEqual(sum(o.isValid and bool(o.component.attributes.itemByName(backend.GROUP,'run_id')) for o in design.entities.values()),1)

    def test_existing_appearance_color_is_reasserted(self):
        prop=NS(value=None);appearance=NS(isValid=True,appearanceProperties=NS(itemById=lambda key:prop))
        design=NS(appearances=NS(itemByName=lambda name:appearance))
        api=NS(core=NS(ColorProperty=NS(cast=lambda x:x),Color=NS(create=lambda *a:a)))
        with patch.object(backend,'adsk',api):result=backend.appearance(None,design,'beam')
        self.assertIs(result,appearance);self.assertEqual(prop.value,(*backend.COLORS['beam'],255))

    def test_compressor_places_only_two_physical_gratings(self):
        plan=layout(COMPRESSOR)
        with patch.object(backend.adsk.fusion,'TemporaryBRepManager',NS(get=lambda:None),create=True), \
             patch.object(backend,'segment_bodies',return_value=[]), \
             patch.object(backend,'optic_bodies',side_effect=lambda m,o,s:[(o['id'],object(),o['kind'])]):
            geometry=backend.temporary_geometry(plan,Design())
        self.assertEqual(sum(k=='grating' for _,_,k in geometry['optics']),2)
        config=core.snapshot_config(plan);config['options']['reuse_gratings']=False
        self.assertFalse(any(o.get('reuse_id') for o in core.plan_layout(config)['optics']))

    def test_selected_return_grating_previews_the_first_physical_part(self):
        group,design,component,api=component_tests.ComponentPreview().fixture()
        config=core.snapshot_config(layout(COMPRESSOR))
        for key,settings in config['optic_overrides'].items():
            if settings['token'].lstrip('+').startswith('gr'):
                settings.update(custom=True,representation='custom',component_token='source')
        plan=core.plan_layout(config);return_grating=next(o for o in plan['optics'] if o.get('reuse_id'))
        first=next(o for o in plan['optics'] if o['id']==return_grating['reuse_id'])
        with patch.object(backend,'adsk',api),patch.object(backend,'resolve_component',return_value=component) as resolve:
            backend.preview(design,plan,quality='selected',optic_id=return_grating['id'])
        self.assertEqual(resolve.call_args.args[1]['id'],first['id'])
        hit=group.bodies[0].points[0]
        self.vector((hit.x,hit.y,hit.z),core.mul(first['position'],.1))


if __name__=='__main__':unittest.main()
