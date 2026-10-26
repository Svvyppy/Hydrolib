import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/xlsm_merge'))
from summary import render


class ValidationSummaryNoiseTests(unittest.TestCase):
    def render_issues(self, issues):
        with tempfile.TemporaryDirectory() as directory:
            data = {'phase': 'PR', 'issues': issues,
                    'errors': sum(i['severity'] == 'error' for i in issues),
                    'warnings': sum(i['severity'] == 'warning' for i in issues)}
            Path(directory, 'validation.json').write_text(json.dumps(data))
            return render(directory, 'failure' if data['errors'] else 'success', 'owner/repo', '8')

    def issue(self, message, severity='warning', existing=True):
        return dict(message=message, severity=severity, existing=existing,
                    sheet='Chips', part='chip', cell='D2')

    def test_old_warnings_are_collapsed_and_errors_stay_visible(self):
        result = self.render_issues([self.issue('OLD'), self.issue('NEW', 'error', False)])
        self.assertLess(result.index('NEW'), result.index('<details>'))
        self.assertGreater(result.index('OLD'), result.index('<details>'))
        self.assertNotIn('Что мешает завершить слияние', result)
        self.assertIn('не блокируют слияние', result)

    def test_existing_blocking_error_stays_visible(self):
        result = self.render_issues([self.issue('DUPLICATE', 'error')])
        self.assertIn('DUPLICATE', result)
        self.assertNotIn('<details>', result)

    def test_warning_only_report_does_not_ask_to_fix_errors(self):
        result = self.render_issues([self.issue('OLD')])
        self.assertIn('Новых замечаний нет', result)
        self.assertNotIn('Исправьте ошибки', result)

    def test_new_warning_is_visible_and_escaped(self):
        result = self.render_issues([self.issue('<unsafe>', existing=False)])
        self.assertIn('&lt;unsafe&gt;', result)
        self.assertNotIn('<unsafe>', result)


if __name__ == '__main__':
    unittest.main()
