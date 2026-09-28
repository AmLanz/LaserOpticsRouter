"""Document-intent regressions. Native conversion/Undo still require Fusion."""
import ast
import json
import sys
import traceback
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core
import workflow
from test_adapter import backend, Design, Occurrences
import test_v120 as old_tests

PART, ASSEMBLY, HYBRID = 0, 1, 2
INTENTS = NS(PartDesignIntentType=PART, AssemblyDesignIntentType=ASSEMBLY,
             HybridDesignIntentType=HYBRID)
REPORTED_COMMANDS = 'p100 l50 p25 p75 l50 p50 p50 r90 p50 _r90f50 p50 pol p50 l50 p50 wp20 p50 r-80 p50'
REPORTED_ERROR = ('3 : Failed to create component: Bauteilkonstruktionsdokumente dürfen nur eine '
                  'Komponente enthalten. Fügen Sie dieses Bauteil einer Baugruppe hinzu, '
                  'um mehrere Komponenten hinzuzufügen.')


class RestrictedOccurrences(Occurrences):
    def addNewComponent(self, transform):
        if self.design.designIntent != HYBRID:
            raise RuntimeError(REPORTED_ERROR)
        return super().addNewComponent(transform)


class IntentDesign(Design):
    def __init__(self, intent, fail=False, ignore=False):
        super().__init__()
        self._intent, self.fail_conversion, self.ignore_conversion = intent, fail, ignore
        self.rootComponent.occurrences = RestrictedOccurrences(self, self.rootComponent)

    @property
    def designType(self):
        return self._modeling_type

    @designType.setter
    def designType(self, value):
        if hasattr(self, '_modeling_type'):
            raise AssertionError('Do not change modeling mode or delete the parametric timeline.')
        self._modeling_type = value

    @property
    def designIntent(self):
        return self._intent

    @designIntent.setter
    def designIntent(self, value):
        self.log.append(('intent', value))
        if self.fail_conversion:
            raise RuntimeError('native conversion rejected')
        if not self.ignore_conversion:
            self._intent = value


class DesignIntentTests(unittest.TestCase):
    def setUp(self):
        self.types = patch.object(backend.adsk.fusion, 'DesignIntentTypes', INTENTS, create=True)
        self.types.start()
        self.addCleanup(self.types.stop)
        config = core.default_config()
        config['rows'][0]['commands'] = REPORTED_COMMANDS
        self.plan = core.plan_layout(config)
        self.geometry = dict(beam=[('Beam', object(), 'beam')], optics=[], custom=[], warnings=[])

    def build(self, design, convert_from=None, prepared=True):
        with patch.object(backend, 'temporary_geometry', return_value=self.geometry) as geometry, \
                patch.object(backend, 'add_bodies', return_value=[]), \
                patch.object(backend, 'appearance', return_value=None), \
                patch.object(backend, 'refresh_dependencies'):
            result = backend.build(NS(), design, self.plan, prepared=self.geometry if prepared else None,
                                   convert_from=convert_from)
        return result, geometry

    def test_reported_commands_are_valid_in_the_real_planner(self):
        self.assertEqual([o['kind'] for o in self.plan['optics']],
                         ['lens', 'lens', 'mirror', 'oap', 'pol', 'lens', 'wp', 'mirror'])
        self.assertEqual(self.plan['config']['rows'][0]['commands'], REPORTED_COMMANDS)
        self.assertTrue(workflow.wire_geometry(self.plan)['beam'])

    def test_part_and_assembly_show_conversion_but_reads_do_not_change_design(self):
        for intent, name in ((PART, 'part'), (ASSEMBLY, 'assembly')):
            design = IntentDesign(intent)
            status = backend.route_build_context(design)
            self.assertEqual(status['intent'], name)
            self.assertTrue(status['requires_hybrid'])
            self.assertTrue(status['can_build'])
            self.assertEqual(backend.public_plan(design, self.plan)['build_context'], status)
            self.assertEqual(design.designIntent, intent)
            self.assertEqual(design.log, [])

    def test_unacknowledged_conversion_is_rejected_before_geometry_or_mutation(self):
        for intent in (PART, ASSEMBLY):
            design = IntentDesign(intent)
            with patch.object(backend, 'temporary_geometry') as geometry:
                with self.assertRaisesRegex(core.LayoutError, 'Switch to Hybrid & build'):
                    backend.build(NS(), design, self.plan)
                geometry.assert_not_called()
            self.assertEqual(design.log, [])

    def test_explicit_part_or_assembly_build_converts_before_creating_components(self):
        for intent, name in ((PART, 'part'), (ASSEMBLY, 'assembly')):
            for mode in (0, 1):
                design = IntentDesign(intent)
                design._modeling_type = mode
                result, _ = self.build(design, name)
                self.assertEqual(design.log[0], ('intent', HYBRID))
                self.assertEqual(len([e for e in design.log if e[0] == 'create']), 2)
                self.assertEqual(result['build_context']['intent'], 'hybrid')
                self.assertFalse(result['build_context']['requires_hybrid'])
                self.assertEqual(design.designType, mode)
                self.assertEqual(json.loads(design.entities[result['token']].component.attributes
                                            .itemByName(backend.GROUP, 'settings').value)['rows'][0]['commands'],
                                 REPORTED_COMMANDS)

    def test_hybrid_and_legacy_builds_need_no_conversion(self):
        for design in (IntentDesign(HYBRID), Design()):
            result, _ = self.build(design)
            self.assertFalse(any(e[0] == 'intent' for e in design.log))
            self.assertFalse(result['build_context']['requires_hybrid'])

    def test_fusion_without_design_intent_enum_keeps_legacy_workflow(self):
        with patch.object(backend.adsk.fusion, 'DesignIntentTypes', None):
            self.assertEqual(backend.route_build_context(Design())['intent'], 'legacy')

    def test_changed_part_to_assembly_is_not_converted_by_stale_part_action(self):
        design = IntentDesign(ASSEMBLY)
        with self.assertRaisesRegex(core.LayoutError, 'Assembly document'):
            self.build(design, 'part')
        self.assertEqual(design.log, [])

    def test_already_converted_hybrid_does_not_need_a_second_conversion(self):
        design = IntentDesign(HYBRID)
        self.build(design, 'part')
        self.assertFalse(any(e[0] == 'intent' for e in design.log))

    def test_rejected_or_ignored_conversion_never_attempts_component_creation(self):
        for kwargs in (dict(fail=True), dict(ignore=True)):
            design = IntentDesign(PART, **kwargs)
            with self.assertRaisesRegex(RuntimeError, 'Switch document to Hybrid:.*Change its design type'):
                self.build(design, 'part')
            self.assertEqual(design.log, [('intent', HYBRID)])
            self.assertEqual(design.entities, {})

    def test_unreadable_or_unknown_intent_blocks_build_but_public_plan_is_available(self):
        class Unreadable(IntentDesign):
            @property
            def designIntent(self):
                raise RuntimeError('native design unavailable')
        for design in (Unreadable(PART), IntentDesign(999)):
            status = backend.public_plan(design, self.plan)['build_context']
            self.assertFalse(status['can_build'])
            with self.assertRaises(core.LayoutError):
                self.build(design, 'part')
            self.assertEqual(design.log, [])

    def test_refresh_rejects_restricted_document_before_resolving_saved_geometry(self):
        design = IntentDesign(ASSEMBLY)
        for run in (lambda: backend.prepare_route_refresh(design, 'route'),
                    lambda: backend.refresh_route(NS(), design, {})):
            with self.assertRaisesRegex(core.LayoutError, 'Hybrid'):
                run()
        self.assertEqual(design.log, [])

    def bridge(self, design):
        path = ROOT / 'LaserOpticsRouter.py'
        node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'HTMLHandler')
        context = dict(adsk=NS(core=NS(HTMLEventHandler=object)), core=core, backend=backend,
                       json=json, traceback=traceback, _doc_key='doc', _operation_active=False,
                       _pending_build=None, _pending_manage=None, _last_build_error='',
                       design=lambda: design, clear_preview=Mock(), _plans=workflow.PlanCache(),
                       diagnostic=Mock(), _app=NS(activeViewport=NS(refresh=Mock()), log=Mock()),
                       _ui=NS(commandDefinitions=NS(itemById=Mock(return_value=NS(execute=Mock())))),
                       BUILD_ID='build', __name__='intent_bridge_test')
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), context)
        return context

    def test_bridge_preflight_fails_before_preparation_and_returns_current_type(self):
        design = IntentDesign(PART)
        c = self.bridge(design)
        args = NS(action='build', data=json.dumps(dict(doc_key='doc', config=self.plan['config'])))
        with patch.object(backend, 'temporary_geometry') as geometry:
            c['HTMLHandler']().notify(args)
            geometry.assert_not_called()
        reply = json.loads(args.returnData)
        self.assertFalse(reply['ok'])
        self.assertEqual(reply['error']['build_context']['intent'], 'part')
        self.assertIsNone(c['_pending_build'])
        c['_ui'].commandDefinitions.itemById.assert_not_called()
        self.assertEqual(design.log, [])

    def test_bridge_queues_explicit_conversion_without_changing_design_outside_command(self):
        design = IntentDesign(PART)
        c = self.bridge(design)
        args = NS(action='build', data=json.dumps(dict(doc_key='doc', config=self.plan['config'], convert_from='part')))
        with patch.object(backend, 'temporary_geometry', return_value=self.geometry):
            c['HTMLHandler']().notify(args)
        self.assertTrue(json.loads(args.returnData)['ok'])
        self.assertEqual(c['_pending_build']['convert_from'], 'part')
        c['_ui'].commandDefinitions.itemById.return_value.execute.assert_called_once()
        self.assertEqual(design.log, [])

    def test_native_execute_forwards_conversion_and_failure_still_uses_fusion_rollback(self):
        c, sent = old_tests.CommandLifecycleTests().classes()
        design = IntentDesign(PART)
        c['design'] = lambda: design
        c['backend'] = backend
        c['_pending_build'] = dict(doc_key='doc', plan=self.plan, geometry=self.geometry, convert_from='part')
        operation, args = {}, NS(executeFailed=False)
        with patch.object(backend, 'build', side_effect=RuntimeError('native failure')) as build:
            c['BuildExecute'](operation).notify(args)
        self.assertEqual(build.call_args.kwargs['convert_from'], 'part')
        self.assertTrue(callable(build.call_args.kwargs['progress']))
        self.assertTrue(args.executeFailed)
        self.assertEqual(sent, [])
        # Simulate the state at command destruction, after Fusion's rollback.
        c['BuildDestroyed'](operation).notify(NS())
        self.assertEqual(sent[0][0], 'build_failed')
        self.assertEqual(sent[0][1]['build_context']['intent'], 'part')
        self.assertEqual(design.log, [])


if __name__ == '__main__':
    unittest.main()
