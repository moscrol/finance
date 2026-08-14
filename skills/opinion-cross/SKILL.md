---
name: opinion-cross
metadata:
  pattern: pipeline
  also: [reviewer]
description: "把已筛过的卖方观点/产业消息流提纯成三重共振机会卡片：事实硬度分层、多空分歧、三维交叉排 Tier。用户粘贴卖方观点并要提纯/排 Tier 时用，不是扫全市场公告。问「第几篇研报/首覆/扎堆」用知识库 sellside-coverage-cross。"
---

> 硬约束在前；细节见 `references/`。官方压缩截断保开头，所以闸门/红线必须留在文首。


# opinion-cross 观点提纯 → 三重共振机会卡片

## 用途与边界

**输入**：用户已经**人工筛过**的观点流——卖方研报口播、机构观点合集（如「国投硬科技/天风通信/矽电」这类）、产业小作文。**不是**全市场公告，所以不做公告采集/每日全市场编排（那是另一类需求，成本高、噪音大，用户已明确不做）。

**它解决的核心痛点**：观点流里硬证据（订单/入股/合同/官方表态）、软推演（目标价/预期/看好）、情绪噪音（喊单话术）混在一起，且常常多空并存。本 skill 把这坨料**提纯、分层、排序**，让"哪条是真三重共振"一眼可见。

**它不是**最终研究结论——是**可复核草稿**。Tier、硬度、多空都来自原文证据；缺证据就标"待补/仅题材弹性"，规则层不臆造，由 agent 复核盘面维度与硬度后定稿。

## 何时用 / 何时不用

- ✅ 用户贴一段卖方观点/产业消息流，想看"提纯后哪些标的是真机会、排个 Tier"。
- ✅ 想识别一段料里的多空分歧和预期差拐点。
- ❌ 想扫全市场公告找机会 → 不在本 skill 范围（用户已明确不做全市场）。
- ❌ 想做单题材深度产业链拆解 → 用 `theme-radar`（front-map / deep-dive）。

## 用法

```bash
python3 skills/opinion-cross/scripts/opinion_cross.py \
  --term "CPO" \
  --input "/path/to/opinion-stream.txt" \
  --vault "/Users/lbq/Desktop/c c/知识库/wiki" \
  --markdown "/path/to/CPO-opinion-cross.md" \
  --out "/path/to/CPO-opinion-cross.json"
```

> 原文先落库门：`opinion_store.py ingest` 的输入若不在 `wiki/raw/sellside/` 或 `wiki/raw/briefings/` 下，会自动拷贝归档到 `raw/sellside/<报告日期>-<来源>.md` 再入库（输出 `raw_archive` 字段），保证结构化事件永远可回溯原文、可重提纯。

参数：
- `--term`：题材名（可选，用于把标的对齐到该题材的 concept；留空则用标的自身最相关 concept）。
- `--input`：观点流文本文件（必填）。
- `--vault`：知识库 wiki 根目录（默认 `$CONCEPT_VAULT` 或 `~/Desktop/c c/知识库/wiki`）。
- `--markdown` / `--out`：分别落地 Markdown 报告 / 结构化 JSON（均可选）。
- `--format`：`markdown`（默认）/ `json` / `both` 控制 stdout 打印内容。

## 管道（5 步）

```
观点流文本
  → [C1 观点事件抽取]  扫出 KB 内出现的标的（最长优先去重叠），逐标的归集观点句、催化句
  → [C2 事实硬度分层]  每个标的的证据分三档：🟢硬证据 / 🟡软推演(卖方喊单) / 🔴情绪噪音
  → [C3 多空分歧识别]  看多 vs 看空措辞计数 + 预期差拐点（符合预期/辟谣/super expectation）
  → [C4 三维交叉引擎]  复用 theme-radar：逐标的构造 signal/context → signal_dimension_rows → resonance_tier
  → [C5 Tier 卡片报告] 按 Tier1/2/3 分组，每张卡片含 三维交叉表 + 硬度分层 + 催化 + 操作建议
  → 〖复核门〗  定稿/落地最终卡片报告**前**必过 `check_opinion_review.py`（exit-0），见下「复核门」节
```

> C1–C5 是**机器底稿**，最终卡片报告是 agent 复核后的**定稿**。机器底稿与定稿之间隔一道 exit-0 复核门（见下），把「由 agent 复核盘面维度与硬度后定稿」从散文约定硬化成检查点信号门。

**题材无关**：标的清单来自知识库 `relations/entity_exposures.json`，标的→产业方向映射来自 `entity_exposures`（含 `chain_layer/strength/role/fact_hardness`）+ `concept_graph.json`，因此 CPO、硅光、固态电池等任何题材都能跑，不写死。

## 三维交叉与 Tier 判定（复用 theme-radar）

三维交叉（公告/事实 × 产业趋势 × 市场热点）取数口径、Tier1/2/3 判定规则，以及「事实维度只放硬证据/催化、产业信号只走 context」的关键实现细节见 `references/resonance-tier-rubric.md`。

## 事实硬度词典

事实硬度三档词典（🟢 HARD_FACT_KEYS / 🟡 SOFT_KEYS / 🔴 NOISE_KEYS）见 `references/fact-hardness-dictionary.md`。硬度仅用于分层与排序，不做硬过滤。

## 输出 JSON schema（要点）

输出 JSON 的结构（term / divergence / opportunities[] / summary 等要点）见 `references/output-schema.md`，按该 schema 落地结构化结果。

## 已验证（CPO 观点料）

用户贴的 CPO 观点合集（国投硬科技/天风通信/矽电…）跑出：
- 9 个 KB 内标的；**多空分歧**正确识别（看多 11 / 看空 10），预期差拐点抓到「符合预期就是超预期」「英伟达辟谣」。
- **Tier 2 ⭐⭐**：罗博特科（光通信订单 15 亿）、兆驰股份（3.35 亿合同）——有硬证据。
- **Tier 3 ⭐**：新易盛/天孚通信/炬光科技/中际旭创/联特科技/矽电股份（卖方喊单软推演）+ 中芯国际（客户名单提及）。

## 已知局限（交给 agent 复核）

1. **主体指代（anaphora）**：当硬事实句以「公司…」指代主体而未写出标的名时，会归错或漏归。例：矽电的「华为哈勃入股 3%」「与兆驰签 3.35 亿」中，3.35 亿被归到句中出现的"兆驰股份"，矽电因此被低估为 Tier 3。agent 复核时应把这类硬事实归回正确主体。
2. **市场热点维度**：静态文本里通常没有当日盘面，多为"待补"，因此 Tier 上限常停在 2。要升 Tier 1 需接 `limit-advance`/`top-gainers`/`market-overview` 当日盘面信号（后续可做）。
3. **标的识别依赖 KB**：只识别 `entity_exposures` 里已存在的实体；题材或公司未入库则漏识别（先走 disclosure/ingest 补库）。

## 复核门（C5 之后、定稿前必做 · `check_opinion_review.py`）

上面三条「已知局限」过去只是散文约定——机器底稿吐完，agent 凭自觉复核。本门把它硬化成 **exit-0 检查点信号门**（体例同知识库仓 cross-analysis `check_cross_review.py` / sellside `check_opinion_review.py`、disclosure-archive `--apply`）：**机器底稿的每个🟢硬证据标的**都必须有一条复核结论，且必须核过主体指代归属、对市场热点维度表态、给出合法 Tier。门未过（exit 1）禁止定稿最终卡片报告。

```bash
# 1) 跑机器底稿（C1–C5），落 --out JSON
python3 skills/opinion-cross/scripts/opinion_cross.py --term CPO --input stream.txt --out /tmp/oc.json
# 2) 按「已知局限」逐标的复核，填 /tmp/opinion_review.json（--template 出空白模板）
python3 skills/opinion-cross/scripts/check_opinion_review.py --template > /tmp/opinion_review.json
# 3) 过门：exit 0 才放行定稿
python3 skills/opinion-cross/scripts/check_opinion_review.py /tmp/oc.json /tmp/opinion_review.json
```

复核产物 `reviewed[]` 每条对应一个标的：`target`（对齐 `opportunities[].target`）、`final_tier`（Tier 1/2/3/排除，可改判机器 Tier）、`anaphora_checked`（bool，硬证据标的**必须** true = 已核对硬事实归属正确主体，堵局限①主体指代）、`market_heat`（市场热点维度表态，待补也要显式写「待补」= 局限②）、`note`（复核结论）。

门校验（只读，不改 `opinion_cross.py`、不写任何库）：

- 机器命中的**每个🟢硬证据标的**（`hardness.dominant==硬证据` 或 `hardness.hard` 非空）必须在 `reviewed[]` 里有结论，且 `anaphora_checked==true`；纯软推演标的不强制（与机器同档，不抬权）。
- 每条 `reviewed` 的 `final_tier` 合法、`anaphora_checked` 是 bool、`market_heat`/`note` 非空。
- 退出码：0 = 复核充分可定稿；1 = 门控未过；2 = 用法/解析错误。

**诚实的天花板**：门只能保证「每个硬证据标的被有意识地复核过」，**不能**验证 agent 真的纠对了主体指代、或真补全了盘面——同 sellside 观点不可枚举的天花板同源（区别：opinion-cross 命中标的可枚举，故能强制逐标的覆盖）。市场热点维度仍多为「待补」，要真升 Tier 1 需接 `limit-advance`/`top-gainers`/`market-overview` 当日盘面（见局限②）。


## 累积层与回测细节

按需读取，不要一次性加载进主上下文：

- `references/opinion-store.md` — 观点事件库 opinion_store.py（入库/聚合/晨汇补漏）
- `references/consensus-views.md` — consensus_staging.py 三视图与 consensus_bridge.py 桥
- `references/backtest-winrate.md` — T+N 回测与机构胜率榜
- `references/pitfalls.md` — 踩坑与迭代总结

## 与其他 skill 的关系

- **复用** `theme-radar`：三维交叉引擎（`signal_dimension_rows`/`resonance_tier`）+ 认同度阶梯（`recognition_score`/stage 体系）+ KB relations（`concept_graph`/`entity_exposures`）。
- **盘面维度（待接）**：`limit-advance` / `top-gainers` / `high-volume-gainers` / `market-overview`。
- **补库（上游）**：标的/题材缺失时用 `disclosure-archive` / `*-ingest` 先补 KB。

