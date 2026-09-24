# 读数链：同一道题跑四遍，撞出三道顶（2026-09-07 03:24–04:30 CST）

上文：`2026-09-07-max-shape-readings-and-sub-research-live.md`（D 组 + 子研究 live）、`2026-09-07-forward-call-gate-live.md`（D9 硬门）。
本文是「先找能力 max、再按超限的部分加约束 / 放开」这条线的第二段：一道可拆的跟踪题（`theme_track`）连跑四遍，每一遍
撞出一道新顶，修一道再跑一遍。三张 PR：#615（分支预算随档位）、#616（修复轮表达槽绑定）、#617（LLM 调用保险丝随档位）。

题：「固态电池和钠电池两条题材线最近一个月的产业进展与舆论热度对比：各自的核心催化和主要反证」。另两道可拆题
（长电 vs 通富、中际旭创 vs 新易盛）只用于 §1 的分支读数。

## 0. 四遍的形状

| 遍 | 8792 | 分支 | 修复轮 | 判官 | 结果 |
|---|---|---|---|---|---|
| 1（03:31） | `ed22039a`（分支 60s/8） | **failed ×2**（`deadline_exhausted`，0 证据）+ partial ×1 | `unknown_output: track_next_watch` → `invalid_repair_finish` | — | partial |
| 2（03:53） | `1acbbb1c`（#615 分支 150s/10） | partial ×3（18/18/84 条） | `unknown_output: track_ttl` → `invalid_repair_finish` | — | partial |
| 3（04:11） | `0399b980`（#616 表达槽可修正） | partial ×3 + partial ×2（第二次 `sub_research`，合计 28 次模型调用） | 无需修复（首稿已含复核期限 / 下期关注） | **unavailable：`semantic judge call budget exhausted`** | degraded |
| 4（04:27） | `d65ed015`（#617 保险丝 40 → 120） | partial ×3（31/24/92 条，分支 17 次模型调用） | 无需修复 | **repaired**（删一句无证据的「2027 拐点」） | **completed**，degrade 0，202s |

每一遍暴露的顶都不是上一遍能看见的：分支上限挡住了修复轮，修复轮的硬拒挡住了保险丝。**同题重跑是找顶的唯一方法**，
换题只会把不同的顶混在一起。

## 1. 顶一：分支上限不随档位走（#615）

三道可拆题、9 支分支，60s / 8 次下 **9/9 没有一支跑完**（7 partial、2 failed 零证据），父臂每次派发时都还剩 ~590s、
`sub_research` 整个调用只用 60–97s。放开：`branch_limits("max") = (10, 150.0)`，其它档不动；max 起步调用 32 → 40、硬顶 48 → 60
（分支调用从父账本扣，长电那题分支 20 + 父臂 12 恰好用满 32）。第 2 遍起分支不再 failed。

## 2. 顶二：修复轮要的东西被自己硬拒（#616）

`track_contract` 把 TTL / 下期关注缺件以合成 id（`track_ttl` / `track_next_watch`）并进 `RepairGoal.missing_answer_elements`，
模型看见 id 就当 output 去绑，`validate_episode_finish` 判 `unknown_output`（INTEGRITY，不回灌不恢复）。第 1、2 遍 2/2 死在这里。
修：绑到表达槽 → `expression_slot_binding`（FORMAT，回灌「写进 draft、bindings 只留契约 output」）；真陌生 id 仍 INTEGRITY；
REPAIR_GOAL 消息在真有表达槽时多一键 `expression_elements_note` 说明写法。第 3、4 遍首稿就把复核期限 / 下期关注写进了正文，修复轮没再起。
这条与 max 无关，是存量 bug——max 只是让跟踪题跑得够久、够到修复轮。

## 3. 顶三：turn 级 LLM 调用保险丝烧穿在判官头上（#617）

`ResearchExecutionPolicy.max_llm_calls = 40`，controller / judge / agent / 分支 / 合成共用一本账。第 3 遍两次 `sub_research`
5 支分支 28 次模型调用 + 父臂 ~10 + controller → 40 用尽，**最后要发的调用是判官** → `LLMCallBudgetExceeded` →
`judge_status=unavailable` → terminal degraded。Grok CLI 同分钟直调 11s 正常。保险丝的注释原文是「失控保险丝而不是常态限流」；
并行分支是 max 档的常态开销。放开：`llm_call_fuse_for_tier("max") = 120`，只在 profile 的值更小时抬，墙钟 / 合成保留 / grounded profile 不动。
第 4 遍判官 repaired、degrade 0。

## 4. 这一段说明了什么

- 「能力 max」不是一个开关，是一串顶：预算线 → 分支线 → 修复线 → 保险丝线，每道都是为 standard 形状量的。一道题跑四遍
  比跑四道题更有效——顶是串联的，前一道不掀掉看不见后一道。
- 三处改动都带一条读数、都只动 max 档（或修存量 bug），standard / deep 的数字一个没变。
- 判官这一层始终在工作：第 4 遍它删掉的正是一句注册表里没有的「2027 拐点」。出口硬层没有因为输入放开而变软。

## 5. 未量 / 下一步

- 分支 150s 下仍 9/9 partial（各支报「研究截止时间已到」）：分支自己在 150s 里跑 8–10 次调用 + 3–10 次模型轮，还是撞时间。
  下一档候选：分支起步用 quick 档的 4 次每批帽（`batch_call_cap` 对分支上下文是 quick）——可能是分支慢的原因之一，先量分支内每批派发数再动。
- 中际旭创 vs 新易盛（03:24，第 1 遍代码）：partial、4 条数据形状 gap；未在新代码下重跑。
- A/B/C 组 28 题 max 形状全景未跑（Codex 5h 窗 70%、周窗 69%，等用户拍）。
- 09-06 22:56 成批文件改写、机器 03:00 load 200+（Devin ×26 / Codex cua_node ×13 / mdworker ×17）：用户侧。
