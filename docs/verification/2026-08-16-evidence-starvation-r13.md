# R-13 宽题取证饿死：T2 GLM 窗已齐，T3 未切开（未结案）

- 日期：2026-08-16
- 案号：`R-20260816-13`（判定）/ `R-20260816-14`（绊线）
- 状态：**T1 完成；T2 完成（GLM Coding Plan）；T3 未切开；T4 未做**
- 被审 runtime：8795 `16f2cd47` dirty=false；8792 全程 `6cd0756e` 未切
- 机器产物：`docs/verification/2026-08-16-r13-t2-score.json`

## 0. 预注册判据（逐字，未改）

> 8795 含工具批埋点 tip 读数；**deep 自然完成值合计（分支+取证+合成+核验）>
> standard 总窗 → H-a**；**evidence_search 自然时长小（单发 ≤10s）且失败仅出现在
> dispatch 时 `stage_timeout_granted`≤0 或 slot 耗尽的槽 → H-c**。缺字段不得结案。

R-10 看 judge 首轮 asked；本案看工具批派发五元组。两判据同侧车、不互混。
R-11 已自结，本案不代结。R-15 不并案。

## 1. T1 埋点

- PR **#100** 合 `16f2cd47`。
- 五元组进 `tool_request`/`tool_error`，不进模型消息。
- #100 无 T / 批窗 / slot / 档位上调。R-14 未触线。

## 2. T2 重放

### 2.1 第一窗（中转 5xx，作废）

terra / `x.ailzd.com`。W01×3 + 孤儿 W04 首轮 HTTP 5xx，零工具。已挪
`~/.finance-runtime/r13-starve-20260816/runs/blocked-503/`。
本机直探：`/v1/models`=200，chat 仍 5xx。官方 GLM `paas/v4` 同 key 是 429。

### 2.2 第二窗（本收据主窗）

用户授权改走 **GLM-5.2 Coding Plan**（Keychain `finance-workbench-glm`，
`open.bigmodel.cn/api/coding/paas/v4`）。自然时长是 GLM，不是 terra。

- 8795 pid **73668**，`16f2cd47` dirty=false，ready。未动 T / 批窗 / slot / 档位。
  `ASK_TOOL_BATCH_TIMEOUT=60` 是侧车旧值，本窗未新开 PR。
- user `r13-starve-0816`，11 槽 22:24–22:49 全跑完。
- 11/11 五元组齐（`clock_missing=[]`）。11/11 `degraded`。
- **0 次 `evidence_search` 请求**（合同允许，模型没发）。
- **0 次 judge 调用**。本窗不得偷结 R-10。
- **D01 两槽合同 `research_tier=standard`**。题面有「深挖」，但
  `theme_analysis` 走 theme owner，不经过
  `_build_generic_research_contract` 的「深挖→deep」升档。
  **预注册要的 deep 自然合计，本窗没有。**

| slot | run_id | 合同档 | asked | granted | 墙钟 s | 闸 |
|---|---|---|---|---|---|---|
| W01 r1 | `run_20260816_222458_854118` | standard | 30 | 16.9 | 116.4 | ok 3 / time-other 1 |
| W01 r2 | `run_20260816_222655_447536` | standard | 30 | 20.2 | 125.3 | ok 3 / time-other 1 |
| W01 r3 | `run_20260816_222901_005274` | standard | 30 | 15.1 | 148.6 | ok 3 / time-other 1 / slot 2 |
| W04 r1 | `run_20260816_223129_686497` | standard | 30 | 19.9 / 10.5 | 130.7 | ok 5 / time-other 1 |
| W05 r1 | `run_20260816_223340_523601` | standard | 30 | 22.1 / 13.7 | 107.0 | ok 4 |
| N01 r1 | `run_20260816_223527_625207` | standard | 30 | 17.3 | 127.8 | ok 3 |
| N02 r1 | `run_20260816_223735_473986` | standard | 30 | 20.1 | 171.4 | ok 4 / slot 1 |
| D01 r1 | `run_20260816_224026_949253` | **standard** | 30 | 12.2 | 129.7 | ok 3 / time-other 1 / slot 1 |
| D01 r2 | `run_20260816_224236_801336` | **standard** | 30 | 16.3 | 173.1 | ok 4 / slot 1 |
| R11L03 | `run_20260816_224530_026545` | standard | 30 | 23.8 / 11.3 | 106.0 | ok 4 |
| R11L05 | `run_20260816_224716_151184` | standard | 30 | 16.8 | 160.7 | ok 1 / time-other 1 |

`asked=30` 的来源（不是本窗调参）：`theme_analysis` / 多数题
`synthesis_reserve_for_task` = `min(75, _BALANCED_SYNTHESIS_RESERVE=60)` = 60；
standard 总窗 90 → `derive_stage_caps.tool_batch_seconds` = 30。
`ASK_TOOL_BATCH_TIMEOUT=60` 只能降低、抬不上去。派发时思考已吃 6–18s，
`stage_timeout_granted` 落到 10–24s。

`kb_search` 成功自然值（本窗）：10.1 / 13.5 / 14.0s。
`kb_search` `tool_timeout` 六次：全部 `granted` 10.5–20.2s（>0），
`queued_ms` 0.0–5.9。是时间闸的「窗内跑不够」，不是 732198 那种
`granted≤0` 零执行。

## 3. T3 判定

**未切开。** 部分验证不得写 `confirmed`。不得开 T4 调参。

| 假设 | 结果 | 为什么 |
|---|---|---|
| H-a（deep 四段自然合计 > 90s） | **INCONCLUSIVE** | D01 两槽合同档是 standard，不是 deep。没有预注册要的 deep 四段合计。墙钟 106–173s 不能代替。 |
| H-c（`evidence_search` ≤10s 且失败仅 grant≤0 / slot 耗尽） | **NOT MET** | 本窗 0 次 `evidence_search`，没有该工具的自然完成值。不得把 H-c 写成 confirmed 或 refuted。 |
| 旁证 | 不结案 | 相邻产物 `evidence_search` 成功 5 次 32–59s、0 次 ≤10s；本窗 `kb_search` 成功已 10–14s。预测 H-c 的 ≤10s 很难，但仍缺本 tip 的 `evidence_search` 五元组。 |

R-11 移交：L03 重放是 `market_data`/`mainline_context`/`finance_query` 成功，
不是饿死形。L05 重放 `kb_search` timeout（granted 16.8）+ `web_search` 12.2s。
R-11 已 Closed，不回写。

## 4. T4 处置

未做。禁止把本窗写成调 T / 批窗 / slot / 档位的许可。

若后续切开 H-a，交接原文的架构菜单仍在：预计算证据包 / 异步 track /
宽题显式进 deep。最后一项本窗已见反证——题面「深挖」没有把
`theme_analysis` 升到 deep。路由/档位升格要用户拍板。

## 5. 身份

| 端口 | revision | dirty | 备注 |
|---|---|---|---|
| 8795 | `16f2cd47` | false | pid 73668；GLM-5.2 Coding Plan |
| 8792 | `6cd0756e` | false | 全程未切；pid 87031 |

## 6. 下一步

1. 要结 H-a：必须有真正 `research_tier=deep` 的同题自然四段。本窗 D01 不够。
2. 要结 H-c：必须有 `evidence_search` 实际发出的重放（terra 恢复，或强制该工具的夹具臂）。
3. 检阅方复核「T2 已齐、T3 未切开、D01 未升档」是否成立。
