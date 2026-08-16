# R-13 宽题取证饿死：T1/T2 已齐，T3 未切开（未结案）

- 日期：2026-08-16
- 案号：`R-20260816-13`（判定）/ `R-20260816-14`（绊线）
- 状态：**T1 完成；T2 完成（GLM Coding Plan）；T3 未切开 H-a/H-c；T4 未做**
- 被审 runtime：8795 `16f2cd47` dirty=false；8792 全程 `6cd0756e` 未切
- 机器产物：`docs/verification/2026-08-16-r13-t2-score.json`

## 0. 预注册判据（逐字，未改）

> 8795 含工具批埋点 tip 读数；**deep 自然完成值合计（分支+取证+合成+核验）>
> standard 总窗 → H-a**；**evidence_search 自然时长小（单发 ≤10s）且失败仅出现在
> dispatch 时 `stage_timeout_granted`≤0 或 slot 耗尽的槽 → H-c**。缺字段不得结案。

R-10 看 judge 首轮 asked；本案看工具批派发五元组。两判据同侧车、不互混。
R-11 已自结，本案不代结、不回写其行。R-15 不并案。

## 1. T1 埋点

- PR **#100** 合 `16f2cd47`。
- 五元组：`batch_grant_asked` / `stage_timeout_granted` /
  `episode_remaining_at_dispatch` / `remaining_slots_at_dispatch` /
  `turn_elapsed_at_dispatch`，进 `tool_request`/`tool_error`，不进模型消息。
- #100 diff **无** `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot /
  档位上调。R-14 未触线，绊线常在。

## 2. T2 重放

### 2.1 第一窗（中转 5xx，作废）

21:57–21:58，terra / ailzd。W01×3 + 孤儿 W04 均首轮 HTTP 5xx，零 `tool_request`。
已挪到 `runs/blocked-503/`。本机直探中转 chat 仍 502（`/models`=200）。

### 2.2 第二窗（本收据主窗）

- 8795 仍 `16f2cd47` dirty=false，pid **73668**，`--port 8795`。
- 中转 chat 仍 5xx，侧车改走 **GLM-5.2 Coding Plan**
  （`open.bigmodel.cn` coding paas）。自然时长是 GLM，不是 terra。
- 启动器存量：`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS=300`、
  `ASK_TOOL_BATCH_TIMEOUT=60`。这是侧车 generated launcher 的旧值，**不是**本窗
  新 PR，不触发 R-14；但是读超时的混杂项，须写明。
- 计划 11 槽全跑完（22:24–22:49）。user `r13-starve-0816`。
- 11/11 `clock_missing=[]`：五元组已落盘。`score_replay.py` 因缺
  `evidence_search` 自然完成值且缺 branch/judge 秒数，桶全是 `incomplete`。
- 11/11 `terminal_outcome=degraded`。**0 次 `evidence_search` 请求**
  （合同里有该工具，模型没发）。judge 全程未调用（`judge_status=None`，
  `timeout_asked=None`）——本窗不得偷结 R-10。

| slot | run_id | gates | episode_s | compose_s | judge |
|---|---|---|---|---|---|
| `r13_W01_r1` | `run_20260816_222458_854118` | ok 3 / time-other 1 | 115.6 | 42.6 | None |
| `r13_W01_r2` | `run_20260816_222655_447536` | ok 3 / time-other 1 | 74.3 | 37.1 | None |
| `r13_W01_r3` | `run_20260816_222901_005274` | ok 3 / time-other 1 / slot 2 | 97.5 | 56.2 | None |
| `r13_W04_r1` | `run_20260816_223129_686497` | ok 5 / time-other 1 | 79.7 | 43.9 | None |
| `r13_W05_r1` | `run_20260816_223340_523601` | ok 4 | 56.0 | 13.9 | None |
| `r13_N01_r1` | `run_20260816_223527_625207` | ok 3 | 77.2 | 47.9 | None |
| `r13_N02_r1` | `run_20260816_223735_473986` | ok 4 / slot 1 | 120.5 | 52.2 | None |
| `r13_D01_r1` | `run_20260816_224026_949253` | ok 3 / time-other 1 / slot 1 | 129.3 | 51.1 | None |
| `r13_D01_r2` | `run_20260816_224236_801336` | ok 4 / slot 1 | 122.3 | 59.5 | None |
| `r13_R11L03_r1` | `run_20260816_224530_026545` | ok 4 | 55.4 | 11.5 | None |
| `r13_R11L05_r1` | `run_20260816_224716_151184` | ok 1 / time-other 1 | 109.7 | 44.9 | None |

`tool_request` 计数：`finance_query` 17、`kb_search` 9、`news_search` 6、
`memory_lookup` 6、`graph_lookup` 4、`web_search` 2、`market_data` 2、
`mainline_context` 2、`evidence_search` **0**。

`kb_search` `tool_timeout` 六次，全部 `stage_timeout_granted` 10.5–20.2s（>0）、
`remaining_slots` 2–6、`queued_ms` 0.0–5.9。与 732198 同形的**零执行时间闸**，
但工具是 `kb_search`，不是预注册点名的 `evidence_search`。

## 3. T3 判定

**未切开。** 部分验证不得写 `confirmed`。不得开 T4。

| 假设 | 结果 | 为什么 |
|---|---|---|
| H-a（deep 四段自然合计 > 90s） | **INCONCLUSIVE** | `branch_s` 与 `judge_asked_s` 均为 null。能加的 `tool_s+compose_s`：D01 r1 51s、r2 59s，都 **<90**。deep 墙钟 122–129s >90，但墙钟不是预注册的四段合计。 |
| H-c（`evidence_search` 单发 ≤10s 且失败仅 grant≤0 / slot 耗尽） | **NOT MET** | 本窗 0 次 `evidence_search`，没有自然完成值。缺字段不得把 H-c 写成 confirmed 或 refuted。 |
| 旁证：`kb_search` 超时 | 不代 H-c | 六次超时都是 grant>0 的 `time-other`，说明「失败仅 grant≤0」对这个工具不成立；预注册点名的是 `evidence_search`，不升格。 |

serial-phase 旁证仍在：相邻产物里 `evidence_search` 成功 5 次均 32–59s，0 次 ≤10s。
没有本窗的 `evidence_search` 五元组，旁证仍不能结案。

R-11 移交槽（L03/L05 题面重放）有工具批、无 `evidence_search`、无饿死形。
R-11 已 Closed，不回写。

## 4. T4 处置

未做。禁止把本窗写成调 T / 批窗 / slot / 档位的许可。

## 5. 身份

| 端口 | revision | dirty | 备注 |
|---|---|---|---|
| 8795 | `16f2cd47` | false | T1 tip；pid 73668；GLM-5.2 Coding Plan |
| 8792 | `6cd0756e` | false | 全程未切 |

## 6. 下一步

1. 要结 H-c：必须有 `evidence_search` 实际发出的重放（terra 恢复后，或强制该工具的夹具臂）。本窗 GLM 自选工具不够。
2. 要结 H-a：deep 臂要落到四段自然秒（branch / 取证 / 合成 / 核验），不能用墙钟代替。
3. R-10 另开 judge 有稿窗；本窗 0 次 judge。
4. 检阅方复核「T2 已齐、T3 未切开」是否成立。
