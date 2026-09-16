# 预算 P1 工具侧处置：RAG worker 保活 + 装不下的工具不上菜单（2026-09-03）

`2026-09-03-tool-duration-floor-offline.md` 量出工具侧没有「一个地板」可拍，要拍的是 RAG 路径三选一。
用户「执行」了 1（worker 保活）+ 2（低余量不派 RAG 工具，兜底）。两张 PR，零 LLM 调用，
零预算算术改动。

| | PR | 落点 | 钉子 / 变异 |
|---|---|---|---|
| 2 菜单裁剪 | #544 `9b7ac30a` | `ToolSpec.min_window_seconds` + `MIN_WINDOW_SECONDS={kb_search:20, evidence_search:30}`；`EpisodeToolBatchSession.menu()`；两条 loop 记 durable 事件 `tool_menu` | 5 条（会话 3 + 两 loop 同机 2）；门禁 7551P/5F |
| 1 worker 保活 | #545 | `rag_worker.WorkerRequestAbandoned`：热 worker 首次超窗放弃请求、保留进程，迟到响应下一次查询排掉；连续第二次才杀 + 原自愈；`status()` 加处置账 | 4 条改/新；变异「永不放弃」3 红、「不排迟到响应」1 红 |

## 为什么是这两刀

- 老处置里 **一次慢查询 = 杀热 worker = 重生 50–145s = 期间所有 kb_search 必败**，这是 66% 超时率的放大器。
  保活只损失那一次；两次连续都答不上来才当它卡死，原来的自愈路径（预热窗重生、单飞、冷却）一个字没动。
- `kb_search` 内部是「一次检索 + 一次 LLM 相关性裁判」，`evidence_search` 是 narrow→broad→counter 多轮检索加
  语义裁判——它们本来就要 20s / 30s 以上。研究窗只剩十几秒时把它们摆给模型，是让模型烧 23s 换一个
  `tool_timeout`，再把后面的工具推进零授权（今天首发切流探针第二轮的形状）。菜单裁剪让底座按「本轮能授多少秒」
  决定摆不摆；领域只申报「我最少要几秒」。

## 生产上会看到什么（切流后的读法）

- `/api/readiness` → `workers.rag.counters`：`timeouts_abandoned_kept_warm` 多、`timeouts_killed` 少 = 保活在起作用；
  `timeouts_killed` 多 = worker 真在卡死（不是冷启），那就该查 worker 本身。`stale_responses_drained` 应 ≈ abandoned。
- 生产 `continuous-episode.json` 里出现 `tool_menu` 事件 = 某轮藏了工具，payload 写明藏了谁、本轮窗多少。
  standard 档（总 90 / reserve 60）预期形状：首轮不出现（菜单时窗 ≈ 30s，两条都装得下），第二轮起
  `remaining − 60 ≈ 0` 两条都藏。
- 复跑 `scripts/offline_tool_duration_floor.py` 看 `kb_search` / `evidence_search` 真超时数与零授权数是否下降。
- `kb_rag` 的 warning 文案分两种：「请求已放弃、worker 保留」 vs 「进程已终止」。

## 边界（有意不做）

- **不改 90/60/30**、不改 asked、不改 reserve、不改任何授予算术（能力放大 spec §6 与预算线红线）。
- 菜单是引导不是锁：执行器仍按能力授权放行，模型硬点被藏工具照旧执行（与既有 episode 级隐藏一致）。
- 菜单口径用「菜单时」的窗，不减思考时间：首轮派发时 kb_search 拿到约 24s（≥20）装得下，evidence_search
  拿不到 30——这是已知边界，等 live 读数决定要不要减去思考 p50（5.9s）。
- 三选一的第 3 项（RAG asked 缩短快失败）没做：1 做成了它就不值。
- 冷 worker（没加载过模型）超时照旧杀：那时没有「热」可保。

## 并发注记

12:26 目击另一会话在本会话刚开的 `fwp-wt-rag-window` 树里并行改 `rag_worker.py`（同一设计、改到一半）。按 AGENTS.md
「同一棵树两个 agent」红线：本会话把方案 2 搬到独立树 `fwp-wt-rag-menu` 走完，方案 1 在独立树 `fwp-wt-rag-keepalive`
重做；`fwp-wt-rag-window` 里只留对方的未提交改动（12:29 起未再变动）。若对方后续提交同题 PR，以 #545 为准对账。
