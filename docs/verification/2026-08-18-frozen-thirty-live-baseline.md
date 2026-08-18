# 冻结 30 题 live 基线（2026-08-18）

这是答案质量的**回归对比锚**，不是绝对质量宣称。后续数据根 / 死资产 / prompt 大改前后用同参再跑一发对比。

## 怎么跑的

- sidecar `:8796`，代码树 `4a3bb31366c2`（开跑时 8792 等效 revision），`WORKBENCH_GROUNDED_PRESENTER=1`，`WORKBENCH_PERSIST_LLM_CONTEXT=1`
- 不碰 8792 的 ask 入口。驱动：`python scripts/run_frozen_thirty_live.py`
- 题面一字不改。`POST /api/runs` 没有 `as_of` 字段，fixture 的 as_of **只进元数据、不注入题面**
- 每题单跑。判分只读 `finance_answer_rubric`（确定性，无 LLM）
- 先决冒烟：`A1-market-overview` source_date=`2026-08-17`，无「本轮没有连接本地市场数据」，无 07-15 冻

## 读数

| 项 | 值 |
|---|---|
| 题数 | 30 / 30 有三件套（answer.md / llm_context.json / trace.jsonl） |
| infra_fail | 0（无重跑） |
| quality_pass / quality_fail | 23 / 7 |
| rubric 档 | A 23 · B 2 · F 5 |
| 盘面依赖子集（21） | pass 14 / fail 7 |
| 非盘面子（9） | pass 9 / fail 0 |
| 墙钟 | 83.2 min（median 183s，min 39.5，max 227.4） |
| 答案模型 | zhipu / glm-5.2（sidecar 生产合成） |
| 判分 | 确定性 rubric → 异源，无同源 confound |
| 数据根 | 30 题 `no_local_market=false`；29 题 `source_date=2026-08-17` |

机读：`intelligence/eval/measurements/2026-08-18-frozen-thirty-live-4a3bb313.json`  
原件：`~/.finance-runtime/frozen-thirty-live-20260818/`

## 失败分类（原样入账，未挑跑）

全是 `quality_fail`，不是探针挂。

| id | 档 | 秒 | 备注 |
|---|---|---:|---|
| index-rebound-space | F 12/100 | 39.5 | 短答，缺本地/分层标记 |
| sci-tech-support | F 12/100 | 57.3 | 同上（科创50 支撑） |
| A7-mainline | F 26/70 | 189.4 | `llm_unavailable_template_answer`，无 source_date |
| current-mainline | F 30/100 | 96.7 | 证据标记 3/8，被密度闸封顶 |
| A8-market-stage | F 34/100 | 62.4 | 同上 |
| A2-next-day-call | B 118/150 | 97.6 | 前瞻组：策略映射 / 假设条数 |
| C7-temporal-leakage | B 114/150 | 91.0 | 前瞻组：四源合议 / 策略映射 |

7 个 fail **全部落在盘面依赖子集**。知识/方法/估值 9 题全 A。这是尺子形状（结构词 + 证据标记），不是「盘面通道又断了」。

## 必须自陈的局限

1. **题集非独立出题**（08-10 章审：题目我出、判分我判；用户独立出题复测 8/10）。本页只作回归锚。独立出题人仍是 open item。
2. **单跑**。方差治理（`10_knowledge/eval-harness-variance-governance.md`）：单次运行读不出「这一刀有没有用」；先确定性判据。本单不做多跑。
3. **as_of 未注入**。A1 题面写 2026-07-23，产品路径用最新主线快照（08-17），模型自陈「没有 07-23 当日直接记录」。`fact_market_daily` 其实有 07-23 行——这是候选/日报 asof，不是 #167 接线残废。
4. **覆盖面偏知识/逻辑**；盘面能力看上面 21 题子集，勿把 23/30 当成盘面能力分。
5. **rubric 未做历史盲测**，advisory，不得当交易闸。
6. 跑窗内 8792 被**别人**从 `4a3bb313`/pid 67921 切到 `3af5c81f`/pid 70247。本单 sidecar 全程钉在 `4a3bb313:8796`，未 bootout 8792。

## 同参（下次对比必须对齐）

- 题集：`intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json`（不改字）
- sidecar + grounded=1 + persist llm_context
- 判分：`finance_answer_rubric.score_answer`，不改尺子
- 单跑；infra_fail 才允许重跑一次并记账
- 结果不好看也入账

## 附录：逐题收据

根目录 `~/.finance-runtime/frozen-thirty-live-20260818/cases/<id>/`，每题 `answer.md` + `llm_context.json` + `trace.jsonl` + `case.json`。

| id | run_id | 档 | 秒 | 盘面 |
|---|---|---|---:|---|
| rebound-duration | run_20260818_111743_398643 | A 100/100 | 215.8 | 是 |
| index-rebound-space | run_20260818_112119_189208 | F 12/100 | 39.5 | 是 |
| ruihuatai-valuation | run_20260818_112158_678275 | A 96/100 | 204.6 | 否 |
| weekly-market-cause | run_20260818_112523_321904 | A 98/100 | 189.3 | 是 |
| current-mainline | run_20260818_112832_622158 | F 30/100 | 96.7 | 是 |
| theme-comparison | run_20260818_113009_372179 | A 100/100 | 227.4 | 否 |
| counterfactual-mainline | run_20260818_113356_741032 | A 99/100 | 174.7 | 否 |
| unfamiliar-methodology | run_20260818_113651_422677 | A 98/100 | 190.3 | 否 |
| contextual-follow-up | run_20260818_114001_758893 | A 100/100 | 187.5 | 否 |
| A1-market-overview | run_20260818_111400_478919 | A 98/100 | 194.7 | 是 |
| A4-dual-red | run_20260818_114309_250498 | A 100/100 | 178.9 | 是 |
| A5-limit-heat | run_20260818_114608_166579 | A 99/100 | 185.9 | 是 |
| A6-limit-advance-ladder | run_20260818_114914_073502 | A 88/100 | 194.8 | 是 |
| A8-market-stage | run_20260818_115228_862807 | F 34/100 | 62.4 | 是 |
| C2-non-trading-day | run_20260818_115331_291176 | A 99/100 | 182.8 | 是 |
| C1-future-date-no-data | run_20260818_115634_071970 | A 100/100 | 178.3 | 是 |
| sci-tech-support | run_20260818_115932_360670 | F 12/100 | 57.3 | 是 |
| A2-next-day-call | run_20260818_120029_667594 | B 118/150 | 97.6 | 是 |
| C6-strict-definition | run_20260818_120207_252576 | A 99/100 | 183.3 | 是 |
| A7-mainline | run_20260818_120510_522567 | F 26/70 | 189.4 | 是 |
| A3-stock-deep-dive | run_20260818_120819_969089 | A 97/100 | 197.7 | 否 |
| B4-fermentation-trace | run_20260818_121137_647693 | A 94/100 | 196.9 | 是 |
| B7-volume-sentiment-evolution | run_20260818_121454_570365 | A 100/100 | 180.6 | 是 |
| B8-valuation-band | run_20260818_121755_178208 | A 94/100 | 207.7 | 否 |
| B5-cross-table-intersection | run_20260818_122122_931192 | A 96/100 | 181.1 | 是 |
| C7-temporal-leakage | run_20260818_122424_019654 | B 114/150 | 91.0 | 是 |
| C9-citation-integrity | run_20260818_122554_996024 | A 94/100 | 193.2 | 否 |
| A10-new-high-structure | run_20260818_122908_225569 | A 96/100 | 174.4 | 是 |
| A9-sentiment-contradiction | run_20260818_123202_605194 | A 100/100 | 167.8 | 是 |
| open-event-fed | run_20260818_123450_443759 | A 100/100 | 170.5 | 否 |
