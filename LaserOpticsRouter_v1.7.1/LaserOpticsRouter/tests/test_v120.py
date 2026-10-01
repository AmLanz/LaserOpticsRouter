import base64
import ast
import copy
import csv
import io
import json
import math
from pathlib import Path
import sys
import unittest
from dataclasses import asdict
from unittest.mock import patch
from xml.etree import ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import exports
from test_adapter import backend, Design, Component, Occurrence, Matrix, NS


def config(commands):
    c=core.default_config(); c['rows'][0]['commands']=commands
    return c


class ReferenceTests(unittest.TestCase):
    def test_cubes_keep_size_prefix_and_reverse_suffix(self):
        for prefix,diameter in (('',25.4),('-',12.7),('+',50.8)):
            a=core.plan_layout(config(prefix+'bsc p10'))
            b=core.plan_layout(config(prefix+'bsc- p10'))
            self.assertEqual(a['optics'][0]['diameter_mm'],diameter)
            self.assertEqual(b['optics'][0]['diameter_mm'],diameter)
            self.assertEqual(a['optics'][0]['default_key'],b['optics'][0]['default_key'])
            self.assertAlmostEqual(core.dot(a['optics'][0]['output_direction'],b['optics'][0]['output_direction']),-1)
            self.assertEqual(a['rows'][0]['endpoint']['stats']['position'],b['rows'][0]['endpoint']['stats']['position'])

    def test_oap_calibration_from_each_variant_maps_same_local_normal(self):
        variants=('r90f50','r-90f50','_r90f50','_r-90f50')
        for source in variants:
            c=config('p20 '+source)
            source_optic=core.plan_layout(c)['optics'][0]
            # Nontrivial component calibration and nonzero datum.
            template=dict(component_token='part',reference=[7,-3,2],shift=[0,0,0],rotation=[13,-27,31])
            c['component_defaults']={source:template}
            normals=[]
            for target in variants:
                c['rows'][0]['commands']='p20 '+target
                optic=core.plan_layout(c)['optics'][0]
                self.assertTrue(optic['settings']['custom'])
                self.assertEqual(optic['default_key'],'r90f50')
                origin,axes=core.custom_transform(optic)
                hit=origin
                self.assertLess(core.norm(core.sub(axes[0],optic['normal'])),1e-10)
                self.assertLess(core.norm(core.sub(hit,optic['position'])),1e-10)
                normals.append([core.dot(axis,optic['normal']) for axis in axes])
            for n in normals[1:]:
                for a,b in zip(n,normals[0]):self.assertAlmostEqual(a,b)

    def test_oap_key_uses_actual_3d_bend(self):
        c=config('r90v30f50'); c['source']['elevation']=10
        o=core.plan_layout(c)['optics'][0]
        self.assertNotEqual(o['default_key'],'r90f50')
        self.assertAlmostEqual(float(o['default_key'][1:-3]),o['bend_deg'],places=7)

    def test_reference_values_do_not_change_spatial_beam(self):
        c=config('p100 l50 p20 bs90 p30')
        before=core.plan_layout(c)
        c['optic_overrides']={'line1:1':dict(token='l50',budget=dict(loss_pct=10,gdd_fs2=80,n=1.5,thickness_mm=4)),
                              'line1:3':dict(token='bs90',budget=dict(transmission_pct=60,reflection_pct=30,gdd_t_fs2=-20,gdd_r_fs2=40,n_t=1.5,thickness_t_mm=6))}
        after=core.plan_layout(c)
        s=after['rows'][0]['endpoint']['stats']
        self.assertAlmostEqual(s['loss_pct'],46)
        self.assertAlmostEqual(s['gdd_fs2'],60)
        self.assertAlmostEqual(s['optical_path_mm'],155)
        reflected=after['rows'][0]['ports'][0]['stats']
        self.assertAlmostEqual(reflected['loss_pct'],73)
        self.assertAlmostEqual(reflected['gdd_fs2'],120)
        self.assertAlmostEqual(reflected['optical_path_mm'],122)
        for a,b in zip(before['endpoints'],after['endpoints']):
            for k in ('position','direction','diameter_mm','half_angle_mrad'):
                self.assertEqual(a['stats'][k],b['stats'][k])

    def test_custom_optic_zero_reference_defaults(self):
        c=config('l50')
        c['optic_overrides']['line1:0']=dict(token='l50',custom=True,component_token='custom')
        s=core.plan_layout(c)['endpoints'][0]['stats']
        self.assertEqual(s['loss_pct'],0);self.assertEqual(s['gdd_fs2'],0)
        self.assertEqual(s['optical_path_mm'],0)

    def test_invalid_budget_properties_rejected(self):
        for command,b in [('l50',{'loss_pct':101}),('bsc',{'transmission_pct':70,'reflection_pct':70}),('l50',{'n':0,'thickness_mm':3}),('l50',{'n':-1})]:
            c=config(command);c['optic_overrides']['line1:0']=dict(token=command,budget=b)
            with self.assertRaises(core.LayoutError):core.plan_layout(c)

    def test_lor2_and_legacy_lor1(self):
        p=core.plan_layout(config('p100 l50 p20'))
        packet=p['endpoints'][0]['endpoint'];state,_=core.decode_endpoint(packet)
        self.assertTrue(packet.startswith('LOR2:'));self.assertEqual(asdict(state),p['endpoints'][0]['state'])
        legacy=asdict(core.BeamState())
        for k in ('extra_opl_mm','throughput','gdd_fs2','trace','link'):legacy.pop(k)
        data=dict(format='LaserOpticsRouter.Endpoint',version=1,name='Old',state=legacy)
        packet='LOR1:'+base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        restored,_=core.decode_endpoint(packet)
        self.assertEqual(restored.trace,[]);self.assertEqual(restored.throughput,1)

    def test_connected_calculator_deduplicates_and_rejects_wrong_arm(self):
        a=core.plan_layout(config('p100 bsc p20'))
        branch=a['rows'][0]['ports'][0]
        c=config('p50 l50 p10');c['rows'][0].update(start_mode='snapshot',endpoint=branch['endpoint'])
        b=core.plan_layout(c)['endpoints'][0]
        summary=core.calculate_chain([branch,b,branch])
        self.assertAlmostEqual(summary['geometric_mm'],160)
        self.assertAlmostEqual(summary['loss_pct'],100*(1-.49*.99))
        with self.assertRaisesRegex(core.LayoutError,'one connected arm'):
            core.calculate_chain([a['rows'][0]['endpoint'],b])
        local=core.calculate_chain([b])
        self.assertEqual(local['geometric_mm'],60)

    def test_calculator_rejects_missing_middle_path(self):
        endpoints=[];c=config('p10')
        for _ in range(3):
            p=core.plan_layout(c);endpoints.append(p['endpoints'][0])
            c=config('p10');c['rows'][0].update(start_mode='snapshot',endpoint=endpoints[-1]['endpoint'])
        with self.assertRaisesRegex(core.LayoutError,'connecting path'):
            core.calculate_chain([endpoints[0],endpoints[2]])

    def test_calculator_rejects_geometry_change_even_when_budgets_equal(self):
        c=config('p100 r90 p20');old=core.plan_layout(c)['endpoints'][0]
        tail=config('p30');tail['rows'][0].update(start_mode='snapshot',endpoint=old['endpoint'])
        continuation=core.plan_layout(tail)['endpoints'][0]
        c['rows'][0]['commands']='p100 r-90 p20';new=core.plan_layout(c)['endpoints'][0]
        with self.assertRaisesRegex(core.LayoutError,'different source histories'):
            core.calculate_chain([new,continuation])

    def test_csv_roundtrip_editable_values_and_formula_text(self):
        c=config('+l50 p100 bsc- p20');c['run_name']='=not a formula'
        c['optic_overrides']['line1:0']=dict(token='+l50',budget=dict(gdd_fs2=-123))
        before=core.plan_layout(c);text=exports.export_csv(before)
        self.assertIn("'=not a formula",text);self.assertIn("'+l50",text)
        restored=exports.import_csv(text,document_id=c['document_id'])
        after=core.plan_layout(restored)
        self.assertEqual(restored['run_name'],c['run_name'])
        self.assertEqual(restored['rows'][0]['commands'],c['rows'][0]['commands'])
        self.assertEqual(after['endpoints'][-1]['stats'],before['endpoints'][-1]['stats'])
        self.assertNotEqual(restored['route_id'],c['route_id'])

    def test_csv_cross_document_requires_component_reselection(self):
        c=config('l50 p20');c['optic_overrides']['line1:0']=dict(token='l50',custom=True,component_token='private-token',reference=[1,2,3])
        restored=exports.import_csv(exports.export_csv(core.plan_layout(c)),document_id='another-document')
        self.assertFalse(restored['optic_overrides']['line1:0']['component_token'])
        self.assertNotIn('reference',restored['optic_overrides']['line1:0'])

    def test_csv_clone_rebinds_internal_branch_history(self):
        c=config('p100 bsc p30');p=core.plan_layout(c)
        c['rows'].append(dict(id='branch',name='Branch',commands='p40',start_mode='snapshot',endpoint=p['rows'][0]['ports'][0]['endpoint']))
        cloned=core.plan_layout(exports.import_csv(exports.export_csv(core.plan_layout(c)),document_id='new'))
        result=core.calculate_chain([cloned['rows'][0]['ports'][0],cloned['rows'][1]['endpoint']])
        self.assertEqual(result['geometric_mm'],140)

    def test_svg_projects_coordinates_and_escapes_labels(self):
        c=config('p100 r90v30 p50');c['run_name']='Test <&>'
        plan=core.plan_layout(c)
        for projection in ('XY','XZ','YZ'):
            svg=exports.export_svg(plan,projection)
            root=ET.fromstring(svg);ns={'s':'http://www.w3.org/2000/svg'}
            self.assertEqual(len(root.findall('s:line',ns)),2)
            self.assertEqual(root.attrib['viewBox'],'0 0 900 320')
            self.assertIn('millimetres',root.find('s:desc',ns).text)
            self.assertEqual(root.findall('s:line',ns)[0].attrib['data-world-end'],'100,0,0')
            self.assertIn('Test <&>',root.find('s:title',ns).text)


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.d=Design();self.d.attributes.add(backend.GROUP,'document_id','doc')

    def save(self,c,name,transform=None):
        c['document_id']='doc';c['route_id']=name
        p=core.plan_layout(c);comp=Component(self.d,name)
        for key,value in [('run_id',name),('revision','1'),('settings',json.dumps(core.snapshot_config(p))),('endpoints',json.dumps(p['endpoints']))]:
            comp.attributes.add(backend.GROUP,key,value)
        o=Occurrence(self.d,name,comp,transform);self.d.entities[name]=o
        return o

    def chain(self):
        self.parent=self.save(config('p100'),'parent')
        end=backend.saved_endpoints(self.d)['items'][0]
        c=config('p40 r90 p20');c['rows'][0].update(start_mode='snapshot',endpoint=end['endpoint'])
        self.child=self.save(c,'child')

    def test_default_keeps_downstream_pose_and_marks_stale(self):
        self.chain();before=self.child.transform2.copy()
        self.parent.transform2=Matrix(translation=(1,2,0))
        backend.refresh_dependencies(None,self.d)
        run=next(r for r in backend.saved_endpoints(self.d)['runs'] if r['run_id']=='child')
        self.assertTrue(run['stale']);self.assertEqual(self.child.transform2.translation,before.translation)
        self.assertNotEqual(backend._attribute(self.child.component,'stale_display'),'true')

    def test_calculator_rejects_manually_moved_source_with_old_continuation(self):
        self.chain();self.parent.transform2=Matrix(translation=(1,2,0))
        items=backend.saved_endpoints(self.d)['items']
        with self.assertRaisesRegex(core.LayoutError,'moved or its beam state changed'):
            core.calculate_chain(items)

    def test_opt_in_follow_maps_complete_route_and_refreshes_origin(self):
        self.chain()
        self.parent.transform2=Matrix(((0,1,0),(-1,0,0),(0,0,1)),(1,2,3))
        backend.refresh_dependencies(None,self.d,follow=True)
        data=backend.saved_endpoints(self.d)
        run=next(r for r in data['runs'] if r['run_id']=='child')
        self.assertFalse(run['stale'])
        for a,b in zip(self.child.transform2.translation,(1,2,3)):self.assertAlmostEqual(a,b)
        for column,expected in zip(self.child.transform2.axes,self.parent.transform2.axes):
            for a,b in zip(column,expected):self.assertAlmostEqual(a,b)
        end=next(e for e in data['items'] if e['run_id']=='child')
        for a,b in zip(end['stats']['position'],(-10,160,30)):self.assertAlmostEqual(a,b)

    def test_deleted_parent_and_changed_beam_require_manual_review(self):
        self.chain();self.parent.deleteMe()
        backend.refresh_dependencies(None,self.d,follow=True)
        data=backend.saved_endpoints(self.d)
        self.assertTrue(data['runs'][0]['stale'])
        self.assertEqual(self.child.transform2.translation,(0,0,0))

    def test_changed_envelope_is_not_moved_as_if_it_were_rigid(self):
        self.chain()
        records=json.loads(backend._attribute(self.parent.component,'endpoints'))
        records[-1]['state']['y']=7
        self.parent.component.attributes.add(backend.GROUP,'endpoints',json.dumps(records))
        backend.refresh_dependencies(None,self.d,follow=True)
        run=next(r for r in backend.saved_endpoints(self.d)['runs'] if r['run_id']=='child')
        self.assertFalse(run['stale']);self.assertTrue(run['needs_refresh'])
        self.assertEqual(self.child.transform2.translation,(0,0,0))

    def test_internal_branch_does_not_become_stale_just_from_own_revision(self):
        c=config('p100 bsc p20');c['route_id']='same';c['document_id']='doc'
        p=core.plan_layout(c);port=p['rows'][0]['ports'][0]
        state=core.state_from_dict(port['state'])
        state.link=core.endpoint_link(state,'doc','same',1,port['id'])
        c['rows'].append(dict(id='branch',name='Branch',commands='p30',start_mode='snapshot',endpoint=core.encode_endpoint(state)))
        o=self.save(c,'same');o.component.attributes.add(backend.GROUP,'revision','2')
        self.assertFalse(backend.saved_endpoints(self.d)['runs'][0]['stale'])

    def test_follow_is_limited_to_descendants_of_edited_route(self):
        self.chain()
        self.parent.transform2=Matrix(translation=(1,2,0))
        backend.refresh_dependencies(None,self.d,follow=True,root_run_id='unrelated')
        self.assertEqual(self.child.transform2.translation,(0,0,0))
        self.assertTrue(next(r for r in backend.saved_endpoints(self.d)['runs'] if r['run_id']=='child')['stale'])
        backend.refresh_dependencies(None,self.d,follow=True,root_run_id='parent')
        self.assertFalse(next(r for r in backend.saved_endpoints(self.d)['runs'] if r['run_id']=='child')['stale'])


class CommandLifecycleTests(unittest.TestCase):
    def classes(self):
        path=Path(__file__).resolve().parents[1]/'LaserOpticsRouter.py'
        names=('BuildExecute','BuildDestroyed')
        nodes=[n for n in ast.parse(path.read_text()).body if (isinstance(n,ast.ClassDef) and n.name in names) or (isinstance(n,ast.FunctionDef) and n.name == 'release_handlers')]
        sent=[]
        context=dict(adsk=NS(core=NS(CommandEventHandler=object)),core=core,backend=NS(),
                     _handlers=[],_operation_active=True,_pending_build=None,_last_build_error='',_doc_key='doc',
                     send=lambda action,data:sent.append((action,data)),palette=lambda:None,
                     diagnostic=lambda text:'diagnostic.log',_app=NS(log=lambda text:None),
                     design=lambda:None,__name__='lifecycle_test')
        import traceback
        context['traceback']=traceback
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),context)
        return context,sent

    def test_failure_aborts_transaction_and_reports_only_after_destroy(self):
        c,sent=self.classes();operation={};args=NS(executeFailed=False)
        c['BuildExecute'](operation).notify(args)
        self.assertTrue(args.executeFailed);self.assertEqual(sent,[])
        c['BuildDestroyed'](operation).notify(NS())
        self.assertEqual(sent[0][0],'build_failed');self.assertFalse(c['_operation_active'])
        self.assertEqual(operation,{})

    def test_manage_completion_keeps_its_own_reply_type(self):
        c,sent=self.classes();operation=dict(success_action='managed',failure_action='manage_failed',success={'operation':'refresh_status'})
        c['BuildDestroyed'](operation).notify(NS())
        self.assertEqual(sent,[('managed',{'operation':'refresh_status'})])


if __name__=='__main__':unittest.main()
