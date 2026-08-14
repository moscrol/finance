# Theme Radar 外部新词画像 Schema

> 本文件由 `skills/theme-radar/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

web access 搜到资料后，先抽成这个结构。字段缺失可以留空，不要编造。

```json
{
  "term": "感光干膜",
  "definition": "用于PCB、IC载板等图形转移环节的光敏材料。",
  "aliases": ["干膜光刻胶", "dry film photoresist"],
  "english_terms": ["dry film photoresist", "DFR"],
  "parent_concepts": ["PCB", "IC载板", "半导体材料"],
  "chain_position": ["上游材料", "图形转移材料"],
  "related_terms": ["mSAP", "ABF载板", "高端PCB", "线路精细化"],
  "problem_solved": "高端PCB线路精细化后，传统图形转移材料性能要求提升。",
  "technical_modules": ["图形转移", "曝光显影", "精细线路制造"],
  "required_capabilities": ["高端电子化学品", "PCB材料认证", "IC载板材料认证"],
  "adjacent_concepts": [
    {
      "name": "湿膜光刻胶",
      "difference": "干膜以预制薄膜形态贴附使用，湿膜以液态涂布。"
    }
  ],
  "capability_stack": ["配方能力", "涂布能力", "洁净生产", "客户认证", "批量稳定供货"],
  "demand_drivers": ["mSAP渗透率提升", "线路精细化", "国产替代"],
  "company_screening_rules": ["主营或明确布局感光干膜", "具备PCB/IC载板客户认证", "有量产或送样证据"],
  "company_exclusion_rules": ["只做PCB下游制造但无材料业务", "只因半导体材料标签相关"],
  "evidence_requirements": ["产品/业务明确提到感光干膜", "客户验证、订单、量产、价格信号至少一项"],
  "evidence_stack": {
    "external_definition": ["来源摘要"],
    "industry_translation": ["需求场景/技术模块/传导路径"],
    "baseline_validation": ["主营、产品、客户、产能、能力栈"],
    "fact_validation": ["公告、订单、送样、认证、量产、涨价"],
    "market_signal": ["复盘提及、盘面强度、卖方覆盖"]
  },
  "proxy_variables": ["EDA", "先进封装", "高速互连"],
  "company_evidence_tiers": [
    {
      "company": "候选公司",
      "tier": "Tier 3",
      "basis": "能力栈匹配，暂无直接公告验证",
      "matched_layer": ["baseline_validation"],
      "missing_validation": ["订单", "客户认证", "收入占比"]
    }
  ],
  "segment_scores": [
    {
      "segment": "高端感光材料",
      "relevance": "high",
      "mapped_concepts": ["光刻胶", "半导体材料"],
      "reason": "新词本体就是材料环节。"
    },
    {
      "segment": "PCB/IC载板制造",
      "relevance": "medium",
      "mapped_concepts": ["PCB", "ABF载板"],
      "reason": "属于下游需求，不宜直接判核心。"
    }
  ],
  "direction_scan": [
    {
      "direction": "感光干膜",
      "sector": "PCB材料",
      "prosperity": "mSAP扩散带动高端干膜需求，量价弹性可能提升。",
      "mention_frequency": "低频",
      "recognition_level": "L1-L2",
      "classification": "布局",
      "core_catalyst": "mSAP产线扩张 -> 干膜需求提升",
      "mapped_concepts": ["光刻胶", "半导体材料"],
      "candidate_companies": ["福斯特", "容大感光"]
    }
  ],
  "demand_scenarios": [
    {
      "scenario": "1.6T光模块",
      "logic": "速率提升推动PCB线宽/线距和高频材料要求提升。",
      "process_requirement": "线宽25±5μm，高层数，高密度",
      "evidence": ["资料原句或来源摘要"]
    }
  ],
  "industry_chain_map": {
    "downstream": [{"name": "1.6T光模块", "evidence_type": "source"}],
    "midstream": [{"name": "mSAP半加成法", "evidence_type": "source"}],
    "upstream_materials": [{"name": "感光干膜", "evidence_type": "source"}],
    "upstream_equipment": []
  },
  "progress_ranking": [
    {
      "direction": "感光干膜",
      "stage": "萌芽期",
      "recognition_level": "L1-L2",
      "evidence_level": "Tier 2",
      "progress_score": 65,
      "key_signal": "mSAP扩产预期开始向材料端扩散",
      "next_validation": "高端干膜订单、客户认证、价格信号",
      "priority": "重点跟踪"
    }
  ],
  "catalyst_calendar": [
    {
      "time": "6月",
      "event": "Rubin试产后mSAP需求确认",
      "watch_item": "订单、客户认证、材料涨价"
    }
  ],
  "validation_checklist": [
    {
      "item": "高端干膜是否进入头部PCB客户",
      "why": "验证材料端是否从逻辑进入订单",
      "status": "待验证"
    }
  ],
  "extraction_quality": {
    "mode": "rule_draft",
    "source_backed_items": 8,
    "inferred_items": 3,
    "missing_fields": [],
    "review_required": true
  },
  "excluded_broad_concepts": ["泛PCB", "普通电子材料"],
  "upstream": ["光敏树脂", "单体", "光引发剂", "PET基膜"],
  "midstream": ["感光干膜制造", "涂布", "曝光显影"],
  "downstream": ["PCB", "IC载板", "先进封装"],
  "core_benefit_links": ["mSAP渗透率提升带动高端干膜需求", "线路精细化提升材料性能要求"],
  "bottlenecks": ["高端产品进口依赖", "客户认证周期长"],
  "verification_nodes": ["价格信号", "客户验证", "量产订单", "国产替代份额提升"],
  "candidate_companies": ["福斯特", "容大感光"],
  "source_urls": ["https://example.com"],
  "confidence": "medium"
}
```

### 需要了解的维度

用于匹配知识库的硬字段：

- `definition`：一句话定义，说明它是什么。
- `aliases` / `english_terms`：同义词、英文名、缩写，解决检索命中问题。
- `parent_concepts`：上位概念，比如 PCB、先进封装、半导体材料。
- `chain_position`：产业链位置，比如上游材料、设备、制造、封测、应用。
- `related_terms`：相关技术/制程/材料，用来连到已有概念图谱。
- `problem_solved`：这个新词解决的产业/技术问题。
- `technical_modules`：把新词拆成技术模块，避免直接从大概念拉股票。
- `required_capabilities`：实现该技术所需能力，比如 EDA、SoC设计、先进封装、材料认证。
- `adjacent_concepts`：相邻概念区分，比如 ODM/OEM/EMS/JDM，避免混淆。
- `capability_stack`：公司要被判定为核心标的所需能力栈。
- `demand_drivers`：为什么现在可能被关注，需求由什么驱动。
- `company_screening_rules`：进入核心/观察池的筛选条件。
- `company_exclusion_rules`：必须剔除的伪相关公司类型。
- `evidence_requirements`：公司从线索升级为核心所需证据。
- `evidence_stack`：证据分层，说明定义、产业逻辑、baseline、公告和市场信号分别来自哪里。
- `proxy_variables`：新概念暂无直接公告时，用哪些代理变量映射到既有知识库。
- `company_evidence_tiers`：公司证据分级，明确 Tier、依据、命中层级和缺失验证。
- `segment_scores`：环节级相关度，只有 `high/medium_high` 默认进入公司映射。
- `direction_scan`：从题材向下扫描工艺/材料/设备/应用等细分方向，判断景气、认知层和催化。
- `demand_scenarios`：解释为什么现在爆发，把需求场景、传导逻辑、工艺要求放在一张表里。
- `industry_chain_map`：把方向放入下游需求、中游工艺/制造、上游材料、上游设备。
- `progress_ranking`：把细分方向按发酵阶段、认知层级、证据等级和优先级排序。
- `catalyst_calendar`：后续时间点和待观察事项。
- `validation_checklist`：把逻辑变成可检查的事实清单。
- `extraction_quality`：标明哪些条目有原文支撑，哪些只是规则推断。
- `excluded_broad_concepts`：需要排除的泛化概念，防止把整个板块都拉出来。
- `upstream` / `midstream` / `downstream`：上下游拆解，默认只展示和辅助人工判断，不直接参与公司分层。
- `report_contexts.json`：由 raw full.md 研究报告回填脚本生成的本地研报产业链上下文，用于补 `产业链全景` 和 `细分方向扫描` 的 L1 产业翻译证据；它不能直接把公司升级为核心。
- `entity_exposures.json` 中的 `chain_layer` / `evidence_layer` / `update_type` 会进入公司分层表，用来区分 `上游材料/设备/中游/下游/生态`、`L1/L3/L1_L3_candidate` 和 `graph_only/exposure_only/delta`。

用于题材判断的软字段：

- `core_benefit_links`：为什么会受益，需求传导路径是什么。
- `bottlenecks`：瓶颈在哪里，是否有供给约束、进口依赖、认证壁垒。
- `verification_nodes`：后续验证点，比如涨价、订单、送样、量产、客户导入。
- `candidate_companies`：外部资料提到的候选公司，只能作为线索，不直接判核心。
- `recognition_level` 约定：`L0` 资料出现但无人关注，`L1` 产业端感知，`L2` 小圈子讨论，`L3` 卖方/复盘覆盖，`L4` 盘面明显反应，`L5` 一致预期。
- `stage` 约定：`暗流期`、`萌芽期`、`第一轮`、`催化共振`、`一致认同`。
- `source_urls`：外部来源，后续做证据回查。
- `confidence`：外部画像置信度，`high/medium/low`。
