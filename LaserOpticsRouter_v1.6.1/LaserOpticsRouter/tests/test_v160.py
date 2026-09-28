"""New passive optics, live component defaults, geometric budgets and CAD frames."""
import copy
import json
import math
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from xml.etree import ElementTree as ET
import core
import exports
import schematic_svg
from test_adapter import backend, Design, Component, Occurrence, Matrix, Point
from test_v150 import layout

ROOT=Path(__file__).resolve().parents[1]


def independent(commands, position=(0,0,0), azimuth=0, token=None):
    c=core.default_config();c['rows'][0]['commands']=commands
    c['source'].update(position=list(position),azimuth=azimuth)
    p=core.plan_layout(c)
    if token:
        for e in p['endpoints']:e.update(run_token=token,run_id=c['route_id'],endpoint_id=e['id'])
    return p


class PassiveElements(unittest.TestCase):
    def test_waveplates_and_nd_leave_envelope_color_direction_unchanged(self):
        for model in ('geometric','gaussian'):
            c=core.default_config();c['source'].update(model=model,color='blue',half_angle_mrad=3)
            c['rows'][0]['commands']='p10 laha p10 laqu p10 nd p10'
            a=core.plan_layout(c);c['rows'][0]['commands']='p40';b=core.plan_layout(c)
            for k in ('position','direction','diameter_mm','half_angle_mrad','path_mm'):
                av,bv=a['endpoints'][-1]['stats'][k],b['endpoints'][-1]['stats'][k]
                self.assertEqual(av,bv) if isinstance(av,list) else self.assertAlmostEqual(av,bv)
            s=a['endpoints'][-1]['state'];self.assertEqual(s['color'],'blue')
            self.assertAlmostEqual(s['throughput'],.99*.99*.1)
            self.assertEqual(s['gdd_fs2'],200)

    def test_passive_budgets_override_and_csv_preserves_each_value(self):
        p=layout('laha laqu nd p10',{'line1:0':dict(token='laha',budget=dict(loss_pct=3,gdd_fs2=-40,n=1.5,thickness_mm=2))})
        q=core.plan_layout(exports.import_csv(exports.export_csv(p)))
        self.assertEqual(p['endpoints'][-1]['stats'],q['endpoints'][-1]['stats'])
        self.assertEqual(q['endpoints'][-1]['stats']['optical_path_mm'],11)

    def test_passive_placeholders_are_discs_with_thicker_nd(self):
        depths={}
        for kind in ('laha','laqu','nd','tp30d0.5'):
            optic=layout(kind)['optics'][0]
            with patch.object(backend,'cylinder',return_value='disc') as call:
                backend.optic_bodies(None,optic,{})
            _,a,r,b,r2=call.call_args.args
            self.assertEqual(r,r2);depths[optic['kind']]=core.norm(core.sub(a,b))
        self.assertEqual(depths['laha'],1);self.assertEqual(depths['laqu'],1)
        self.assertGreater(depths['nd'],depths['laha'])
        self.assertAlmostEqual(depths['tp'],1.5)

    def test_tweaker_signed_offset_and_normal(self):
        for command,y in [('tp30d0.5',.5),('tp-30d0.5',-.5),('tp30d-0.5',-.5),('tp0d0.5',.5)]:
            with self.subTest(command=command):
                p=layout('p10 '+command+' p20');o=p['optics'][0];end=p['endpoints'][-1]['state']
                self.assertEqual(tuple(end['position']),(30.,y,0.));self.assertEqual(end['path_mm'],30.)
                self.assertEqual(end['y'],2.5);self.assertEqual(end['color'],'red')
                self.assertEqual(o['position'],[10.,0.,0.]);self.assertEqual(o['transmission_position'],[10.,y,0.])
                self.assertAlmostEqual(core.norm(o['normal']),1)
                self.assertAlmostEqual(o['incidence_deg'],abs(o['plate_angle_deg']))
        p=independent('tp30d0.5 p20',azimuth=90)
        self.assertAlmostEqual(p['endpoints'][-1]['state']['position'][0],-.5)
        self.assertAlmostEqual(p['endpoints'][-1]['state']['position'][1],20)

    def test_tweaker_size_flip_and_invalid_values(self):
        for cmd in ('tp90d1','tp-90d1','tp30d10001','tp30dnan','_tp30d1','tpxd1','tp30d'):
            with self.subTest(cmd=cmd),self.assertRaises(core.LayoutError):core.parse_commands(cmd)
        self.assertEqual(core.default_key(core.parse_commands('f+tp-30d2')[0]),'+tp')
        self.assertEqual(core.parse_commands('tp30')[0]['displacement'],0)
        a,b=layout('tp30d0.5')['optics'][0],layout('ftp30d0.5')['optics'][0]
        self.assertEqual(a['transmission_position'],b['transmission_position'])

    def test_splitter_displaces_only_transmission_and_uses_correct_budget(self):
        for command in ('bs90','bs-90','bs30','bs0v30','bsc'):
            p=layout('p10 '+command+' p20',{'line1:1':dict(token=command,displacement_mm=.5)})
            o=p['optics'][0];r=p['rows'][0]['ports'][0]['state'];t=p['endpoints'][-1]['state']
            self.assertEqual(tuple(r['position']),(10.,0.,0.));self.assertAlmostEqual(r['throughput'],.49)
            self.assertEqual(t['path_mm'],30);self.assertAlmostEqual(t['throughput'],.49)
            self.assertAlmostEqual(core.norm(core.sub(p['segments'][-1]['state'].position,(10,0,0))),.5)
            transverse=core.sub(o['output_direction'],core.mul(o['input_direction'],core.dot(o['input_direction'],o['output_direction'])))
            self.assertLess(core.dot(o['transmission_offset'],transverse),0)
            self.assertEqual(t['azimuth'],0);self.assertEqual(t['elevation'],0)
        self.assertEqual(tuple(layout('bs90 p10')['endpoints'][-1]['state']['position']),(10.,0.,0.))

    def test_negative_and_invalid_splitter_displacement(self):
        p=layout('bs90 p10',{'line1:0':dict(token='bs90',displacement_mm=-.5)})
        self.assertEqual(tuple(p['endpoints'][-1]['state']['position']),(10.,.5,0.))
        for d in (float('nan'),float('inf'),10001):
            with self.assertRaises(core.LayoutError):layout('bs90',{'line1:0':dict(token='bs90',displacement_mm=d)})

    def test_displaced_transmission_clears_prior_trim_and_keeps_reflected_origin(self):
        p=layout('r90 bs-90 p20',{'line1:1':dict(token='bs-90',displacement_mm=1)})
        self.assertIsNone(p['segments'][0]['trim_start'])
        self.assertEqual(tuple(p['rows'][0]['ports'][0]['state']['position']),(0.,0.,0.))
        p=layout('r90 tp30d1 p20');self.assertIsNone(p['segments'][0]['trim_start'])


class DefaultWorkflow(unittest.TestCase):
    def test_new_optics_always_use_live_defaults_with_builtin_fallback(self):
        p=layout('l50 bs30 laha laqu nd tp30d0.5 g')
        self.assertTrue(all(o['settings']['representation']=='default' for o in p['optics']))
        self.assertTrue(all(not o['settings']['custom'] for o in p['optics']))

    def test_bs_angles_share_one_default_but_sizes_remain_distinct(self):
        c=core.default_config();c['rows'][0]['commands']='bs30 bs-90 fbs60v20 +bs30'
        c['component_defaults']={'bs':dict(component_token='plate',shift=[1,2,3],rotation=[0,0,90],displacement_mm=.5)}
        p=core.plan_layout(c)
        for o in p['optics'][:3]:
            self.assertEqual(o['default_key'],'bs');self.assertEqual(o['settings']['component_token'],'plate')
            self.assertEqual(o['settings']['rotation'],[0,0,90]);self.assertEqual(o['displacement_mm'],.5)
        self.assertFalse(p['optics'][3]['settings']['custom']);self.assertEqual(p['optics'][3]['default_key'],'+bs')

    def test_live_default_ignores_stale_local_values_and_snapshot_is_pinned(self):
        c=core.default_config();c['rows'][0]['commands']='bs30'
        c['component_defaults']={'bs':dict(component_token='plate',rotation=[0,0,90],displacement_mm=1)}
        c['optic_overrides']={'line1:0':dict(token='bs30',representation='default',component_token='stale',rotation=[90,0,0],displacement_mm=5)}
        p=core.plan_layout(c);self.assertEqual(p['optics'][0]['settings']['component_token'],'plate')
        self.assertEqual(p['optics'][0]['displacement_mm'],1)
        pinned=core.snapshot_config(p);pinned['component_defaults']['bs']['rotation']=[45,45,45]
        self.assertEqual(core.plan_layout(pinned)['optics'][0]['settings']['rotation'],[0,0,90])
        c['component_defaults']={};o=core.plan_layout(c)['optics'][0]
        self.assertFalse(o['settings']['custom']);self.assertEqual(o['displacement_mm'],0)

    def test_legacy_partial_overrides_remain_local(self):
        p=layout('g',{'line1:0':dict(token='g',shape='cube',budget=dict(loss_pct=7))})
        self.assertEqual(p['optics'][0]['shape'],'cube');self.assertEqual(p['optics'][0]['budget']['loss_pct'],7)
        self.assertEqual(p['optics'][0]['settings']['representation'],'builtin')

    def test_legacy_bs_defaults_merge_read_only_with_canonical_precedence(self):
        old={'bs30':dict(component_token='angle'), 'bs':dict(component_token='canonical'), 'bs-90':dict(component_token='other'), '+bs-30':dict(component_token='large')}
        before=copy.deepcopy(old);result=core.normalize_component_defaults(old)
        self.assertEqual(old,before);self.assertEqual(result['bs']['component_token'],'canonical')
        self.assertEqual(result['+bs']['component_token'],'large')
        self.assertEqual(core.normalize_component_defaults({'bs-90':old['bs-90']})['bs']['component_token'],'other')

    def test_saving_builtin_default_requires_no_cad_and_validates_budgets(self):
        d=Design()
        with patch.object(backend,'resolve_component',side_effect=AssertionError('Built-in needs no CAD')):
            result=backend.save_component_default(d,'bs',dict(custom=False,displacement_mm=.5,budget=dict(transmission_pct=70,reflection_pct=25)))
        self.assertEqual(result['bs']['displacement_mm'],.5)
        with self.assertRaises(core.LayoutError):backend.save_component_default(d,'bs',dict(custom=False,budget=dict(transmission_pct=90,reflection_pct=90)))
        with self.assertRaises(core.LayoutError):backend.save_component_default(d,'bs',dict(custom=True))


class GeometricBudgets(unittest.TestCase):
    def end(self,p):return p['endpoints'][-1]
    def total(self,requested,available):return core.calculate_chain([self.end(p) for p in requested],[e for p in available for e in p['endpoints']])

    def test_independent_contiguous_paths_sum_local_optics_and_lengths(self):
        a=independent('p100 laha',token='a');b=independent('p50 nd',(100,0,0),token='b')
        result=self.total([b,a],[a,b])
        self.assertEqual(result['geometric_mm'],150);self.assertEqual(result['gdd_fs2'],150)
        self.assertAlmostEqual(result['loss_pct'],90.1);self.assertEqual(result['connection_mode'],'geometry')

    def test_unique_intermediate_is_included_and_identified(self):
        a=independent('p20',token='a');b=independent('p30 laha',(20,0,0),token='b');c=independent('p40',(50,0,0),token='c')
        result=self.total([a,c],[a,b,c]);self.assertEqual(result['geometric_mm'],90)
        auto=[s for s in result['selections'] if s['automatic']]
        self.assertEqual(len(auto),1);self.assertEqual(auto[0]['run_token'],'b')
        self.assertEqual(auto[0]['included_commands'],'p30 laha');self.assertEqual(result['gdd_fs2'],50)

    def test_ambiguous_bridge_requires_explicit_choice(self):
        a=independent('p20',token='a');b=independent('p30',(20,0,0),token='b');d=independent('p30',(20,0,0),token='d');c=independent('p40',(50,0,0),token='c')
        with self.assertRaisesRegex(core.LayoutError,'More than one'):self.total([a,c],[a,b,d,c])
        self.assertEqual(self.total([a,b,c],[a,b,d,c])['geometric_mm'],90)

    def test_position_and_forward_direction_are_both_required(self):
        a=independent('p20');b=independent('p30',(20.0005,0,0))
        self.assertEqual(self.total([a,b],[a,b])['geometric_mm'],50)
        for pos,az in [((20.002,0,0),0),((20,0,0),180),((20,0,0),.002)]:
            c=independent('p30',pos,az)
            with self.subTest(pos=pos,az=az),self.assertRaises(core.LayoutError):self.total([a,c],[a,c])

    def test_independent_reflection_trims_selected_parent_transmission(self):
        a=independent('p100 bs90 p20',token='a');b=independent('p40',(100,0,0),90,token='b')
        result=self.total([a,b],[a,b])
        self.assertEqual(result['geometric_mm'],140);self.assertAlmostEqual(result['loss_pct'],51)
        selected=next(s for s in result['selections'] if s['run_token']=='a')
        self.assertEqual(selected['included_commands'],'p100 bs90 [R]')

    def test_route_instances_with_reused_event_ids_are_not_deduplicated(self):
        a=independent('p20',token='a');b=copy.deepcopy(a)
        for e in b['endpoints']:
            e.update(run_token='b');e['start_state']['position']=[20,0,0];e['state']['position']=[40,0,0]
        result=self.total([a,b],[a,b]);self.assertEqual(result['geometric_mm'],40)
        self.assertEqual(result['contributions'],2)

    def test_dense_connection_search_has_a_work_limit(self):
        paths=[independent('laha',token=str(i)) for i in range(5)]
        with patch.object(core,'MAX_CONNECTION_CANDIDATES',10):
            with self.assertRaisesRegex(core.LayoutError,'Too many coincident endpoints'):
                self.total(paths[:2],paths)


class PreviewFrames(unittest.TestCase):
    def test_nested_native_geometry_rz90_matches_built_component_frame(self):
        d=Design();part=Component(d,'CAD assembly');child=Component(d,'Rotated child');leaf=Component(d,'Leaf')
        local_a=Matrix(core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),33,0,20),(1,2,3))
        local_b=Matrix(core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),0,-40,15),(-2,4,1))
        body=NS(isVisible=True,points=[Point(1,2,3),Point(2,3,4)])
        part.bRepBodies=[];child.bRepBodies=[];leaf.bRepBodies=[body]
        leaf.occurrences=[];child.occurrences=[NS(component=leaf,transform2=local_b)]
        part.occurrences=[NS(component=child,transform2=local_a)]
        # A rooted allOccurrences proxy must not be mistaken for a local child.
        part.allOccurrences=[NS(component=leaf,transform2=Matrix(translation=(99,99,99)))]
        p=layout('p10 r90f50',{'line1:1':dict(token='r90f50',custom=True,component_ref_token='part',shift=[1,2,3],rotation=[12,17,90],reference=[2,1,3])})
        optic=p['optics'][0];d.entities['part']=part
        class Manager:
            def copy(self,b):return copy.deepcopy(b)
            def transform(self,b,m):
                for point in b.points:point.transformBy(m)
                return True
        placement=backend.custom_placement(optic)
        preview=backend.custom_preview_bodies(Manager(),part,placement)[0]
        parent=NS(occurrences=NS(addExistingComponent=lambda c,m:NS(component=c,transform2=m.copy())))
        built=backend.insert_custom_component(d,parent,optic,part,placement)
        for source,shown in zip(body.points,preview.points):
            expected=source.copy();expected.transformBy(local_b);expected.transformBy(local_a);expected.transformBy(built.transform2)
            for k in ('x','y','z'):self.assertAlmostEqual(getattr(expected,k),getattr(shown,k))
        self.assertEqual((body.points[0].x,body.points[0].y,body.points[0].z),(1,2,3))

    def test_failed_preview_transform_is_reported(self):
        body=NS(isVisible=True);part=NS(bRepBodies=[body],occurrences=[])
        with self.assertRaisesRegex(core.LayoutError,'preview transform'):
            backend.custom_preview_bodies(NS(copy=lambda b:object(),transform=lambda *a:False),part,Matrix())


class SchematicExport(unittest.TestCase):
    def test_static_and_interactive_symbols_match_all_families_and_projections(self):
        optics=layout('l50 l-50 r30 r-90 r90f50 bs30 bsc bsc- laha laqu nd tp30d0.5 pol g')['optics']
        for cmd in ('wp20','wp20v','rp10.6h-','bd4v','_bd4v'):
            optics.extend(layout(cmd)['optics'])
        optics.extend(layout('g g',{'line1:0':dict(token='g',shape='cube'),'line1:1':dict(token='g',shape='ball')})['optics'])
        script="const S=require('./schematic.js');let data='';process.stdin.on('data',s=>data+=s);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(data).flatMap(o=>['XY','XZ','YZ'].map(p=>S.symbol(o,S.axesFor(p)))))));"
        result=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(optics).encode(),cwd=ROOT))
        actual=[schematic_svg.symbol(o,axes) for o in optics for axes in ((0,1),(0,2),(1,2))]
        def tree(text):
            def walk(e):
                attrs={k:v.replace('-0)', '0)').replace('(-0 ', '(0 ') for k,v in e.attrib.items()}
                return (e.tag,attrs,[walk(c) for c in e])
            return walk(ET.fromstring('<g>'+text+'</g>'))
        self.assertEqual([tree(s) for s in actual],[tree(s) for s in result])

    def test_export_has_router_grid_shapes_and_world_coordinates(self):
        p=layout('p10 laha p20 tp30d0.5 p10 nd p10 bs30 p20')
        svg=exports.export_svg(p);root=ET.fromstring(svg);ns={'s':'http://www.w3.org/2000/svg'}
        self.assertIn('symbols not to scale',svg);self.assertIn('grid ',svg)
        self.assertEqual(len(root.findall("s:g[@class='map-optic']",ns)),4)
        lines=root.findall('s:line',ns);self.assertEqual(lines[-1].get('data-world-start'),'50,0.5,0')
        self.assertEqual(lines[-1].get('stroke'),core.BEAM_COLORS['red'])

    def test_rotated_document_export_transforms_symbol_normal_and_frame(self):
        optic=layout('bs30')['optics'][0];axes=core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),25,30,90)
        moved=schematic_svg.moved_optic(optic,(10,20,30),axes)
        self.assertEqual(moved['position'],(10.,20.,30.));self.assertEqual(moved['normal'],core.world(axes,optic['normal']))
        self.assertNotEqual(schematic_svg.symbol(optic,(0,1)),schematic_svg.symbol(moved,(0,1)))


if __name__=='__main__':unittest.main()
