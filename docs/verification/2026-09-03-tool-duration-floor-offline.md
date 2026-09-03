# 离线量：工具调用要多长——预算 P1「工具有地板」那一半的数（2026-09-03）

零 LLM，零生产改动。脚本：`scripts/offline_tool_duration_floor.py`。数字：
`docs/verification/2026-09-03-tool-duration-floor-offline.json`。

**结论：工具侧没有「一个地板」可拍。** 生产 656 次成功调用 p50 = 0.067s、p95 = 6.1s；11 个工具里 9 个
p95 < 9s（结构化本地工具全部 < 0.3s，`news_search` 8.7s）。尾巴集中在两条 RAG 工具：`kb_search` 成功 30 次 /
真超时 57 次（成功率 34%），`evidence_search` 成功 3 次 / 真超时 66 次（成功率 4%），它们被切时的实授中位
23.1s / 19.1s。**P1 的「工具有地板」对 9 个工具没意义、对 2 个工具在 90s 档下满足不了**——那两条要的是 25–40s，
加上合成侧 25–35s（`2026-09-02-finalize-duration-offline.md`），90s 档一次都装不下。所以工具侧真正要拍的不是地板
数字，是 RAG 路径怎么处置（见「对 P1 的含义」）。公式仍不动。

## 为什么要量

`inflight/main.md` 09-03 03:20 行：「预算 P1 仍待拍（reserve 不可侵犯 vs 工具有地板；**工具侧地板未量**）」。
合成侧已有数（生产成功写作 P95 = 26.9s，20s 地板证伪），工具侧是空白。半边数据拍出来的决定日后要重拍。

## 怎么量 [代码路径]

- 事件：`tool_result` / `tool_error`（`agent_episode.py` `_append_tool_error` / `consume`），字段
  `elapsed_ms`（`episode_tool_batch._ToolTiming`，**工作线程自测**，不是事件 `at` 差——finalize 那份脚本已注明
  `at` 差不能当工具时长）、`stage_timeout_granted`（派发点实授，`ToolDispatchClock.to_payload`）。
- 派发前就被拒的调用没有 `elapsed_ms`，单独计数，不写 0。
- 零授权假超时 = `tool_timeout` ∧ `stage_timeout_granted ≤ 0`（P0/P0.1 让模型看见的那一格）；其余 `tool_timeout`
  记「真超时」。派发时钟字段是 08 月下旬才有的，更早的超时 `stage_timeout_granted` 缺席，列为「实授未知」。
- 队列：生产 `linxiaoqi5111` 全期 / 近 14 天 / 全部（含探针与 finance-base-ab）。825 份 episode、2948 条工具事件。

## 读数 [实测]

### 成功调用耗时（生产）

| 队列 | n 成功 | p50 | p90 | p95 | p99 | max | ≤20s 覆盖 | ≤30s 覆盖 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 生产全期 | 656 | 0.067 | 2.54 | **6.11** | 20.4 | 39.7 | 98.8% | 99.7% |
| 生产近 14 天 | 256 | 0.063 | 3.07 | **7.43** | 21.3 | 24.3 | 98.4% | 100% |

成功调用拿到的实授中位 23.2s（p95 25.8，max 30）；吃掉 ≥80% 实授窗还成功的只有 6 次。
**注意成功样本被实授窗右截断**：>23s 的调用大多没机会成功，所以 p95 低估了 RAG 工具的真实需求。

### 按工具（生产全期）

| 工具 | n 成功 | p50 | p95 | 真超时 | 超时时实授 p50 | 零授权 |
|---|---:|---:|---:|---:|---:|---:|
| `finance_query` | 294 | 0.05 | 0.26 | 12（实授未知，旧 schema） | — | 1 |
| `mainline_context` | 97 | 0.05 | 0.16 | 0 | — | 0 |
| `market_data` | 92 | 0.05 | 0.27 | 3 | 30.0 | 2 |
| `news_search` | 64 | 1.53 | 8.68 | 3 | — | 0 |
| `graph_lookup` | 30 | 0.48 | 2.27 | 2 | — | 0 |
| `kb_search` | **30** | 9.45 | 23.3 | **57** | 23.1 | 0 |
| `evidence_lookup` | 18 | 0.14 | 0.29 | 0 | — | 0 |
| `memory_lookup` | 14 | 0.02 | 0.20 | 0 | — | 0 |
| `web_search` | 8 | 2.72 | 4.76 | 2 | 9.3 | 1 |
| `financial_data` | 6 | 0.64 | 2.67 | 0 | — | 0 |
| `evidence_search` | **3** | 32.3 | 39.0 | **66** | 19.1 | 0 |

### 失败形状（生产全期）

| error | n |
|---|---:|
| `tool_timeout` | 149（零授权 4 · 真超时 145 · 其中实授已知 31：`kb_search` 16 / `evidence_search` 12 / `web_search` 2 / `market_data` 1） |
| `tool_budget_exhausted` | 94 |
| `tool_exception` | 26 |
| `invalid_arguments` | 18 |
| `duplicate_query` | 2 |

真超时里实授已知的 31 次：实授 min 2.3 / p50 22.7 / p95 28.0 / max 30.0。若给工具设地板 F，「实授低于 F 的真超时」
数为：F=10 → 5，F=15 → 9，F=20 → 15，F=30 → 30——也就是说把地板抬到 30 也只是让这 30 次多拿几秒，
`kb_search` / `evidence_search` 的成功耗时（9.5s / 32s 中位）说明它们要的不是「多几秒」。

### 与切流探针的对照 [实测 2026-09-03 10:13 / 10:16]

8792 切 `6d4a9df1` 后两发长电探针：首发 `kb_search` / `evidence_search` 在 22.8s 实授内超时 → 第二轮剩 46s →
`finance_query` 两次零授权（`stage_timeout_granted=0`，#534 让模型看见的那一格）→ 无 `fact_*` 口径；复跑
`kb_search` 仍在 20.8s 超时但 `finance_query` 成功 → `fact_stock_daily×4`、数据日 == 库内 max。按上表，
`kb_search` 66% 的超时率是**切前 532cdb07 上就有的生产形状**，不是本批引入；首发作废、只采复跑与 08-28 先例同。

## 对 P1 的含义

- **「工具有地板」这个问法对 9/11 个工具不成立**：它们 p95 < 9s，任何 ≥10s 的实授都够，现行 23s 中位已是 2–100 倍余量。
- **对 `kb_search` / `evidence_search` 成立但满足不了**：成功时 9.5s / 32s 中位，且成功样本被 23s 窗右截断，真实需求
  25–40s。合成侧要 25–35s，两项相加已超 90s 档的全部工具窗。**给它们地板 = 直接把 90s 档的合成 reserve 吃掉**，
  这与「reserve 不可侵犯」正面冲突——P1 两个选项在这两条工具上不可兼得。
- **因此工具侧要拍的是三选一**，不是一个数：
  1. **RAG 路径提速**：`kb_search` 成功时 p50 9.5s、超时后 worker 会被终止重建（`canonical-8792-cutover.md` §4），
     冷启—超时—重建是自我强化的环；先量 worker 冷/热两态的 `kb_search` 耗时再决定（本脚本按 `elapsed_ms` 分不出冷热，
     要加 worker 侧埋点）。
  2. **低余量时不派 RAG 工具**：`episode_remaining_at_dispatch` < 某阈值（如 40s）时把两条 RAG 工具从授权集摘掉或标
     「本轮不可用」，让模型别在必失败的调用上烧 23s。这改的是授权可见性，不改 90/60/30 公式。
  3. **RAG 工具 asked 缩短、快失败**：把它们的 `batch_grant_asked` 从 30 降到 10–12，超时就早失败给别的工具留窗。
     代价是 `kb_search` 成功率会从 34% 再降。
- **零授权假超时**只有 4 次（全在近 14 天），P0/P0.1 已把它对模型说清；不是 P1 的主体。
- **`tool_budget_exhausted` 94 次**是次数闸，不在本单口径内，但比真超时（145）同量级，P1 若只看时间闸会漏掉它。

## 没做

没烧配额。没改 Episode / 8792 / 档位 / 任何 asked 或 reserve。没量 RAG worker 冷热两态（需 worker 侧埋点，另案）。
`finance_query` 的 12 次真超时全是旧 schema（无实授字段），无法判断当时给了多少。
