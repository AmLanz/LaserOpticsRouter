"""Default reuse, CAD-only flips and complete 3D continuation regressions."""
import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core


class DefaultsAndFlipTests(unittest.TestCase):
    def config(self, commands):
        c = core.default_config()
        c['rows'][0]['commands'] = commands
        c['component_defaults']['l50'] = dict(component_token='occ-A', component_ref_token='part-A',
            component_name='Lens A', reference=[1, 2, 3], shift=[4, 5, 6], rotation=[10, 20, 30])
        return c

    def assertVector(self, actual, expected):
        for a, b in zip(actual, expected): self.assertAlmostEqual(a, b, places=9)

    def test_defaults_match_command_size_and_normalized_numbers(self):
        plan = core.plan_layout(self.config('l50 L5e1 fl50 l-50 +l50 -l50'))
        self.assertEqual([o['settings']['custom'] for o in plan['optics']], [True, True, True, False, False, False])
        self.assertEqual([o['default_key'] for o in plan['optics']], ['l50', 'l50', 'l50', 'l-50', '+l50', '-l50'])
        self.assertEqual(plan['optics'][2]['settings']['reference'], [1, 2, 3])

    def test_builtin_default_and_new_custom_are_independent_choices(self):
        c = self.config('l50 l50 l50')
        c['optic_overrides'] = {
            'line1:0': dict(token='l50', representation='builtin'),
            'line1:1': dict(token='l50', representation='default'),
            'line1:2': dict(token='l50', representation='custom', component_token='occ-B')}
        a, b, d = core.plan_layout(c)['optics']
        self.assertFalse(a['settings']['custom'])
        self.assertEqual(b['settings']['component_token'], 'occ-A')
        self.assertEqual(d['settings']['component_token'], 'occ-B')
        self.assertEqual(c['component_defaults']['l50']['component_token'], 'occ-A')

    def test_old_custom_flag_is_preserved_after_upgrade(self):
        c = self.config('l50 l50')
        c['optic_overrides'] = {'line1:0': dict(token='l50', custom=False),
            'line1:1': dict(token='l50', custom=True, component_token='legacy')}
        optics = core.plan_layout(c)['optics']
        self.assertFalse(optics[0]['settings']['custom'])
        self.assertEqual(optics[1]['settings']['component_token'], 'legacy')

    def test_missing_default_uses_builtin_fallback_and_remains_live(self):
        c = self.config('l-50')
        c['optic_overrides']['line1:0'] = dict(representation='default')
        s=core.plan_layout(c)['optics'][0]['settings']
        self.assertEqual(s['representation'],'default');self.assertFalse(s['custom'])

    def test_snapshot_freezes_both_builtin_and_default_choices(self):
        c = self.config('l50 l75')
        frozen = core.snapshot_config(core.plan_layout(c))
        frozen['component_defaults'] = {'l50': dict(component_token='changed'), 'l75': dict(component_token='new')}
        first, second = core.plan_layout(frozen)['optics']
        self.assertEqual(first['settings']['component_token'], 'occ-A')
        self.assertFalse(second['settings']['custom'])

    def test_template_is_a_deep_copy_and_excludes_command_flip(self):
        s = dict(component_token='part', reference=[1, 2, 3], visual_flip=True, token='fl50', custom=True)
        t = core.component_template(s)
        t['reference'][0] = 7
        self.assertEqual(s['reference'][0], 1)
        self.assertNotIn('visual_flip', t)
        self.assertNotIn('token', t)
        self.assertEqual(t['shift'], [0, 0, 0])
        with self.assertRaises(core.LayoutError): core.component_template({"custom":True})

    def test_f_prefix_accepts_all_optics_and_modifier_orders(self):
        tokens = core.parse_commands('fl50 f+l-50 +fl50 -fpol f-pol fr90 fbs30 fbsc f_r90v30f50 _+fr90f50')
        self.assertTrue(all(t['visual_flip'] for t in tokens))
        self.assertEqual(tokens[1]['focal'], -50)
        self.assertEqual(tokens[-1]['size'], 'large')
        self.assertTrue(tokens[-1]['flip'])
        for command in ('fp50', 'f50', 'ffl50', 'f+-l50', 'f__r90f50'):
            with self.subTest(command=command), self.assertRaises(core.LayoutError): core.parse_commands(command)

    def test_f_flip_keeps_optical_states_for_all_families(self):
        for command in ('l50', 'r60v20', 'pol', 'bs30v15', 'bsc', 'r90f50', '_r90f50'):
            with self.subTest(command=command):
                a = core.plan_layout(self.config(command+' p80'))
                b = core.plan_layout(self.config('f'+command+' p80'))
                for ea, eb in zip(a['endpoints'], b['endpoints']):
                    self.assertEqual({k:v for k,v in ea['state'].items() if k != 'trace'},
                                     {k:v for k,v in eb['state'].items() if k != 'trace'})
                basis_a, basis_b = map(core.representation_frame, (a['optics'][0], b['optics'][0]))
                self.assertVector(basis_b[0], core.mul(basis_a[0], -1))
                self.assertVector(basis_b[1], core.mul(basis_a[1], -1))
                self.assertVector(basis_b[2], basis_a[2])

    def test_flipped_custom_datum_stays_fixed_with_offsets_and_rotations(self):
        o = core.plan_layout(self.config('fl50'))['optics'][0]
        origin, basis = core.custom_transform(o)
        self.assertVector(core.add(origin, core.world(basis, o['settings']['reference'])),
                          core.add(o['position'], core.world(o['frame'], o['settings']['shift'])))
        expected = core.rotated_columns(o['frame'], 10, 20, 210)
        for a, b in zip(basis, expected): self.assertVector(a, b)

    def test_copy_paste_keeps_3d_direction_and_divergence_in_both_models(self):
        for model in ('geometric', 'gaussian'):
            c = self.config('p20 l-50 r70v25 p35 bs30v-10')
            c['source'].update(model=model, azimuth=17, elevation=-4)
            p = core.plan_layout(c)
            for e in p['endpoints']:
                state, _ = core.decode_endpoint(e['endpoint'])
                self.assertVector(state.d, e['stats']['direction'])
                follow = self.config('p100')
                follow['rows'][0].update(start_mode='snapshot', endpoint=e['endpoint'])
                actual = core.plan_layout(follow)['rows'][0]['endpoint']['stats']
                expected = state.propagated(100).stats()
                self.assertVector(actual['direction'], expected['direction'])
                self.assertVector(actual['position'], expected['position'])
                self.assertAlmostEqual(actual['half_angle_mrad'], expected['half_angle_mrad'])

    def test_renamed_and_removed_rows_update_endpoint_records(self):
        c = self.config('p10')
        c['rows'] += [dict(id='remove', name='Remove', commands='p20', start_mode='previous'),
                      dict(id='keep', name='Keep', commands='p30', start_mode='previous')]
        c['rows'].pop(1)
        c['rows'][0]['name'] = 'Renamed'
        p = core.plan_layout(c)
        self.assertEqual([e['name'] for e in p['endpoints']], ['Renamed · end', 'Keep · end'])
        self.assertEqual(p['endpoints'][-1]['stats']['path_mm'], 40)


    def test_oap_orientations_share_the_same_default_key(self):
        for a, b in [('r90f50', '_r90f50'), ('+r90v30f50', '_+r90v30f50'),
                     ('fr60f100', '+fr60f100')]:
            left, right = map(lambda s:core.default_key(core.parse_commands(s)[0]), (a,b))
            if a.startswith('fr60'): self.assertNotEqual(left, right)  # Sizes remain distinct.
            else: self.assertEqual(left, right)
        self.assertNotEqual(core.default_key(core.parse_commands('r90f50')[0]),
                            core.default_key(core.parse_commands('r60f50')[0]))
        self.assertNotEqual(core.default_key(core.parse_commands('r90f50')[0]),
                            core.default_key(core.parse_commands('r90f100')[0]))

    def test_one_oap_default_supplies_both_frames_without_changing_calibration(self):
        c = self.config('r90f50 _r90f50')
        calibration = dict(component_token='oap', reference=[11,4,2], shift=[1,0,0], rotation=[5,6,7])
        c['component_defaults'] = {'r90f50': calibration}
        optics = core.plan_layout(c)['optics']
        for optic in optics:
            self.assertEqual(optic['default_key'], 'r90f50')
            self.assertTrue(optic['settings']['custom'])
            for field, expected in calibration.items(): self.assertEqual(optic['settings'][field], expected)
            origin, basis = core.custom_transform(optic)
            self.assertVector(core.add(origin, core.world(basis, calibration['reference'])),
                core.add(optic['position'], core.world(optic['frame'], calibration['shift'])))
        self.assertNotEqual(optics[0]['frame'], optics[1]['frame'])

    def test_legacy_underscore_only_default_is_available_in_both_orientations(self):
        c = self.config('r90f50 _r90f50')
        c['component_defaults'] = {'_r90f50': {'component_token':'old-oap'}}
        before = copy.deepcopy(c)
        optics = core.plan_layout(c)['optics']
        self.assertEqual([o['settings']['component_token'] for o in optics], ['old-oap','old-oap'])
        self.assertEqual(c, before)

    def test_oap_default_collision_prefers_unprefixed_independent_of_order(self):
        a, b = {'component_token':'unprefixed'}, {'component_token':'flipped'}
        for table in ({'_r90f50':b,'r90f50':a}, {'r90f50':a,'_r90f50':b}):
            normalized = core.normalize_component_defaults(table)
            self.assertEqual(normalized, {'r90f50':a})
            normalized['r90f50']['component_token'] = 'changed'
            self.assertEqual(a['component_token'], 'unprefixed')

    def test_existing_explicit_oap_placements_survive_default_merge(self):
        c = self.config('r90f50 _r90f50')
        c['component_defaults'] = {'r90f50':dict(component_token='new-shared')}
        c['optic_overrides'] = {
            'line1:0':dict(token='r90f50', representation='custom', component_token='existing-A', rotation=[1,2,3]),
            'line1:1':dict(token='_r90f50', representation='custom', component_token='existing-B', rotation=[4,5,6])}
        optics = core.plan_layout(core.snapshot_config(core.plan_layout(c)))['optics']
        self.assertEqual([o['settings']['component_token'] for o in optics], ['existing-A','existing-B'])
        self.assertEqual(optics[1]['settings']['rotation'], [4,5,6])


if __name__ == '__main__': unittest.main()
