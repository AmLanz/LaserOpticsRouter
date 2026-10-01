"""Planning/CAD isolation, bounded native work, link checks and cancellation.

These exercise the adapter with API doubles; Fusion's kernel and Undo remain
native acceptance checks, not guarantees inferred from these tests.
"""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
from test_adapter import backend, Design, Component, Occurrence, Matrix, Point
import test_v120 as lifecycle_tests


def assigned_plan(use_cad=False):
    c = core.default_config()
    c['rows'][0]['commands'] = 'p10 l50 p20 g p30'
    c['options']['use_assigned_components'] = use_cad
    c['optic_overrides'] = {
        'line1:1': dict(token='l50', custom=True, component_token='lens-source'),
        'line1:3': dict(token='g', custom=True, component_token='generic-source', shape='cube')}
    return core.plan_layout(c)


class ComponentPlanning(unittest.TestCase):
    def test_planning_geometry_does_not_resolve_missing_assignments(self):
        p = assigned_plan()
        with patch.object(backend.adsk.fusion, 'TemporaryBRepManager', NS(get=lambda:None), create=True), \
             patch.object(backend, 'segment_bodies', return_value=[]), \
             patch.object(backend, 'optic_bodies', side_effect=lambda m,o,s:[(o['id'], object(), o['kind'])]), \
             patch.object(backend, 'resolve_component', side_effect=AssertionError('No CAD access in planning mode')):
            result = backend.temporary_geometry(p, Design())
        self.assertEqual(result['custom'], [])
        self.assertEqual([x[0] for x in result['optics']], ['line1:1','line1:3'])

    def test_cad_mode_resolves_each_assignment_without_copying_bodies(self):
        p, component = assigned_plan(True), object()
        with patch.object(backend.adsk.fusion, 'TemporaryBRepManager', NS(get=lambda:None), create=True), \
             patch.object(backend, 'segment_bodies', return_value=[]), \
             patch.object(backend, 'optic_bodies', side_effect=AssertionError('Assigned optics use instances')), \
             patch.object(backend, 'resolve_component', return_value=component) as resolve:
            result = backend.temporary_geometry(p, Design())
        self.assertEqual(resolve.call_count,2)
        self.assertEqual(len(result['custom']),2)
        self.assertTrue(all(part is component for _,part in result['custom']))

    def test_planning_build_snapshot_retains_assignment_and_link_metadata(self):
        p=assigned_plan();p['optics'][0]['settings']['component_linked']=True
        saved=core.snapshot_config(p)
        self.assertFalse(saved['options']['use_assigned_components'])
        self.assertEqual(saved['optic_overrides']['line1:1']['component_token'],'lens-source')
        self.assertTrue(saved['optic_overrides']['line1:1']['component_linked'])
        restored=core.plan_layout(saved)
        self.assertTrue(restored['optics'][0]['settings']['custom'])

    def test_old_saved_settings_keep_the_previous_cad_build_behavior(self):
        import json
        d=Design();c=core.default_config();del c['options']['use_assigned_components']
        d.attributes.add(backend.GROUP,'last_settings',json.dumps(c))
        self.assertTrue(backend.load_settings(d)['options']['use_assigned_components'])
        self.assertFalse(backend.load_settings(Design())['options']['use_assigned_components'])

    def test_prepare_cancel_stops_before_next_geometry_operation(self):
        d=Design(); calls=[]
        def progress(label,done,total):
            if done==1: raise core.LayoutError('Operation cancelled.')
        with patch.object(backend.adsk.fusion,'TemporaryBRepManager',NS(get=lambda:None),create=True), \
             patch.object(backend,'segment_bodies',side_effect=lambda *a:calls.append('segment') or []):
            with self.assertRaisesRegex(core.LayoutError,'cancelled'):
                backend.temporary_geometry(assigned_plan(),d,progress=progress)
        self.assertEqual(calls,['segment']);self.assertEqual(d.log,[])

    def test_linked_instance_requires_external_reference_on_result(self):
        d=Design();p=assigned_plan(True);optic=p['optics'][0];component=Component(d,'lens')
        source=Occurrence(d,'lens-source',component);source.isReferencedComponent=True
        d.entities[source.entityToken]=source
        result=NS(isReferencedComponent=True)
        parent=NS(occurrences=NS(addExistingComponent=Mock(return_value=result)))
        self.assertIs(backend.insert_custom_component(d,parent,optic,component,Matrix()),result)
        result.isReferencedComponent=False
        with self.assertRaisesRegex(core.LayoutError,'did not preserve'):
            backend.insert_custom_component(d,parent,optic,component,Matrix())
        self.assertTrue(source.isReferencedComponent)

    def test_saved_link_flag_is_checked_when_original_occurrence_is_missing(self):
        optic=assigned_plan(True)['optics'][0];optic['settings']['component_linked']=True
        parent=NS(occurrences=NS(addExistingComponent=lambda *a:NS(isReferencedComponent=False)))
        with self.assertRaisesRegex(core.LayoutError,'external component link'):
            backend.insert_custom_component(Design(),parent,optic,object(),Matrix())

    def test_selection_guard_only_changes_the_inserted_instance(self):
        source=NS(isSelectable=True);instance=NS(isSelectable=True);warnings=[]
        backend.protect_inserted_component(instance,warnings)
        self.assertFalse(instance.isSelectable);self.assertTrue(source.isSelectable);self.assertEqual(warnings,[])
        class Refused:
            @property
            def isSelectable(self): return True
            @isSelectable.setter
            def isSelectable(self,value): raise RuntimeError('not available')
        backend.protect_inserted_component(Refused(),warnings)
        self.assertIn('could not',warnings[0])

    def test_build_batches_solids_and_yields_between_sequential_component_insertions(self):
        p=assigned_plan(True);d=Design();component=Component(d,'part')
        geometry=dict(beam=[('beam',object(),'beam')]*85,optics=[],
                      custom=[(o,component) for o in p['optics']],warnings=[])
        batches=[];events=[]
        def add(c,design,entries): batches.append(len(entries));events.append('batch');return []
        def progress(label,done,total): events.append(label)
        with patch.object(backend,'add_bodies',side_effect=add),patch.object(backend,'refresh_dependencies'):
            backend.build(None,d,p,prepared=geometry,progress=progress)
        self.assertEqual(batches,[40,40,5])
        self.assertEqual(sum(x.startswith('Placed ') for x in events),2)
        self.assertLess(events.index('Placed '+p['optics'][0]['label']),events.index('Insert custom optic '+p['optics'][1]['label']))
        instances=[e for e in d.entities.values() if isinstance(e,Occurrence) and e.component is component]
        self.assertTrue(all(not e.isSelectable for e in instances))

    def test_native_cancel_uses_execute_failed_and_reports_after_command_destroy(self):
        context,sent=lifecycle_tests.CommandLifecycleTests().classes();context['backend']=backend
        context['_pending_build']=dict(doc_key='doc',plan=assigned_plan(),geometry={})
        args=NS(executeFailed=False);state={}
        with patch.object(backend,'build',side_effect=core.LayoutError('Operation cancelled.')):
            context['BuildExecute'](state).notify(args)
        self.assertTrue(args.executeFailed);self.assertEqual(sent,[])
        context['BuildDestroyed'](state).notify(NS())
        self.assertEqual(sent[0][0],'build_failed');self.assertIn('cancelled',sent[0][1]['message'])

    def test_direct_model_batches_keep_prior_bodies_and_name_each_new_body(self):
        class Bodies:
            def __init__(self):self.items=[]
            @property
            def count(self):return len(self.items)
            def add(self,temporary):
                body=NS(attributes=NS(add=lambda *a:None));self.items.append(body);return body
            def item(self,index):return self.items[index]
        component=NS(bRepBodies=Bodies());design=NS(designType=0)
        first=[('part'+str(i),object(),'lens') for i in range(40)]
        second=[('next'+str(i),object(),'mirror') for i in range(5)]
        a=backend.add_bodies(component,design,first);b=backend.add_bodies(component,design,second)
        self.assertEqual(component.bRepBodies.count,45)
        self.assertEqual([body.name for body,_ in a],[e[0] for e in first])
        self.assertEqual([body.name for body,_ in b],[e[0] for e in second])

    def test_cancellation_during_appearance_is_not_swallowed_or_old_route_deleted(self):
        d=Design();p=assigned_plan();old=Occurrence(d,'old',Component(d,'previous'))
        old.component.attributes.add(backend.GROUP,'run_id','previous');d.entities['old']=old
        geometry=dict(beam=[('beam',object(),'beam')],optics=[],custom=[],warnings=[])
        def progress(label,done,total):
            if label.startswith('Apply beam'):raise core.LayoutError('Operation cancelled.')
        with patch.object(backend,'add_bodies',return_value=[(NS(),'beam')]), \
             patch.object(backend,'appearance',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'cancelled'):
                backend.build(None,d,p,'old',prepared=geometry,progress=progress)
        self.assertTrue(old.isValid)
        self.assertFalse(any(action=='delete' for action,_ in d.log))


class ComponentPreview(unittest.TestCase):
    def fixture(self):
        group=NS(deleted=False,bodies=[],lines=[])
        def lines(*args):
            graphic=NS();group.lines.append(graphic);return graphic
        def solid(body):
            group.bodies.append(body);return NS(setOpacity=lambda *a:None)
        group.addLines=lines;group.addBRepBody=solid;group.deleteMe=lambda:setattr(group,'deleted',True)
        d=NS(rootComponent=NS(customGraphicsGroups=NS(add=lambda:group)))
        component=NS(bRepBodies=[NS(isVisible=True,points=[Point(0,0,0),Point(0,0,1)])],allOccurrences=[])
        class Manager:
            def copy(self,body): return copy.deepcopy(body)
            def transform(self,body,matrix):
                for p in body.points:p.transformBy(matrix)
        api=NS(core=NS(Color=NS(create=lambda *a:a),Matrix3D=Matrix,Point3D=Point,Vector3D=backend.adsk.core.Vector3D),
               fusion=NS(TemporaryBRepManager=NS(get=Manager),CustomGraphicsCoordinates=NS(create=lambda x:x),
                         CustomGraphicsSolidColorEffect=NS(create=lambda x:x)))
        return group,d,component,api

    def test_selected_cad_copies_only_one_component_over_a_draft_and_keeps_source(self):
        group,d,component,api=self.fixture();p=assigned_plan()
        before=[(x.x,x.y,x.z) for x in component.bRepBodies[0].points]
        with patch.object(backend,'adsk',api),patch.object(backend,'resolve_component',return_value=component) as resolve, \
             patch.object(backend,'temporary_geometry',side_effect=AssertionError('No whole-route solids')):
            result,_=backend.preview(d,p,quality='selected',optic_id='line1:3')
        self.assertIs(result,group);self.assertEqual(len(group.bodies),1)
        self.assertEqual(resolve.call_args.args[1]['id'],'line1:3')
        self.assertEqual(len(group.lines),6)  # three draft groups, three datum axes
        self.assertEqual([(x.x,x.y,x.z) for x in component.bRepBodies[0].points],before)

    def test_selected_cad_cancellation_cleans_the_temporary_graphics(self):
        group,d,component,api=self.fixture()
        with patch.object(backend,'adsk',api),patch.object(backend,'resolve_component',return_value=component):
            with self.assertRaisesRegex(core.LayoutError,'cancelled'):
                backend.preview(d,assigned_plan(),quality='selected',optic_id='line1:1',
                                progress=Mock(side_effect=core.LayoutError('cancelled')))
        self.assertTrue(group.deleted);self.assertEqual(len(component.bRepBodies),1)

    def test_preview_complexity_limit_is_checked_before_copy(self):
        component=NS(bRepBodies=[NS(isVisible=True,faces=NS(count=100001))],allOccurrences=[])
        manager=NS(copy=Mock(),transform=Mock())
        with self.assertRaisesRegex(core.LayoutError,'too detailed'):
            list(backend.iter_custom_preview_bodies(manager,component,Matrix()))
        manager.copy.assert_not_called()


class Progress(unittest.TestCase):
    def test_cancel_and_document_guard_always_close_dialog(self):
        for cancelled,guard in ((True,lambda:True),(False,lambda:False)):
            dialog=NS(show=Mock(),hide=Mock(),wasCancelled=cancelled)
            pump=Mock();ui=NS(createProgressDialog=lambda:dialog)
            with patch.object(backend.adsk,'doEvents',pump,create=True):
                with self.assertRaisesRegex(core.LayoutError,'cancelled'):
                    with backend.OperationProgress(ui,'Build',guard) as report:report('Inserting',1,2)
            dialog.hide.assert_called_once();pump.assert_called_once()


if __name__=='__main__': unittest.main()
