"""Offline conflict picker; workbook values are embedded as inert JSON data."""
import json
from pathlib import Path


def write_resolution_ui(directory, repo, number):
    directory = Path(directory)
    output = directory / 'resolve-conflicts.html'
    report_path = directory / 'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    if not report.get('conflicts') or not report.get('inputs'):
        output.unlink(missing_ok=True)
        return None
    context_path = directory / 'context.json'
    if context_path.exists():
        number = json.loads(context_path.read_text(encoding='utf-8'))['number']
    payload = json.dumps({'report': report, 'repo': repo, 'number': str(number)}, ensure_ascii=False)
    payload = payload.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    output.write_text(PAGE.replace('__PAYLOAD__', payload), encoding='utf-8')
    return output


PAGE = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'">
<title>Hydrolib — выбор решений</title>
<style>
:root{font:15px system-ui,sans-serif;color:#172b3a;background:#f3f6f8}body{margin:0}main{max-width:1100px;margin:auto;padding:32px 20px}h1{font-size:30px;margin:10px 0}h2{font-size:17px;margin:0 0 12px}.muted{color:#526879}.tag{color:#007b73;font-weight:700;letter-spacing:.08em;font-size:12px}p{line-height:1.6}.panel,.card{background:white;border:1px solid #d9e2e8;border-radius:14px;padding:20px;margin:16px 0}.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}input[type=search]{flex:1;min-width:200px;padding:12px;border:1px solid #bacad5;border-radius:8px}button,.link{display:inline-block;border:1px solid #b8cbd3;border-radius:8px;background:white;color:#173b4b;padding:11px 14px;font:inherit;cursor:pointer;text-decoration:none}button:hover,.link:hover{background:#edf7f6}button:disabled{opacity:.45;cursor:not-allowed}.primary{background:#007b73;color:white;border-color:#007b73}.primary:hover{background:#00635d}.counts{font-weight:700;margin:14px 0}progress{width:100%;height:8px;accent-color:#007b73}.options{display:grid;grid-template-columns:1fr 1fr;gap:14px}.option{border:2px solid #dbe5eb;border-radius:10px;padding:16px;cursor:pointer;min-width:0}.option:has(input:checked){border-color:#007b73;background:#effaf7}.option strong{margin-left:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace;line-height:1.55;margin:12px 0 0;max-height:280px;overflow:auto}.warning{background:#fff8e7;border:1px solid #f0d397;padding:12px;border-radius:8px}details{margin-top:12px}textarea{width:100%;box-sizing:border-box;min-height:180px;padding:12px;font:12px monospace;margin-top:12px}.footer{position:sticky;bottom:0;background:#f3f6f8ef;padding:12px 0}.footer .panel{margin:0}.status{color:#00635d;min-height:24px}.steps{padding-left:22px;line-height:1.8}label{cursor:pointer}@media(max-width:650px){.options{grid-template-columns:1fr}main{padding:20px 12px}h1{font-size:25px}}
</style></head><body><main>
<div class="tag">HYDROLIB · РАЗРЕШЕНИЕ КОНФЛИКТОВ</div><h1>Выберите значение для каждого конфликта</h1>
<p id="context" class="muted"></p>
<div class="panel"><h2>Как применить решения</h2><ol class="steps"><li>Выберите «Наше» или «Их» в каждой карточке.</li><li>Нажмите «Скопировать решения».</li><li>Откройте workflow, выберите основную ветку, укажите номер PR, <b>conflict_side = manual</b> и вставьте скопированный текст в <b>resolutions_json</b>. Нажмите Run workflow.</li></ol><p class="muted">Форма работает локально и ничего не отправляет. Токены и вход в GitHub здесь не нужны. Если книга изменилась, получите новый отчёт: старые решения будут отклонены.</p><a id="workflow" class="link" target="_blank" rel="noreferrer">Открыть workflow применения</a></div>
<div class="toolbar"><input id="search" type="search" placeholder="Найти компонент, лист или поле" aria-label="Поиск конфликтов"><label><input id="pendingOnly" type="checkbox"> Только без решения</label></div>
<div id="counts" class="counts" role="status" aria-live="polite"></div><progress id="progress" value="0" max="1"></progress>
<div class="toolbar" style="margin-top:16px"><span class="muted">Для всех конфликтов:</span><button id="allOurs">Выбрать ours</button><button id="allTheirs">Выбрать theirs</button><button id="reset">Сбросить выбор</button></div>
<p class="muted">Массовый выбор относится ко всему списку, включая скрытые поиском карточки. Независимые изменения обеих веток сохраняются автоматически.</p>
<div id="cards"></div><p id="empty" hidden>Нет конфликтов, подходящих под фильтр.</p>
<div class="footer"><div class="panel"><div class="toolbar"><button id="copy" class="primary" disabled>Скопировать решения</button><button id="save" disabled>Скачать resolutions.json</button><span id="remaining"></span></div><p id="status" class="status" role="status" aria-live="polite"></p><details id="manual"><summary>Показать текст решений для копирования</summary><textarea id="json" readonly aria-label="Решения JSON"></textarea></details></div></div>
</main><script id="data" type="application/json">__PAYLOAD__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const report=data.report, conflicts=report.conflicts;
const el=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
el('context').textContent=`PR #${data.number} · Наше (ours) — ветка автора PR. Их (theirs) — целевая ветка.`;
el('workflow').href=`https://github.com/${encodeURIComponent(data.repo.split('/')[0])}/${encodeURIComponent(data.repo.split('/')[1])}/actions/workflows/xlsm-update.yml`;
const display=v=>v&&v.missing===true?'Удалено / отсутствует':v&&v.sha256?'Бинарная версия SHA256: '+v.sha256:typeof v==='string'?v:JSON.stringify(v,null,2);
const cards=[];
conflicts.forEach((c,i)=>{
 if(!['ours','theirs'].includes(c.choice))c.choice=null;
 const card=node('section',undefined,'card');card.dataset.index=i;
 const place=[c.sheet,c.part,c.field||c.column].filter(v=>v!==undefined&&v!==null).join(' / ');
 const kind={binary_part:'VBA-проект',column_layout:'Оформление колонок',row_format:'Оформление строки',record:'Запись целиком',cell:'Поле'}[c.kind]||'Конфликт';
 card.append(node('h2',`${i+1}. ${kind}${place?' · '+place:''}`));
 if(c.kind==='binary_part')card.append(node('p','VBA выбирается целиком. Объединение отдельных макросов не выполняется.','warning'));
 if(c.kind==='record')card.append(node('p','Выбор относится ко всей записи, включая удаление.','warning'));
 const options=node('div',undefined,'options');
 ['ours','theirs'].forEach(side=>{const label=node('label',undefined,'option');const radio=document.createElement('input');radio.type='radio';radio.name='conflict-'+i;radio.value=side;radio.checked=c.choice===side;radio.addEventListener('change',()=>{c.choice=side;el('status').textContent='';refresh();});label.append(radio,node('strong',side==='ours'?'Наше · ours':'Их · theirs'),node('pre',display(c[side])));options.append(label);});
 const base=node('details');base.append(node('summary','Исходное значение'),node('pre',display(c.base)));
 card.append(options,base);el('cards').append(card);cards.push({card,search:(place+' '+kind).toLocaleLowerCase()});
});
function documentJSON(){return JSON.stringify({version:report.version,inputs:report.inputs,conflicts:conflicts.map(c=>({id:c.id,choice:c.choice}))},null,2);}
function refresh(){const pending=conflicts.filter(c=>!c.choice).length;const chosen=conflicts.length-pending;el('counts').textContent=`Выбрано ${chosen} из ${conflicts.length} · Осталось ${pending}`;el('progress').max=conflicts.length||1;el('progress').value=chosen;el('remaining').textContent=pending?'Выберите все оставшиеся конфликты':'Все конфликты решены — можно применять';el('copy').disabled=el('save').disabled=!!pending;el('json').value=documentJSON();let visible=0;const q=el('search').value.toLocaleLowerCase();cards.forEach(({card,search},i)=>{card.hidden=!search.includes(q)||(el('pendingOnly').checked&&!!conflicts[i].choice);if(!card.hidden)visible++;card.querySelectorAll('input').forEach(r=>{r.checked=r.value===conflicts[i].choice;});});el('empty').hidden=!!visible;}
function all(side){conflicts.forEach(c=>{c.choice=side;});el('status').textContent='';refresh();}
el('allOurs').onclick=()=>all('ours');el('allTheirs').onclick=()=>all('theirs');el('reset').onclick=()=>all(null);el('search').oninput=refresh;el('pendingOnly').onchange=refresh;
el('copy').onclick=async()=>{if(conflicts.some(c=>!c.choice))return;try{await navigator.clipboard.writeText(documentJSON());el('status').textContent='Решения скопированы. Вставьте их в resolutions_json, выбрав manual.';}catch(error){el('manual').open=true;el('json').focus();el('json').select();el('status').textContent='Браузер не разрешил копирование. Скопируйте выделенный текст вручную.';}};
el('save').onclick=()=>{if(conflicts.some(c=>!c.choice))return;const url=URL.createObjectURL(new Blob([documentJSON()],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='resolutions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
refresh();
</script></body></html>'''
