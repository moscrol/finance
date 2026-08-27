# Handoff：复盘会公开资产接通消费——四张零消费表进语义层，两个死 JSON 归档裁决

日期：2026-08-18
派单人：主 agent（2026-08-18 数据资产审计批次）
先例：`fact_dragon_*` 三表 2026-08-13 接入语义层（`finance_query.py` 注释原话「复盘会公开资产……此前入库但 agent 够不着」）——本单是同一动作的续集。

## 背景与已核实事实（派单前实测，收据见审计对话）

2026-08-18 数据资产审计逐通道实测发现一批「写端活着、读端不存在」的资产。写管线每天在花钱，agent 一个字都吃不到：

| 资产 | 规模/新鲜度 | 非测试消费方 | 判决 |
|---|---|---|---|
| `fact_auction_stock_daily` | 9107 行，2026-01-16~08-14，竞价面板（昨日涨停/1-5日断板梯队，auction_pct/auction_amount/limit_seq/leader_plate） | 0 | **接语义层** |
| `fact_research_report_catalog` | 458 行（industry 407 + report 51），到 08-13，含 sector_tags/concept_tags/stocks | 0 | **接语义层** |
| `fact_event_daily` | 2455 行，其中 `is_future=true` 13 条、最新 08-17（fupanhui public-api 来源） | 0 | **接语义层** |
| `feature_stock_technical_daily` | 200 万行，每日更新到 08-17（close/ma26/std26/up_value/deviation_pct） | 0 | **接语义层** |
| `relations/catalyst_calendar.json` | 76 events，updated 2026-07-28 停更 | 0 | **不接，归档裁决** |
| `relations/fupanhui_panorama.json` | 2 panoramas，2026-06-22 一次性抽取 | 0 | **不接，归档裁决** |

判决理由：

- 四张表都是「分析师结构化查询」形态（谁在竞价抢筹 / 最近研报覆盖 / 事件催化 / 个股乖离），dragon 先例证明语义层是最薄的接法：注册 `_DATASETS` 即 agent 可查，不动检索与 prompt。
- 催化消费**不接** `catalyst_calendar.json`：`fact_event_daily` 的 `is_future=true` 事件（最新 08-17）就是它的上位替代，07-28 的 JSON 接进来反而喂旧催化。
- `fupanhui_panorama` 已被 `fact_mainline_*`（9 个消费文件）取代，无接线价值。
- 空表（`fact_top_gainers`、`fact_high_volume_gainers`、`fact_stock_technical_snapshot`、`config_*` 四张）无数据可接，不在本单，写端处置另行裁决。

## 实施边界

只动：

- `intelligence/services/finance_query.py`：`_DATASETS` 注册 4 个 dataset（照 dragon 三表的写法）
- 对应语义层测试文件
- `docs/adr/`：一条简短 ADR 记录「接四表、archive 两 JSON」判决
- `docs/handoffs/inflight/main.md`：登记

不动：

- 检索 top-8 / 排序 / prompt / #146 闸 / #165 stale 旁路
- 数据根解析（#164 另一张单，别搅进来）
- 写端管线（auction 停 08-14、catalog 停 08-13、ops 管线 08-13 停摆——断流排查是另一张单）
- `catalyst_calendar` / `fupanhui_panorama` 文件本体（归档动作留给用户裁决，本单只在 ADR 记判决）

## Dataset 规格草案（列名以 `describe` 实测为准，可微调）

1. `auction_stock_daily`「竞价表现（昨日涨停/断板梯队）」
   - time_field：`trade_date`
   - dimensions：trade_date / panel_key（label 用 panel_label 语义）/ stock_code(stock_ts_code) / stock_name / leader_plate / limit_seq
   - metrics：auction_pct（竞价涨幅）/ pct_chg（收盘涨跌）/ auction_amount（竞价额）/ day_amount（全天额）
2. `research_report_catalog`「卖方/产业研报目录」
   - time_field：`report_date`
   - dimensions：report_date / report_type / is_hot / title / sector_tags / concept_tags
   - metrics：stock_count
   - ⚠️ sector_tags/concept_tags 是 JSON 字符串列：过滤实现避开 finance_query `contains` 的 ESCAPE 子句已知 bug（台账 FINANCEWORKS-2，backlog）。遇到就立案，别顺手改过滤器实现。
3. `event_daily`「事件/催化日历（含未来事件）」
   - time_field：`event_date`
   - dimensions：event_date / title / event_type / importance / is_future / sectors
   - metrics：importance（max）
   - label 写明「`is_future=true` 即未来催化」，让 agent 从 schema 就懂这是催化入口
4. `stock_technical_daily`「个股均线通道/乖离」
   - time_field：`trade_date`
   - dimensions：trade_date / stock_code(stock_ts_code) / stock_name
   - metrics：close / ma26 / std26 / up_value / deviation_pct
   - 200 万行：limit 与 time_range 约束必须生效（沿用语义层现有 min(limit,25) 逻辑），测试里压一条「无 time_range 也不全表扫」

## 测试要求（先红后绿）

每个 dataset 至少四条：

1. `run()` 返回行（fixture 库或真库只读）
2. 维度过滤一条（auction：panel_key='zt'；catalog：report_type；event：is_future=true；technical：stock_code）
3. limit/time_range 约束生效（technical 必须有）
4. `FINANCE_QUERY_PARAMETERS` 参数面里新 dataset 可见（agent 够得着的前提）

## live 验证（合并后，#152 sidecar 探针，不碰 8792）

「够得着」≠「想得到用」。各问一发，验 trace 里 finance_query 真被调且 dataset 命中：

1. 「今天竞价哪些昨日涨停在抢筹」→ auction_stock_daily
2. 「最近有哪些算力/AI 方向的研报」→ research_report_catalog
3. 「近期有什么值得盯的事件催化」→ event_daily（is_future）

若 agent 没调工具，把现象记进验收报告（那是工具描述/prompt 引导问题，另行裁决，本单不硬修）。

## 红线

- 不铸 EvidenceAtom、不切 8792、不改 launcher
- 数据停更不在本单修（拉新数据 ≠ 接通消费）
- 别动 #164（数据根）与 #165（stale 旁路）的实现
- ESCAPE bug 不顺手修（FINANCEWORKS-2 立案处理）

## 验收标准

1. 四件套绿（ruff / pytest / webapp lint+typecheck+test+build）
2. 四个 dataset 语义层测试绿 + 参数面可见
3. live 三问收据（trace 里 finance_query 调用与 dataset 名），路径写进交接说明
4. ADR + inflight 登记
5. PR mergeable

## skill 与工具建议

skill：leila-runtime + tdd。工具：git worktree、pytest、live_probe（#152 sidecar）、Gitea API。
