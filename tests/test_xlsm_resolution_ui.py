import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xlsm_merge'))
from resolution_ui import write_resolution_ui
from merge import Resolver, Conflict

class ResolutionUITests(unittest.TestCase):
    def test_safe_embedded_report_and_version_binding(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            paths = [d / f'{i}.xlsx' for i in range(3)]
            for i, p in enumerate(paths):
                p.write_bytes(str(i).encode())
            resolver = Resolver(paths)
            resolver.choose('base', '</script><script>alert(1)</script>', 'theirs', {'kind': 'cell', 'part': '<img>'})
            report = resolver.report('conflict')
            (d / 'report.json').write_text(json.dumps(report))
            (d / 'context.json').write_text(json.dumps({'number': '13'}))
            page = write_resolution_ui(d, 'a/b', 'other').read_text()
            self.assertNotIn('</script><script>alert(1)</script>', page)
            payload = page.split('<script id="data" type="application/json">')[1].split('</script>')[0]
            data = json.loads(payload)
            self.assertEqual(data['number'], '13')
            self.assertEqual(data['report'], report)
            document = {'version': report['version'], 'inputs': report['inputs'],
                        'conflicts': [{'id': report['conflicts'][0]['id'], 'choice': 'theirs'}]}
            resolved = Resolver(paths, document)
            self.assertEqual(resolved.choose('base', 'ours', 'theirs', {'kind': 'cell', 'part': '<img>'}), 'theirs')
            resolved.finish()
            paths[1].write_bytes(b'changed')
            with self.assertRaisesRegex(Conflict, 'stale'):
                Resolver(paths, document)

    def test_no_conflicts_removes_stale_picker(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, 'resolve-conflicts.html')
            p.write_text('old')
            self.assertIsNone(write_resolution_ui(d, 'a/b', '1'))
            self.assertFalse(p.exists())

    def test_javascript_mixed_choices_filters_and_export(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is unavailable for embedded JavaScript checks')
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            paths = [d / f'{i}.xlsx' for i in range(3)]
            for i, p in enumerate(paths):
                p.write_bytes(str(i).encode())
            resolver = Resolver(paths)
            for part in ('FIRST', '</script><img>', 'THIRD'):
                resolver.choose('base', 'ours', 'theirs', {'kind': 'cell', 'part': part})
            (d / 'report.json').write_text(json.dumps(resolver.report('conflict')))
            page = write_resolution_ui(d, 'a/b', '13')
            script = Path(__file__).with_name('xlsm_resolution_ui.cjs')
            result = subprocess.run([node, str(script), str(page)], check=True, capture_output=True, text=True)
            document = json.loads(result.stdout)
            resolved = Resolver(paths, document)
            for part, expected in zip(('FIRST', '</script><img>', 'THIRD'), ('ours', 'theirs', 'ours')):
                self.assertEqual(resolved.choose('base', 'ours', 'theirs', {'kind': 'cell', 'part': part}), expected)
            resolved.finish()
