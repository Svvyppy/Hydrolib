"""Human-readable Actions result. Only reads artifacts, never executes PR data."""
import html
import json
import os
from pathlib import Path


def render(directory, outcome, repo, number, fork=False):
    directory = Path(directory)
    context_path = directory / 'context.json'
    if context_path.exists():
        context = json.loads(context_path.read_text(encoding='utf-8'))
        fork, number = context['fork'], context['number']
    report_path = directory / 'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    conflicts = report.get('conflicts', [])
    unresolved = [c for c in conflicts if c.get('choice') is None]
    esc = lambda value: html.escape(str(value))
    url = 'https://github.com/' + repo + '/actions/workflows/'
    if outcome == 'success':
        title = '✅ Книгу удалось объединить'
        message = 'Проверка успешна. Автоматическая проверка не меняет ветки. Перед использованием результата откройте книгу в Excel, пересчитайте и сохраните.'
    elif unresolved:
        title = '⚠️ Не удалось объединить книгу: нужен выбор стороны'
        message = f'Неразрешённых конфликтов: {len(unresolved)}. Это расхождения между версиями, а не ошибка запуска.'
    else:
        title = '❌ Проверка не завершилась'
        error = directory / 'failure.txt'
        message = report.get('message') or (error.read_text(encoding='utf-8') if error.exists() else 'Проверка книги не запускалась или остановилась раньше. Откройте красный шаг в разделе Jobs.')
    parts = [f'<h2>{title}</h2><p>{esc(message)}</p>', f'<p>PR: <a href="https://github.com/{esc(repo)}/pull/{esc(number)}">#{esc(number)}</a>. Наше (ours) — ветка PR; их (theirs) — целевая ветка.</p>']
    if conflicts:
        parts.append('<h3>Что не удалось объединить</h3><table><tr><th>Место</th><th>Наше</th><th>Их</th><th>Решение</th></tr>')
        def display(value):
            if value == {'missing': True}:
                return 'Удалено / отсутствует'
            if isinstance(value, dict) and 'sha256' in value:
                return 'Бинарная версия ' + value['sha256'][:12]
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            return esc(text[:500])
        for c in conflicts:
            place = ' / '.join(str(c[k]) for k in ('sheet', 'part', 'field') if k in c)
            if c.get('kind') == 'binary_part':
                place = 'VBA: макросы различаются (выбираются целиком)'
            parts.append(f'<tr><td>{esc(place)}</td><td>{display(c.get("ours"))}</td><td>{display(c.get("theirs"))}</td><td>{esc(c.get("choice") or "Не выбрано")}</td></tr>')
        parts.append('</table>')
    parts.append('<h3>Что делать дальше</h3>')
    if fork:
        parts.append('<p>PR поступил из другого форка. Проверка доступна, но автоматическая запись в чужой форк не поддерживается. Автору нужно объединить книгу локально и отправить коммит в свою ветку. Не запускайте обновление PR с ожиданием записи в чужой форк.</p>')
    elif unresolved:
        parts.append(f'<p>Откройте <a href="{url}xlsm-update.yml">Объединить XLSM</a> → Run workflow → master → номер PR {esc(number)} → ours или theirs → Run workflow. Независимые изменения сохранятся. При расхождении VBA выбирается весь VBA-проект стороны.</p>')
    elif outcome != 'success':
        parts.append('<p>Если причина — структура книги, шрифты или другие неподдерживаемые изменения, нужен ручной разбор. Выбор ours/theirs не обходит эти ограничения.</p>')
    parts.append(f'<p><a href="{url}xlsm-check.yml">Повторить проверку по номеру PR</a>. Подробности и исходные книги находятся в Artifacts этого запуска.</p>')
    return '\n'.join(parts)


if __name__ == '__main__':
    output = render('xlsm-artifacts', os.environ.get('MERGE_OUTCOME', 'failure'),
                    os.environ['GITHUB_REPOSITORY'], os.environ.get('PR_NUMBER', ''),
                    os.environ.get('IS_FORK') == 'true')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
        stream.write(output)
