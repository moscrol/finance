# R-13 宽题取证饿死：T1 落地 / T2 受阻（未结案）

- 日期：2026-08-16
- 案号：`R-20260816-13`（判定）/ `R-20260816-14`（绊线）
- 状态：**T1 完成；T2 未完成；T3 缺字段不得结案；T4 未做**
- 被审 runtime：8795 `16f2cd47` dirty=false；8792 全程 `6cd0756e` 未切

## 0. 预注册判据（逐字，未改）

> 8795 含工具批埋点 tip 读数；**deep 自然完成值合计（分支+取证+合成+核验）>
> standard 总窗 → H-a**；**evidence_search 自然时长小（单发 ≤10s）且失败仅出现在
> dispatch 时 `stage_timeout_granted`≤0 或 slot 耗尽的槽 → H-c**。缺字段不得结案。

R-10 看 judge 首轮 asked；本案看工具批派发五元组。两判据同侧车、不互混。
R-11 已自结（#72 判断槽量具），本案不代结、不回写其行。

## 1. T1 埋点

- PR **#100** 合 `16f2cd47`。
- 五元组：`batch_grant_asked` / `stage_timeout_granted` /
  `episode_remaining_at_dispatch` / `remaining_slots_at_dispatch` /
  `turn_elapsed_at_dispatch`，进 `tool_request`/`tool_error`，不进模型消息。
- judge `passed`/`repaired` 出口补 `_attach_judge_clock` + `judge_attempt_index`。
- 夹具 `intelligence/tests/fixtures/r13-evidence-starvation-732198.json` 钉住
  `run_20260816_205439_732198`：四发 `evidence_search`=`tool_timeout` + 一发
  `finance_query`=`tool_budget_exhausted`。
- 离线：`test_episode_tool_batch` + `test_episode_semantic_verifier` + 相关
  `test_agent_episode` = 197 passed。
- #100 diff **无** `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot /
  档位上调。R-14 未触线，绊线常在。

## 2. T2 重放（受阻）

- 8795 从 `02fa203e`（pid 77042）`ps -p` 确认 `--port 8795` 后杀掉，切到快照
  `~/.finance-runtime/finance-workspace-16f2cd47`。现 pid **53843**，
  readiness=`ready`，`source_revision=16f2cd47…`，`source_dirty=false`。
- 计划：医药宽题 ×3 + 同形宽题 ×2 + 窄题 ×2 + 深挖原题 ×2 + R-11 L03/L05 各 1。
  目录 `~/.finance-runtime/r13-starve-20260816/`，user `r13-starve-0816`。
- 实跑：W01 r1–r3 三槽有 smoke JSON；W04 在停 replay 前已落盘
  `run_20260816_215829_340473`（无对应 smoke）。四槽均为首轮
  `LLM 调用 HTTP 503`，**零 `tool_request`，五元组未落盘。**
- 已停 replay（只杀 replay pid，8795/8792 未动）。侧车保持，供中转恢复后重跑。
- 本机直探中转（不经 8795，不打生产）：`GET /v1/models` = 200；
  `POST /v1/chat/completions`（`gpt-5.6-terra`，max_tokens=8）连续 4 次 =
  503 / 502 / 503 / 503，1.1–1.4s。不是侧车配置问题。

| slot | run_id | outcome | tools | 首错 |
|---|---|---|---|---|
| `r13:W01:r1` | `run_20260816_215717_255189` | degraded | 0 | HTTP 503 |
| `r13:W01:r2` | `run_20260816_215744_165644` | degraded | 0 | HTTP 503 |
| `r13:W01:r3` | `run_20260816_215806_957194` | degraded | 0 | HTTP 503 |
| `r13:W04:r1`（孤儿，无 smoke） | `run_20260816_215829_340473` | degraded | 0 | HTTP 503 |

## 3. T3 判定

**未判定。** 预注册要求 8795 含埋点 tip 的工具批读数；本窗没有。
不得用下面旁证写 `confirmed` / H-a / H-c。

### 3.1 serial-phase 相邻 artifact（旁证，非结案）

声明「缺自然完成值」前先扫相邻产物（`docs/trace-profile.md` §4）：

- 460 份 `continuous-episode.json` 里，`evidence_search` **成功** 5 次：
  32.3 / 39.6 / 39.7 / 53.7 / 58.9s。**0 次 ≤10s**。
- 同工具 `tool_timeout` 且记下 `queued_ms` 的 48 次里，30 次 `queued_ms`≤3ms
  （与 732198 零执行时间闸同形）。
- 代码注释存量：RAG 本体 13–14s；冷 `evidence_search` 28.2s
  （`start-finance-workbench` / `episode_tool_batch` docstring）。
- 这些数**预测** H-c 的「单发 ≤10s」很难成立，但没有本 tip 的
  `stage_timeout_granted`，仍只是旁证。

### 3.2 对 R-11 的移交证据（不代结）

R-11 已自结。下列只供其档案对照，本案不改其 Closed 行：

| 冻结样本 | run_id | 工具批形状 |
|---|---|---|
| `post:L01:r3` | `run_20260816_184718_305950` | 4×`finance_query` 成功（47–55ms），无 `evidence_search` |
| `post:L03:r2` | `run_20260816_185901_871285` | `market_data`/`mainline_context`/`finance_query` 成功，无饿死形 |
| `post:L05:r2` | `run_20260816_190657_142513` | `kb_search`+`evidence_search` `tool_timeout`，`queued_ms` 0.2/1.1；`web_search` 成功 1.8s。**与 732198 同形的零执行时间闸** |

以上三份均无派发五元组（T1 前产物）。

## 4. T4 处置

未做。禁止拍脑袋调 T / 批窗 / 次数 / 档位。中转恢复后先补 T2 再按预注册分桶。

## 5. 身份

| 端口 | revision | dirty | 备注 |
|---|---|---|---|
| 8795 | `16f2cd47` | false | T1 tip；pid 53843；`--port 8795` |
| 8792 | `6cd0756e` | false | 全程未切 |

## 6. 下一步

1. 中转不再 5xx 后，同一 8795/`16f2cd47` 重跑 `run_replay.py`（已写计划，可 skip 已有 W01 或整窗重来）。
2. 用 `score_replay.py` 按槽表五元组 × 错误类 × 自然时长，再写 H-a/H-c。
3. 检阅方复核本收据「未结案」是否成立。
