#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

WIKI = Path('/Users/lbq/Desktop/c c/知识库/wiki')
THEME_RADAR_DIR = WIKI / 'raw/theme-radar'


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def render_prompt(data: dict, limit: int = 12) -> str:
    theme = data.get('theme', '')
    rows = [row for row in data.get('rows', []) if row.get('priority') in {'P0', 'P1'}]
    rows = rows[:limit]
    company_lines = []
    for row in rows:
        company_lines.append(
            '- {company}{code}：{role}；chain_layer={chain_layer}；strength={strength}；缺口={missing}'.format(
                company=row.get('company', ''),
                code=f"（{row.get('code')}）" if row.get('code') else '',
                role=row.get('role', ''),
                chain_layer=row.get('chain_layer', ''),
                strength=row.get('strength', ''),
                missing=row.get('missing_reason', ''),
            )
        )
    return f'''使用 disclosure-archive skill。

任务：为【{theme}】补 P0/P1 官方/公司级证据。

依据 readiness 报告：wiki/raw/theme-radar/theme-evidence-readiness-{theme}.md

只处理以下公司，不处理 P2 市场信号噪声：
{chr(10).join(company_lines) if company_lines else '- 暂无 P0/P1 公司'}

目标：查找能提高题材雷达置信度的官方/公司级证据。

优先来源顺序：
1. 年报、半年报、招股书、募集说明书、交易所问询回复
2. 公司公告：订单、合同、中标、客户导入、认证、量产、产能、投产、扩产
3. 公司官网产品页、官网新闻、产品手册
4. 互动易、上证 e 互动、投资者关系活动记录
5. 官方公众号或权威媒体只作为弱补充，不能单独标 baseline/hard_delta

归档要求：
- 只归档到 wiki/raw/disclosures/，不入库。
- 不修改 wiki/entities、wiki/concepts、wiki/relations。
- 每条记录必须包含 URL、publish_date、quoted_text、extracted_facts。
- 每条记录必须填写 source_origin、concept_match_type、evidence_polarity、time_scope、fact_traceability。
- quoted_text 必须是原文摘录，不要改写。
- extracted_facts 必须能被 quoted_text 直接支持。
- 如果只是“可应用于、规划、正在布局、框架协议、关注相关技术”，不得标 hard_delta，只能标 review_candidate、graph_only 或 weak_signal。
- L2 官方来源可作为 baseline/hard_delta 候选；L3 互动易/投关记录默认 review_candidate；L4 新闻/媒体默认 weak_signal 或 reject。
- 默认 exposure_strength 不标 core，除非官方证据直接证明该题材是主营/核心产品。

归档后请执行：
1. python3 skills/disclosure-archive/scripts/check.py
2. python3 skills/disclosure-archive/scripts/batch_summary.py --batch-id <本批batch_id>
3. python3 skills/disclosure-archive/scripts/review_queue.py --theme-term "{theme}"

最后输出：
- archived_count / skipped_count / failed_count
- by_evidence_layer / by_update_type
- review queue 路径
- 哪些公司仍未找到官方直接证据
'''


def main():
    parser = argparse.ArgumentParser(description='Build disclosure-archive prompt from Theme Evidence Readiness report.')
    parser.add_argument('--theme', required=True)
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--out', default='')
    args = parser.parse_args()
    in_path = THEME_RADAR_DIR / f'theme-evidence-readiness-{args.theme}.json'
    data = load_json(in_path)
    prompt = render_prompt(data, args.limit)
    out_path = Path(args.out) if args.out else THEME_RADAR_DIR / f'disclosure-archive-prompt-{args.theme}.md'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f'# Disclosure Archive Prompt - {args.theme}\n\nGenerated: {datetime.now().isoformat(timespec="seconds")}\n\n```text\n{prompt}\n```\n', encoding='utf-8')
    print(str(out_path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
