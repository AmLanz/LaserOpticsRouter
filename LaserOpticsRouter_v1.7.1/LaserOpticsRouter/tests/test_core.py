"""Run with: python -m unittest discover -s tests -v (no Fusion required)."""
import base64
import copy
import json
import math
import pathlib
import sys
import unittest
from dataclasses import asdict
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core


class RouterTests(unittest.TestCase):
    def plan(self, text, **source):
        config = core.default_config()
        config["source"].update(source)
        config["rows"][0]["commands"] = text
        return core.plan_layout(config)

    def end(self, text, **source):
        return self.plan(text, **source)["rows"][0]["endpoint"]["stats"]

    def assertVector(self, actual, expected, places=9):
        for a, e in zip(actual, expected): self.assertAlmostEqual(a, e, places=places)

    def test_size_prefix_and_focal_sign_are_independent(self):
        optics = self.plan("l50 +l-50 -l50 pol +bs30 -bsc +_r90f50")["optics"]
        self.assertEqual([o["diameter_mm"] for o in optics], [25.4, 50.8, 12.7, 25.4, 50.8, 12.7, 50.8])
        self.assertEqual([o["focal_mm"] for o in optics[:3]], [50, -50, 50])
        self.assertTrue(optics[-1]["flip"])

    def test_every_family_has_configurable_size(self):
        config = core.default_config()
        config["rows"][0]["commands"] = "+l50 +r90 +pol +bs30 +bsc +r90f50"
        for i, kind in enumerate(core.FAMILIES): config["sizes"][kind]["large"] = 31+i
        for optic in core.plan_layout(config)["optics"]:
            self.assertEqual(optic["diameter_mm"], config["sizes"][optic["kind"]]["large"])

    def test_spaces_required_and_legacy_commands_rejected(self):
        for text in ("l50+p50", "l50p50", "p50,l50", "f50", "c0", "e100", "p-1", "l0", "_bs90", "r90f-50"):
            with self.subTest(text=text), self.assertRaises(core.LayoutError): core.parse_commands(text)

    def test_parser_marks_bad_token_exactly(self):
        with self.assertRaises(core.LayoutError) as caught: core.parse_commands("p50 bad l50", 2)
        error = caught.exception
        self.assertEqual((error.row, error.token, error.start, error.end), (2, 1, 4, 7))

    def test_scientific_notation_and_comments(self):
        result = self.end("P1e2 L5e1 p50 # focus here")
        self.assertEqual(result["path_mm"], 150)
        self.assertEqual(result["diameter_mm"], 0)

    def test_positive_lens_focus_and_signed_height_after_focus(self):
        at_focus = self.end("l50 p50")
        after = self.end("l50 p100")
        self.assertEqual(at_focus["status"], "geometric focus")
        self.assertAlmostEqual(after["diameter_mm"], 5)
        self.assertGreater(after["half_angle_mrad"], 0)
        recollimated = self.end("l50 p100 l50 p100")
        self.assertAlmostEqual(recollimated["diameter_mm"], 5)
        self.assertAlmostEqual(recollimated["half_angle_mrad"], 0)

    def test_negative_lens_expansion(self):
        self.assertAlmostEqual(self.end("l-50 p50")["diameter_mm"], 10)

    def test_folded_focus_length(self):
        p = self.plan("p100 l50 p25 r90 p25")
        end = p["rows"][0]["endpoint"]["stats"]
        self.assertVector(end["position"], (125, 25, 0))
        self.assertEqual(end["diameter_mm"], 0)
        self.assertEqual(end["path_mm"], 150)
        self.assertIsNotNone(p["segments"][-2]["trim_end"])
        self.assertIsNotNone(p["segments"][-1]["trim_start"])

    def test_additive_angles_cancel(self):
        s = self.end("r90v30 p100 r-90v-30 p100", azimuth=23, elevation=-12)
        self.assertAlmostEqual(s["azimuth"], 23)
        self.assertAlmostEqual(s["elevation"], -12)
        self.assertVector(s["direction"], core.direction(23, -12))

    def test_vertical_limits_and_degenerate_reflections(self):
        for command in ("r90v91", "r0", "r360", "bs0", "r90f0"):
            with self.subTest(command=command), self.assertRaises(core.LayoutError): self.plan(command)
        state = self.end("r0v90 p20 r0v-90 p10")
        self.assertVector(state["position"], (10, 0, 20))

    def test_specular_normal_in_three_dimensions(self):
        for command in ("r90v30", "r-47v-22", "bs30v17", "r0v50"):
            o = self.plan(command, azimuth=19, elevation=12)["optics"][0]
            reflected = core.sub(o["input_direction"], core.mul(o["normal"], 2*core.dot(o["input_direction"], o["normal"])))
            self.assertVector(reflected, o["output_direction"])
            self.assertAlmostEqual(core.dot(o["frame"][0], o["frame"][2]), 0)

    def test_splitter_keeps_transmission_and_copies_full_branch_state(self):
        p = self.plan("p100 l-50 p20 bs30 p70")
        port = p["rows"][0]["ports"][0]
        state, _ = core.decode_endpoint(port["endpoint"])
        self.assertVector(state.position, (120, 0, 0))
        self.assertAlmostEqual(state.azimuth, 30)
        self.assertAlmostEqual(state.slope, 0.05)
        self.assertEqual(state.path_mm, 120)
        end = p["rows"][0]["endpoint"]["stats"]
        self.assertVector(end["position"], (190, 0, 0))
        self.assertAlmostEqual(p["optics"][-1]["incidence_deg"], 75)
        self.assertEqual(state.boundary_kind, "bs")

    def test_cube_is_always_a_right_angle_for_all_rolls(self):
        for roll in (0, 90, 180, 270, 37):
            config = core.default_config()
            config["source"].update(azimuth=17, elevation=43)
            config["rows"][0]["commands"] = "bsc"
            config["optic_overrides"] = {"line1:0": {"token": "bsc", "roll_deg": roll}}
            optic = core.plan_layout(config)["optics"][0]
            self.assertAlmostEqual(core.dot(optic["input_direction"], optic["output_direction"]), 0)
            self.assertAlmostEqual(optic["bend_deg"], 90)

    def test_oap_parent_axis_and_focal_point(self):
        for flipped in (False, True):
            optic = self.plan(("_" if flipped else "")+"r90v30f50")["optics"][0]
            data = optic["oap"]
            self.assertAlmostEqual(data["parent_focal_mm"], 25)
            self.assertVector(data["parent_axis"], optic["output_direction"] if flipped else (-1,0,0))
            expected_focus = core.add(optic["position"], core.mul(optic["input_direction"], -50)) if flipped else core.add(optic["position"], core.mul(optic["output_direction"], 50))
            self.assertVector(data["focus"], expected_focus)

    def test_oap_surface_reflects_parallel_rays_to_one_focus(self):
        # Independent ray/surface check, beyond just the central ray.
        for command in ("r90f50", "r60v20f80", "r-130v-10f60"):
            optic = self.plan(command, azimuth=27, elevation=15)["optics"][0]
            f = optic["oap"]["parent_focal_mm"]
            rho = optic["oap"]["decenter_mm"]
            for x, y in ((-5,0), (0,4), (6,-3)):
                z = ((x+rho)**2+y*y-rho*rho)/(4*f)
                hit = core.add(optic["position"], core.world(optic["frame"], (x,y,z)))
                local_normal = core.unit((-(x+rho)/(2*f), -y/(2*f), 1))
                normal = core.world(optic["frame"], local_normal)
                d = optic["input_direction"]
                reflected = core.sub(d, core.mul(normal, 2*core.dot(d,normal)))
                self.assertVector(reflected, core.unit(core.sub(optic["oap"]["focus"], hit)))

    def test_flipped_oap_collimates_from_its_focus(self):
        optic = self.plan("_r65v20f80", azimuth=10, elevation=5)["optics"][0]
        f, rho = optic["oap"]["parent_focal_mm"], optic["oap"]["decenter_mm"]
        for x,y in ((-4,2), (0,0), (5,-3)):
            z=((x+rho)**2+y*y-rho*rho)/(4*f)
            hit=core.add(optic["position"],core.world(optic["frame"],(x,y,z)))
            normal=core.world(optic["frame"],core.unit((-(x+rho)/(2*f),-y/(2*f),1)))
            incoming=core.unit(core.sub(hit,optic["oap"]["focus"]))
            reflected=core.sub(incoming,core.mul(normal,2*core.dot(incoming,normal)))
            self.assertVector(reflected,optic["output_direction"])

    def test_oap_pair_recollimates_and_preserves_diameter(self):
        end = self.end("r90f50 p100 _r-90f50 p100")
        self.assertAlmostEqual(end["diameter_mm"], 5)
        self.assertAlmostEqual(end["half_angle_mrad"], 0)
        self.assertVector(end["direction"], (1,0,0))

    def test_gaussian_free_space_matches_rayleigh_solution(self):
        s = core.initial_state(dict(model="gaussian", diameter_mm=1, wavelength_nm=1000, m2=1))
        zr=math.pi*0.5**2/0.001
        self.assertAlmostEqual(s.q_imag,zr)
        self.assertAlmostEqual(s.propagated(zr).radius,0.5*math.sqrt(2))
        self.assertAlmostEqual(s.stats()["far_half_angle_mrad"],1000*math.atan(0.001/(math.pi*0.5)))

    def test_gaussian_lens_has_finite_waist_and_inverse_recovers_input(self):
        s=core.initial_state(dict(model="gaussian",diameter_mm=5,wavelength_nm=800,m2=1.3))
        focused=s.focused(50)
        waist=focused.propagated(-focused.q_real)
        self.assertGreater(waist.radius,0)
        expected=math.sqrt(s.beta*s.q_imag/(1+(s.q_imag/50)**2))
        self.assertAlmostEqual(waist.radius,expected)
        restored=focused.focused(-50)
        self.assertAlmostEqual(restored.q_real,s.q_real,places=7)
        self.assertAlmostEqual(restored.q_imag,s.q_imag,places=7)
        self.assertEqual(waist.stats()["status"],"at Gaussian waist")

    def test_gaussian_quality_parameter_and_diameter_definition(self):
        a=self.end("l50 p50",model="gaussian",m2=1)
        b=self.end("l50 p50",model="gaussian",m2=2)
        self.assertGreater(b["diameter_mm"],a["diameter_mm"]*1.99)
        for key,value in (("m2",0.9),("wavelength_nm",0),("diameter_mm",0)):
            with self.assertRaises(core.LayoutError): self.plan("p100",model="gaussian",**{key:value})

    def test_gaussian_sampling_includes_waist_and_controls_error(self):
        p=self.plan("l50 p100",model="gaussian")
        segment=p["segments"][0]
        samples=core.sample_segment(segment)
        self.assertTrue(any(abs(x+segment["state"].q_real)<1e-10 for x,_ in samples))
        for (a,ra),(b,rb) in zip(samples,samples[1:]):
            r=segment["state"].propagated((a+b)/2).radius
            self.assertLessEqual(abs((ra+rb)/2-r),min(0.01,max(r*0.005,1e-6))+1e-10)

    def test_endpoint_round_trip_preserves_complete_beam_and_interface(self):
        for model in ("geometric","gaussian"):
            p=self.plan("l50 p75 bs-60v15",model=model,m2=1.5)
            port=p["rows"][0]["ports"][0]
            state,name=core.decode_endpoint(port["endpoint"])
            self.assertEqual(asdict(state), {**port["state"],"position":tuple(port["state"]["position"]),"boundary_normal":tuple(port["state"]["boundary_normal"])})
            q=core.default_config();q["rows"][0].update(start_mode="snapshot",endpoint=port["endpoint"],commands="p40")
            continuation=core.plan_layout(q)
            expected=state.propagated(40)
            self.assertVector(continuation["rows"][0]["endpoint"]["stats"]["position"],expected.position)
            self.assertAlmostEqual(continuation["rows"][0]["endpoint"]["stats"]["diameter_mm"],2*expected.radius)
            self.assertIsNotNone(continuation["segments"][0]["trim_start"])

    def test_malformed_or_partial_endpoint_is_rejected(self):
        for value in ("", "LOR1:garbage", "hello", "LOR1:"+base64.urlsafe_b64encode(b'{"version":1}').decode()):
            with self.assertRaises(core.LayoutError): core.decode_endpoint(value)

    def test_multiple_lines_keep_local_and_cumulative_lengths(self):
        c=core.default_config();c["rows"][0]["commands"]="l-50 p50"
        c["rows"].append(dict(id="line2",name="Continuation",commands="p75",start_mode="previous"))
        p=core.plan_layout(c)
        self.assertEqual([r["length_mm"] for r in p["rows"]],[50,75])
        self.assertEqual(p["rows"][1]["endpoint"]["stats"]["path_mm"],125)
        self.assertAlmostEqual(p["rows"][1]["endpoint"]["stats"]["diameter_mm"],17.5)

    def test_custom_transform_ignores_old_calibration_and_uses_x_normal(self):
        optic=self.plan("r70v20f50")["optics"][0]
        optic["settings"]={"reference":[11,-4,8],"shift":[2,3,-1],"rotation":[25,70,-30]}
        origin,basis=core.custom_transform(optic)
        self.assertVector(origin,optic['position'])
        self.assertVector(basis[0],optic['normal'])
        self.assertVector(core.cross(basis[0],basis[1]),basis[2])

    def test_fixed_axis_rotation_order(self):
        basis=core.rotated_columns(((1,0,0),(0,1,0),(0,0,1)),90,90,0)
        self.assertVector(core.world(basis,(0,0,1)),(0,-1,0))

    def test_plan_does_not_mutate_configuration(self):
        config=core.default_config();before=copy.deepcopy(config)
        core.plan_layout(config)
        self.assertEqual(config,before)

    def test_singular_and_nonfinite_input_rejected(self):
        for changes in ({"position":[0,0,float('nan')]},{"half_angle_mrad":float('inf')},{"elevation":91},{"model":"unknown"}):
            with self.assertRaises(core.LayoutError): core.initial_state(changes)


if __name__ == "__main__": unittest.main()
