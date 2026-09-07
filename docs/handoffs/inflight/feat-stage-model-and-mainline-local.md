# feat/stage-model-and-mainline-local

## 这个分支做什么
用户（2026-09-07 19:19）：周期阶段「b 自己训练一个分类器，后续恢复访问也可以对照」；主线题材/核心个股「可做可不做…我们自己也可以有分类定义标准，
应该是按照人气值来看…看看 fupanhui 咋定义的，他的结构化数据我们其实自己都可以做分类，这样以后我们自己就是一个数据源了」。

1. **周期阶段自训分类器 v1** `market_feature_store/models/market_stage.py`
   - numpy 多分类逻辑回归（环境无 sklearn；不动共享 venv），30 个特征全来自本地表：上证收盘链（ret/MA/位置/波动）、量能比、涨家数广度、
     涨跌停、强度、前三行业占比、全A等权涨跌、站上 20 日线比例、20 日新高比例。监督 = fupanhui 343 个可用标签日（2025-04-08～2026-09-02）。
   - **分块 5 折：精确 43.7%，粗粒度（上行/下行/横盘）55.1%**；手写规则 37%/58%。最近一块（2026-05-28～09-02）只有 22%。
     结论：fupanhui 的周期不是价格/量能/广度的线性函数；v1 是**自家低置信标签**，写库带 `market_stage_source='local:stage-lr-v1'`、
     `market_stage_confidence`（schema 加两列，老库 `ensure_stage_columns`）。滞回：新阶段概率高出当前 0.15 才切换，`stage_day` 随切换累计。
     有 fupanhui 标签的日子不覆盖。CLI `train-market-stage`（重训并导出 JSON 产物 `models/market_stage_lr_v1.json`，8.5KB）、`compute-market-stage-local`。
   - 生产：09-03 下跌阶段(0.70) → 09-04 第 2 天(0.65) → 09-07 第 3 天(0.55)。
2. **主线题材人气值 v1** `compute-mainline-local`
   - 先反推 fupanhui 定义（53 日 / 14 题材 / 73 板块）：主线板块在**20 日涨幅 72 分位**、5 日均额 64 分位、61% 有涨停，但**当日涨幅只在 50 分位**——
     是多周趋势 + 人气，不是当日强势；题材持续中位 5 日、最长 35 日；板块→题材归组稳定（73 板块只有 5 个换过题材）。
   - 规则搜索（Jaccard 与其题材集合）：20 日涨幅×2 + 5 日涨停数×1 + 5 日均额×0.5 + 5 日双红×0.5，题材分 = 成员板块 top-3 均值，取前 4。
     **Jaccard 0.28**（随机 0.09；限定在其 14 题材内选 0.47）。板块→题材：其历史归组兜底申万一级（我们自己的分类标准，可扩）。
   - 主线个股：主线板块成员里涨停股（不计 ST）优先，再按涨幅×log(成交额)，每题材 ≤20。09-07：农林牧渔/AI算力/电子/通信，80 只——
     农林牧渔与 fupanhui 09-02 的主线及其个股（万向德农/金健米业/新华百货）重合。
3. 两步进 `plans.local`（market-editorial-local 之后 / features 之前）；registry mainline 数据族 `local: [mainline-local]`。
4. 双轨脚本加主线 Jaccard / 周期一致率对照段（fupanhui 恢复后有同日标签自动出读数）。

## 核心个股（未做，方向已定）
fupanhui 的 `fact_core_stock_daily` 50 只是编辑池。我们的标准建议：主线题材成员 × 知识库年报暴露度（业务占比/关系图，判「正宗」）× 人气
（涨停/连板/成交额/新高）。年报暴露度在知识库仓（entities/relations），需要另一单接入。

## 读数
- 09-07 `check_daily_review_data --phase data --plan local` → COMPLETE（含 mainline 三表、强度字段）。
- 双轨 08-13～09-02：十族 PASS；编辑层：强度 1.8% / 状态 14/15 / 量能 15/15。
- 门禁：ruff 绿；pytest 见 PR；`registry-check` 通过。

## 验收标准
1. `compute-market-stage-local --trade-date 2026-09-07 --dry-run` 输出与库中一致（下跌阶段 第3天 0.549）；`train-market-stage --out /tmp/x.json` 复现 CV ≈43.7%（±1pp，随机初始化为零、确定性）。
2. `SELECT theme_name FROM fact_mainline_theme_daily WHERE trade_date='2026-09-07'` = 农林牧渔/AI算力/电子/通信，source `local:mainline-v1`。
3. `pytest tests/test_market_stage_model.py tests/test_compute_local_stats.py` 13 passed。
4. fupanhui 访问恢复后：`qa_local_vs_fupanhui.py` 编辑层/主线/周期段出对照读数。

## 不在本单
核心个股（知识库年报暴露度）；keywords/summary；名单换源；周期模型升级（非线性/更多标签）。
