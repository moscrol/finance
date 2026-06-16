# Theme Radar JSON Schema：题材雷达结构化产品数据设计

更新时间：2026-06-11

## 1. 目标

Theme Radar 当前主要输出 Markdown 报告。JSON schema 的目标是把报告背后的关键信息结构化，成为网站题材页、AI Copilot、统一 CLI、workflow summary 和后续评估系统都能复用的数据契约。

核心目标：

```text
输入一个题材 / 新词 / 盘面触发方向
  ↓
输出一个标准 ThemeRadarPayload JSON
  ↓
同一份数据可渲染 Markdown、HTML、网站页面和 Copilot 答案
```

第一阶段原则：

- 不重写 `radar.py`。
- 不替代现有 Markdown 报告。
- 先定义 schema，再逐步让脚本输出该 schema。
- 所有 AI 生成字段必须能追溯到 evidence 或 marked_as_inference。
- 允许字段为空，但必须显式写入 `missing_confirmations` 或 `quality_flags`。

## 2. 顶层对象

标准对象名：

```text
ThemeRadarPayload
```

顶层结构：

```json
{
  "schema_version": "1.0.0",
  "payload_type": "theme_radar",
  "generated_at": "2026-06-11T01:58:00+08:00",
  "term": "商业航天",
  "canonical_theme": "商业航天",
  "mode": "deep-dive",
  "status": "PASS",
  "metadata": {},
  "definition": {},
  "concept_resolution": {},
  "chain_map": {},
  "demand_bottleneck_map": [],
  "direction_scan": [],
  "entity_tiers": [],
  "evidence_items": [],
  "market_signals": {},
  "readiness": {},
  "validation_checklist": [],
  "catalyst_calendar": [],
  "opportunity_profile": {},
  "missing_confirmations": [],
  "quality_flags": [],
  "rendered_markdown": "",
  "rendered_html": ""
}
```

## 3. 字段来源总览

| 字段 | 主要来源 | 是否必填 | 说明 |
|---|---|---:|---|
| `metadata` | workflow / CLI | 是 | 运行上下文 |
| `definition` | definition/context/wiki concept/supplement pool | 是 | 题材定义 |
| `concept_resolution` | aliases/concept_graph | 是 | 概念匹配结果 |
| `chain_map` | report_contexts/supplement pool/direction pool | 是 | 产业链结构 |
| `demand_bottleneck_map` | direction pool | 否 | 需求-瓶颈-环节传导 |
| `direction_scan` | direction pool/supplement pool/radar context | 否 | 细分方向扫描 |
| `entity_tiers` | entity_exposures/evidence_index/radar companies | 是 | 公司分层 |
| `evidence_items` | evidence_index/direction trace/supplement evidence | 是 | 证据列表 |
| `market_signals` | market_feature_store/build_market_triggered_theme_brief | 否 | 盘面信号 |
| `readiness` | build_theme_evidence_readiness.py | 否 | 证据准备度 |
| `validation_checklist` | direction/supplement pool | 否 | 后续验证项 |
| `catalyst_calendar` | direction/supplement pool | 否 | 催化日历 |
| `opportunity_profile` | direction pool/radar inference | 否 | 机会优先级 |
| `missing_confirmations` | readiness/qc/radar warnings | 是 | 缺口 |
| `quality_flags` | quality rules/regression | 是 | 质量标记 |
| `rendered_markdown` | radar.py | 否 | 渲染结果 |
| `rendered_html` | renderer | 否 | 渲染结果 |

## 4. metadata

用途：记录生成上下文。

```json
{
  "metadata": {
    "workflow": "theme-radar",
    "run_id": "theme-radar-20260611-015800",
    "mode": "deep-dive",
    "source": "manual|daily-review|market-triggered|website",
    "review_source": "日复盘",
    "review_direction": "商业航天",
    "review_companies": ["华工科技"],
    "vault": "/Users/lbq/Desktop/c c/知识库/wiki",
    "finance_root": "/Users/lbq/Desktop/c c/金融",
    "inputs": {
      "definition_file": "",
      "context_json": "",
      "theme_info_jsonl": "",
      "theme_direction_pool": "",
      "theme_supplement_pool": ""
    }
  }
}
```

字段要求：

- `workflow` 必填。
- `mode` 必须与 CLI 参数一致。
- `source` 用于区分人工题材分析和盘面触发分析。
- 所有路径字段只记录来源，不代表要写入。

## 5. definition

用途：给题材一个可引用、可审计的一句话定义和扩展定义。

```json
{
  "definition": {
    "one_liner": "商业航天是以商业公司为主体参与火箭发射、卫星制造、卫星运营和终端应用的产业体系。",
    "expanded": "...",
    "aliases": ["商业航空航天", "低轨卫星"],
    "english_terms": ["commercial aerospace"],
    "source_type": "wiki|external_definition|report_context|theme_supplement_pool|inference",
    "source_refs": ["[[商业航天]]"],
    "confidence": "high|medium|low",
    "needs_review": false
  }
}
```

规则：

- `one_liner` 必填。
- 如果来自 AI 推断，`source_type` 必须为 `inference`，且 `needs_review=true`。
- 如果定义来自 wiki concept 页面，应记录 wikilink。

## 6. concept_resolution

用途：记录输入 term 如何匹配知识库概念。

```json
{
  "concept_resolution": {
    "query": "商业航天",
    "canonical": "商业航天",
    "term_matched": true,
    "matches": ["商业航天", "卫星互联网"],
    "related_concepts": ["低轨卫星", "卫星通信", "火箭发射"],
    "aliases_hit": [],
    "notes": ["通过 aliases/concept_graph 命中。"],
    "broadened_scope": false
  }
}
```

来源映射：

- `canonical` 对应 `radar.py` 的 `primary`。
- `matches` 对应 `matches`。
- `related_concepts` 对应 `rels`。
- `term_matched` 对应 `term_matched`。
- `notes` 对应 `notes`。

## 7. chain_map

用途：结构化表示产业链。

```json
{
  "chain_map": {
    "upstream": [
      {
        "name": "材料",
        "description": "...",
        "entities": [],
        "evidence_refs": []
      }
    ],
    "midstream": [],
    "downstream": [],
    "services": [],
    "ecosystem": [],
    "unknown": []
  }
}
```

字段规则：

- `name` 必填。
- `entities` 可为空。
- 如果链条来自 AI 归纳但无证据，必须把缺口写入 `missing_confirmations`。

来源：

- `report_contexts.json`
- `theme_supplement_pool.industry_chain_panorama`
- `theme_direction_pool.directions[].chain_bucket`
- `radar.py context.industry_chain_map`

## 8. demand_bottleneck_map

用途：表达“需求来源 -> 瓶颈 -> 环节 -> 公司 -> 验证”的传导。

```json
{
  "demand_bottleneck_map": [
    {
      "demand_source": "低轨星座建设",
      "bottleneck": "宇航级可靠性",
      "chain_links": ["卫星制造", "射频通信"],
      "directions": ["星载射频组件"],
      "entities": ["铖昌科技", "臻镭科技"],
      "evidence_refs": ["evidence:disc-20260528-0001"],
      "verification_items": ["卫星批产订单", "星座发射节奏"],
      "catalysts": [],
      "confidence": "medium",
      "needs_review": false
    }
  ]
}
```

来源：

- `build_theme_direction_pool.py` 输出的 `demand_bottleneck_map`。

规则：

- 如果有 `entities`，必须尽量提供 `evidence_refs`。
- 没有官方证据时，不得把公司标为高确定性。

## 9. direction_scan

用途：细分方向扫描和认知阶段排序。

```json
{
  "direction_scan": [
    {
      "direction": "星载射频组件",
      "primary_sector": "卫星制造",
      "secondary_sectors": ["射频通信"],
      "direction_type": "component_module",
      "chain_bucket": "midstream",
      "recognition_stage": "发酵期",
      "recognition_score": 72,
      "progress_score": 68,
      "candidate_companies": ["铖昌科技"],
      "demand_sources": ["低轨星座建设"],
      "bottlenecks_solved": ["射频通信/高速传输"],
      "core_catalyst": "低轨星座招标",
      "next_validation": "订单/批产/发射排期",
      "evidence_profile": {
        "item_count": 4,
        "highest_evidence_layer": "curated_research",
        "has_official_evidence": false,
        "has_multi_source_support": true,
        "review_required_count": 1
      },
      "source_refs": []
    }
  ]
}
```

来源：

- `theme_direction_pool.directions`
- `radar.py build_theme_direction_pool_context()` 生成的 `direction_scan`
- `theme_supplement_pool.material_process_scan`

## 10. entity_tiers

用途：标准化公司分层。

```json
{
  "entity_tiers": [
    {
      "entity": "铖昌科技",
      "ticker": "001270.SZ",
      "tier": "core|beneficiary|watch|risk|missing_evidence",
      "rank": 1,
      "role": "星载射频芯片供应商",
      "chain_layer": "midstream",
      "strength": "core|related|peripheral",
      "evidence_bucket": "delta|curated_research|baseline|graph_only|missing",
      "evidence_layer": "L1|L2|L3|graph_only|unknown",
      "confidence": "high|medium|low",
      "source_refs": ["[[source-page]]"],
      "evidence_refs": ["evidence:item-id"],
      "market_refs": [],
      "reason": "...",
      "risks": [],
      "needs_review": false
    }
  ]
}
```

来源：

- `radar.py` 的 `companies`。
- `entity_exposures.json`。
- `evidence_index.json`。
- `build_theme_evidence_readiness.py` rows。

规则：

- `tier=core` 必须有非 `missing` 的 evidence bucket。
- `graph_only` 只能作为观察，不得成为强结论。
- `needs_review=true` 时前端应显示待复核。

## 11. evidence_items

用途：统一证据格式。

```json
{
  "evidence_items": [
    {
      "id": "evidence:disc-20260528-0001",
      "source": "[[disc-20260528-0001]]",
      "source_type": "official_disclosure|research_report|source_note|theme_pool|market_data|inference",
      "source_date": "2026-05-28",
      "target_type": "entity|concept|direction|theme|market_signal",
      "target": "铖昌科技",
      "concept": "商业航天",
      "direction": "星载射频组件",
      "claim": "...",
      "evidence": "...",
      "confidence": "high|medium|low",
      "evidence_layer": "L1|L2|L3|graph_only|unknown",
      "update_type": "baseline|curated_research|delta|hard_delta|graph_only|exposure_only",
      "fact_hardness": "hard|soft|unknown",
      "source_quality": "official|broker_research|media|unknown",
      "needs_review": false,
      "source_ref": "path:line"
    }
  ]
}
```

规则：

- `claim` 是面向用户的短句。
- `evidence` 是原始或半原始证据摘要。
- `source_type=inference` 的证据不能支撑 hard conclusion。
- `hard_delta` 必须来自高质量来源。

## 12. market_signals

用途：接入 Market Feature Store 的盘面触发信息。

```json
{
  "market_signals": {
    "enabled": true,
    "trade_date": "2026-06-10",
    "market_context": {
      "market_stage": "下跌阶段",
      "advancers": 1556,
      "total_amount": 26401,
      "top_capacity_industries": [
        {"rank": 1, "sw_l1": "电子", "ratio": 29.4}
      ]
    },
    "signal_summary": {
      "double_red_count": 2,
      "limit_heat_count": 20,
      "limit_advance_theme_count": 5,
      "multi_period_row_count": 10,
      "new_high_direction_count": 6,
      "candidate_theme_count": 8
    },
    "trigger_types": ["double_red", "limit_heat", "new_high_direction"],
    "triggered_themes": [
      {
        "market_theme": "半导体设备",
        "canonical_concept": "半导体设备",
        "priority_score": 88,
        "trigger_types": ["double_red", "limit_heat"],
        "market_evidence": [],
        "top_stocks": []
      }
    ]
  }
}
```

来源：

- `scripts/build_market_triggered_theme_brief.py` 的输出：
  - `market_context`
  - `signal_summary`
  - `deep_themes`
  - `watch_themes`
  - `new_high_directions`

规则：

- `enabled=false` 时，其余字段可为空。
- 市场信号只能说明“盘面触发”，不能替代公司硬证据。

## 13. readiness

用途：记录证据准备度。

```json
{
  "readiness": {
    "enabled": true,
    "theme": "商业航天",
    "generated_at": "2026-06-11T01:58:00",
    "summary": {
      "company_count": 20,
      "high_confidence": 6,
      "medium_confidence": 8,
      "low_confidence": 6,
      "entity_baseline_ready": 15,
      "theme_evidence_ready": 10,
      "official_evidence_ready": 4,
      "direct_theme_evidence_ready": 7,
      "review_required": 5
    },
    "rows": []
  }
}
```

来源：

- `scripts/build_theme_evidence_readiness.py`。

规则：

- readiness 不等于投资结论。
- `official_evidence_ready` 低时，报告必须降低结论强度。

## 14. validation_checklist

用途：结构化后续验证事项。

```json
{
  "validation_checklist": [
    {
      "direction": "星载射频组件",
      "item": "星座招标/订单落地",
      "window": "1-3个月",
      "upgrade_condition": "出现明确订单或批产节奏",
      "downgrade_condition": "招标推迟或仅停留概念映射",
      "status": "待验证|已验证|失效",
      "validation_type": "order|capacity|price|shipment|policy|market_signal",
      "source_refs": [],
      "owner": "human|agent",
      "needs_follow_up": true
    }
  ]
}
```

来源：

- direction pool `validation_plan`。
- supplement pool `validation_items`。
- AI 归纳但必须标注 `source_refs` 或 `needs_review`。

## 15. catalyst_calendar

```json
{
  "catalyst_calendar": [
    {
      "direction": "星载射频组件",
      "time_window": "2026Q3",
      "event": "低轨星座批量发射",
      "event_type": "policy|order|product|earnings|industry_event|market_signal",
      "evidence_refs": [],
      "watch_item": "发射排期是否兑现",
      "status": "upcoming|occurred|delayed|cancelled"
    }
  ]
}
```

## 16. opportunity_profile

用途：形成产品层的“机会/风险/行动建议”，但必须与证据强度绑定。

```json
{
  "opportunity_profile": {
    "overall_stage": "萌芽|发酵|主升|分歧|退潮|未知",
    "opportunity_score": 72,
    "priority": "P0|P1|P2|watch",
    "supporting_evidence": [],
    "missing_proof": [],
    "core_risks": [],
    "next_actions": [
      "补官方证据",
      "跟踪订单验证",
      "观察盘面是否进入容量前三"
    ],
    "not_investment_advice": true
  }
}
```

规则：

- `opportunity_score` 不能只由 AI 主观给出。
- 必须能解释来自证据、市场信号、readiness 或方向池。
- 风险必须与机会同级展示。

## 17. missing_confirmations

用途：显式列出缺口。

```json
{
  "missing_confirmations": [
    {
      "type": "official_evidence_missing|entity_baseline_missing|direct_theme_evidence_missing|market_signal_missing|definition_weak|chain_layer_conflict",
      "target": "铖昌科技",
      "concept": "商业航天",
      "severity": "P0|P1|P2",
      "description": "缺少官方披露证明其商业航天直接收入或订单。",
      "suggested_action": "触发 disclosure archive archive-only。"
    }
  ]
}
```

规则：

- 不允许缺口只藏在正文里。
- 任何弱证据强结论都必须生成缺口或 quality flag。

## 18. quality_flags

用途：给 workflow / UI / regression 使用。

```json
{
  "quality_flags": [
    {
      "code": "GRAPH_ONLY_OVER_RANKED",
      "severity": "warn|error",
      "message": "Top company only has graph_only evidence.",
      "targets": ["某公司"],
      "blocking": false
    }
  ]
}
```

建议 code：

```text
TERM_NOT_MATCHED
DEFINITION_WEAK
NO_ENTITY_FOUND
GRAPH_ONLY_OVER_RANKED
OFFICIAL_EVIDENCE_LOW
CHAIN_LAYER_CONFLICT
READINESS_REVIEW_REQUIRED
MARKET_SIGNAL_WEAK
REGRESSION_SCORE_DROP
SUPPLEMENT_POOL_QC_FAILED
```

## 19. rendered_markdown / rendered_html

渲染字段：

```json
{
  "rendered_markdown": "# 商业航天题材雷达\n...",
  "rendered_html": "<article>...</article>"
}
```

规则：

- 第一阶段 `rendered_html` 可为空。
- `rendered_markdown` 可来自当前 `radar.py`。
- 长文本可选择不嵌入，只放路径：

```json
{
  "rendered": {
    "markdown_path": "market_feature_store/exports/theme-radar/商业航天.md",
    "html_path": ""
  }
}
```

## 20. PASS / WARN / FAIL 规则

```text
PASS：核心定义、公司分层、证据、缺口均可用，无阻断错误。
WARN：可输出但存在缺证、弱市场信号、graph_only、review_required。
FAIL：无法读取知识库、题材无法解析、核心字段缺失、强结论无证据。
```

阻断规则：

- `TERM_NOT_MATCHED` 且无 definition/context -> FAIL。
- `NO_ENTITY_FOUND` 且 mode 不是 pure definition -> WARN/FAIL。
- Top tier 公司全是 `graph_only` -> WARN，若仍输出强结论则 FAIL。
- `SUPPLEMENT_POOL_QC_FAILED` -> FAIL for deep-dive。
- `REGRESSION_SCORE_DROP` -> FAIL for release。

## 21. 与现有脚本映射

| 现有脚本/函数 | 映射到 schema |
|---|---|
| `radar.py build_theme_state()` | `concept_resolution`, `definition`, `entity_tiers`, `evidence_items` |
| `build_theme_direction_pool.py` | `direction_scan`, `demand_bottleneck_map`, `validation_checklist`, `opportunity_profile` |
| `build_theme_supplement_pool.py` | `definition`, `chain_map`, `validation_checklist`, `catalyst_calendar`, `evidence_items` |
| `build_market_triggered_theme_brief.py` | `market_signals` |
| `build_theme_evidence_readiness.py` | `readiness`, `missing_confirmations` |
| `run_theme_radar_regression.py` | `quality_flags` |

## 22. 最小可交付版本

第一阶段 JSON 可以只包含：

```json
{
  "schema_version": "1.0.0",
  "payload_type": "theme_radar",
  "generated_at": "...",
  "term": "商业航天",
  "canonical_theme": "商业航天",
  "mode": "radar",
  "status": "WARN",
  "definition": {},
  "concept_resolution": {},
  "entity_tiers": [],
  "evidence_items": [],
  "missing_confirmations": [],
  "quality_flags": [],
  "rendered": {
    "markdown_path": "...",
    "html_path": ""
  }
}
```

## 23. 后续实现建议

建议新增：

```text
intelligence/schemas/theme_radar.py
intelligence/services/theme_radar.py
```

实现顺序：

1. 定义 Python dict builder，不引入复杂依赖。
2. 从 `radar.py build_theme_state()` 返回值构造最小 payload。
3. 写出 `*.theme-radar.json`。
4. 保留现有 Markdown 输出。
5. 再逐步接入 direction pool、market_signals、readiness。

目标命令：

```bash
python3 -m intelligence.cli theme --term 商业航天 --mode deep-dive --json
```

输出：

```text
market_feature_store/exports/theme-radar/商业航天.theme-radar.json
market_feature_store/exports/theme-radar/商业航天.theme-radar.md
```

## 24. 验收标准

文档验收：

- 顶层 schema 完整。
- 字段来源明确。
- 必填/可空边界明确。
- 证据要求明确。
- 缺口和质量 flags 明确。
- 能映射到现有脚本。

未来代码验收：

- JSON 可被 `json.loads` 解析。
- 关键数组字段永远是 list。
- 空字段显式为空结构，不缺 key。
- 任何强结论都有 evidence_refs 或 quality flag。
- Markdown 和 JSON 可由同一 state 生成。
