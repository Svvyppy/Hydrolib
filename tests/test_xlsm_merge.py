from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as E
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xlsm_merge'))
from merge import merge, Conflict, Q


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'base.xlsx'
        w = openpyxl.Workbook()
        s = w.active
        s.title = 'Parts'
        s.append(['Part Number', 'Value', 'Name'])
        s.append(['A', 10, '=A2&B2'])
        w.save(self.base)
        self.ours = self.variant('ours', {})
        self.theirs = self.variant('theirs', {})
        self.output = self.root / 'output.xlsx'

    def variant(self, name, edits, delete=False, part=None):
        with ZipFile(self.base) as z:
            parts = {n: z.read(n) for n in z.namelist()}
        r = E.fromstring(parts['xl/worksheets/sheet1.xml'])
        data = r.find(Q('sheetData'))
        if delete:
            data.remove(data[1])
        for coord, value in edits.items():
            rownum = ''.join(c for c in coord if c.isdigit())
            row = data.find(f"{Q('row')}[@r='{rownum}']")
            if row is None:
                row = E.SubElement(data, Q('row'), r=rownum)
            c = row.find(f"{Q('c')}[@r='{coord}']")
            if c is not None:
                row.remove(c)
            c = E.SubElement(row, Q('c'), r=coord)
            if isinstance(value, str) and value.startswith('='):
                E.SubElement(c, Q('f')).text = value[1:]
            elif isinstance(value, str):
                c.set('t', 'inlineStr')
                E.SubElement(E.SubElement(c, Q('is')), Q('t')).text = value
            else:
                E.SubElement(c, Q('v')).text = str(value)
        parts['xl/worksheets/sheet1.xml'] = E.tostring(r)
        if part:
            parts[part[0]] = part[1]
        p = self.root / (name + '.xlsx')
        with ZipFile(p, 'w', ZIP_DEFLATED) as z:
            for n, value in parts.items():
                z.writestr(n, value)
        return p

    def run_merge(self):
        merge(self.base, self.ours, self.theirs, self.output)
        return openpyxl.load_workbook(self.output)['Parts']

    def test_independent_cells(self):
        self.ours = self.variant('ours', {'B2': 20})
        self.theirs = self.variant('theirs', {'C2': '=A2&"x"'})
        s = self.run_merge()
        self.assertEqual(s['B2'].value, 20)
        self.assertEqual(s['C2'].value, '=A2&"x"')

    def test_concurrent_append_translates_formula(self):
        self.ours = self.variant('ours', {'A3': 'B', 'B3': 2, 'C3': '=A3&B3'})
        self.theirs = self.variant('theirs', {'A3': 'C', 'B3': 3, 'C3': '=A3&B3'})
        s = self.run_merge()
        self.assertEqual(s['A3'].value, 'B')
        self.assertEqual(s['A4'].value, 'C')
        self.assertEqual(s['C4'].value, '=A4&B4')

    def test_conflict_is_transactional(self):
        self.ours = self.variant('ours', {'B2': 20})
        self.theirs = self.variant('theirs', {'B2': 30})
        original = self.ours.read_bytes()
        with self.assertRaises(Conflict):
            merge(self.base, self.ours, self.theirs, self.ours)
        self.assertEqual(self.ours.read_bytes(), original)

    def test_delete_edit_conflicts(self):
        self.ours = self.variant('ours', {}, delete=True)
        self.theirs = self.variant('theirs', {'B2': 20})
        with self.assertRaises(Conflict):
            self.run_merge()

    def test_delete_unchanged(self):
        self.ours = self.variant('ours', {}, delete=True)
        self.assertIsNone(self.run_merge()['A2'].value)

    def test_duplicate_identity(self):
        self.theirs = self.variant('theirs', {'A3': 'A'})
        with self.assertRaises(Conflict):
            self.run_merge()

    def test_cross_row_reference_cannot_move(self):
        self.ours = self.variant('ours', {'A3': 'B'})
        self.theirs = self.variant('theirs', {'A3': 'C', 'C3': '=B2'})
        with self.assertRaises(Conflict):
            self.run_merge()

    def test_cross_row_reference_unchanged(self):
        self.base = self.variant('newbase', {'C2': '=B99'})
        self.ours = self.variant('ours', {})
        self.theirs = self.variant('theirs', {})
        self.assertEqual(self.run_merge()['C2'].value, '=B99')

    def test_real_library_parallel_additions(self):
        self.base = Path(__file__).resolve().parents[1] / 'Database/Hydrolib_bd.xlsm'
        self.ours = self.variant('ours', {'A74': 'TEST-OURS', 'C74': '=A74'})
        self.theirs = self.variant('theirs', {'A74': 'TEST-THEIRS', 'C74': '=A74'})
        merge(self.base, self.ours, self.theirs, self.output)
        s = openpyxl.load_workbook(self.output)['Chips']
        self.assertEqual(s['A74'].value, 'TEST-OURS')
        self.assertEqual(s['A75'].value, 'TEST-THEIRS')
        self.assertEqual(s['C75'].value, '=A75')
        self.assertEqual(next(iter(s.tables.values())).ref, 'A1:M75')

    def test_real_library_roundtrip(self):
        actual = Path(__file__).resolve().parents[1] / 'Database/Hydrolib_bd.xlsm'
        merge(actual, actual, actual, self.output)
        a = openpyxl.load_workbook(actual)
        b = openpyxl.load_workbook(self.output)
        for sheet in a:
            for row in sheet:
                for cell in row:
                    self.assertEqual(cell.value, b[sheet.title][cell.coordinate].value)
        with ZipFile(actual) as x, ZipFile(self.output) as y:
            for n in x.namelist():
                if n not in {'xl/workbook.xml', 'xl/calcChain.xml', 'xl/_rels/workbook.xml.rels', '[Content_Types].xml'} and not n.startswith(('xl/worksheets/sheet', 'xl/tables/')):
                    self.assertEqual(x.read(n), y.read(n), n)


if __name__ == '__main__':
    unittest.main()
