"""Paired central rays and non-destructive endpoint refresh; no native Fusion."""
import copy
import io
import json
import math
import unittest
from dataclasses import asdict
from unittest.mock import patch
from xml.etree import ElementTree as ET

import core
import exports
from test_adapter import backend, Design, Matrix, NS, Occurrence
import test_v120 as v120
from test_v122 import plan


class PrismTests(unittest.TestCase):
    def vector(self,a,b):
        for x,y in zip(a,b): self.assertAlmostEqual(x,y,places=8)

    def ends(self,p): return [e for e in p['endpoints'] if e['kind']=='end']

    def test_wollaston_has_total_angle_not_double_angle(self):
        for axis,component in [('h',1),('v',2)]:
            p=plan('wp20'+axis+' p100'); secondary,main=self.ends(p)
            a,b=[core.state_from_dict(e['state']) for e in (secondary,main)]
            self.assertAlmostEqual(math.degrees(math.acos(core.dot(a.d,b.d))),20)
            self.assertAlmostEqual(a.position[component],100*math.sin(math.radians(10)))
            self.assertAlmostEqual(b.position[component],-a.position[component])
            self.assertEqual(len(p['segments']),2)
            self.assertEqual((a.path_mm,b.path_mm),(100,100))

    def test_rochon_keeps_main_on_axis_and_uses_default_horizontal(self):
        p=plan('rp10.6 p100');secondary,main=self.ends(p)
        self.vector(main['stats']['position'],(100,0,0))
        self.assertAlmostEqual(secondary['stats']['azimuth'],10.6)
        self.assertEqual(main['stats']['azimuth'],0)

    def test_displacer_distance_sign_and_length_threshold(self):
        for amount,length in [(2.7,28),(2.7001,41),(4,41)]:
            for axis,index in [('h',1),('v',2)]:
                for sign in ('','-'):
                    p=plan(f'bd{amount}{axis}{sign} p50')
                    secondary,main=self.ends(p)
                    expected=[50,0,0];expected[index]=amount*(-1 if sign else 1)
                    self.vector(secondary['stats']['position'],expected)
                    self.vector(main['stats']['direction'],secondary['stats']['direction'])
                    self.assertEqual(p['optics'][0]['tube_length_mm'],length)

    def test_recombination_draws_one_continuing_beam_and_retains_two_budgets(self):
        p=plan('bd4h p50 _bd4h p20')
        secondary,main=self.ends(p)
        self.assertEqual(len(p['segments']),3)
        self.vector(secondary['stats']['position'],main['stats']['position'])
        self.assertIn('combined',main['name']);self.assertIn('secondary arm',secondary['name'])
        for e in (main,secondary):
            r=core.calculate_chain([e],p['endpoints'])
            self.assertEqual(r['geometric_mm'],70)
            self.assertAlmostEqual(r['loss_pct'],100*(1-.49*.99))
        with self.assertRaisesRegex(core.LayoutError,'one connected arm'):
            core.calculate_chain([main,secondary],p['endpoints'])

    def test_wrong_orientation_missing_beam_or_distance_warn_without_false_merge(self):
        for commands in ['bd4h p50 _bd4h- p20','bd4v p50 _bd4h p20','bd4h p50 _bd3h p20','_bd4h p20']:
            p=plan(commands)
            self.assertTrue(any('beam displacer orientation wrong' in w for w in p['warnings']))
            if commands.startswith('bd'):
                self.assertEqual(len(p['segments']),4)
                secondary,main=self.ends(p)
                self.assertFalse(core.connection_matches(core.state_from_dict(main['state']),core.state_from_dict(secondary['state'])))
                self.assertAlmostEqual(main['stats']['loss_pct'],51)

    def test_negative_vertical_pair_and_previous_line_work(self):
        c=core.default_config();c['rows'][0]['commands']='bd4v- p50'
        c['rows'].append(dict(id='second',name='Recombine',commands='_bd4v- p20',start_mode='previous'))
        p=core.plan_layout(c);self.assertEqual(len(p['segments']),3)
        ends=[e for e in self.ends(p) if e['id'].startswith('second:')]
        self.vector(ends[0]['stats']['position'],ends[1]['stats']['position'])
        self.assertEqual(core.calculate_chain([ends[0]])['geometric_mm'],20)

    def test_local_transverse_directions_work_for_inclined_and_vertical_sources(self):
        for az,el in [(37,28),(42,90),(105,-90)]:
            for axis,index in [('h',0),('v',1)]:
                c=core.default_config();c['source'].update(azimuth=az,elevation=el)
                c['rows'][0]['commands']='bd4'+axis+' p50 _bd4'+axis+' p20'
                p=core.plan_layout(c);s=core.initial_state(c['source'])
                port=next(e for e in p['endpoints'] if e['kind']=='secondary')
                self.vector(port['state']['position'],core.mul(core.beam_frame(s)[index],4))
                ends=self.ends(p);self.vector(ends[0]['stats']['position'],ends[1]['stats']['position'])

    def test_default_dimensions_and_scaled_sizes_are_explicit(self):
        for token in ('wp20','rp10.6'):
            o=plan(token)['optics'][0]
            self.assertEqual((o['crystal_width_mm'],o['tube_length_mm'],o['diameter_mm']),(10,14,25.4))
        o=plan('+bd4h')['optics'][0]
        self.assertEqual((o['crystal_width_mm'],o['tube_length_mm'],o['diameter_mm']),(20,82,50.8))

    def test_representation_dimensions_can_be_overridden_and_are_validated(self):
        o=plan('rp10.6',overrides={'line1:0':dict(token='rp10.6',tube_length_mm=18,crystal_width_mm=9)})['optics'][0]
        self.assertEqual((o['tube_length_mm'],o['crystal_width_mm']),(18,9))
        with self.assertRaisesRegex(core.LayoutError,'fit inside'):
            plan('bd4h',overrides={'line1:0':dict(token='bd4h',crystal_width_mm=20)})

    def test_one_custom_default_is_shared_across_orientation_and_combiner(self):
        c=core.default_config();c['component_defaults']={'bd4h':dict(component_token='part',reference=[0,0,0],rotation=[3,4,5])}
        c['rows'][0]['commands']='bd4v- p50 _bd4v-'
        p=core.plan_layout(c)
        self.assertEqual([o['default_key'] for o in p['optics']],['bd4','bd4'])
        self.assertTrue(all(o['settings']['custom'] for o in p['optics']))
        a,b=p['optics'];self.vector(a['frame'][2],b['frame'][2]);self.vector(a['frame'][0],core.mul(b['frame'][0],-1))
        self.assertEqual(a['settings']['rotation'],b['settings']['rotation'])

    def test_visual_flip_does_not_change_prism_rays(self):
        for token in ['wp20v','rp10.6h-','bd4v-']:
            a,b=plan(token+' p20'),plan('f'+token+' p20')
            for x,y in zip(self.ends(a),self.ends(b)): self.vector(x['stats']['position'],y['stats']['position'])
            self.assertTrue(b['optics'][0]['visual_flip'])

    def test_invalid_commands_report_their_token(self):
        for token in ['wp0h','rp180','bd-4v','_wp20','wp20x','bd4v--']:
            with self.subTest(token=token),self.assertRaises(core.LayoutError) as ctx: plan('p50 '+token)
            self.assertEqual(ctx.exception.token,1)

    def test_gaussian_beam_state_is_carried_by_both_outputs(self):
        c=core.default_config();c['source'].update(model='gaussian',wavelength_nm=1030,m2=1.4)
        c['rows'][0]['commands']='l100 p20 bd4h p50 _bd4h p40';p=core.plan_layout(c)
        ends=self.ends(p)
        self.assertAlmostEqual(ends[0]['stats']['diameter_mm'],ends[1]['stats']['diameter_mm'])
        for e in ends:
            restored,_=core.decode_endpoint(e['endpoint'])
            self.assertEqual(restored.m2,1.4);self.assertEqual(restored.wavelength_nm,1030)

    def test_intervening_lens_affects_main_only_and_keeps_different_envelopes(self):
        p=plan('bd4h p10 l50 p40 _bd4h p20')
        secondary,main=self.ends(p)
        self.vector(secondary['stats']['position'],main['stats']['position'])
        self.assertNotEqual(secondary['stats']['diameter_mm'],main['stats']['diameter_mm'])
        self.assertTrue(any('main beam only' in w for w in p['warnings']))
        self.assertTrue(any('different envelopes' in w for w in p['warnings']))

    def test_secondary_continuation_counts_full_parent_arm_not_only_split_point(self):
        a=plan('p10 rp10.6 p100')
        port=next(e for e in a['endpoints'] if e['id'].endswith('end:B1'))
        b=plan('p40',port)
        r=core.calculate_chain([a['rows'][0]['endpoint'],b['rows'][0]['endpoint']],a['endpoints']+b['endpoints'])
        self.assertEqual(r['geometric_mm'],150)
        self.assertAlmostEqual(r['loss_pct'],51)
        self.assertEqual(len(r['notes']),1)

    def test_budget_and_csv_svg_roundtrip_include_both_outputs(self):
        p=plan('rp10.6 p50',overrides={'line1:0':dict(token='rp10.6',budget=dict(transmission_pct=60,reflection_pct=30,gdd_t_fs2=20,gdd_r_fs2=-40))})
        secondary,main=self.ends(p)
        self.assertEqual((main['stats']['loss_pct'],secondary['stats']['loss_pct']),(40,70))
        self.assertEqual((main['stats']['gdd_fs2'],secondary['stats']['gdd_fs2']),(20,-40))
        c=exports.import_csv(exports.export_csv(p),document_id=p['config']['document_id'])
        restored=core.plan_layout(c)
        for a,b in zip(self.ends(restored),self.ends(p)): self.vector(a['stats']['position'],b['stats']['position'])
        svg=ET.fromstring(exports.export_svg(p));self.assertEqual(len(svg.findall('{http://www.w3.org/2000/svg}line')),2)

    def test_second_split_requires_an_explicit_output_line(self):
        with self.assertRaisesRegex(core.LayoutError,'Continue an output'):
            plan('wp20 p50 bd4h')

    def test_tube_and_crystal_shapes_use_requested_dimensions(self):
        operations=[]
        def cyl(manager,p0,r0,p1,r1):
            body=dict(type='cylinder',p0=p0,p1=p1,r0=r0,r1=r1);operations.append(body);return body
        def box(manager,p,basis,lengths):
            body=dict(type='box',center=p,lengths=lengths);operations.append(body);return body
        manager=NS(copy=copy.deepcopy)
        types=NS(DifferenceBooleanType='difference',IntersectionBooleanType='intersection')
        with patch.object(backend,'cylinder',cyl),patch.object(backend,'box',box),patch.object(backend,'boolean') as boolean,patch.object(backend.adsk.fusion,'BooleanTypes',types,create=True):
            for token,length in [('wp20h',14),('rp10.6',14),('bd2.7v',28),('bd4h',41)]:
                operations.clear();o=plan(token)['optics'][0]
                result=backend.optic_bodies(manager,o,{})
                housing,crystal=result[0][1],result[1][1]
                self.assertAlmostEqual(core.norm(core.sub(housing['p1'],housing['p0'])),length)
                self.assertAlmostEqual(housing['r0'],12.7)
                self.assertEqual(crystal['lengths'][:2],(10,10))
                self.assertTrue(any(call.args[-1]=='difference' for call in boolean.call_args_list))


class RefreshTests(unittest.TestCase):
    save=v120.DependencyTests.save
    chain=v120.DependencyTests.chain
    def setUp(self):
        self.d=Design();self.d.attributes.add(backend.GROUP,'document_id','doc')
        self.chain()
        self.beam=self.child.component.occurrences.addNewComponent(Matrix());self.beam.component.name='Beam'
        self.optics=self.child.component.occurrences.addNewComponent(Matrix(translation=(3,4,5)))
        self.optics.component.name='Optics manually adjusted'

    def run_info(self): return next(r for r in backend.saved_endpoints(self.d)['runs'] if r['token']==self.child.entityToken)

    def change_parent(self, diameter=8):
        c=json.loads(backend._attribute(self.parent.component,'settings'));c['source']['diameter_mm']=diameter
        p=core.plan_layout(c)
        self.parent.component.attributes.add(backend.GROUP,'settings',json.dumps(core.snapshot_config(p)))
        self.parent.component.attributes.add(backend.GROUP,'endpoints',json.dumps(p['endpoints']))
        self.parent.component.attributes.add(backend.GROUP,'revision','2')

    def prepare(self, choices=None):
        geometry=dict(beam=[('refreshed',object(),'beam')],optics=[],custom=[],warnings=[])
        with patch.object(backend,'temporary_geometry',return_value=geometry) as make:
            prepared=backend.prepare_route_refresh(self.d,self.child.entityToken,choices)
            self.assertTrue(make.call_args.kwargs['beam_only'])
            return prepared

    def test_revision_only_change_is_current_and_calculator_still_works(self):
        self.parent.component.attributes.add(backend.GROUP,'revision','99')
        self.assertEqual(self.run_info()['status'],'current')
        items=backend.saved_endpoints(self.d)['items']
        self.assertEqual(core.calculate_chain(items)['geometric_mm'],160)

    def test_state_change_has_update_status_without_disconnection_or_clear_beam(self):
        self.change_parent();r=self.run_info()
        self.assertFalse(r['stale']);self.assertTrue(r['needs_refresh'])
        self.assertEqual(r['status'],'update_available')
        backend.refresh_dependencies(None,self.d)
        self.assertNotEqual(backend._attribute(self.child.component,'stale_display'),'true')

    def test_preparation_is_read_only_and_keeps_every_optic_pose(self):
        self.change_parent();before=copy.deepcopy(self.d.log)
        prepared=self.prepare();self.assertEqual(self.d.log,before)
        old=core.plan_layout(json.loads(backend._attribute(self.child.component,'settings')))
        for a,b in zip(old['optics'],prepared['plan']['optics']):
            self.assertEqual((a['position'],a['frame']),(b['position'],b['frame']))
        self.assertEqual(prepared['plan']['rows'][0]['start_state']['y'],4)

    def test_refresh_replaces_beam_only_and_clears_update_status(self):
        self.change_parent();prepared=self.prepare();optic_pose=self.optics.transform2
        with patch.object(backend,'add_bodies',return_value=[]): result=backend.refresh_route(None,self.d,prepared)
        self.assertFalse(self.beam.isValid);self.assertTrue(self.optics.isValid);self.assertTrue(self.child.isValid)
        self.assertEqual(self.optics.transform2.translation,optic_pose.translation)
        self.assertEqual(result['operation'],'refresh_route');self.assertEqual(self.run_info()['status'],'current')
        self.assertEqual(backend._attribute(self.child.component,'revision'),'2')

    def test_refresh_in_moved_rotated_route_preserves_local_optics(self):
        placement=Matrix(((0,1,0),(-1,0,0),(0,0,1)),(3,5,2))
        self.parent.transform2=placement;self.child.transform2=placement;self.change_parent()
        prepared=self.prepare()
        self.assertEqual(prepared['plan']['optics'][0]['position'],[140,0,0])
        with patch.object(backend,'add_bodies',return_value=[]): backend.refresh_route(None,self.d,prepared)
        self.assertEqual(self.child.transform2.translation,placement.translation)
        self.assertEqual(self.run_info()['status'],'current')

    def test_source_change_after_preparation_aborts_before_mutation(self):
        self.change_parent();prepared=self.prepare();self.change_parent(12);before=copy.deepcopy(self.d.log)
        with self.assertRaisesRegex(core.LayoutError,'source endpoint changed'):
            backend.refresh_route(None,self.d,prepared)
        self.assertEqual(self.d.log,before);self.assertTrue(self.beam.isValid)

    def test_disconnection_is_reversible_when_endpoint_returns(self):
        self.parent.transform2=Matrix(translation=(1,0,0));self.assertEqual(self.run_info()['status'],'disconnected')
        self.parent.transform2=Matrix();self.assertEqual(self.run_info()['status'],'current')

    def test_replacement_identity_is_reconnected_only_at_matching_pose(self):
        self.parent.deleteMe()
        c=core.default_config();c['rows'][0]['commands']='p100'
        replacement=self.save(c,'replacement')
        self.assertEqual(self.run_info()['status'],'update_available')
        prepared=self.prepare();start=core.state_from_dict(prepared['plan']['rows'][0]['start_state'])
        self.assertEqual(start.link['run_id'],'replacement')
        replacement.transform2=Matrix(((1,0,0),(0,-1,0),(0,0,-1))) # same +X direction: still compatible
        self.assertEqual(self.run_info()['status'],'update_available')

    def test_ambiguous_replacements_require_explicit_choice(self):
        self.parent.deleteMe()
        for name in ('first','second'):
            c=core.default_config();c['rows'][0]['commands']='p100';self.save(c,name)
        data=backend.refresh_candidates(self.d,self.child.entityToken);row=data['rows'][0]
        self.assertEqual(row['selected'],'');self.assertEqual(len(row['candidates']),2)
        with self.assertRaisesRegex(core.LayoutError,'choose a matching'): self.prepare()
        prepared=self.prepare({row['id']:row['candidates'][1]['id']})
        self.assertEqual(prepared['plan']['rows'][0]['start_state']['link']['run_id'],'second')

    def test_opposite_direction_is_not_a_compatible_source(self):
        self.parent.deleteMe();c=core.default_config();c['source'].update(position=[200,0,0],azimuth=180)
        c['rows'][0]['commands']='p100';self.save(c,'opposite')
        self.assertEqual(self.run_info()['status'],'disconnected')
        self.assertEqual(backend.refresh_candidates(self.d,self.child.entityToken)['rows'][0]['candidates'],[])

    def test_dependent_route_cannot_be_its_own_source(self):
        endpoint=next(e for e in backend.saved_endpoints(self.d)['items'] if e['run_id']=='child')
        c=core.default_config();c['rows'][0].update(commands='r180 p60',start_mode='snapshot',endpoint=endpoint['endpoint'])
        self.save(c,'descendant');self.parent.deleteMe()
        self.assertEqual(backend.refresh_candidates(self.d,self.child.entityToken)['rows'][0]['candidates'],[])

    def test_multiple_component_instances_are_not_modified_together(self):
        duplicate=Occurrence(self.d,'duplicate',self.child.component);self.d.entities['duplicate']=duplicate
        with self.assertRaisesRegex(core.LayoutError,'multiple instances'): self.prepare()

    def test_missing_beam_group_is_reported_without_deleting_optics(self):
        self.beam.component.name='Unidentified body group';self.change_parent()
        with self.assertRaisesRegex(core.LayoutError,'single existing Beam group'): self.prepare()
        self.assertTrue(self.optics.isValid)

    def test_upstream_pending_is_not_reported_as_missing_geometry(self):
        endpoint=next(e for e in backend.saved_endpoints(self.d)['items'] if e['run_id']=='child')
        c=core.default_config();c['rows'][0].update(commands='p40',start_mode='snapshot',endpoint=endpoint['endpoint'])
        tail=self.save(c,'tail');self.change_parent()
        run=next(r for r in backend.saved_endpoints(self.d)['runs'] if r['token']=='tail')
        self.assertFalse(run['stale']);self.assertEqual(run['status'],'upstream_pending')
        row=backend.refresh_candidates(self.d,tail.entityToken)['rows'][0]
        self.assertTrue(row['candidates']);self.assertFalse(any(e['usable'] for e in row['candidates']))

    def test_internal_reflected_snapshot_recalculates_after_external_source(self):
        endpoint=next(e for e in backend.saved_endpoints(self.d)['items'] if e['run_id']=='parent')
        c=core.default_config();c.update(route_id='internal',document_id='doc')
        c['rows'][0].update(commands='p20 bsc p50',start_mode='snapshot',endpoint=endpoint['endpoint'])
        p=core.plan_layout(c);port=p['rows'][0]['ports'][0]
        state=core.state_from_dict(port['state']);state.link=core.endpoint_link(state,'doc','internal',1,port['id'])
        c['rows'].append(dict(id='branch',name='Branch',commands='p40',start_mode='snapshot',endpoint=core.encode_endpoint(state)))
        route=self.save(c,'internal');beam=route.component.occurrences.addNewComponent(Matrix());beam.component.name='Beam'
        self.change_parent()
        with patch.object(backend,'temporary_geometry',return_value=dict(beam=[],optics=[],custom=[],warnings=[])):
            prepared=backend.prepare_route_refresh(self.d,route.entityToken)
        self.assertEqual(prepared['plan']['rows'][1]['start_state']['y'],4)
        self.assertEqual(prepared['plan']['rows'][1]['start_state']['link']['revision'],2)

    def test_failed_native_beam_creation_leaves_previous_groups_for_transaction_rollback(self):
        self.change_parent();prepared=self.prepare()
        with patch.object(backend,'add_bodies',side_effect=RuntimeError('test kernel failure')):
            with self.assertRaisesRegex(RuntimeError,'Create refreshed beam: test kernel failure'):
                backend.refresh_route(None,self.d,prepared)
        self.assertTrue(self.beam.isValid);self.assertTrue(self.optics.isValid)
        self.assertEqual(backend._attribute(self.child.component,'revision'),'1')

    def test_failed_refresh_command_uses_manage_error_and_retains_request_until_destroy(self):
        c,sent=v120.CommandLifecycleTests().classes();prepared=object();context={};args=NS(executeFailed=False)
        c['_pending_build']=dict(operation='refresh_route',prepared=prepared,doc_key='doc',close=False)
        def failed(*args): raise RuntimeError('test rollback')
        c['backend'].refresh_route=failed
        c['BuildExecute'](context).notify(args)
        self.assertTrue(args.executeFailed);self.assertIs(context['request']['prepared'],prepared)
        c['BuildDestroyed'](context).notify(NS());self.assertEqual(sent[0][0],'manage_failed')

    def test_refresh_command_retains_transients_and_reports_managed_after_destroy(self):
        c,sent=v120.CommandLifecycleTests().classes();prepared=object();context={};args=NS(executeFailed=False)
        c['_pending_build']=dict(operation='refresh_route',prepared=prepared,doc_key='doc',close=False)
        c['backend'].refresh_route=lambda *args:dict(operation='refresh_route')
        c['backend'].saved_endpoints=lambda *args:dict(items=[],runs=[],warnings=[])
        c['BuildExecute'](context).notify(args)
        self.assertFalse(args.executeFailed);self.assertIs(context['request']['prepared'],prepared);self.assertEqual(sent,[])
        c['BuildDestroyed'](context).notify(NS())
        self.assertEqual(sent[0][0],'managed');self.assertEqual(context,{})


if __name__=='__main__': unittest.main()
