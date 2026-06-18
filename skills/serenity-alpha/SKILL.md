---
name: serenity-alpha
metadata:
  pattern: generator
  also: [pipeline]
description: Serenity Alpha 本地知识库版——基于新闻/题材/复盘线索，结合本地 wiki 概念图谱、个股逻辑卡、题材雷达、海外对标和近端行情反馈，分析个股弹性预期差、补涨顺序、市场误分类和交易含义。触发词：serenity、alpha、弹性预期差、个股弹性、补涨排序、反推个股、预期差排序、交易含义、分歧反证。
---

# Serenity Alpha：个股弹性预期差分析

## 核心定位

本 skill 不是公告验证工具，也不是财报模型工具。

它回答的是：

```text
题材/新闻/产业链线索 -> 哪些环节产业逻辑最强 -> 哪些个股股价已经反映 -> 哪些个股还没充分定价 -> 补涨顺序与分歧反证
```

核心目标是做出类似：

```text
现在不是“泛 PCB”，而是 PCB 主线内部再分账。
如果要找补涨，优先看：胜宏科技、三孚新科、深南/沪电、生益科技。
一句话：补涨看胜宏，弹性看三孚，锚定看生益，确认看深南/沪电。
```

## 与原版 Serenity 的区别

原版 Serenity 强调：

```text
news -> demand -> financial statements -> small-cap elasticity -> validation path
```

本地版改为：

```text
news/theme -> wiki 产业链强弱 -> company exposure -> price reaction -> relative lag -> expectation gap -> trading meaning
```

不要把输出重点放在“等公告/等财报验证”。

可以提“后续观察”，但必须服务于交易预期差，而不是把分析退回到审计式验证。

## 默认数据源

优先使用本地 wiki 和已有临时报告，不要批量通读正文。

本地 wiki：

```text
/Users/a77/Desktop/c c/知识库/wiki
```

可读取的数据：

```text
wiki/relations/concept_graph.json
wiki/relations/entity_exposures.json
wiki/relations/evidence_index.json
wiki/relations/report_contexts.json
wiki/relations/benchmark_maps.json
wiki/relations/theme_signals.json
wiki/concepts/*.md
wiki/entities/*.md
wiki/sources/*.md
wiki/synthesis/*.md
```

## 推荐入口：上下文包脚本

## 云端/跨电脑标准入口（新版默认）

云端 agent 使用本 skill 时，必须先确认**金融仓库**和**知识库仓库**都已同步到 `main`。Serenity Alpha 的新版上下文解析脚本在金融仓库，知识库只提供 wiki 数据底座；只拉知识库 `main` 不会更新 `serenity_context.py`。

默认路径可按机器调整，先设置变量再同步：

```bash
export FINANCE_REPO="${FINANCE_REPO:-/Users/a77/Desktop/c c/金融}"
export KNOWLEDGE_REPO="${KNOWLEDGE_REPO:-/Users/a77/Desktop/c c/知识库}"
export KNOWLEDGE_WIKI="${KNOWLEDGE_WIKI:-$KNOWLEDGE_REPO/wiki}"
export TERM="${TERM:-MLCC}"

git -C "$FINANCE_REPO" pull origin main
git -C "$KNOWLEDGE_REPO" pull origin main
python3 "$FINANCE_REPO/skills/serenity-alpha/scripts/serenity_context.py" --help
```

默认先生成 markdown 上下文包，再基于上下文做人为排序，不要手动遍历 relations JSON 或批量读页面正文：

```bash
python3 "$FINANCE_REPO/skills/serenity-alpha/scripts/serenity_context.py" \
  --term "$TERM" \
  --vault "$KNOWLEDGE_WIKI" \
  --limit 40
```

如需落盘：

```bash
python3 "$FINANCE_REPO/skills/serenity-alpha/scripts/serenity_context.py" \
  --term "$TERM" \
  --vault "$KNOWLEDGE_WIKI" \
  --limit 40 \
  --out "/tmp/${TERM}-serenity-context.md"
```

新版上下文包必须优先使用其中的「概念定位」「候选池」「细分卡位」「角色预分桶」「历史快照」。如果输出里没有这些模块，说明云端没有拉到新版金融仓库。

不要手动遍历 relations JSON 或批量读页面正文。默认先跑：

```bash
python3 "/Users/a77/Desktop/c c/金融/skills/serenity-alpha/scripts/serenity_context.py" \
  --term "题材或环节名" --limit 30
```

一次性输出紧凑 markdown 上下文包（`--format json` 可切回 JSON，`--out` 可落盘），包含：

| 上下文包模块 | 来源 | 对应输出模板的哪一节 |
|---|---|---|
| 概念定位 + 概念知识卡 | aliases/concept_graph + concepts/*.md 定锚与核心逻辑 | 「问题」：市场交易的到底是哪条链 |
| 候选池（直接/扩散、细分概念、强度、证据数、逻辑卡、wiki 一句话定位、页更新） | entity_exposures + evidence_index + entities/*.md | 「候选池横向比较」防锚定 |
| 细分卡位（名称含题材词的 wiki 细分概念 → 公司列表） | entity_exposures 细概念暴露（如 ArF光刻胶/光刻胶树脂） | 「产业链强弱排序」：谁卡哪个细分环节 |
| 角色预分桶（锚/二阶瓶颈/旧标签/扩散） | strength + chain_layer + wiki 定位与题材词重合度 | 四类角色起点，仅启发不是结论 |
| 历史 Serenity / 合成研究快照 | synthesis/*.md | 防重复劳动；引用历史排序后按当前盘面重做 |
| 海外对标 + 临时报告 | benchmark_maps + /private/tmp | 叙事可迁移性 + 可复用上下文 |

使用规则：

- 候选池里「命中=直接」的公司优先进入排序；「扩散」只作产业链补位或二阶发散，不要直接当补涨首选。
- 「细分卡位」是预期差排序的优先视角：同一题材下卡不同细分（如 ArF 量产 vs 树脂原料 vs 光引发剂）的公司不是同质化竞争，不要拉通排序；独占某细分的公司优先检查是否存在认知差。
- wiki 一句话定位是「旧标签重估」判断的关键素材：定位与本题材词不重合但暴露逻辑成立的，优先检查是否被旧主业压价。
- 页更新日期老于 2 周的候选，其 wiki 判断要降权，必须用近端行情和最新材料复核。
- 历史快照里已有同题材 serenity 分析时，先读它的排序和反证，再说明本次排序相对历史版本的增量变化（哪些候选升级/降级、哪些反证已落地）。

金融项目可复用：

```text
/Users/a77/Desktop/c c/金融/skills/serenity-alpha/scripts/serenity_context.py   # 首选：一次性生成上下文包
/Users/a77/Desktop/c c/金融/skills/theme-radar/scripts/radar.py
/Users/a77/Desktop/c c/金融/scripts/apply_ima_stock_logic_to_obsidian.py
```

临时报告可优先参考：

```text
/private/tmp/*front_map*.md
/private/tmp/*radar*.md
/private/tmp/*serenity*.md
```

行情反馈可来自：

```text
cn_stock_price_daily_wind
Tencent K-line
已有 SQL / 临时行情输出
用户给出的涨幅表
```

如无法直接取得行情，必须明确标注“涨幅待补”，但仍可先做产业链强弱排序。

## 输入类型

支持：

- 一条新闻：如“AI服务器 PCB 价值量提升”
- 一个题材：如“光模块”“AI服务器PCB”“CPO”“GLP-1”
- 一个复盘问题：如“这个方向谁最有补涨弹性？”
- 一组候选公司：如“胜宏、三孚、深南、沪电、生益怎么排？”
- 一份已有 Theme Radar / front-map 报告

## 分析框架

完整的 8 步分析框架（先定主线 → 产业证据强度 → 股价反映度 → 强逻辑×低反映 → 最佳补涨迁移 → 防锚定候选池 → 市场误分类 → 分歧反证）见 `references/analysis-framework.md`。每次分析前必须加载该文件并逐步执行，不要凭记忆跳步。

## 输出模板

每次输出必须套用 `assets/output-template.md` 的结构（结论 / 问题 / 候选池横向比较 / 补涨迁移链 / 产业链强弱排序 / 股票池 / 证据链 / 交易含义 / 分歧反证 / 最后一句）。直接复制该模板填空，不要自创结构。

## 排序口径

排序优先级、四项「禁止」红线、以及必须解释的判断项见 `references/ranking-rubric.md`。给出排序前必须按该口径自检。

## 与 Theme Radar 的协同

如果用户只给题材，先跑或参考 `theme-radar front-map`，拿到：

- 产业链分层
- 核心公司
- 延伸公司
- 海外龙头对标
- 反哺复盘

然后再用本 skill 做二次排序：

```text
Theme Radar 负责找全图谱；Serenity Alpha 负责排弹性和预期差。
```

## 与交易复盘层的协同

当用户要求“用 Serenity Alpha 分析今天某票涨停/异动/补涨是否成立”时，必须把产业逻辑和交易复盘层分开。

交易复盘层使用 `market_feature_store`，默认只读查询，不直接同步、不写库。

可用入口：

```bash
python -m market_feature_store.cli daily-review --trade-date YYYY-MM-DD
python -m market_feature_store.cli stock-sectors 股票代码或名称 --trade-date YYYY-MM-DD
python -m market_feature_store.cli sector-stocks --sector 板块名 --trade-date YYYY-MM-DD --order-by pct_chg_20d
python -m market_feature_store.cli top-sectors --trade-date YYYY-MM-DD --order-by diff_ratio
python -m market_feature_store.cli weighted-gainers --start YYYY-MM-DD --end YYYY-MM-DD
python -m market_feature_store.cli query-limit-heat --trade-date YYYY-MM-DD --with-stocks
python -m market_feature_store.cli query-stock-high --trade-date YYYY-MM-DD
```

对应 Python API：

```text
market_feature_store.query.stock_sectors
market_feature_store.query.sector_stocks
market_feature_store.query.top_sectors
market_feature_store.query.weighted_gainers
market_feature_store.query.limit_heat
market_feature_store.query.stock_highs
market_feature_store.query.advancers_extrema
```

交易复盘层需要回答：

| 层级 | 要查什么 | 用途 |
|---|---|---|
| 个股 | 当日涨幅、3/5/10/20 日涨幅、成交额、涨停状态、新高状态 | 判断是首次启动、趋势加速还是高位兑现 |
| 板块 | 所属复盘会板块、板块涨幅、成交额、边际量 `diff_ratio` | 判断是单票材料驱动还是板块共振 |
| 扩散 | 同板块成分股涨幅、涨停热力、代表涨停股 | 判断分支是否被市场确认 |
| 市场 | 成交额、量能比、涨家数、涨停/跌停、市场阶段、偏离度 | 判断环境是转点、共振、退潮还是普通日 |
| 区间 | 区间加权涨幅、近端涨幅排名、板块内排序 | 判断股价是否已充分反映 |

输出时必须区分：

```text
产业证据：客户、订单、产能、价格、利润、技术壁垒
交易反馈：涨停、放量、板块扩散、边际量、新高、承接
```

涨停只是价格反馈，不是产业证据。

如果某票涨停但板块无跟随，结论应偏向“单票材料驱动/个股 Alpha”。

如果某票涨停且产业锚、同链条候选、涨停热力和边际量同步增强，才可上调为“分支被市场确认”。

如果明牌锚已涨、该票低位放量补涨，才可描述为“主线锚确认后的二阶补涨”。

示例：

```text
旭光电子涨停，不等于 AI 陶瓷主线已经成立。
需要同时看三环集团、国瓷材料、中瓷电子、博敏电子、昀冢科技是否跟涨，
陶瓷基板/HBM/光模块相关板块是否放量，
涨停热力是否出现 AI 陶瓷或上游材料，
以及旭光自身 5/10/20 日涨幅是否已经透支。
```

## 与公告/入库 skill 的边界

不要默认调用：

```text
disclosure-archive
entity-delta-ingest
company-baseline-ingest
```

除非用户明确说：

```text
补公告
入库
写 entity
更新知识库
```

本 skill 默认只读、只分析、不写库。

## 质量要求

输出前逐项核对 `references/quality-checklist.md`（必须给排序、区分补涨/弹性/锚/确认、说明股价反映度与逻辑落差、列反证但不退化成公告 checklist、行情/证据缺失时的降级措辞）。
