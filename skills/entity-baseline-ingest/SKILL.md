---
name: entity-baseline-ingest
description: 公司基础画像入库——用 iFinD MCP 拉取上市公司基础资料、主营业务、产品构成、财务摘要、公告/新闻片段，补全 wiki/entities 的静态 baseline，并同步维护 wiki/relations/entity_exposures.json。适用于“补全某公司 entity baseline”“批量补全某概念相关公司画像”“从 iFinD 拉公司基础信息”。不写短期边际变化，短期事件用 entity-delta-ingest。
---

# Entity Baseline Ingest Skill

把 `entities/` 从“边际变化记录”升级成可推理的公司底座。它回答：

- 这家公司是谁、主营什么？
- 属于哪些行业/赛道？
- 在产业链中处于哪个环节？
- 相关概念有哪些，强度如何？
- 证据来自 iFinD 基本资料、年报公告还是新闻？

## 适用场景

- `补全 京东方A entity baseline`
- `批量补全 Micro LED光互连 相关公司 baseline`
- `从 iFinD 拉 德赛西威、华灿光电 的公司画像`
- 新建 entity 后，需要补“静态底座”，但不想污染 `## 边际变化`

不适用：

- 单篇研报/PDF/公告中的短期催化、订单、涨价、产能、客户导入：用 `entity-delta-ingest`。
- 新概念入库：用 `concept-ingest`。
- 只有涨跌、资金流、龙虎榜：默认不写 baseline。

## 核心原则

`baseline` 和 `delta` 分开：

| 类型 | 写入位置 | 来源 |
|---|---|---|
| 公司长期能力/主营业务/产品/行业/产业链位置 | `## 基础画像`、`## 产业链暴露` | iFinD 基础资料、年报、公告 |
| 最近订单/事件/政策催化/涨价/产能变化 | `## 边际变化` | PDF、研报、新闻、公告 |

本 skill 只写 baseline。不要把当天市场逻辑、短期涨跌原因写进 baseline。

## 工作流

单家公司：

```
确定公司名/代码
  ↓
fetch_ifind_baseline.py 拉 iFinD 原始材料
  ↓
LLM 从 raw 中抽取 baseline JSON
  ↓
entity_baseline_writer.py 写入 entity 静态区
  ↓
检查 entity 与 wiki/relations/entity_exposures.json
```

批量公司：

- 一次最多 5 家，避免 iFinD/MCP 超时。
- 每家公司先生成独立 raw，再合并成一个 `updates[]` 调用 writer。
- 不确定的产业链角色写 `confidence="low"`，不要硬判核心。

## Step 1: 拉 iFinD 原始材料

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/entity-baseline-ingest/scripts/fetch_ifind_baseline.py" \
  --company "京东方A" \
  --code "000725" \
  --out-dir "/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline"
```

脚本会调用：

- `stock.get_stock_info`
- `stock.get_stock_summary`
- `news.search_notice`
- `news.search_news`

输出 JSON raw 文件，供 LLM 抽取结构化 baseline。若 iFinD 暂时失败，不要编造；报告失败并稍后重试。

## Step 2: 抽取 baseline JSON

从 raw 中抽取以下结构。字段必须来自 iFinD raw 或已有 entity，不确定则留空。

```json
{
  "source_name": "iFinD baseline 2026-05-25",
  "updates": [
    {
      "company": "京东方A",
      "code": "000725",
      "raw_source": "raw/ifind-baseline/京东方A.json",
      "industry": {
        "申万行业": "电子--光学光电子--面板",
        "同花顺行业": "电子--光学光电子--面板",
        "证监会行业": "制造业--计算机、通信和其他电子设备制造业"
      },
      "main_business": "显示器件业务、物联网创新业务、传感业务、MLED业务、智慧医工业务。",
      "products": ["显示器件", "物联网创新", "传感", "MLED", "智慧医工"],
      "business_segments": [
        {"name": "显示器件业务", "revenue": "1664.17亿元", "gross_margin": "12.92%", "period": "2025年"}
      ],
      "concepts": ["显示面板", "AI眼镜", "玻璃基板", "Micro LED光互连"],
      "exposures": [
        {
          "concept": "玻璃基板",
          "role": "中游封装载板/玻璃基应用",
          "strength": "core",
          "evidence": "年报提及传感业务重点突破玻璃基封装载板。",
          "confidence": "high"
        }
      ],
      "customers_ecosystem": ["待补充"],
      "competitors": [],
      "key_data": [
        {"indicator": "显示器件业务收入", "value": "1664.17亿元", "period": "2025年", "source": "iFinD"}
      ],
      "risks": ["面板周期波动影响盈利能力。"],
      "open_questions": ["玻璃基封装载板是否形成量产收入？"]
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `industry` | 行业分类，优先 iFinD 摘要里的申万/同花顺/证监会行业 |
| `main_business` | 主营业务，不写市场观点 |
| `products` | 主营产品/业务类型 |
| `business_segments` | 收入构成，有数据才写 |
| `concepts` | 该公司相关概念，用已有概念名优先 |
| `exposures` | 公司-概念-产业链角色，是最重要字段 |
| `strength` | `core/related/peripheral` |
| `confidence` | `high/medium/low`；年报/公告为 high，摘要/新闻为 medium，弱推断为 low |
| `evidence` | 短证据，不搬运长段原文 |

## Step 3: 写入

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/entity-baseline-ingest/scripts/entity_baseline_writer.py" <<'JSON'
{
  "source_name": "iFinD baseline 2026-05-25",
  "updates": []
}
JSON
```

脚本会：

1. 更新或新建 `wiki/entities/{公司}.md`。
2. 更新 frontmatter：`updated`、`revision`、`tickers`、`raw_sources`、`tags`。
3. 重写静态区：
   - `## 基础画像`
   - `## 产业链暴露`
   - `## 关键数据`
   - `## 风险与反证`
   - `## 待核实问题`
   - `## iFinD 证据`
4. 不改写 `## 边际变化` 内容。
5. 同步更新 `wiki/relations/entity_exposures.json` 和 `evidence_index.json`。

## 质量门槛

- baseline 只能写长期事实，不写“今日涨停/市场关注/短线催化”。
- 每个 `exposures[]` 必须有 `concept`、`role`、`strength`、`evidence`、`confidence`。
- 证据不够时，`strength` 降级为 `related/peripheral`，`confidence` 降级为 `low`。
- 写入后检查：
  ```bash
  rg -n "sources:\\s*\\[\\[|\\?（" "/Users/lbq/Desktop/c c/知识库/wiki/entities/公司.md"
  python3 -m json.tool "/Users/lbq/Desktop/c c/知识库/wiki/relations/entity_exposures.json" >/dev/null
  ```

## 与其他 skill 的衔接

- `concept-ingest` 发现核心公司缺 baseline：可在单篇处理后触发本 skill。
- `entity-delta-ingest` 新建 entity 后：建议再用本 skill 补基础画像。
- `new-term-radar`/概念雷达后续可以直接读取 `wiki/relations/entity_exposures.json` 进行公司映射。
