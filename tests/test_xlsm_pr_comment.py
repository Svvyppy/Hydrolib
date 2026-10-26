import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/xlsm_merge'))
from pr_comment import publish, MARKER

class CommentTests(unittest.TestCase):
    def test_create_and_update_ignore_user_marker(self):
        comments, writes = [], []
        def api(path, method='GET', payload=None):
            if method == 'GET':
                return comments
            writes.append((path, method, payload))
        comments.append({'id': 1, 'user': {'login': 'someone', 'type': 'User'}, 'body': MARKER})
        self.assertEqual(publish(api, '13', '<p>OK</p>', 'a/b', '10', '1'), 'created')
        self.assertEqual(writes[-1][1], 'POST')
        comments.append({'id': 2, 'user': {'login': 'github-actions[bot]', 'type': 'Bot'}, 'body': writes[-1][2]['body']})
        self.assertEqual(publish(api, '13', '<p>New</p>', 'a/b', '11', '1'), 'updated')
        self.assertEqual(writes[-1][0], 'issues/comments/2')
        self.assertIn('<p>New</p>', writes[-1][2]['body'])

    def test_old_run_cannot_replace_newer_report(self):
        def api(path, method='GET', payload=None):
            self.assertEqual(method, 'GET')
            return [{'id': 2, 'user': {'login': 'github-actions[bot]', 'type': 'Bot'},
                     'body': MARKER + '\n<!-- run:20 attempt:2 -->'}]
        self.assertEqual(publish(api, '13', 'old', 'a/b', '19', '9'), 'skipped older run')
        self.assertEqual(publish(api, '13', 'old', 'a/b', '20', '1'), 'skipped older run')

    def test_pagination_size_limit_and_validation(self):
        calls = []
        def api(path, method='GET', payload=None):
            calls.append((path, method, payload))
            if method == 'GET':
                return [{}] * 100 if path.endswith('&page=1') else []
        publish(api, '13', 'Я' * 40000, 'a/b', '10', '1')
        self.assertIn('page=2', calls[1][0])
        self.assertIn('Открыть полную сводку', calls[-1][2]['body'])
        with self.assertRaises(ValueError):
            publish(api, '../1', '', 'a/b', '10', '1')
