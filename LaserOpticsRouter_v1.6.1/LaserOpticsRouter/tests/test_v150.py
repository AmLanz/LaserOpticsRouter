"""Generic optics, display colors and exact schematic/budget selections."""
import base64
import copy
import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import core
import exports
import workflow
import test_adapter as adapter
from test_adapter import backend


def layout(commands, overrides=None, color='red'):
    c=core.default_config();c['rows'][0]['commands']=commands;c['source']['color']=color
    c['optic_overrides']=overrides or {}
    return core.plan_layout(c)


class GenericOptics(unittest.TestCase):
    def test_generic_tokens_and_modifiers(self):
        for command,size,flip in [('g','normal',False),('+g','large',False),('-g','small',False),('fg','normal',True)]:
            t=core.parse_commands(command)[0]
            self.assertEqual((t['kind'],t['size'],t['visual_flip']),('generic',size,flip))
            self.assertEqual(core.default_key(t),command.replace('f',''))
        with self.assertRaises(core.LayoutError):core.parse_commands('_g')

    def test_generic_budget_changes_totals_but_not_beam_propagation(self):
        p=layout('p10 g p20',{'line1:1':dict(token='g',shape='cube',beam_color='blue',budget=dict(loss_pct=10,gdd_fs2=-45,n=1.6,thickness_mm=3))})
        end=p['endpoints'][-1]['stats']
        self.assertEqual(end['path_mm'],30)
        self.assertAlmostEqual(end['optical_path_mm'],31.8)
        self.assertAlmostEqual(end['loss_pct'],10)
        self.assertEqual(end['gdd_fs2'],-45)
        self.assertEqual(end['diameter_mm'],5)
        self.assertEqual(p['optics'][0]['shape'],'cube')
        self.assertEqual([s['state'].color for s in p['segments']],['red','blue'])
        self.assertEqual(p['endpoints'][-1]['state']['wavelength_nm'],800)

    def test_shape_color_and_dimensions_are_validated(self):
        for value in ({'shape':'pyramid'},{'beam_color':'ultraviolet'},{'depth_mm':0},{'depth_mm':float('nan')}):
            with self.assertRaises(core.LayoutError):layout('g p10',{'line1:0':dict(token='g',**value)})
        with self.assertRaises(core.LayoutError):layout('p10',color='inherit')

    def test_default_generic_is_lossless_and_inherits_color(self):
        p=layout('g p10',color='green');s=p['endpoints'][-1]['state']
        self.assertEqual(s['color'],'green');self.assertEqual(s['throughput'],1);self.assertEqual(s['gdd_fs2'],0)

    def test_pair_colors_only_change_on_the_encountered_ray(self):
        p=layout('g wp20 p10 g p20',{
            'line1:0':dict(token='g',beam_color='blue'),
            'line1:3':dict(token='g',beam_color='green')})
        self.assertEqual([(s['secondary'],s['state'].color) for s in p['segments']],
                         [(False,'blue'),(True,'blue'),(False,'green'),(True,'blue')])
        secondary=next(e for e in p['endpoints'] if 'secondary end' in e['name'])
        self.assertEqual(secondary['included_commands'],'g wp20 [R] p10 p20')
        self.assertEqual(p['endpoints'][-1]['included_commands'],'g wp20 [T] p10 g p20')

    def test_color_survives_endpoint_and_csv_roundtrip(self):
        p=layout('g p15',{'line1:0':dict(token='g',shape='ball',beam_color='purple')})
        state,_=core.decode_endpoint(p['endpoints'][-1]['endpoint']);self.assertEqual(state.color,'purple')
        c=exports.import_csv(exports.export_csv(p));q=core.plan_layout(c)
        self.assertEqual(q['optics'][0]['shape'],'ball')
        self.assertEqual(q['endpoints'][-1]['state']['color'],'purple')
        c=core.default_config();c['rows'][0].update(start_mode='snapshot',endpoint=p['endpoints'][-1]['endpoint'],commands='p20')
        self.assertEqual(core.plan_layout(c)['endpoints'][-1]['state']['color'],'purple')

    def test_old_endpoint_without_color_is_still_readable(self):
        data=asdict(core.BeamState());data.pop('color')
        payload=dict(format='LaserOpticsRouter.Endpoint',version=1,name='Legacy',state=data)
        packet='LOR1:'+base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        state,_=core.decode_endpoint(packet);self.assertEqual(state.color,'red')

    def test_display_color_does_not_rewrite_existing_budget_trace_identity(self):
        a=asdict(core.BeamState());b=dict(a,color='blue')
        self.assertEqual(core.state_fingerprint(a),core.state_fingerprint(b))
        old=dict(a);old.pop('color');self.assertEqual(core.state_fingerprint(a),core.state_fingerprint(old))

    def test_three_native_placeholder_shapes_use_correct_dimensions(self):
        manager=NS(createSphere=lambda point,radius:('sphere',radius))
        for shape in ('disc','cube','ball'):
            optic=layout('g',{'line1:0':dict(token='g',shape=shape,diameter_mm=20,depth_mm=4)})['optics'][0]
            with patch.object(backend,'cylinder',return_value='disc') as cylinder,patch.object(backend,'box',return_value='cube') as box:
                result=backend.optic_bodies(manager,optic,{})
                self.assertEqual(result[0][2],'generic')
                if shape=='disc':self.assertEqual(cylinder.call_args.args[1:],((-2.,0.,0.),10.,(2.,0.,0.),10.))
                elif shape=='cube':self.assertEqual(box.call_args.args[-1],(20,20,20))
                else:self.assertEqual(result[0][1],('sphere',1))

    def test_draft_wire_groups_preserve_color_and_distinguish_cube_ball_disc(self):
        counts={}
        for shape in ('disc','cube','ball'):
            p=layout('g p20',{'line1:0':dict(token='g',shape=shape,beam_color='blue')})
            wire=workflow.wire_geometry(p);self.assertEqual(len(wire['beam-blue']),2)
            self.assertTrue(wire['envelope-blue']);counts[shape]=len(wire['optic'])
        self.assertEqual(counts,dict(disc=50,cube=26,ball=146))

    def test_source_and_generic_colors_reach_public_schematic_and_svg(self):
        p=layout('p10 g p20',{'line1:1':dict(token='g',beam_color='blue')},color='green')
        self.assertEqual([l['color'] for l in core.public_plan(p)['lines']],['green','blue'])
        svg=exports.export_svg(p);self.assertIn(core.BEAM_COLORS['blue'],svg);self.assertIn(core.BEAM_COLORS['green'],svg)


class SchematicContributions(unittest.TestCase):
    def test_splitter_port_lists_only_encountered_optics_and_propagation(self):
        p=layout('p100 bsc p200 l50 p20')
        port=next(e for e in p['endpoints'] if e['kind']=='reflected')
        self.assertEqual(port['included_commands'],'p100 bsc [R]')
        self.assertEqual(p['endpoints'][-1]['included_commands'],'p100 bsc [T] p200 l50 p20')
        self.assertEqual([e['kind'] for e in port['included']],['propagate','bsc'])

    def test_calculator_returns_exact_resolved_path_for_the_requested_parent_color(self):
        p=layout('p100 bsc p200')
        port=next(e for e in p['endpoints'] if e['kind']=='reflected')
        c=core.default_config();c['rows'][0].update(start_mode='snapshot',endpoint=port['endpoint'],commands='p40')
        child=core.plan_layout(c)['endpoints'][-1]
        def saved(e,run):return dict(e,id=run+'|'+e['id'],endpoint_id=e['id'],run_token=run)
        parent_end=saved(p['endpoints'][-1],'parent');parent_port=saved(port,'parent');child=saved(child,'child')
        result=core.calculate_chain([parent_end,child],[parent_end,parent_port,child])
        self.assertEqual(result['geometric_mm'],140)
        selected=result['selections'][0]
        self.assertEqual(selected['requested_id'],parent_end['id']);self.assertEqual(selected['resolved_id'],parent_port['id'])
        self.assertEqual(selected['included_commands'],'p100 bsc [R]')
        self.assertEqual(len(selected['event_ids']),2)
        self.assertNotIn(p['segments'][-1]['event_ids'][0],selected['event_ids'])

    def test_combined_pair_draws_one_line_with_both_budget_event_identities(self):
        p=layout('bd4h p20 _bd4h p30')
        last=core.public_plan(p)['lines'][-1]
        self.assertEqual(len(last['event_ids']),2)
        secondary=next(e for e in p['endpoints'] if 'combined end (secondary' in e['name'])
        ids={e['id'] for e in secondary['state']['trace']}
        self.assertTrue(ids.intersection(last['event_ids']))

    def test_previous_line_end_includes_the_full_source_path_for_highlighting(self):
        c=core.default_config();c['rows']=[dict(id='a',name='A',commands='p20 l50',start_mode='source'),dict(id='b',name='B',commands='p40',start_mode='previous')]
        p=core.plan_layout(c);end=p['rows'][1]['endpoint']
        events={e['id'] for e in end['state']['trace']}
        self.assertTrue(all(events.intersection(l['event_ids']) for l in core.public_plan(p)['lines']))
        self.assertEqual(end['included_commands'],'p40')

    def test_reported_route_has_five_mm_endpoint_and_a_distinct_intermediate_focus(self):
        p=layout('p100 l50 p25 p75 l50 p50 p50 r90 p50 _r90f50 p50 pol p50 l50 p50 wp20 p50 r-80 p50')
        self.assertTrue(all(e['stats']['diameter_mm']==5 for e in p['endpoints']))
        self.assertEqual(p['rows'][0]['steps'][10]['diameter_mm'],0)
        self.assertEqual(p['rows'][0]['steps'][10]['status'],'geometric focus')

    def test_saved_schematic_transforms_positions_normals_and_directions_to_world(self):
        fixture=adapter.AdapterTests();fixture.setUp()
        before=copy.deepcopy(fixture.plan)
        result=backend.document_schematic(fixture.design)
        self.assertEqual(result['lines'][0]['start'],[100.,200.,30.])
        self.assertEqual(result['lines'][0]['end'],[100.,300.,30.])
        optic=result['optics'][0]
        self.assertAlmostEqual(optic['input_direction'][0],0);self.assertAlmostEqual(optic['input_direction'][1],1)
        self.assertEqual(optic['run_token'],'old')
        self.assertEqual(fixture.plan,before);self.assertEqual(fixture.design.log,[])


if __name__=='__main__':unittest.main()
