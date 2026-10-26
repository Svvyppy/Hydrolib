import unittest
import sys
from pathlib import Path
import openpyxl
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xlsm_merge'))
from merge import workbook_changes, merge, Resolver
import test_xlsm_merge

class ChangesTests(unittest.TestCase):
    def test_delta_and_formula_relocation(self):
        before, after = openpyxl.Workbook(), openpyxl.Workbook()
        for w in (before, after):
            w.active.append(['Part Number', 'Value', 'Formula'])
        before.active.append(['A', 10, '=A2&B2'])
        before.active.append(['DELETED', 1])
        after.active.append(['NEW', 1])
        after.active.append(['A', 20, '=A3&B3'])
        changes = workbook_changes(before, after)
        self.assertEqual(changes['added'][0]['part'], 'NEW')
        self.assertEqual(changes['deleted'][0]['part'], 'DELETED')
        self.assertEqual(len(changes['modified']), 1)
        self.assertEqual(changes['modified'][0]['before'], 10)
        self.assertEqual(changes['modified'][0]['after'], 20)

    def test_report_uses_target_and_includes_merged_additions(self):
        fixture = test_xlsm_merge.MergeTests()
        fixture.setUp()
        try:
            fixture.ours = fixture.variant('ours', {'A3': 'NEW', 'B3': 42})
            fixture.theirs = fixture.variant('theirs', {'B2': 99})
            resolver = Resolver((fixture.base, fixture.ours, fixture.theirs))
            merge(fixture.base, fixture.ours, fixture.theirs, fixture.output, resolver)
            changes = resolver.report('merged')['changes']
            self.assertEqual(changes['added'][0]['part'], 'NEW')
            self.assertEqual(changes['modified'], [])
        finally:
            fixture.doCleanups()
