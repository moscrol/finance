# 四张零消费表进语义层，两个死 JSON 归档不接

2026-08-18 数据资产审计后拍板：写端活着、读端不存在的四张表走 `finance_query._DATASETS` 注册（照 2026-08-13 龙虎榜先例）；`catalyst_calendar.json` 与 `fupanhui_panorama.json` 不接线。详见执行单 `docs/handoffs/2026-08-18-dead-assets-consumption-wiring.md`。

---

## 实测（2026-08-18 审计）

| 资产 | 规模/新鲜度 | 非测试消费方 |
|---|---|---|
| `fact_auction_stock_daily` | 9107 行，至 08-14 | 0 |
| `fact_research_report_catalog` | 458 行，至 08-13 | 0 |
| `fact_event_daily` | 2455 行，`is_future=true` 13 条最新 08-17 | 0 |
| `feature_stock_technical_daily` | 200 万行，日更至 08-17 | 0 |
| `relations/catalyst_calendar.json` | 76 events，07-28 停更 | 0 |
| `relations/fupanhui_panorama.json` | 2 panoramas，06-22 一次性 | 0 |

## 考虑过的替代

| 选项 | 为何不选 |
|---|---|
| 接 `catalyst_calendar.json` | 07-28 停更；`fact_event_daily` 的未来事件已是上位替代，接 JSON 会喂旧催化。 |
| 接 `fupanhui_panorama.json` | 已被 `fact_mainline_*`（9 个消费文件）取代。 |
| 改检索 / prompt / 铸 EvidenceAtom | 龙虎榜先例证明注册 `_DATASETS` 即够得着；本单只接通，不教模型「想得到用」。 |
| 顺手修 contains ESCAPE（FINANCEWORKS-2） | 已知 backlog，研报 JSON 标签列用 `report_type` 过滤绕开，不改过滤器。 |

## 后果

- 四个 dataset：`auction_stock_daily` / `research_report_catalog` / `event_daily` / `stock_technical_daily`。工具枚举从 `_DATASETS` 派生，注册即进参数面。
- `event_daily.importance` 只挂 metric（max）。规格草案同时写进 dim/metric，引擎 `selected fields must be unique`，过滤走 filters。
- 研报 `sector_tags` / `concept_tags` 可展示，过滤请用 `report_type` / `title`，不对 JSON 列走 `contains`。
- 两个 JSON 文件本体不动，归档动作留给用户裁决。
- 不铸 EvidenceAtom，不切 8792，不改 launcher，不动检索 top-8 / prompt / #146 闸 / #165 旁路 / #164 数据根。

## live 三问（2026-08-18，#152 sidecar，不硬修）

`POST /api/runs` ask 车道三发均 **0** 次 `finance_query`。路由分别是 `market_forecast` / `theme_analysis` / `general_finance_qa`，吃盘面总览与 wiki，没点到新注册的四表。语义层测试已证明够得着；想得到用另开单。详见 `docs/verification/2026-08-18-dead-assets-live.md`。
