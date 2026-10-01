"""Public-release regressions: concave OAPs and persistent built beam colors."""
import math
import re
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from xml.etree import ElementTree as ET
import core
import schematic_svg
import test_v120 as fixtures
from test_adapter import backend, Matrix, Attributes


class PersistentDisplay(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.DependencyTests();fixture.setUp();fixture.chain()
        self.d,self.parent,self.child=fixture.d,fixture.parent,fixture.child
        self.beam=self.child.component.occurrences.addNewComponent(Matrix()).component
        self.beam.name='Beam';self.beam.opacity=.3
        self.beam.bRepBodies=[]
        for kind in ('beam','beam-blue','beam-blue'):
            body=NS(attributes=Attributes(),appearance='original-'+kind)
            body.attributes.add(backend.GROUP,'beam_style',kind)
            self.beam.bRepBodies.append(body)
        self.optics=self.child.component.occurrences.addNewComponent(Matrix()).component
        self.optics.name='Optics';self.optics.opacity=.65
        self.optics.bRepBodies=[NS(appearance='source CAD finish')]

    def test_connection_changes_never_restyle_or_rebuild_saved_geometry(self):
        before=[b.appearance for b in self.beam.bRepBodies]
        with patch.object(backend,'appearance') as materials,patch.object(backend,'temporary_geometry') as geometry:
            for placement in (Matrix(),Matrix(translation=(1,2,0)),Matrix()):
                self.parent.transform2=placement
                data=backend.refresh_dependencies(object(),self.d)
                self.assertEqual([b.appearance for b in self.beam.bRepBodies],before)
                self.assertEqual(self.beam.opacity,.3)
            materials.assert_not_called();geometry.assert_not_called()
        self.assertFalse(next(r for r in data['runs'] if r['run_id']=='child')['stale'])

    def test_legacy_clear_beams_restore_once_with_per_color_cache(self):
        self.child.component.attributes.add(backend.GROUP,'stale_display','true')
        self.beam.opacity=.12
        self.parent.transform2=Matrix(translation=(1,2,0))
        self.assertTrue(next(r for r in backend.saved_endpoints(self.d)['runs'] if r['run_id']=='child')['display_repair_needed'])
        with patch.object(backend,'appearance',side_effect=lambda app,d,kind:'restored-'+kind) as materials:
            data=backend.refresh_dependencies(object(),self.d)
            self.assertEqual(materials.call_count,2)
            self.assertEqual([b.appearance for b in self.beam.bRepBodies],['restored-beam','restored-beam-blue','restored-beam-blue'])
            self.assertEqual(self.beam.opacity,.3)
            backend.refresh_dependencies(object(),self.d);self.assertEqual(materials.call_count,2)
        run=next(r for r in data['runs'] if r['run_id']=='child')
        self.assertTrue(run['stale']);self.assertFalse(run['display_repair_needed'])
        self.assertEqual(self.optics.opacity,.65)
        self.assertEqual(self.optics.bRepBodies[0].appearance,'source CAD finish')

    def test_failed_color_repair_remains_retryable_and_keeps_connection_warning(self):
        self.child.component.attributes.add(backend.GROUP,'stale_display','true');self.beam.opacity=.12
        with patch.object(backend,'appearance',return_value=None):
            data=backend.refresh_dependencies(object(),self.d)
        self.assertEqual(self.beam.opacity,.12)
        self.assertEqual(backend._attribute(self.child.component,'stale_display'),'true')
        self.assertTrue(any('colors could not be restored' in w for w in data['warnings']))


class StarterSnapshot(unittest.TestCase):
    def test_built_snapshot_confirms_starter_but_does_not_mutate_draft(self):
        c=core.default_config();c['rows'][0].update(commands='p100',step_ids=['starter'],starter_step_id='starter')
        p=core.plan_layout(c);saved=core.snapshot_config(p)
        self.assertNotIn('starter_step_id',saved['rows'][0])
        self.assertEqual(p['config']['rows'][0]['starter_step_id'],'starter')
        self.assertEqual(saved['rows'][0]['commands'],'p100')


class ConcaveOAP(unittest.TestCase):
    def test_open_face_points_toward_projected_optical_normal_and_ray_datum(self):
        for command in ('r30f50','r-30f50','r90f50','_r90f50','_r-90f50','r90v30f50'):
            c=core.default_config();c['rows'][0]['commands']=command
            optic=core.plan_layout(c)['optics'][0]
            for axes in ((0,1),(0,2),(1,2)):
                root=ET.fromstring(schematic_svg.symbol(optic,axes))
                rotation=float(root.get('transform')[7:-1])*math.pi/180
                # Front quadratic start, control and end, measured against its chord.
                coords=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',root.find('path').get('d'))[:6]))
                a,q,b=coords[:2],coords[2:4],coords[4:6]
                centre=tuple((a[i]+2*q[i]+b[i])/4 for i in range(2))
                self.assertEqual(centre,(0,0))
                opening=tuple((a[i]+b[i])/2-centre[i] for i in range(2))
                facing=(math.cos(rotation)*opening[0]-math.sin(rotation)*opening[1],math.sin(rotation)*opening[0]+math.cos(rotation)*opening[1])
                normal=schematic_svg.xy(optic['normal'],axes)
                if math.hypot(*normal)>1e-8:self.assertGreater(sum(x*y for x,y in zip(facing,normal)),0,command)


if __name__=='__main__':unittest.main()
