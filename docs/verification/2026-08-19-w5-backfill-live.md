# W5 回填 repair sidecar live（2026-08-19）

> 派单：`docs/superpowers/specs/2026-08-19-loop-robustness-r1.md` §W5  
> 代码：`gitea/main@850d6143`（#243 合入后 tip；W5 代码仍是 #237）  
> sidecar：`:8796`，用户 `w5-backfill`，`source_dirty=false`  
> 入口：`POST /api/conversations`（W5 在 `continuous_turn_adapter`，`live_probe ask` 打不到）  
> **生产 `:8792` 未切**，仍 `30f98d73`。  
> **结论：W5 准入路径活性过。验收第 1 条的「回填后 completed」没打满——回填那次 `market_data` 撞 `duplicate_query`。不切 8792。**

## 两发

| | 阈值题（打 W5） | 估值题（对照） |
|---|---|---|
| 题目 | 08-18 成交额是否>1.2 万亿 / 涨家数是否>2500 / 涨停是否>40，并写证伪数字 | 立新能源贵不贵，估值分位 + 证伪数字 |
| run | `run_20260819_222138_157460`（38.4s） | `run_20260819_222242_102781`（76.5s） |
| 题型 | `general_finance_qa` | `valuation_estimate` |
| `backfill_turns` | **1** | 0 |
| `repair_attempts` / `cycles` | 0 / 0 | 1 / 1 |
| `verified_status` | `partial` | `completed` |
| `judge_status` | `repaired` | `repaired` |
| `ju` | 0 | 0 |

## 阈值题：W5 走了哪几步

1. 首轮草稿写出具体数字（成交 24006.36 亿、涨家 2121、涨停 79），收据带 `numeric_unsupported`。数字来自 `finance_query`，`prime_quote` 因类型不合法被剥。
2. 首轮已调 `market_data`，返回「结构化数据仅到 2026-08-18，早于所需 2026-08-19」，`evidence=[]`。今天日历是 08-19，题型不是 dated 盘面题，工具按「今天」要数。
3. `_issue_backfill_plan` 命中 → `admit_backfill_repair`：`missing_evidence_modes=["market_data"]`，`remaining_calls=1`，`remaining_seconds=22.5`（= 90×25%）。
4. repair 相再调 `market_data arguments={}` → **`duplicate_query`**，没补到新证据。
5. 终态仍 `partial`。公开稿有数字，但结构层仍缺 `market_data`/`mainline_context` 能力证据。

单测锁的是「缺数字锚时先补一次 market_data，而不是立刻让判官删句」。live 证明准入和预算帽在场；**没证明补证能越过 duplicate 闸放到 completed**。

## 估值题：不是 W5

走的是缺口进度 repair（`missing_answer_elements` 含 `financial_business_anchor` 等，`remaining_calls=0`，秒数 40，不是 25% 帽）。首轮 `financial_data` + `market_data` 已 success，结构层 `completed`。W5 的 `backfill_turns` 仍为 0。不要把这发写成财务锚回填结案。

## 判定

| 条 | 规格 | 读数 | 结果 |
|---|---|---|---|
| 1a | 首轮 `numeric_unsupported` | 收据 issues 有该 code | **过** |
| 1b | 回填 turn 只开对应 capability | repair_goal 只有 `market_data`，1 call / 22.5s | **过** |
| 1c | 拉到数据 → `completed` | 回填 `duplicate_query`；终态 `partial` | **未过** |
| 2–3 | 新增句子 fail closed / 超预算放弃 | 本发不是这两条的反例构造 | 单测仍锁 |
| 生产 | 不切 8792 | 仍 `30f98d73` | 过 |

## 下一步（代码，另开分支）

回填 turn 若与首轮打出**同一条** `market_data {}`，会被 duplicate 闸直接打掉。尤其是首轮已经空返回（as_of 错日）时，补证需要带日期的第二次查询，或空结果不应占 duplicate key。不要把 `track_*` 并进 `BACKFILL_TRIGGER_CODES`。

## 产物

`~/.finance-runtime/live-probe-traceability/w5-850d6143/`
sidecar 已停。
