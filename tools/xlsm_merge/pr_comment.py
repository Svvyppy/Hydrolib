"""Publish trusted report as one bot comment; workbook content is data only."""
import json
import os
from pathlib import Path
import re
import urllib.request

MARKER = '<!-- hydrolib-xlsm-report -->'


def api(path, method='GET', payload=None):
    request = urllib.request.Request(
        'https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + '/' + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method, headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                               'Accept': 'application/vnd.github+json',
                               'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def publish(request, number, report, repo, run, attempt):
    if not str(number).isdecimal():
        raise ValueError('PR_NUMBER must be numeric')
    sequence = (int(run), int(attempt))
    prefix = MARKER + f'\n<!-- run:{sequence[0]} attempt:{sequence[1]} -->\n'
    link = f'https://github.com/{repo}/actions/runs/{int(run)}'
    # GitHub has a comment size limit. Preserve complete HTML tags by using
    # a short message instead of cutting a table in the middle.
    if len((prefix + report).encode('utf-8')) > 55000:
        report = f'Отчёт слишком большой для комментария. [Открыть полную сводку]({link}). Полный список изменений — в report.json в Artifacts.'
    body = prefix + report
    page = 1
    existing = None
    while True:
        comments = request(f'issues/{number}/comments?per_page=100&page={page}')
        for comment in comments:
            user = comment.get('user', {})
            if (user.get('login') == 'github-actions[bot]' and user.get('type') == 'Bot'
                    and comment.get('body', '').startswith(MARKER)):
                match = re.search(r'<!-- run:(\d+) attempt:(\d+) -->', comment['body'])
                if match and tuple(map(int, match.groups())) > sequence:
                    return 'skipped older run'
                existing = comment
        if len(comments) < 100:
            break
        page += 1
    if existing:
        request(f'issues/comments/{existing["id"]}', 'PATCH', {'body': body})
        return 'updated'
    request(f'issues/{number}/comments', 'POST', {'body': body})
    return 'created'


if __name__ == '__main__':
    print(publish(api, os.environ['PR_NUMBER'],
                  Path('xlsm-artifacts/summary.html').read_text(encoding='utf-8'),
                  os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID'],
                  os.environ.get('GITHUB_RUN_ATTEMPT', '1')))
