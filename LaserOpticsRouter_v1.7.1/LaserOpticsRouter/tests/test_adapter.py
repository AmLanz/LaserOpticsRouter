"""Persistence and coordinate-boundary tests with small Fusion API doubles.
These do not exercise Fusion's native browser, transaction system or BRep kernel.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core


class Matrix:
    def __init__(self, axes=((1,0,0),(0,1,0),(0,0,1)), translation=(0,0,0)):
        self.axes, self.translation = axes, translation
    @staticmethod
    def create(): return Matrix()
    def copy(self): return copy.deepcopy(self)
    def setWithCoordinateSystem(self, origin, x, y, z):
        self.translation = (origin.x, origin.y, origin.z)
        self.axes = tuple((v.x, v.y, v.z) for v in (x, y, z))
        return True
    def invert(self):
        self.axes = tuple(tuple(self.axes[j][i] for j in range(3)) for i in range(3))
        self.translation = core.world(self.axes, core.mul(self.translation, -1))
        return True


class Point:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
    @classmethod
    def create(cls, x, y, z): return cls(x,y,z)
    def copy(self): return copy.deepcopy(self)
    def transformBy(self, m):
        value = core.world(m.axes, (self.x, self.y, self.z))
        if not isinstance(self, Vector): value = core.add(value, m.translation)
        self.x, self.y, self.z = value
        return True


class Vector(Point): pass
class Circle:
    def __init__(self, center): self.center = center
    def copy(self): return copy.deepcopy(self)
    @classmethod
    def cast(cls, x): return x if isinstance(x, cls) else None
class Arc(Circle): pass
class Edge: pass
class Vertex: pass
class SketchCurve: pass
class SketchCircle(SketchCurve): pass
class SketchArc(SketchCurve): pass
class SketchPoint: pass


class Attributes:
    def __init__(self): self.data = {}
    def itemByName(self, group, name): return self.data.get((group, name))
    def add(self, group, name, value):
        attr = NS(value=value)
        self.data[group, name] = attr
        return attr


class Component:
    def __init__(self, design, name='part'):
        self.name = name; self.attributes = Attributes(); self.entityToken = 'component-'+name
        self.occurrences = Occurrences(design, self)


class Occurrence:
    def __init__(self, design, token, component, transform=None, parent_component=None):
        self.design, self.entityToken, self.component = design, token, component
        self.parentComponent = parent_component or design.rootComponent
        self._transform = (transform or Matrix()).copy()
        self._initial = self.transform2.copy()
        self.isVaildForEditInitialPosition = True
        self.isGroundToParent = True; self._pinned = False; self.grounded_reads = 0
        self.fullPathName = self.name = token
        self.assemblyContext = None; self.isValid = True; self.delete_ok = True
    @staticmethod
    def cast(entity): return entity if isinstance(entity, Occurrence) else None
    @property
    def transform2(self): return self._transform.copy()
    @transform2.setter
    def transform2(self, transform):
        if self.parentComponent is not self.design.rootComponent:
            raise RuntimeError('3 : transform overrides can only be set on Occurrence proxy from root component')
        self._transform = transform.copy()
        self.design.snapshots.hasPendingSnapshot = True
    @property
    def is_rooted(self):
        return self.assemblyContext is None and self.parentComponent is self.design.rootComponent
    def createForAssemblyContext(self, parent):
        if self.assemblyContext is not None: raise RuntimeError('not native')
        if parent.component is not self.parentComponent: raise RuntimeError('wrong parent context')
        key = parent.fullPathName+'+'+self.fullPathName
        if key not in self.design.proxies:
            self.design.proxies[key] = OccurrenceProxy(self, parent, key)
        return self.design.proxies[key]
    @property
    def initialTransform(self): return self._initial.copy()
    @initialTransform.setter
    def initialTransform(self, transform):
        if self.isGroundToParent or self._pinned: raise RuntimeError('grounded')
        if not self.is_rooted: raise RuntimeError('initial position not editable here')
        self._initial = transform.copy(); self._transform = transform.copy()
    @property
    def isGrounded(self):
        self.grounded_reads += 1
        raise RuntimeError('3 : isGrounded property is not available for the occurence of a sub component.')
    def activate(self):
        self.design.activeOccurrence = self
        self.design.log.append(('activate', self.entityToken))
        return True
    def deleteMe(self):
        self.design.log.append(('delete', self.entityToken))
        if self.delete_ok: self.isValid = False
        return self.delete_ok


class OccurrenceProxy:
    """Root-context transforms with per-instance overrides, not native writes."""
    def __init__(self, native, parent, key):
        self.nativeObject, self._parent = native, parent
        self.design, self.component = native.design, native.component
        self.assemblyContext = parent.assemblyContext or parent
        self.fullPathName = self.entityToken = self.name = key
    @property
    def is_rooted(self): return self._parent.is_rooted
    @property
    def isValid(self): return self.nativeObject.isValid and self._parent.isValid
    @property
    def isGroundToParent(self): return self.nativeObject.isGroundToParent
    @isGroundToParent.setter
    def isGroundToParent(self, value): self.nativeObject.isGroundToParent = value
    @property
    def isGrounded(self): return self.nativeObject.isGrounded
    @property
    def transform2(self):
        # Independent composition using test matrices, in Fusion's cm units.
        parent = self._parent.transform2
        local = self.design.proxy_overrides.get(self.fullPathName, self.nativeObject.transform2)
        return Matrix(tuple(core.world(parent.axes, a) for a in local.axes),
                      core.add(parent.translation, core.world(parent.axes, local.translation)))
    @transform2.setter
    def transform2(self, world):
        if not self.is_rooted:
            raise RuntimeError('3 : transform overrides can only be set on Occurrence proxy from root component')
        if self.isGroundToParent: raise RuntimeError('grounded to parent')
        inverse = self._parent.transform2; inverse.invert()
        local = Matrix(tuple(core.world(inverse.axes, a) for a in world.axes),
                       core.add(inverse.translation, core.world(inverse.axes, world.translation)))
        self.design.proxy_overrides[self.fullPathName] = local
        self.design.snapshots.hasPendingSnapshot = True
        self.design.log.append(('proxy_move', self.fullPathName))


class Occurrences:
    def __init__(self, design, owner): self.design, self.owner = design, owner
    def __iter__(self):
        return iter(o for o in self.design.entities.values() if isinstance(o,Occurrence) and o.isValid and o.parentComponent is self.owner)
    def addNewComponent(self, transform):
        token = 'new-'+str(len(self.design.entities))
        c = Component(self.design, token)
        o = Occurrence(self.design, token, c, transform, self.owner)
        self.design.entities[token] = o
        self.design.log.append(('create', token))
        return o
    def addExistingComponent(self, component, transform):
        token = 'instance-'+str(len(self.design.entities))
        # Reproduce an insertion inheriting an unwanted source displacement.
        inserted = transform.copy()
        inserted.translation = core.add(inserted.translation, getattr(self.design, 'insertion_shift', (7,-4,2)))
        o = Occurrence(self.design, token, component, inserted, self.owner)
        self.design.entities[token] = o
        return o


class Root:
    def __init__(self, design): self.design = design; self.occurrences = Occurrences(design, self)
    @property
    def allOccurrences(self): return [x for x in self.design.entities.values() if isinstance(x, Occurrence) and x.isValid]
    def allOccurrencesByComponent(self, component): return [o for o in self.allOccurrences if o.component is component]


class Design:
    def __init__(self):
        self.entities = {}; self.log = []; self.attributes = Attributes(); self.rootComponent = Root(self)
        self.proxies = {}; self.proxy_overrides = {}; self.saved_overrides = {}
        self.activeOccurrence = None
        self.designType = 1
        self.snapshots = NS(hasPendingSnapshot=False, add=self.capture)
    def capture(self):
        self.saved_overrides = copy.deepcopy(self.proxy_overrides)
        self.snapshots.hasPendingSnapshot = False
        self.log.append(('capture', 'positions'))
        return object()
    def reevaluate(self):
        self.proxy_overrides = copy.deepcopy(self.saved_overrides)
    def findEntityByToken(self, token):
        entity = self.entities.get(token)
        return [entity] if entity and getattr(entity, 'isValid', True) else []
    def activateRootComponent(self):
        self.activeOccurrence = None
        self.log.append(('activate', 'root'))
        return True


adsk = ModuleType('adsk'); adsk.core = ModuleType('adsk.core'); adsk.fusion = ModuleType('adsk.fusion')
adsk.core.Point3D = Point; adsk.core.Vector3D = Vector; adsk.core.Matrix3D = Matrix
adsk.core.Circle3D = Circle; adsk.core.Arc3D = Arc
adsk.fusion.DesignTypes = NS(ParametricDesignType=1, DirectDesignType=0)
for name, cls in dict(Occurrence=Occurrence, Component=Component, BRepEdge=Edge, BRepVertex=Vertex,
                      SketchCurve=SketchCurve, SketchCircle=SketchCircle, SketchArc=SketchArc, SketchPoint=SketchPoint).items():
    setattr(adsk.fusion, name, cls)
with patch.dict(sys.modules, {'adsk':adsk, 'adsk.core':adsk.core, 'adsk.fusion':adsk.fusion}):
    spec = importlib.util.spec_from_file_location('adapter_for_test', Path(__file__).resolve().parents[1]/'fusion_backend.py')
    backend = importlib.util.module_from_spec(spec); spec.loader.exec_module(backend)


def isolated_entry_function(name, context):
    source = Path(__file__).resolve().parents[1]/'LaserOpticsRouter.py'
    node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)
    context.update(adsk=adsk, core=core, backend=backend)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), context)
    return context[name]


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.design = Design()
        config = core.default_config(); config['rows'][0]['commands'] = 'p100 bs30v20 p10'
        self.plan = core.plan_layout(config)
        comp = Component(self.design, 'Saved route')
        for key, value in [('run_id','run-old'), ('settings',json.dumps(config)), ('endpoints',json.dumps(self.plan['endpoints']))]:
            comp.attributes.add(backend.GROUP, key, value)
        self.old = Occurrence(self.design, 'old', comp, Matrix(((0,1,0),(-1,0,0),(0,0,1)), (10,20,3)))
        self.design.entities['old'] = self.old
    def assertVector(self, a, b):
        for x, y in zip(a,b): self.assertAlmostEqual(x,y,places=8)
    def blank_geometry(self, plan, design):
        design.log.append(('geometry', 'ready'))
        return dict(beam=[], optics=[], custom=[], warnings=[])

    def test_saved_packets_include_transformed_direction_and_branch_slope(self):
        result = backend.saved_endpoints(self.design)
        self.assertEqual(len(result['runs']), 1)
        for item, expected in zip(result['items'], self.plan['endpoints']):
            state, _ = core.decode_endpoint(item['endpoint'])
            self.assertVector(state.d, core.world(self.old.transform2.axes, expected['stats']['direction']))
            self.assertAlmostEqual(state.stats()['half_angle_mrad'], expected['stats']['half_angle_mrad'])
            self.assertEqual(item['run_token'], 'old')

    def test_edit_endpoint_display_and_paste_round_trip_in_moved_route(self):
        public = backend.public_plan(self.design, self.plan, 'old')
        self.assertVector(public['rows'][0]['endpoint']['stats']['position'], (100,310,30))
        self.assertVector(public['rows'][0]['endpoint']['stats']['direction'], (0,1,0))
        self.assertVector(public['optics'][0]['input_direction'], (0,1,0))
        self.assertVector(self.plan['rows'][0]['endpoint']['stats']['position'], (110,0,0))
        for a, b in zip(public['endpoints'], self.plan['endpoints']):
            recovered = backend.endpoint_in_run_frame(self.design, a['endpoint'], 'old')
            state, _ = core.decode_endpoint(recovered['endpoint'])
            self.assertVector(state.position, b['stats']['position'])
            self.assertVector(state.d, b['stats']['direction'])
        self.assertIs(public['rows'][0]['endpoint'], public['endpoints'][-1])

    def test_defaults_save_remove_and_survive_load_without_build(self):
        part = Component(self.design, 'Lens'); self.design.entities['part'] = part
        defaults = backend.save_component_default(self.design, 'l50', dict(component_ref_token='part', reference=[1,2,3]))
        self.assertEqual(backend.load_settings(self.design)['component_defaults'], defaults)
        self.assertNotIn('rotation',defaults['l50'])
        self.assertEqual(backend.save_component_default(self.design, 'l50', None), {})

    def test_load_old_route_preserves_builtins_despite_new_default(self):
        part = Component(self.design, 'BS'); self.design.entities['part'] = part
        backend.save_component_default(self.design, 'bs30v20', dict(component_ref_token='part'))
        config = backend.load_run(self.design, 'old')['config']
        self.assertIn('bs', config['component_defaults'])
        self.assertFalse(core.plan_layout(config)['optics'][0]['settings']['custom'])

    def test_rename_updates_component_and_editable_settings(self):
        self.assertEqual(backend.rename_run(self.design, 'old', 'Renamed route'), 'Renamed route')
        self.assertEqual(self.old.component.name, 'Renamed route')
        self.assertEqual(backend.load_run(self.design, 'old')['config']['run_name'], 'Renamed route')

    def test_delete_is_limited_to_identified_router_occurrences(self):
        self.design.entities['plain'] = Occurrence(self.design, 'plain', Component(self.design))
        with self.assertRaises(core.LayoutError): backend.delete_run(self.design, 'plain')
        backend.delete_run(self.design, 'old')
        self.assertFalse(self.old.isValid)
        self.assertTrue(self.design.entities['plain'].isValid)
        self.assertEqual(backend.saved_endpoints(self.design)['items'], [])

    def test_nested_routes_are_read_only_for_management(self):
        self.old.assemblyContext = object()
        self.assertFalse(backend.saved_endpoints(self.design)['runs'][0]['editable'])
        for action in (lambda:backend.load_run(self.design,'old'), lambda:backend.delete_run(self.design,'old')):
            with self.assertRaises(core.LayoutError): action()

    def test_replace_preserves_placement_and_deletes_only_after_build(self):
        with patch.object(backend, 'temporary_geometry', self.blank_geometry), patch.object(backend,'appearance',return_value=None):
            result = backend.build(None, self.design, self.plan, 'old')
        self.assertTrue(result['replaced']); self.assertFalse(self.old.isValid)
        new = self.design.rootComponent.allOccurrences[0]
        self.assertEqual(new.transform2.axes, self.old.transform2.axes)
        self.assertEqual(new.transform2.translation, self.old.transform2.translation)
        self.assertLess(self.design.log.index(('geometry','ready')), self.design.log.index(('delete','old')))

    def test_geometry_failure_keeps_original_route(self):
        with patch.object(backend, 'temporary_geometry', side_effect=RuntimeError('native geometry failure')):
            with self.assertRaises(RuntimeError): backend.build(None, self.design, self.plan, 'old')
        self.assertTrue(self.old.isValid)
        self.assertEqual(len(self.design.rootComponent.allOccurrences), 1)

    def test_failed_delete_leaves_cleanup_to_command_transaction(self):
        self.old.delete_ok = False
        self.design.attributes.add(backend.GROUP, 'last_settings', 'previous settings')
        with patch.object(backend, 'temporary_geometry', self.blank_geometry):
            with self.assertRaises(RuntimeError): backend.build(None, self.design, self.plan, 'old')
        self.assertTrue(self.old.isValid)
        self.assertTrue(any(o is not self.old for o in self.design.rootComponent.allOccurrences))
        self.assertFalse(any(action=='delete' and token!='old' for action,token in self.design.log))

    def test_circle_datum_uses_centre_in_component_coordinates(self):
        # Selected circle proxy: world cm -> inverse occurrence -> component mm.
        edge = Edge(); edge.assemblyContext = self.old; edge.body = NS(parentComponent=self.old.component)
        edge.geometry = Circle(Point(9.8,20.1,3.3))
        palette = NS(isVisible=True,isValid=True)
        fn = isolated_entry_function('pick_reference', dict(design=lambda:self.design, palette=lambda:palette,
            _ui=NS(selectEntity=lambda *args:NS(entity=edge))))
        result = fn('old')
        self.assertVector(result['reference'], (1,2,3))
        self.assertIn('centre', result['reference_name'])
        self.assertTrue(palette.isVisible)

    def test_native_circle_datum_is_not_double_transformed(self):
        edge = Edge(); edge.assemblyContext = None; edge.body = NS(parentComponent=self.old.component)
        edge.geometry = Circle(Point(.1,.2,.3))
        fn = isolated_entry_function('pick_reference', dict(design=lambda:self.design, palette=lambda:NS(isValid=True),
            _ui=NS(selectEntity=lambda *args:NS(entity=edge))))
        self.assertVector(fn('old')['reference'], (1,2,3))

    def test_select_component_defaults_to_its_file_origin(self):
        fn = isolated_entry_function('pick_component', dict(palette=lambda:NS(isValid=True),
            _ui=NS(selectEntity=lambda *args:NS(entity=self.old))))
        data = fn()
        self.assertEqual(data['reference'], [0,0,0])
        self.assertEqual(data['reference_name'], 'Component origin')
        self.assertEqual(data['component_ref_token'], self.old.component.entityToken)


    def test_custom_preview_and_build_match_despite_inherited_insertion_shift(self):
        self._check_custom_preview_and_build()

    def test_moved_rotated_route_replacement_matches_world_preview_after_capture(self):
        self._check_custom_preview_and_build(replace_token='old')

    def test_correct_nested_insertion_needs_no_write_or_capture(self):
        self.design.insertion_shift = (0,0,0)
        self._check_custom_preview_and_build(replace_token='old')
        self.assertFalse(any(action in ('proxy_move','capture') for action,_ in self.design.log))

    def _check_custom_preview_and_build(self, replace_token=None):
        class Manager:
            def copy(self, body): return copy.deepcopy(body)
            def transform(self, body, placement):
                for p in body.points: p.transformBy(placement)
                return True
        manager = Manager()
        source = Component(self.design, 'Asymmetric optic')
        source.bRepBodies = [NS(isVisible=True, points=[Point(.7,-.3,.2), Point(1.8,.4,-.5)])]
        source.allOccurrences = []
        native_points = [(p.x,p.y,p.z) for p in source.bRepBodies[0].points]
        source_matrix = Matrix(((0,0,1),(1,0,0),(0,1,0)), (50,-80,10))
        source_occ = Occurrence(self.design, 'source', source, source_matrix)
        self.design.entities['source'] = source_occ
        self.design.activeOccurrence = source_occ
        c = core.default_config(); c['rows'][0]['commands'] = 'p120 fr90v20f50 p40 _r60v-10f50'
        for index, command in ((1,'fr90v20f50'), (3,'_r60v-10f50')):
            c['optic_overrides']['line1:'+str(index)] = dict(token=command, custom=True,
                component_token='source', reference=[7,-3,2], shift=[1,2,-3], rotation=[15,-23,31])
        plan = core.plan_layout(c)
        geometry = dict(beam=[object()], optics=[], custom=[(o,source) for o in plan['optics']], warnings=[])
        previews = [backend.custom_preview_bodies(manager, source, backend.custom_placement(o)) for o in plan['optics']]
        with patch.object(backend,'temporary_geometry',return_value=geometry), \
             patch.object(backend,'appearance',return_value=None), patch.object(backend,'add_bodies',return_value=[]):
            backend.build(None, self.design, plan, replace_token)
        built = [o for o in self.design.proxies.values() if o.component is source]
        self.assertEqual(len(built), 2)
        self.design.reevaluate()
        root_transform = self.old.transform2 if replace_token else Matrix()
        shifted = getattr(self.design, 'insertion_shift', (7,-4,2)) != (0,0,0)
        for occurrence, expected in zip(built, previews):
            for local, target in zip(source.bRepBodies[0].points, expected[0].points):
                actual = local.copy(); actual.transformBy(occurrence.transform2)
                target = target.copy(); target.transformBy(root_transform)
                self.assertVector((actual.x,actual.y,actual.z), (target.x,target.y,target.z))
            self.assertEqual(occurrence.isGroundToParent, not shifted)
            self.assertTrue(occurrence.is_rooted)
            self.assertEqual(occurrence.nativeObject.grounded_reads, 0)
        for proxy in self.design.proxies.values():
            if proxy.component.name in ('Optics','Beam'):
                backend.check_occurrence_pose(proxy, root_transform, proxy.component.name)
        self.assertEqual(self.design.log.count(('capture','positions')), int(shifted))
        self.assertEqual([(p.x,p.y,p.z) for p in source.bRepBodies[0].points], native_points)
        self.assertEqual(source_occ.transform2.translation, (50,-80,10))
        self.assertEqual(source_occ.transform2.axes, source_matrix.axes)
        self.assertTrue(source_occ.isGroundToParent)
        self.assertIsNone(self.design.activeOccurrence)  # protected builds leave the design root active
        self.assertIn(('activate','root'), self.design.log)

    def test_nested_native_reproduces_reported_error_and_root_proxy_succeeds(self):
        group = self.old.component.occurrences.addNewComponent(Matrix(translation=(1,2,3)))
        optic = group.component.occurrences.addNewComponent(Matrix())
        expected = Matrix(((0,0,1),(1,0,0),(0,1,0)), (9,8,7))
        with self.assertRaisesRegex(RuntimeError, 'transform overrides can only be set'):
            optic.transform2 = expected
        proxy = backend.root_proxy(optic, backend.root_proxy(group,self.old,'Optics'), 'Lens')
        self.assertTrue(backend.set_occurrence_pose(proxy,expected,'Lens'))
        backend.capture_placements(self.design,True,[(proxy,expected,'Lens')])
        self.design.reevaluate()
        backend.check_occurrence_pose(proxy,expected,'Lens')

    def test_missing_proxy_reports_stage_and_preserves_old_route(self):
        geometry = dict(beam=[object()],optics=[],custom=[],warnings=[])
        self.design.activeOccurrence = self.old
        with patch.object(Occurrence,'createForAssemblyContext',return_value=None), \
             patch.object(backend,'temporary_geometry',return_value=geometry):
            with self.assertRaisesRegex(RuntimeError,'Resolve and place Beam in root context'):
                backend.build(None,self.design,self.plan,'old')
        self.assertTrue(self.old.isValid)
        self.assertIs(self.design.activeOccurrence,self.old)
        self.assertFalse(any(action=='delete' for action,_ in self.design.log))

    def test_failed_capture_does_not_delete_previous_route(self):
        source = Component(self.design,'Lens')
        config = core.default_config(); config['rows'][0]['commands'] = 'p10 l50'
        plan = core.plan_layout(config)
        geometry = dict(beam=[],optics=[],custom=[(plan['optics'][0],source)],warnings=[])
        self.design.snapshots.add = lambda:None
        with patch.object(backend,'temporary_geometry',return_value=geometry):
            with self.assertRaisesRegex(RuntimeError,'Capture and verify component placements'):
                backend.build(None,self.design,plan,'old')
        self.assertTrue(self.old.isValid)
        self.assertFalse(any(action=='delete' for action,_ in self.design.log))

    def test_absolute_pose_handles_automatic_grounding_and_persists(self):
        occurrence = Occurrence(self.design, 'new', Component(self.design), Matrix(translation=(8,9,10)))
        expected = Matrix(((0,1,0),(-1,0,0),(0,0,1)), (1,2,3))
        self.assertFalse(backend.set_occurrence_pose(occurrence, expected, 'Custom optic'))
        self.assertEqual(occurrence.grounded_reads, 0)
        occurrence.transform2 = occurrence.initialTransform
        backend.check_occurrence_pose(occurrence, expected, 'Custom optic')

    def test_transient_fallback_captures_position_once(self):
        occurrence = Occurrence(self.design, 'new', Component(self.design))
        occurrence.isVaildForEditInitialPosition = False
        self.design.entities['new'] = occurrence
        expected = Matrix(translation=(1,2,3))
        pending = backend.set_occurrence_pose(occurrence, expected, 'Custom optic')
        captures = []
        def capture():
            captures.append(True); occurrence._initial = occurrence.transform2.copy()
            return object()
        self.design.snapshots = NS(hasPendingSnapshot=True, add=capture)
        backend.capture_placements(self.design, pending, [(occurrence,expected,'Custom optic')])
        self.assertEqual(len(captures), 1)
        occurrence.transform2 = occurrence.initialTransform
        backend.check_occurrence_pose(occurrence, expected, 'Custom optic')

    def test_direct_design_fallback_needs_no_snapshot(self):
        self.design.designType = adsk.fusion.DesignTypes.DirectDesignType
        occurrence = Occurrence(self.design, 'new', Component(self.design))
        occurrence.isVaildForEditInitialPosition = False
        expected = Matrix(translation=(1,2,3))
        pending = backend.set_occurrence_pose(occurrence, expected, 'Custom optic')
        backend.capture_placements(self.design, pending, [(occurrence,expected,'Custom optic')])

    def test_remaining_shift_or_rotation_is_reported_instead_of_accepted(self):
        occurrence = Occurrence(self.design, 'new', Component(self.design), Matrix(translation=(.1,0,0)))
        with self.assertRaisesRegex(core.LayoutError, 'position error 1 mm'):
            backend.check_occurrence_pose(occurrence, Matrix(), 'Lens')
        occurrence.transform2 = Matrix(((0,1,0),(-1,0,0),(0,0,1)))
        with self.assertRaisesRegex(core.LayoutError, 'axis error'):
            backend.check_occurrence_pose(occurrence, Matrix(), 'Lens')

    def test_oap_default_merge_is_read_only_until_save_and_retains_backup(self):
        table = {'_r90f50':dict(component_token='old-flipped'), 'r90f50':dict(component_token='old-normal')}
        self.design.attributes.add(backend.GROUP,'component_defaults',json.dumps(table))
        self.assertEqual(backend.load_component_defaults(self.design), {'r90f50':table['r90f50']})
        self.assertEqual(json.loads(self.design.attributes.itemByName(backend.GROUP,'component_defaults').value), table)
        result = backend.save_component_default(self.design, '_r90f50', None)
        self.assertEqual(result, {})
        self.assertEqual(backend.load_component_defaults(self.design), {})
        backup = self.design.attributes.itemByName(backend.GROUP,'component_defaults_before_1_2_0')
        self.assertEqual(json.loads(backup.value), table)


if __name__ == '__main__': unittest.main()
