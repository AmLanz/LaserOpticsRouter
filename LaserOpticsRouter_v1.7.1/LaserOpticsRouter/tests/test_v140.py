"""Workflow regressions, with native Fusion boundaries explicitly substituted."""
import ast
import copy
import json
import math
import re
import sys
import tempfile
import unittest
from dataclasses import asdict
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core
import exports
import workflow
from test_adapter import backend, Matrix
import test_v120 as old_tests


class StableSteps(unittest.TestCase):
    def config(self):
        c = core.default_config()
        c['rows'][0].update(commands='p50 l100 p50 bsc p20', step_ids=['a','lens','b','cube','c'],
                            step_labels={'lens':'Telescope lens','cube':'Arm splitter'})
        c['optic_overrides']['line1:lens'] = dict(token='l100', representation='builtin', diameter_mm=33,
                                                budget={'loss_pct':7,'gdd_fs2':-50})
        return c

    def test_reordering_keeps_the_correct_optic_and_port_identity(self):
        c = self.config()
        p = core.plan_layout(c)
        before = next(e for e in p['endpoints'] if e['kind']=='reflected')
        c['rows'][0].update(commands='p25 p50 l100 p50 bsc p20',step_ids=['new','a','lens','b','cube','c'])
        updated = core.plan_layout(c)
        lens = updated['optics'][0]
        self.assertEqual(lens['id'],'line1:lens')
        self.assertEqual(lens['diameter_mm'],33)
        self.assertEqual(lens['budget']['loss_pct'],7)
        self.assertIn('Telescope lens',lens['label'])
        after = next(e for e in updated['endpoints'] if e['kind']=='reflected')
        self.assertEqual(before['id'],after['id'])
        self.assertAlmostEqual(after['stats']['path_mm']-before['stats']['path_mm'],25)

    def test_csv_round_trip_retains_labels_step_ids_and_calibration(self):
        c = self.config()
        imported = exports.import_csv(exports.export_csv(core.plan_layout(c)), document_id=c['document_id'])
        self.assertEqual(imported['rows'][0]['step_ids'],c['rows'][0]['step_ids'])
        self.assertEqual(imported['rows'][0]['step_labels'],c['rows'][0]['step_labels'])
        p = core.plan_layout(imported)
        self.assertEqual(p['optics'][0]['diameter_mm'],33)
        self.assertEqual(p['optics'][0]['budget']['gdd_fs2'],-50)

    def test_invalid_identity_records_are_rejected_without_silent_reassignment(self):
        for ids in (['a'],['a','a','b','c','d'],['a','b','c','d','x:y'],[0,1,2,3,4]):
            c = self.config();c['rows'][0]['step_ids']=ids
            with self.assertRaisesRegex(core.LayoutError,'identities'):core.plan_layout(c)

    def test_legacy_routes_keep_numeric_port_ids(self):
        c = core.default_config();c['rows'][0]['commands']='p50 bsc p20'
        self.assertIn('line1:1:R',[e['id'] for e in core.plan_layout(c)['endpoints']])

    def test_user_label_cannot_turn_a_main_beam_into_a_secondary(self):
        c = core.default_config()
        c['rows'][0].update(commands='p50 r90 p50',step_labels={'0':'test · secondary'})
        p=core.plan_layout(c)
        self.assertIsNotNone(p['segments'][0]['trim_end'])
        self.assertFalse(any(e['secondary'] for e in core.public_plan(p)['lines']))


class PreviewGeometry(unittest.TestCase):
    def test_geometric_envelope_contains_the_real_focus_and_endpoints(self):
        c=core.default_config();c['rows'][0]['commands']='l50 p100'
        p=core.plan_layout(c);g=workflow.wire_geometry(p)
        self.assertEqual(g['beam'],[(0.,0.,0.),(100.,0.,0.)])
        self.assertIn((50.,0.,0.),g['envelope'])
        self.assertEqual(len(g['envelope']),16)  # Four rails, two sections per rail.
        self.assertEqual(len(g['optic']),50)

    def test_gaussian_draft_is_finite_and_keeps_the_waist(self):
        c=core.default_config();c['source']['model']='gaussian';c['rows'][0]['commands']='l50 p100'
        p=core.plan_layout(c);g=workflow.wire_geometry(p)
        self.assertTrue(all(math.isfinite(x) for points in g.values() for point in points for x in point))
        self.assertTrue(all(math.hypot(point[1],point[2])>0 for point in g['envelope']))
        waist=p['segments'][0]['state'].stats()['waist_distance_mm']
        self.assertTrue(any(abs(point[0]-waist)<1e-10 for point in g['envelope']))

    def test_displacer_pair_keeps_separate_lines_until_recombined(self):
        c=core.default_config();c['rows'][0]['commands']='bd4v p50 _bd4v p30'
        p=core.plan_layout(c);g=workflow.wire_geometry(p)
        self.assertEqual(len(g['beam']),6)
        self.assertEqual(sum(e['secondary'] for e in core.public_plan(p)['lines']),1)

    def test_native_draft_uses_three_line_groups_and_centimetres_not_brep(self):
        c=core.default_config();c['rows'][0]['commands']='p100 l100 p10'
        p=core.plan_layout(c);graphics=[]
        class Group:
            def addLines(self,coords,indices,strip):
                self_test.assertEqual(indices,[]);self_test.assertFalse(strip)
                item=NS(coords=coords);graphics.append(item);return item
            def deleteMe(self):self.deleted=True
        self_test=self;group=Group();group.deleted=False
        design=NS(rootComponent=NS(customGraphicsGroups=NS(add=lambda:group)))
        graphics_api=NS(CustomGraphicsCoordinates=NS(create=lambda x:x),CustomGraphicsSolidColorEffect=NS(create=lambda x:x))
        adsk=NS(fusion=graphics_api,core=NS(Color=NS(create=lambda *x:x)))
        with patch.object(backend,'adsk',adsk),patch.object(backend,'temporary_geometry',side_effect=AssertionError('BRep not permitted')):
            result,warnings=backend.preview(design,p,quality='draft')
        self.assertIs(result,group);self.assertEqual(len(graphics),3)
        self.assertEqual(graphics[0].coords[:6],[0.,0.,0.,10.,0.,0.])
        self.assertFalse(group.deleted)

    def test_native_draft_preserves_moved_route_transform(self):
        c=core.default_config();p=core.plan_layout(c);placement=Matrix(translation=(10,20,30))
        group=NS(addLines=lambda *args:NS(),deleteMe=lambda:None)
        d=NS(rootComponent=NS(customGraphicsGroups=NS(add=lambda:group)))
        api=NS(fusion=NS(CustomGraphicsCoordinates=NS(create=lambda x:x),CustomGraphicsSolidColorEffect=NS(create=lambda x:x)),core=NS(Color=NS(create=lambda *x:x)))
        with patch.object(backend,'adsk',api),patch.object(backend,'find_run',return_value=NS(transform2=placement)):
            backend.preview(d,p,'moved','draft')
        self.assertIs(group.transform,placement)


class WorkflowReliability(unittest.TestCase):
    def test_cache_is_reused_but_callers_cannot_mutate_the_cached_plan(self):
        cache=workflow.PlanCache();c=core.default_config()
        with patch.object(core,'plan_layout',wraps=core.plan_layout) as build:
            first=cache.get(c);first['rows'].clear()
            self.assertEqual(len(cache.get(c)['rows']),1);self.assertEqual(build.call_count,1)
            c['rows'][0]['commands']='p25';self.assertEqual(cache.get(c)['rows'][0]['length_mm'],25)
            self.assertEqual(build.call_count,2)
            cache.clear();cache.get(c);self.assertEqual(build.call_count,3)

    def test_rejected_config_does_not_poison_the_cache(self):
        cache=workflow.PlanCache();c=core.default_config();before=cache.get(c)
        bad=copy.deepcopy(c);bad['rows'][0]['commands']='nonsense'
        with self.assertRaises(core.LayoutError):cache.get(bad)
        self.assertEqual(cache.get(c)['rows'],before['rows'])

    def test_atomic_recovery_round_trip_includes_invalid_command_drafts(self):
        with tempfile.TemporaryDirectory() as directory:
            store=workflow.DraftStore(directory);c=core.default_config();c['rows'][0]['commands']='p'
            saved=store.save('one',c,{'token':'route','name':'Arm'})
            d=store.load('one');self.assertEqual(d['config'],c);self.assertEqual(d['edit_target']['token'],'route')
            self.assertEqual(d['saved_at'],saved);self.assertIsNone(store.load('two'))
            self.assertEqual(len(list(Path(directory).iterdir())),1)
            store.discard('one');self.assertIsNone(store.load('one'))

    def test_interrupted_save_preserves_the_previous_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            store=workflow.DraftStore(directory);c=core.default_config();store.save('doc',c)
            edited=copy.deepcopy(c);edited['run_name']='Unsaved change'
            with patch.object(workflow.os,'replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):store.save('doc',edited)
            self.assertEqual(store.load('doc')['config'],c)
            self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_corrupt_and_oversize_recovery_cannot_be_silently_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            store=workflow.DraftStore(directory);store.path('doc').write_text('{')
            with self.assertRaises(ValueError):store.load('doc')
            store.path('doc').write_text('{}')
            with self.assertRaises(core.LayoutError):store.load('doc')
            store.LIMIT=1
            with self.assertRaises(core.LayoutError):store.save('doc',{})

    def test_completed_commands_release_only_their_own_event_handlers(self):
        c,sent=old_tests.CommandLifecycleTests().classes();context={};other={};removed=[]
        handlers=[(NS(remove=lambda h:removed.append(h)),NS(_lor_scope=scope)) for scope in (None,context,other,context)]
        c['_handlers']=handlers.copy();c['BuildDestroyed'](context).notify(NS())
        self.assertEqual(len(removed),2)
        self.assertEqual([h._lor_scope for _,h in c['_handlers']],[None,other])


class InterfaceStructure(unittest.TestCase):
    def test_static_controls_exist_once_and_scripts_load_in_dependency_order(self):
        class Parser(HTMLParser):
            def __init__(self):super().__init__();self.ids=[];self.scripts=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if attrs.get('id'):self.ids.append(attrs['id'])
                if tag=='script':self.scripts.append(attrs.get('src'))
        parser=Parser();parser.feed((ROOT/'palette.html').read_text())
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertEqual(parser.scripts,['editor.js','schematic.js','studio.js','palette.js'])
        dynamic={'step-label','component-default-status'}
        for file in ('palette.js','studio.js'):
            text=(ROOT/file).read_text()
            for identifier in re.findall(r"\$\('([A-Za-z0-9_-]+)'\)",text):
                self.assertIn(identifier,set(parser.ids)|dynamic,identifier)


if __name__=='__main__':unittest.main()
