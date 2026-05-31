#!/usr/bin/env python3
import html
import json
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
IN_JSON = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision-agent-selected.json'
OUT_HTML = WIKI / 'raw/theme-radar/missing-wikilinks-manual-decision.html'


def build_html(data):
    payload = json.dumps(data, ensure_ascii=False)
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Missing Wikilinks Decision Review</title>
  <style>
    :root {{
      --bg: #f6f3ee;
      --panel: #fffaf2;
      --ink: #1f2933;
      --muted: #6b7280;
      --line: #e5dccb;
      --accent: #2454d6;
      --accent-soft: #e8efff;
      --green: #166534;
      --green-soft: #dcfce7;
      --red: #9f1239;
      --red-soft: #ffe4e6;
      --amber: #92400e;
      --amber-soft: #fef3c7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #fff7da 0, transparent 28rem), var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      line-height: 1.45;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 250, 242, 0.94);
      backdrop-filter: blur(12px);
    }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    .sub {{ color: var(--muted); font-size: 13px; }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1.2fr repeat(3, minmax(150px, 0.45fr)) auto auto;
      gap: 10px;
      align-items: center;
      margin-top: 14px;
    }}
    input, select, textarea, button {{
      font: inherit;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: white;
      color: var(--ink);
    }}
    input, select {{ padding: 9px 10px; min-width: 0; }}
    textarea {{ width: 100%; min-height: 34px; padding: 7px 9px; resize: vertical; }}
    button {{ padding: 9px 12px; cursor: pointer; }}
    button.primary {{ background: var(--accent); border-color: var(--accent); color: white; }}
    button.ghost {{ background: transparent; }}
    button.small {{ padding: 6px 8px; font-size: 12px; border-radius: 8px; }}
    main {{ padding: 18px 22px 40px; }}
    .stats {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
    .stat {{
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.58);
      font-size: 13px;
    }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: 0 16px 36px rgba(31, 41, 51, 0.08);
    }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    thead {{ position: sticky; top: 111px; z-index: 5; background: #f4ead9; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px; vertical-align: top; font-size: 13px; }}
    th {{ text-align: left; color: #374151; font-size: 12px; letter-spacing: 0.02em; }}
    tbody tr {{ background: rgba(255,255,255,0.72); }}
    tbody tr:nth-child(even) {{ background: rgba(255,255,255,0.42); }}
    tbody tr.done {{ background: rgba(220, 252, 231, 0.58); }}
    .target {{ font-weight: 700; font-size: 14px; }}
    .muted {{ color: var(--muted); }}
    .pill {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 12px; border: 1px solid var(--line); background: white; }}
    .pill.create_concept, .pill.create_concept_review {{ color: var(--green); background: var(--green-soft); border-color: #bbf7d0; }}
    .pill.alias_to_existing {{ color: var(--accent); background: var(--accent-soft); border-color: #c7d2fe; }}
    .pill.noise_delete_link {{ color: var(--red); background: var(--red-soft); border-color: #fecdd3; }}
    .pill.source_or_report {{ color: var(--amber); background: var(--amber-soft); border-color: #fde68a; }}
    .examples {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; color: #475569; }}
    .examples div {{ margin-bottom: 5px; overflow-wrap: anywhere; }}
    .actions {{ display: grid; gap: 6px; }}
    .quick {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 6px; }}
    .target-page {{ margin-top: 6px; }}
    .hidden {{ display: none; }}
    .footer-note {{ margin-top: 12px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 1100px) {{
      .toolbar {{ grid-template-columns: 1fr 1fr; }}
      thead {{ top: 160px; }}
      table {{ min-width: 1180px; }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>Missing Wikilinks Decision Review</h1>
  <div class="sub">勾选每一行的处理动作；完成后点击“导出 JSON”。本页面不会直接修改知识库。</div>
  <div class="toolbar">
    <input id="search" placeholder="搜索 target / rationale / examples" />
    <select id="categoryFilter"><option value="">全部 category</option></select>
    <select id="actionFilter"><option value="">全部推荐动作</option></select>
    <select id="decisionFilter"><option value="">全部决策状态</option><option value="empty">未决策</option><option value="filled">已决策</option></select>
    <button class="ghost" id="acceptVisible">采纳当前可见推荐</button>
    <button class="primary" id="exportJson">导出 JSON</button>
  </div>
</header>
<main>
  <div class="stats" id="stats"></div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="width: 150px;">target</th>
          <th style="width: 62px;">count</th>
          <th style="width: 150px;">category</th>
          <th style="width: 170px;">推荐</th>
          <th style="width: 260px;">理由 / examples</th>
          <th style="width: 280px;">你的决策</th>
          <th style="width: 220px;">目标页 / 备注</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
  <div class="footer-note">提示：如果浏览器阻止下载，可打开开发者控制台复制导出的 JSON，或告诉我你保存的位置后我再写入文件。</div>
</main>
<script>
const DATA = __PAYLOAD__;
const ACTIONS = ['create_concept', 'create_concept_review', 'alias_to_existing', 'source_or_report', 'noise_delete_link', 'manual_review', 'skip'];
const rows = DATA.rows.map((row, index) => ({...row, _index: index, decision: row.decision || '', final_target_page: row.final_target_page || '', notes: row.notes || ''}));

const tbody = document.getElementById('tbody');
const stats = document.getElementById('stats');
const search = document.getElementById('search');
const categoryFilter = document.getElementById('categoryFilter');
const actionFilter = document.getElementById('actionFilter');
const decisionFilter = document.getElementById('decisionFilter');

function escapeText(value) {{
  return String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[ch]));
}}

function fillSelect(select, values) {{
  values.forEach(value => {{
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }});
}}

fillSelect(categoryFilter, [...new Set(rows.map(r => r.category))].sort());
fillSelect(actionFilter, [...new Set(rows.map(r => r.recommended_action))].sort());

function visibleRows() {{
  const q = search.value.trim().toLowerCase();
  const cat = categoryFilter.value;
  const act = actionFilter.value;
  const dec = decisionFilter.value;
  return rows.filter(r => {{
    if (cat && r.category !== cat) return false;
    if (act && r.recommended_action !== act) return false;
    if (dec === 'empty' && r.decision) return false;
    if (dec === 'filled' && !r.decision) return false;
    if (!q) return true;
    const haystack = [r.target, r.category, r.recommended_action, r.target_page, r.rationale, ...(r.examples || [])].join(' ').toLowerCase();
    return haystack.includes(q);
  }});
}}

function updateStats(list) {{
  const filled = rows.filter(r => r.decision).length;
  const visibleFilled = list.filter(r => r.decision).length;
  const byDecision = rows.reduce((acc, r) => {{ if (r.decision) acc[r.decision] = (acc[r.decision] || 0) + 1; return acc; }}, {{}});
  stats.innerHTML = [
    `<span class="stat">总数：${{rows.length}}</span>`,
    `<span class="stat">当前可见：${{list.length}}</span>`,
    `<span class="stat">已决策：${{filled}}</span>`,
    `<span class="stat">可见已决策：${{visibleFilled}}</span>`,
    ...Object.entries(byDecision).map(([k,v]) => `<span class="stat">${{escapeText(k)}}：${{v}}</span>`)
  ].join('');
}}

function render() {{
  const list = visibleRows();
  updateStats(list);
  tbody.innerHTML = list.map(r => {{
    const options = [''].concat(ACTIONS).map(a => `<option value="${{escapeText(a)}}" ${{r.decision === a ? 'selected' : ''}}>${{a || '未选择'}}</option>`).join('');
    const examples = (r.examples || []).map(e => `<div>${{escapeText(e)}}</div>`).join('');
    return `<tr data-index="${{r._index}}" class="${{r.decision ? 'done' : ''}}">
      <td><div class="target">${{escapeText(r.target)}}</div></td>
      <td>${{r.count}}</td>
      <td><span class="pill">${{escapeText(r.category)}}</span></td>
      <td>
        <div><span class="pill ${{escapeText(r.recommended_action)}}">${{escapeText(r.recommended_action)}}</span></div>
        <div class="muted target-page">${{escapeText(r.target_page || '')}}</div>
        <div class="quick"><button class="small" data-quick="accept">采纳</button><button class="small" data-quick="skip">skip</button></div>
      </td>
      <td><div>${{escapeText(r.rationale)}}</div><div class="examples">${{examples}}</div></td>
      <td>
        <select data-field="decision">${{options}}</select>
        <div class="quick">
          ${{ACTIONS.slice(0, 5).map(a => `<button class="small" data-set-action="${{a}}">${{a.replace('_', ' ')}}</button>`).join('')}}
        </div>
      </td>
      <td>
        <input data-field="final_target_page" value="${{escapeText(r.final_target_page)}}" placeholder="final_target_page" />
        <textarea data-field="notes" placeholder="notes">${{escapeText(r.notes)}}</textarea>
      </td>
    </tr>`;
  }}).join('');
}}

function setRow(index, patch) {{
  Object.assign(rows[index], patch);
}}

tbody.addEventListener('change', event => {{
  const tr = event.target.closest('tr');
  if (!tr) return;
  const index = Number(tr.dataset.index);
  const field = event.target.dataset.field;
  if (!field) return;
  setRow(index, {{ [field]: event.target.value }});
  render();
}});

tbody.addEventListener('input', event => {{
  const tr = event.target.closest('tr');
  if (!tr) return;
  const index = Number(tr.dataset.index);
  const field = event.target.dataset.field;
  if (!field) return;
  setRow(index, {{ [field]: event.target.value }});
  tr.classList.toggle('done', Boolean(rows[index].decision));
  updateStats(visibleRows());
}});

tbody.addEventListener('click', event => {{
  const tr = event.target.closest('tr');
  if (!tr) return;
  const index = Number(tr.dataset.index);
  if (event.target.dataset.quick === 'accept') {{
    const row = rows[index];
    setRow(index, {{ decision: row.recommended_action, final_target_page: row.final_target_page || row.target_page || row.target }});
    render();
  }}
  if (event.target.dataset.quick === 'skip') {{
    setRow(index, {{ decision: 'skip' }});
    render();
  }}
  if (event.target.dataset.setAction) {{
    const action = event.target.dataset.setAction;
    const row = rows[index];
    const finalTarget = action === 'noise_delete_link' || action === 'source_or_report' || action === 'skip' ? row.final_target_page : (row.final_target_page || row.target_page || row.target);
    setRow(index, {{ decision: action, final_target_page: finalTarget }});
    render();
  }}
}});

[search, categoryFilter, actionFilter, decisionFilter].forEach(el => el.addEventListener('input', render));

document.getElementById('acceptVisible').addEventListener('click', () => {{
  if (!confirm('将当前筛选可见的未决策行全部采纳 recommended_action？')) return;
  visibleRows().forEach(row => {{
    if (!row.decision) row.decision = row.recommended_action;
    if (!row.final_target_page) row.final_target_page = row.target_page || row.target;
  }});
  render();
}});

document.getElementById('exportJson').addEventListener('click', () => {{
  const output = {{
    exported_at: new Date().toISOString(),
    source_total_rows: DATA.total_rows,
    rows: rows.map(({{_index, ...row}}) => row),
    decisions: rows.filter(r => r.decision).map(({{_index, ...row}}) => row)
  }};
  const blob = new Blob([JSON.stringify(output, null, 2)], {{type: 'application/json;charset=utf-8'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'missing-wikilinks-manual-decision-filled.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}});

render();
</script>
</body>
</html>
"""
    template = template.replace('{{', '{').replace('}}', '}')
    return template.replace('__PAYLOAD__', payload)


def main():
    data = json.loads(IN_JSON.read_text(encoding='utf-8'))
    OUT_HTML.write_text(build_html(data), encoding='utf-8')
    print(json.dumps({'input': str(IN_JSON), 'output': str(OUT_HTML), 'rows': data.get('total_rows'), 'summary': data.get('summary')}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
