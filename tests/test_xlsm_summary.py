import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xlsm_merge'))
from summary import render

class SummaryTests(unittest.TestCase):
    def test_success_and_early_failure(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('Книгу удалось', render(d, 'success', 'a/b', '1'))
            self.assertIn('не запускалась', render(d, 'skipped', 'a/b', '1'))

    def test_conflict_and_fork_are_clear_and_escaped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'report.json').write_text(json.dumps({'conflicts': [{'part': 'A', 'field': 'Name', 'ours': '<script>', 'theirs': 'B', 'choice': None}]}))
            text = render(d, 'failure', 'a/b', '3')
            self.assertIn('нужен выбор стороны', text)
            self.assertIn('&lt;script&gt;', text)
            self.assertIn('xlsm-update.yml', text)
            Path(d, 'context.json').write_text(json.dumps({'number': '3', 'fork': True}))
            self.assertIn('из другого форка', render(d, 'failure', 'a/b', '3'))
