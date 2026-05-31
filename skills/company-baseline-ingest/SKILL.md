---
name: company-baseline-ingest
description: 公司基础画像入库——用 iFinD MCP 拉取实现“新词→产业链→核心公司”所必需的轻量公司事实：行业、主营业务、主营产品/能力、相关概念和产业链暴露；补全 wiki/entities 的静态 company baseline，并同步维护 wiki/relations/entity_exposures.json。默认不拉公告/新闻，不抓普通财务摘要，不写短期边际变化。
---

# Company Baseline Ingest Skill

把 `entities/` 从“边际变化记录”升级成可推理的公司底座。它回答：

- 这家公司是谁、主营什么？
- 属于哪些行业/赛道？
- 在产业链中处于哪个环节？
- 相关概念有哪些，强度如何？
- 证据来自 iFinD 基本资料还是公司摘要？

## 适用场景

- `补全 京东方A 公司基础画像`
- `补全 京东方A company baseline`
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
| 公司长期能力/主营业务/产品/行业/产业链位置 | `## 基础画像`、`## 产业链暴露` | iFinD 基础资料、公司摘要 |
| 最近订单/事件/政策催化/涨价/产能变化 | `## 边际变化` | PDF、研报、新闻、公告 |

本 skill 只写 baseline。不要把当天市场逻辑、短期涨跌原因写进 baseline。

## 数据口径

本 skill 的目标不是做财报库，而是用 iFinD 基础资料和公司摘要确认“公司在哪条产业链上、暴露有多强”。只抓取和保留能实现新词映射功能的数据。

必须保留：

- 公司名、股票代码、行业分类：用于实体识别和初步归类。
- 主营业务、主营产品/能力：用于判断公司是否真实参与某产业链。
- 相关概念：用于把公司挂到 concept graph。
- `exposures[]`：公司-概念-产业链角色、强度、证据、置信度，这是最核心输出。

可选保留，仅在 iFinD 直接给出且能帮助判断核心程度时写入：

- 业务收入、收入占比、毛利率：用于判断该业务是不是公司主业。
- 产能、出货量、订单金额、项目投资额：用于判断产业化进度。
- 客户数量、客户类型、供应链认证、量产/送样/验证状态：用于判断真实性。
- 研发投入、专利/认证、产品规格：用于判断技术壁垒。
- 市占率、排名、行业地位：用于判断核心程度。

默认不写或只在风险中简述：

- 总资产、净资产、ROE、每股收益、普通估值指标。
- 与产业链暴露无关的现金流、融资、分红。
- 单纯股价、涨跌幅、资金流、龙虎榜。
- 泛泛的“最新财务摘要”，除非能说明某业务收入占比或产业化规模。

判断口诀：如果一个数据不能帮助回答“这家公司是不是该概念的核心标的”，就不要放进 baseline `## 关键数据`。

## 公告处理边界

默认不拉公告/新闻，避免 baseline 任务量过大、噪音过多。

- `company-baseline-ingest`：只补轻量静态画像，优先用 `stock.get_stock_info` 和 `stock.get_stock_summary`。
- `entity-delta-ingest`：后续单独处理具体公告、订单、客户认证、投产、扩产、风险事件等边际变化。
- 如果 baseline 明显缺口很大，再由用户明确要求“补公告证据”时，才单独检索公告；不要默认批量拉公告。

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
- 每家公司先生成独立 raw，再合并成一个 `updates[]` batch JSON。
- 批量写入时不要把长 JSON 直接塞进终端 heredoc；先落盘到 `wiki/raw/ifind-baseline/baseline-updates-YYYY-MM-DD-batchN.json`，预校验后再用短命令调用 writer。这样便于审核、复用和定位失败。
- 不确定的产业链角色写 `confidence="low"`，不要硬判核心。

## Step 1: 拉 iFinD 原始材料

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/company-baseline-ingest/scripts/fetch_ifind_baseline.py" \
  --company "京东方A" \
  --code "000725" \
  --out-dir "/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline"
```

脚本默认调用：

- `stock.get_stock_info`
- `stock.get_stock_summary`（查询词已限制为主营业务、主营产品、行业分类、业务构成，不主动抓普通财务摘要）

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
      "business_segments": [],
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
      "key_data": [],
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
| `business_segments` | 可选；只有能判断业务是否主业时才写 |
| `concepts` | 该公司相关概念，用已有概念名优先 |
| `exposures` | 公司-概念-产业链角色，是最重要字段 |
| `strength` | `core/related/peripheral` |
| `confidence` | `high/medium/low`；iFinD基础资料/摘要直接支持为 medium，弱推断为 low；没有公告验证时慎用 high |
| `evidence` | 短证据，不搬运长段原文 |

最小合格 JSON 只需要：`company`、`code`、`industry`、`main_business`、`products`、`concepts`、`exposures`、`raw_source`。其他字段没有强证据就留空。

## Step 3: 写入

批量推荐写法：

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline/baseline-updates-2026-05-25-batch1.json")
data = json.loads(p.read_text(encoding="utf-8"))
required = {"concept", "role", "strength", "evidence", "confidence"}
errors = []
for u in data.get("updates", []):
    for i, exp in enumerate(u.get("exposures", []), 1):
        missing = required - set(exp)
        if missing:
            errors.append((u.get("company"), i, sorted(missing)))
print("updates=", len(data.get("updates", [])))
print("exposure_errors=", errors)
raise SystemExit(1 if errors else 0)
PY

python3 "/Users/lbq/Desktop/c c/金融/skills/company-baseline-ingest/scripts/entity_baseline_writer.py" \
  < "/Users/lbq/Desktop/c c/知识库/wiki/raw/ifind-baseline/baseline-updates-2026-05-25-batch1.json"
```

单家公司或临时调试也可用 heredoc：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/company-baseline-ingest/scripts/entity_baseline_writer.py" <<'JSON'
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

writer 输出的 `baseline来源` 应为 `iFinD 基础资料 / 公司摘要`。不要写成 `iFinD / 公告 / 新闻片段`，除非用户明确要求补公告证据并已单独处理。

## 质量门槛

- baseline 只能写长期事实，不写“今日涨停/市场关注/短线催化”。
- 每个 `exposures[]` 必须有 `concept`、`role`、`strength`、`evidence`、`confidence`。
- 证据不够时，`strength` 降级为 `related/peripheral`，`confidence` 降级为 `low`。
- 写入后检查：

```bash
python3 -m json.tool "/Users/lbq/Desktop/c c/知识库/wiki/relations/entity_exposures.json" >/dev/null

python3 - <<'PY'
import re
from pathlib import Path
base = Path("/Users/lbq/Desktop/c c/知识库/wiki/entities")
companies = ["公司A", "公司B"]
sections = ["## 基础画像", "## 产业链暴露", "## 关键数据", "## 风险与反证", "## 待核实问题", "## iFinD 证据"]
for c in companies:
    text = (base / f"{c}.md").read_text(encoding="utf-8")
    missing = [s for s in sections if s not in text]
    bad = bool(re.search(r"sources:\s*\[\[|\?（|iFinD / 公告 / 新闻片段|iFinD \|\n##", text))
    source_ok = "iFinD 基础资料 / 公司摘要" in text
    print(f"{c}: sections={'OK' if not missing else missing} bad_patterns={bad} source_ok={source_ok} delta={'## 边际变化' in text}")
PY
```

## 与其他 skill 的衔接

- `concept-ingest` 发现核心公司缺 baseline：可在单篇处理后触发本 skill。
- `entity-delta-ingest` 新建 entity 后：建议再用本 skill 补基础画像。
- `new-term-radar`/概念雷达后续可以直接读取 `wiki/relations/entity_exposures.json` 进行公司映射。
