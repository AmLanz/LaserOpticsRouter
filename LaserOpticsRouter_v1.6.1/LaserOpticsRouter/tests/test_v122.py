"""Reflected chains, document export, clipboard ownership and palette lifecycle."""
import ast
import copy
import ctypes
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import exports
import clipboard_support
from test_adapter import backend, Design, Component, Occurrence, Matrix, NS, isolated_entry_function
import test_v120


def plan(commands, endpoint=None, overrides=None):
    c = core.default_config()
    c['rows'][0]['commands'] = commands
    if endpoint: c['rows'][0].update(start_mode='snapshot', endpoint=endpoint['endpoint'])
    c['optic_overrides'] = overrides or {}
    return core.plan_layout(c)


def save(design, p, name, transform=None):
    config = core.snapshot_config(p)
    config['document_id'] = 'doc'
    component = Component(design, name)
    for key, value in [('run_id',config['route_id']), ('revision','1'), ('settings',json.dumps(config)),
                       ('endpoints',json.dumps(p['endpoints']))]:
        component.attributes.add(backend.GROUP,key,value)
    occurrence = Occurrence(design,name,component,transform)
    design.entities[name] = occurrence
    return occurrence


class ReflectedCalculatorTests(unittest.TestCase):
    def test_whole_parent_and_child_use_reflected_budget_once_in_either_order(self):
        a = plan('p100 l50 p20 bsc p300 l100 p10', overrides={
            'line1:1':dict(token='l50',budget=dict(loss_pct=10,gdd_fs2=80,n=1.5,thickness_mm=4)),
            'line1:3':dict(token='bsc',budget=dict(transmission_pct=60,reflection_pct=30,
                gdd_t_fs2=-20,gdd_r_fs2=40,n_r=1.5,thickness_r_mm=6))})
        port = a['rows'][0]['ports'][0]
        b = plan('p50 l-50 p10',port)
        end_a, end_b = a['rows'][0]['endpoint'], b['endpoints'][-1]
        available = a['endpoints']+b['endpoints']
        expected = core.calculate_chain([port,end_b])
        for selected in ([end_a,end_b],[end_b,end_a],[end_a,end_b,port,end_a]):
            r = core.calculate_chain(selected,available)
            self.assertAlmostEqual(r['geometric_mm'],180)
            self.assertAlmostEqual(r['optical_path_mm'],185)
            self.assertAlmostEqual(r['loss_pct'],73.27)
            self.assertAlmostEqual(r['gdd_fs2'],220)
            self.assertEqual(r['contributions'],expected['contributions'])
            self.assertEqual(len(r['notes']),1)

    def test_cascaded_reflections_shorten_both_parents(self):
        a = plan('p100 bsc p200')
        b = plan('p40 bsc- p300',a['rows'][0]['ports'][0])
        c = plan('p60',b['rows'][0]['ports'][0])
        r = core.calculate_chain([x['rows'][0]['endpoint'] for x in (a,b,c)],
                                 a['endpoints']+b['endpoints']+c['endpoints'])
        self.assertEqual(r['geometric_mm'],200)
        self.assertAlmostEqual(r['loss_pct'],100*(1-.49**2))
        self.assertEqual(r['gdd_fs2'],600)
        self.assertEqual(len(r['notes']),2)

    def test_two_continuing_arms_still_rejected(self):
        a = plan('p100 bsc p20')
        b = plan('p40',a['rows'][0]['ports'][0])
        c = plan('p60',a['rows'][0]['endpoint'])
        with self.assertRaisesRegex(core.LayoutError,'one connected arm'):
            core.calculate_chain([x['rows'][0]['endpoint'] for x in (a,b,c)],
                                 a['endpoints']+b['endpoints']+c['endpoints'])

    def test_implicit_reflection_includes_unique_connecting_middle_path(self):
        a = plan('p100 bsc p20')
        b = plan('p40',a['rows'][0]['ports'][0])
        c = plan('p60',b['rows'][0]['endpoint'])
        result=core.calculate_chain([x['rows'][0]['endpoint'] for x in (a,c)],
                                   a['endpoints']+b['endpoints']+c['endpoints'])
        self.assertEqual(result['geometric_mm'],200)
        self.assertEqual(len([s for s in result['selections'] if s['automatic']]),1)

    def test_moved_saved_splitter_is_not_silently_combined_with_old_child(self):
        d = Design(); d.attributes.add(backend.GROUP,'document_id','doc')
        parent = save(d,plan('p100 bsc p20'),'parent')
        port = next(e for e in backend.saved_endpoints(d)['items'] if e['kind']=='reflected')
        save(d,plan('p40',port),'child')
        items = backend.saved_endpoints(d)['items']
        r = core.calculate_chain([e for e in items if e['kind']=='end'],items)
        self.assertEqual(r['geometric_mm'],140)
        parent.transform2 = Matrix(translation=(1,0,0))
        items = backend.saved_endpoints(d)['items']
        with self.assertRaisesRegex(core.LayoutError,'source endpoint moved'):
            core.calculate_chain([e for e in items if e['kind']=='end'],items)


class DocumentExportTests(unittest.TestCase):
    def setUp(self):
        self.d = Design(); self.d.attributes.add(backend.GROUP,'document_id','doc')
        self.a = save(self.d,plan('p100 bsc p20'),'=Parent / α',
                      Matrix(((0,1,0),(-1,0,0),(0,0,1)),(10,20,3)))
        port = next(e for e in backend.saved_endpoints(self.d)['items'] if e['kind']=='reflected')
        self.b = save(self.d,plan('p40',port),'Child')

    def test_one_archive_has_all_paths_world_coordinates_and_importable_routes(self):
        before = copy.deepcopy(self.d.attributes.data)
        routes = backend.document_export(self.d)
        with zipfile.ZipFile(io.BytesIO(exports.export_document_zip(routes,'Lab <&>'))) as z:
            self.assertIsNone(z.testzip())
            manifest = json.loads(z.read('document.json'))
            self.assertEqual(len(manifest['routes']),2)
            self.assertEqual(manifest['routes'][0]['placement'][0],[100,200,30])
            rows = list(csv.DictReader(io.StringIO(z.read('all_paths.csv').decode('utf-8-sig'))))
            self.assertEqual(sum(row['record']=='path' for row in rows),2)
            self.assertEqual(sum(row['record']=='summary' for row in rows),3)
            self.assertIn("'=Parent / α",[r['route_name'] for r in rows])
            for row in (r for r in rows if r['record']=='summary'):
                state,_ = core.decode_endpoint(row['endpoint'])
                self.assertEqual(row['coordinate_frame'],'design-root')
                self.assertEqual([float(row[k]) for k in ('x_mm','y_mm','z_mm')],list(state.position))
            for record in manifest['routes']:
                restored = exports.import_csv(z.read(record['csv']).decode('utf-8-sig'),document_id='doc')
                self.assertEqual(restored['rows'][0]['commands'],record['config']['rows'][0]['commands'])
            for projection in ('XY','XZ','YZ'):
                root = ET.fromstring(z.read('all_paths_'+projection+'.svg'))
                ns = {'s':'http://www.w3.org/2000/svg'}
                lines = root.findall('s:line',ns)
                self.assertEqual(len(lines),3)
                if projection=='XY':
                    self.assertEqual(lines[0].get('data-world-start'),'100,200,30')
                    self.assertEqual(lines[0].get('data-world-end'),'100,300,30')
                self.assertIn('Lab <&>',root.find('s:title',ns).text)
            with self.assertRaisesRegex(core.LayoutError,"individual CSV"):
                exports.import_csv(z.read('all_paths.csv').decode('utf-8-sig'))
        self.assertEqual(self.d.attributes.data,before)
        self.assertEqual(self.d.log,[])

    def test_stale_route_export_includes_flag_and_does_not_rebuild(self):
        self.a.transform2 = Matrix()
        routes = backend.document_export(self.d)
        self.assertTrue(routes[1]['stale'])
        self.assertTrue(routes[1]['reasons'])
        with zipfile.ZipFile(io.BytesIO(exports.export_document_zip(routes))) as z:
            rows = list(csv.DictReader(io.StringIO(z.read('all_paths.csv').decode('utf-8-sig'))))
            self.assertTrue(all(r['outdated']=='yes' for r in rows if r['route_key']=='route_002'))

    def test_empty_and_unreadable_document_are_reported(self):
        with self.assertRaisesRegex(core.LayoutError,'Build a route'):
            backend.document_export(Design())
        self.b.component.attributes.add(backend.GROUP,'settings','{broken')
        with self.assertRaisesRegex(core.LayoutError,'could not read every route'):
            backend.document_export(self.d)

    def test_native_file_bridge_exports_document_without_parsing_the_current_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'all.zip'
            dialog = NS(showSave=lambda:1,filename=str(target))
            context = dict(_ui=NS(createFileDialog=lambda:dialog),_app=NS(activeDocument=NS(name='Lab')),
                           pathlib=__import__('pathlib'),design=lambda:self.d,exports=exports)
            fn = isolated_entry_function('file_exchange',context)
            with patch.object(context['adsk'].core,'DialogResults',NS(DialogOK=1),create=True):
                r = fn(dict(format='document',config=None))
            self.assertEqual(r['route_count'],2)
            self.assertEqual(dialog.filter,'ZIP files (*.zip)')
            with zipfile.ZipFile(target) as z: self.assertIn('all_paths.csv',z.namelist())


class Fn:
    def __init__(self, action): self.action=action
    def __call__(self,*args): return self.action(*args)


class ClipboardTests(unittest.TestCase):
    def windows(self, *, accepted=True, opens=True, owner=True):
        events=[]; buffers={}; stored={}
        def allocate(flags,size):
            self.assertEqual(flags,2)
            buffers[123]=ctypes.create_string_buffer(size)
            return 123
        def receive(kind,handle):
            self.assertEqual(kind,13); self.assertEqual(handle,123)
            stored['bytes']=buffers[handle].raw
            events.append('set')
            return handle if accepted else 0
        user=NS(GetActiveWindow=Fn(lambda:42 if owner else 0),GetForegroundWindow=Fn(lambda:0),
                OpenClipboard=Fn(lambda window:events.append(('open',window)) or opens),
                EmptyClipboard=Fn(lambda:events.append('empty') or True),SetClipboardData=Fn(receive),
                CloseClipboard=Fn(lambda:events.append('close') or True))
        kernel=NS(GlobalAlloc=Fn(allocate),GlobalLock=Fn(lambda h:ctypes.addressof(buffers[h])),
                  GlobalUnlock=Fn(lambda h:True),GlobalFree=Fn(lambda h:events.append(('free',h))))
        return lambda name,**_:user if name=='user32' else kernel,events,stored

    def test_windows_unicode_ownership_transfer_and_cleanup(self):
        dll,events,stored=self.windows()
        with patch.object(clipboard_support.sys,'platform','win32'), patch.object(ctypes,'WinDLL',dll,create=True):
            clipboard_support.copy_text('LOR2: λ\nÄ test 🚀')
        self.assertEqual(stored['bytes'],'LOR2: λ\nÄ test 🚀'.encode('utf-16-le')+b'\0\0')
        self.assertEqual(events,[('open',42),'empty','set','close'])

    def test_windows_rejection_frees_memory_and_closes_clipboard(self):
        dll,events,_=self.windows(accepted=False)
        with patch.object(ctypes,'WinDLL',dll,create=True):
            with self.assertRaisesRegex(RuntimeError,'did not accept'):
                clipboard_support._copy_windows('abc')
        self.assertEqual(events[-2:],['close',('free',123)])

    def test_busy_clipboard_retries_without_emptying_or_leaking(self):
        dll,events,_=self.windows(opens=False)
        with patch.object(ctypes,'WinDLL',dll,create=True),patch.object(clipboard_support.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'clipboard is busy'):
                clipboard_support._copy_windows('abc')
        self.assertEqual(events.count(('open',42)),5)
        self.assertNotIn('empty',events);self.assertNotIn('close',events)
        self.assertEqual(events[-1],('free',123))

    def test_macos_uses_utf8_stdin_without_shell(self):
        with patch.object(clipboard_support.sys,'platform','darwin'),patch.object(clipboard_support.subprocess,'run') as run:
            clipboard_support.copy_text('λ $(not a command)')
        self.assertEqual(run.call_args.args[0],['/usr/bin/pbcopy'])
        self.assertEqual(run.call_args.kwargs['input'],'λ $(not a command)'.encode())
        self.assertNotIn('shell',run.call_args.kwargs)


class BuildWindowTests(unittest.TestCase):
    def test_success_only_closes_when_requested(self):
        for close in (False,True):
            context,sent=test_v120.CommandLifecycleTests().classes()
            palette=NS(isVisible=True)
            context['palette']=lambda:palette
            operation=dict(success={'token':'built'},request={'close':close})
            context['BuildDestroyed'](operation).notify(NS())
            self.assertEqual(palette.isVisible,not close)
            self.assertEqual(sent,[('built',{'token':'built'})])


if __name__ == '__main__': unittest.main()
