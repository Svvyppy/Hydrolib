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
            self.assertIn('PR из форка', render(d, 'failure', 'a/b', '3'))

    def test_unresolved_and_resolved_are_separate(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'report.json').write_text(json.dumps({'conflicts': [
                {'part': 'A', 'base': 'old', 'ours': 'new', 'theirs': 'other', 'choice': None},
                {'part': 'B', 'base': 'old', 'ours': 'new', 'theirs': 'other', 'choice': 'ours'}]}))
            text = render(d, 'failure', 'a/b', '1')
            self.assertIn('Нерешённые конфликты: 1', text)
            self.assertIn('Разрешённые конфликты: 1', text)
            self.assertIn('<th>Исходное</th>', text)

    def test_structural_error_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'report.json').write_text(json.dumps({'message': 'Column schema changed', 'conflicts': []}))
            text = render(d, 'failure', 'a/b', '1')
            self.assertIn('Что мешает завершить слияние', text)
            self.assertIn('Column schema changed', text)


    def test_changes_are_visible_and_escaped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'report.json').write_text(json.dumps({'changes': {
                'added': [{'sheet': 'Chips', 'part': '<NEW>', 'row': 3}],
                'deleted': [{'sheet': 'Chips', 'part': 'OLD', 'row': 2}],
                'modified': [{'sheet': 'Chips', 'part': 'A', 'row': 4, 'field': 'Value', 'before': 10, 'after': 20}]}}))
            text = render(d, 'success', 'a/b', '1')
            self.assertIn('Добавлено компонентов: 1', text)
            self.assertIn('Изменено: 1 (полей: 1)', text)
            self.assertIn('&lt;NEW&gt;', text)
            self.assertIn('<td>10</td><td>20</td>', text)
            self.assertNotIn('Добавленные компоненты', render(d, 'failure', 'a/b', '1'))

    def test_change_limit_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, 'report.json')
            p.write_text(json.dumps({'changes': {'added': [], 'deleted': [], 'modified': []}}))
            self.assertIn('Изменений значений и формул нет', render(d, 'success', 'a/b', '1'))
            p.write_text(json.dumps({'changes': {'added': [{'sheet': 'X', 'part': str(i), 'row': i+2} for i in range(201)]}}))
            self.assertIn('первые 200 записей', render(d, 'success', 'a/b', '1'))


    def test_version_run_and_compact_counts(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {
                'GITHUB_SHA': 'abcdef123456789', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2'}):
            Path(d, 'report.json').write_text(json.dumps({'changes': {'added': [{'sheet': 'X', 'part': 'NEW', 'row': 2}]}}))
            text = render(d, 'success', 'a/b', '13')
            self.assertIn('Добавлено 1 · Изменено 0 · Удалено 0 · Конфликтов 0', text)
            self.assertIn('abcdef123456', text)
            self.assertIn('/actions/runs/123/attempts/2', text)
            self.assertIn('Re-run использует прежнюю', text)



    def test_proposed_changes_visible_with_unresolved_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'pr-changes.json').write_text(json.dumps({'comparison': 'ancestor_to_pr', 'changes': {
                'added': [{'sheet': 'Chips', 'part': '<NEW>', 'row': 3}],
                'deleted': [{'sheet': 'Chips', 'part': 'OLD', 'row': 4}],
                'modified': [{'sheet': 'Chips', 'part': 'A', 'row': 2, 'field': 'Value', 'before': 10, 'after': 20}]}}))
            Path(d, 'report.json').write_text(json.dumps({'conflicts': [
                {'part': 'A', 'field': 'Value', 'base': 10, 'ours': 20, 'theirs': 30, 'choice': None}]}))
            text = render(d, 'failure', 'a/b', '13')
            self.assertIn('Изменения автора PR', text)
            self.assertIn('В PR: добавлено 1 · Изменено 1 · Удалено 1', text)
            self.assertIn('&lt;NEW&gt;', text)
            self.assertIn('<td>10</td><td>20</td>', text)
            self.assertIn('Нерешённые конфликты: 1', text)
            self.assertNotIn('Итог слияния: изменения', text)

    def test_unavailable_proposed_changes_explains_reason(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'pr-changes.json').write_text(json.dumps({'message': 'duplicate <ID>'}))
            text = render(d, 'failure', 'a/b', '13')
            self.assertIn('Не удалось составить достоверный список', text)
            self.assertIn('duplicate &lt;ID&gt;', text)



    def test_conflict_report_links_to_individual_picker(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {'GITHUB_RUN_ID': '42'}):
            Path(d, 'report.json').write_text(json.dumps({'conflicts': [{'part': 'A', 'choice': None}]}))
            text = render(d, 'failure', 'a/b', '13')
            self.assertIn('resolve-conflicts.html', text)
            self.assertIn('/actions/runs/42#artifacts', text)
            self.assertIn('resolutions_json', text)
