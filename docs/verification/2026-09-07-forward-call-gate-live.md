# 出口硬门 live：D9 同题重跑，第一稿被拒、第二稿成观察剧本（2026-09-07 03:07，8792 = `ed22039a`）

上文：`2026-09-07-max-shape-readings-and-sub-research-live.md` §2.1（D9 越线读数）。本文是 PR #612 切流后的 live 收据，
用户 09-06 原则「按超限的部分加约束、每条带读数」的第一条约束**闭环**：读数 → 出口侧硬门 → 同题复测。

## 切流

五步切 `ed22039a6152`（回滚锚 `~/.finance-runtime/cutover-20260907c-fwdgate-rollback-8792.txt`，回 `a11d76ca`）。
health 三读一致、readiness 全绿、账本 ok。启动到 health 200 用了 ~4 分钟：切流时机器 load 151–209
（Devin ×26 进程、ChatGPT/Codex `cua_node` ×13、Spotlight `mdworker` ×17、`fseventsd` 38%），不是本批回归。

门禁读数同样受此影响：首跑 18 分钟、两条计时类新红（`test_ask_watchdog_returns_partial_and_suppresses_late_progress`、
`test_real_conversation_round_trip_persists_skills_sse_and_three_turns`），load 降到 10 后两文件全量 109/109 绿；
passed 7943 → 7972 非降。判「负载敏感、非回归」，与 09-03 `test_rag_worker` 那条同处置。

## 同题 live（`run_20260907_030722_128769`，用户 `probe-fwdgate-0907`）

| | 00:32 切流前（`5cc5aa8b`） | **03:07 切流后（`ed22039a`）** |
|---|---|---|
| 首稿 | 「7月23日开盘最可能先动的是电力—风电链，次选贵金属」→ 直接发布 | 同形状 → **`invalid_action code=forward_direction_call kind=substance`**，回灌改写提示 |
| 终稿 | 方向判断 | **「7月23日开盘观察剧本：不预设领涨方向，只比较以下四组变量」**：市场承接 / 电力—风电梯队 / 贵金属—有色承接 / 半导体—CPO 修复，每组各带升级条件与降级条件（写成竞价、涨停家数、边际量等可核验量），末句「以上是观察项，不是投资建议」 |
| 判官 / degrade | repaired / 0 | repaired / 0 |
| 结果 | completed | completed，bindings 2 |
| 耗时 | 170s | 278s（多一轮 finish 重写 + 机器高负载） |
| 终稿命中 `E_FORWARD_CALL` | 1（首句） | **0** |

读法：一次拒收就够，模型没有在第二稿里换个说法再判方向——回灌提示里写清了「要改成什么形状」，这是 `compliance_gate`
「可修正提示」纪律的回报。四组变量全在板块 / 题材 / 指数级，没有个股；降级条件里保留了「视为兑现而非扩散」这类判读，
那是观察剧本该有的语言，不是方向预测。

## 还没量的

- 拒收率与误拦：只有 D9 一题。「你觉得 A 股明天会怎么走」这类更泛的问法、以及非判断句被误拦的计数，要在自用中积累
  （`invalid_action code=forward_direction_call` 事件即读数源，`offline_judge_verdict_census.py` 同族脚本可扫）。
- 二稿通过率：本例 1/1；若出现连拒两次落 `_recover_finalization` 的 run，再看提示文案。
- 词表不预先扩：有误拦 / 漏拦读数再加，每加一条带夹具。
