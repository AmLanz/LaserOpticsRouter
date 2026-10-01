"""v1.7 physics, persistence, prepared components and anisotropic skin regressions."""
import copy
import csv
import io
import math
import random
import sys
import unittest
from collections import Counter
from pathlib import Path
from dataclasses import asdict, replace
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core, beam_matrix, envelope_geometry, exports, workflow
from test_adapter import backend, Design, Component, Occurrence, Matrix


def layout(commands, model='geometric', spectrum=None, **source):
    c=core.default_config();c['rows'][0]['commands']=commands
    c['source'].update(model=model,**source)
    if spectrum is not None:c['source']['spectrum']=spectrum
    return core.plan_layout(c)


def end(plan): return core.state_from_dict(plan['rows'][-1]['endpoint']['state'])


class CylindricalTests(unittest.TestCase):
    def test_horizontal_line_focus_keeps_vertical_diameter(self):
        s=end(layout('cyl50h p50')).stats()
        self.assertAlmostEqual(s['diameter_h_mm'],0)
        self.assertAlmostEqual(s['diameter_v_mm'],5)

    def test_vertical_negative_cylinder_diverges_only_vertical(self):
        s=end(layout('cyl-50v p50')).stats()
        self.assertAlmostEqual(s['diameter_h_mm'],5)
        self.assertAlmostEqual(s['diameter_v_mm'],10)

    def test_crossed_equal_cylinders_equal_spherical_lens(self):
        for model in ('gaussian','geometric'):
            for distance in (0,10,49,50,51,200):
                a=end(layout(f'cyl50h cyl50v p{distance}',model));b=end(layout(f'l50 p{distance}',model))
                self.assertAlmostEqual(a.radius,b.radius,places=7)

    def test_spherical_lens_after_cylinder_focuses_both_planes(self):
        s=end(layout('cyl100h l100 p50')).stats()
        self.assertAlmostEqual(s['diameter_h_mm'],0)
        self.assertAlmostEqual(s['diameter_v_mm'],2.5)

    def test_gaussian_cylinder_has_finite_line_waist(self):
        s=end(layout('cyl100h p100','gaussian'))
        beta=800e-6/math.pi
        self.assertAlmostEqual(s.stats()['diameter_h_mm'],2*beta*100/2.5,places=8)
        self.assertAlmostEqual(s.stats()['diameter_v_mm'],2*math.sqrt(2.5**2+(beta*100/2.5)**2),places=8)

    def test_mirror_fold_transports_cylindrical_plane(self):
        straight=end(layout('cyl50v p50'))
        folded=end(layout('cyl50v p25 r90 p25'))
        self.assertAlmostEqual(straight.stats()['diameter_v_mm'],folded.stats()['diameter_v_mm'])
        self.assertAlmostEqual(folded.stats()['diameter_h_mm'],5)

    def test_gaussian_moment_solver_agrees_with_scalar_at_all_distances(self):
        s=core.initial_state(dict(model='gaussian',diameter_mm=1,half_angle_mrad=-4,wavelength_nm=1030,m2=1.4))
        m=replace(s,moments=beam_matrix.seed(s))
        for d in (0,1,20,100,300):
            self.assertAlmostEqual(s.propagated(d).radius,m.propagated(d).radius,places=10)

    def test_seeded_nonplanar_exact_foci_remain_valid(self):
        r=random.Random(147)
        for i in range(40):
            f,g=r.uniform(10,200),r.uniform(10,200)
            p=layout(f'cyl{f}h p{f} cyl{g}v p{g} r50v10 p100',
                     'gaussian' if i%2 else 'geometric',azimuth=r.uniform(0,360),elevation=r.uniform(-35,35))
            self.assertTrue(math.isfinite(end(p).radius))

    def test_rigid_rotation_and_inverse_recover_covariance(self):
        s=end(layout('cyl70h p23 cyl100v p17'))
        rotation=core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),37,23,-49)
        inv=tuple(tuple(rotation[j][i] for j in range(3)) for i in range(3))
        moved=core.moved_state(s,(0,0,0),rotation)
        restored=core.moved_state(moved,(0,0,0),inv)
        for a,b in zip(s.moments,restored.moments):
            for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=10)


class GratingTests(unittest.TestCase):
    def test_normal_incidence_uses_grating_equation(self):
        p=layout('gr600a0m1h p100');o=p['optics'][0]
        self.assertAlmostEqual(math.sin(math.radians(o['beta_deg'])),.48)
        self.assertAlmostEqual(end(p).d[0],-math.sqrt(1-.48**2))
        self.assertAlmostEqual(end(p).d[1],.48)

    def test_littrow_retroreflection_and_unity_width(self):
        a=math.degrees(math.asin(.48/2))
        p=layout(f'gr600a{a}m1h p10');o=p['optics'][0]
        self.assertAlmostEqual(o['alpha_deg'],o['beta_deg'])
        self.assertAlmostEqual(o['anamorphic'],1)
        self.assertAlmostEqual(end(p).d[0],-1)
        self.assertAlmostEqual(end(p).radius,2.5)

    def test_zero_order_is_specular_for_signed_incidence(self):
        for angle in (-45,0,30):
            p=layout(f'gr600a{angle}m0h');o=p['optics'][0]
            expected=core.sub((1,0,0),core.mul(o['normal'],2*core.dot((1,0,0),o['normal'])))
            for a,b in zip(end(p).d,expected):self.assertAlmostEqual(a,b)
            self.assertAlmostEqual(end(p).radius,2.5)

    def test_anamorphic_width_and_unchanged_groove_dimension(self):
        p=layout('gr600a30m1h');o=p['optics'][0];s=end(p).stats()
        self.assertAlmostEqual(s['diameter_h_mm'],5*o['anamorphic'])
        self.assertAlmostEqual(s['diameter_v_mm'],5)

    def test_negative_order_and_vertical_plane(self):
        a=end(layout('gr600a0m-1v'))
        self.assertAlmostEqual(a.d[2],-.48);self.assertAlmostEqual(a.d[1],0,places=12)

    def test_impossible_and_grazing_orders_fail_explicitly(self):
        for cmd in ('gr2000a0m1h','gr1250a0m1h'):
            with self.assertRaisesRegex(core.LayoutError,'evanescent or grazing'):layout(cmd)

    def test_sidebands_create_three_rays_at_exact_wavelengths(self):
        p=layout('gr600a0m1h p100',spectrum=dict(mode='sidebands',width_nm=20))
        self.assertEqual(len(p['segments']),3)
        self.assertEqual(sorted(s['state'].wavelength_nm for s in p['segments']),[780,800,820])
        self.assertEqual(len(p['rows'][0]['ports']),2)
        for e in p['rows'][0]['ports']:self.assertEqual(e['kind'],'spectral')

    def test_gaussian_spectrum_is_in_wavelength_and_peak_normalized(self):
        p=layout('gr600a0m1h p100',spectrum=dict(mode='gaussian',width_nm=20,samples=7))
        samples=p['optics'][0]['spectral_samples'];sigma=20/(2*math.sqrt(2*math.log(2)))
        self.assertEqual(len(samples),7)
        self.assertAlmostEqual(samples[0]['wavelength_nm'],800-3*sigma)
        self.assertAlmostEqual(samples[0]['weight'],math.exp(-4.5))
        self.assertEqual(samples[3]['weight'],1)
        self.assertAlmostEqual(samples[-1]['weight'],samples[0]['weight'])

    def test_sampled_gaussian_spatial_envelope_at_grating_is_same_incident_size(self):
        s=core.initial_state(dict(model='gaussian',diameter_mm=3,half_angle_mrad=-2))
        for wavelength in (700,800,900):
            r=core.with_wavelength(s,wavelength)
            self.assertAlmostEqual(r.radius,s.radius)
            self.assertAlmostEqual(r.radial_slope,s.radial_slope)

    def test_bandwidth_does_not_change_existing_optics(self):
        a=layout('p50 l50 p80 r90 p30')
        b=layout('p50 l50 p80 r90 p30',spectrum=dict(mode='gaussian',width_nm=40,samples=9))
        self.assertEqual(len(a['segments']),len(b['segments']))
        self.assertEqual(end(a).stats(),end(b).stats())

    def test_spectral_fan_continues_through_next_optic(self):
        p=layout('gr600a0m1h p100 l50 p50',spectrum=dict(mode='sidebands',width_nm=20))
        self.assertEqual(len(p['segments']),6)
        self.assertFalse(any('stop at the next optic' in w for w in p['warnings']))
        self.assertTrue(all(e['stats']['path_mm']>=150 for e in p['rows'][0]['ports']))

    def test_gaussian_samples_invalid_count_and_nonpositive_wavelength_rejected(self):
        for s in (dict(mode='gaussian',width_nm=10,samples=8),dict(mode='sidebands',width_nm=800),dict(mode='gaussian',width_nm=-1),dict(mode='unknown')):
            with self.subTest(s=s),self.assertRaises(core.LayoutError):layout('p10',spectrum=s)

    def test_inaccessible_sideband_order_blocks_the_fan(self):
        with self.assertRaisesRegex(core.LayoutError,'evanescent'):
            layout('gr1200a0m1h p10',spectrum=dict(mode='sidebands',width_nm=100))

    def test_weight_does_not_multiply_budget_throughput(self):
        p=layout('gr600a0m1h p10',spectrum=dict(mode='gaussian',width_nm=30,samples=9))
        for e in p['endpoints']:self.assertEqual(e['state']['throughput'],1)


class ResetTests(unittest.TestCase):
    def test_exact_requested_collimated_example(self):
        s=end(layout('l20 p15 resetd5finf p1000'))
        self.assertEqual(s.radius,2.5);self.assertEqual(s.slope,0)

    def test_exact_requested_geometric_focusing_example(self):
        s=end(layout('resetd5f50 p50'))
        self.assertEqual(s.radius,0)

    def test_reset_preserves_ray_and_budget_but_removes_astigmatism(self):
        p=layout('p20 cyl50h p10 r30 resetd5finf')
        s=end(p);self.assertEqual(s.moments,[])
        self.assertEqual(s.position,(30,0,0));self.assertAlmostEqual(s.azimuth,30)
        self.assertEqual(s.path_mm,30);self.assertAlmostEqual(s.throughput,.99**2)
        self.assertEqual(s.gdd_fs2,100)

    def test_gaussian_reset_places_waist_at_requested_distance(self):
        at=end(layout('resetd5f50','gaussian'))
        self.assertAlmostEqual(at.radius,2.5)
        self.assertAlmostEqual(at.stats()['waist_distance_mm'],50)
        waist=at.propagated(50)
        self.assertEqual(waist.q_real,0);self.assertGreater(waist.radius,0)

    def test_gaussian_collimated_reset_diffraction_is_retained(self):
        at=end(layout('resetd5finf','gaussian'))
        self.assertEqual(at.q_real,0)
        self.assertGreater(at.propagated(1000).radius,at.radius)

    def test_gaussian_impossible_focus_is_rejected(self):
        with self.assertRaisesRegex(core.LayoutError,'cannot have a waist'):
            layout('resetd0.01f100','gaussian')

    def test_negative_focus_means_divergent_beam(self):
        self.assertEqual(end(layout('resetd5f-50 p50')).radius,5)

    def test_zero_diameter_and_focus_are_rejected(self):
        for cmd in ('resetd0finf','resetd5f0','resetd-5finf','cyl0h','gr600a0m1.5h'):
            with self.subTest(cmd=cmd),self.assertRaises(core.LayoutError):layout(cmd)


class PersistenceAndCad(unittest.TestCase):
    def test_v3_packet_keeps_matrix_and_spectrum_and_reads_old_packets(self):
        p=layout('cyl50h p20',spectrum=dict(mode='gaussian',width_nm=20,samples=9))
        ep=p['endpoints'][-1]['endpoint'];self.assertTrue(ep.startswith('LOR3:'))
        s,_=core.decode_endpoint(ep);self.assertEqual(asdict(s),p['endpoints'][-1]['state'])
        old=layout('p10')['endpoints'][-1]['endpoint'];self.assertTrue(old.startswith('LOR2:'));core.decode_endpoint(old)

    def test_csv_roundtrip_and_summary_dimensions(self):
        p=layout('cyl50h p25 resetd5finf gr600a0m1h p10',spectrum=dict(mode='sidebands',width_nm=10))
        data=exports.export_csv(p);restored=core.plan_layout(exports.import_csv(data))
        self.assertEqual(end(p).stats(),end(restored).stats())
        rows=list(csv.DictReader(io.StringIO(data.lstrip('\ufeff'))))
        summaries=[r for r in rows if r['record']=='summary']
        self.assertTrue(all(r['wavelength_nm'] and r['diameter_h_mm'] for r in summaries))

    def test_default_grating_key_ignores_incidence_order_plane(self):
        a,b=map(lambda s:core.default_key(core.parse_commands(s)[0]),('gr600a10m1h','gr600a-30m-1v'))
        self.assertEqual(a,b)

    def test_all_cad_components_have_prepared_origin_and_right_handed_x_normal(self):
        for cmd in ('l50','r90','bs60','r90f50','_r90f50','cyl100v','gr600a20m1h','pol','tp20d1'):
            p=layout('p10 '+cmd);o=p['optics'][0]
            o['settings'].update(reference=[100,200,300],shift=[9,8,7],rotation=[90,20,50])
            origin,axes=core.custom_transform(o)
            self.assertEqual(origin,tuple(o['position']))
            for a,b in zip(axes[0],o['normal']):self.assertAlmostEqual(a,b)
            for a,b in zip(core.cross(axes[0],axes[1]),axes[2]):self.assertAlmostEqual(a,b)

    def test_custom_cad_stays_upright_and_optical_power_frame_is_separate(self):
        o=layout('cyl100v')['optics'][0]
        self.assertEqual(tuple(o['cad_frame'][2]),(0,0,1))
        self.assertEqual(tuple(o['frame'][0]),(0,0,1))
        o=layout('gr600a0m1h')['optics'][0]
        self.assertAlmostEqual(abs(core.dot(o['cad_frame'][2],(0,0,1))),1)

    def test_source_choice_lists_hidden_sources_and_excludes_generated_routes(self):
        d=Design();source=Occurrence(d,'ref',Component(d,'prepared'));source.isLightBulbOn=False
        route=Occurrence(d,'route',Component(d,'route'));route.component.attributes.add(backend.GROUP,'endpoints','[]')
        nested=Occurrence(d,'route+beam',Component(d,'beam'))
        d.rootComponent=NS(allOccurrences=[source,route,nested]);d.entities['ref']=[source]
        choices=backend.component_choices(d)
        self.assertEqual([c['component_token'] for c in choices],['ref'])
        with patch.object(d,'findEntityByToken',return_value=[source]):
            self.assertEqual(backend.choose_component(d,'opaque-token')['component_name'],'ref')
        with patch.object(d,'findEntityByToken',return_value=[]):
            with self.assertRaisesRegex(core.LayoutError,'missing or ambiguous'):backend.choose_component(d,'missing')

    def test_native_transform_adapter_rotates_anisotropic_state(self):
        s=end(layout('cyl100h p40'));m=Matrix(axes=core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),20,30,40),translation=(1,2,3))
        actual=backend.transformed_state(asdict(s),m)
        expected=core.moved_state(s,(10,20,30),m.axes)
        self.assertAlmostEqual(actual.radius,expected.radius)
        for x,y in zip(actual.position,expected.position):self.assertAlmostEqual(x,y)

    def test_old_scalar_fingerprint_remains_identical(self):
        import hashlib,json
        data=asdict(end(layout('p10')))
        legacy={k:v for k,v in data.items() if k not in ('trace','link','color','moments','spectrum','spectral_weight','spectral_rays')}
        def rounded(v):
            if isinstance(v,(float,int)):return round(v,7)
            if isinstance(v,(list,tuple)):return [rounded(x) for x in v]
            return v
        expected=hashlib.sha256(json.dumps({k:rounded(v) for k,v in legacy.items()},sort_keys=True).encode()).hexdigest()[:24]
        self.assertEqual(core.state_fingerprint(data),expected)


class EnvelopeSkinTests(unittest.TestCase):
    def test_closed_oriented_skin_has_two_opposing_uses_of_each_edge(self):
        seg=layout('cyl100h p60')['segments'][0]
        vertices,faces,limited=envelope_geometry.skin(seg)
        directed=Counter((a,b) for f in faces for a,b in zip(f,f[1:]+f[:1]))
        for (a,b),n in directed.items():self.assertEqual(n,1);self.assertEqual(directed[b,a],1)
        self.assertFalse(limited)
        self.assertTrue(all(math.isfinite(v) for p in vertices for v in p))

    def test_faceted_volume_matches_analytic_cylindrical_focus_cone(self):
        seg=layout('cyl100h p60')['segments'][0]
        vertices,faces,_=envelope_geometry.skin(seg,sides=96)
        volume=0
        for f in faces:
            a=vertices[f[0]]
            for i in range(1,len(f)-1):volume+=core.dot(a,core.cross(vertices[f[i]],vertices[f[i+1]]))/6
        expected=math.pi*2.5**2*(60-60**2/200)
        self.assertGreater(volume,0);self.assertAlmostEqual(volume/expected,1,delta=.002)

    def test_geometric_line_focus_is_clamped_for_solid_only(self):
        p=layout('cyl50h p50');_,_,limited=envelope_geometry.skin(p['segments'][0])
        self.assertTrue(limited);self.assertEqual(end(p).stats()['diameter_h_mm'],0)

    def test_wire_preview_shows_narrowing_dimension(self):
        p=layout('cyl50h p50');g=workflow.wire_geometry(p)
        points=g['envelope'];self.assertTrue(points)
        end_points=[v for v in points if abs(v[0]-50)<1e-8]
        self.assertTrue(all(abs(v[1])<1e-8 for v in end_points))
        self.assertTrue(any(abs(v[2])>2 for v in end_points))


if __name__=='__main__':unittest.main()
