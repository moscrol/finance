# P1-E1/E3 live：四态接 repair + 判断 TTL（2026-08-19）

> 派单：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 轨道 D  
> 判据：`docs/learning/spec-continuous-depth-gap-r1.md` R5 §三 P1-E  
> 代码：`feat/e1-e3-repair-ttl` @ `aaba343c`  
> sidecar：`:8814`，`source_revision=aaba343c` dirty=false，用户 `e1e3-d`  
> 生产 `:8792` 未切，仍 `441c60f2` dirty=false  
> 入口：`POST /api/conversations`（真 `theme_track`；`live_probe ask` 没有这一档）  
> **结论：实现过。可合（等你确认）。不切 8792。C 未出分支，本枝从当时 main 长出，C 先合则 rebase。**

## 做了什么

| 项 | 落点 | 不做什么 |
|---|---|---|
| E1 | `contract_missing_outputs` 并入 episode `missing_outputs`；仅表达层缺口走 `contract_rewrite_candidate`（tool-closed delivery）。不写进 verifier `issues` | 不注入第二套文案；不改 #224 前缀 |
| E3 | 收据加 `prior_verdict_check` / `valid_until` / `ttl_status`；过期只盖「已过期，待复核」 | 不删结论 |

## 题目（非隔夜预测题）

1. 无基线跟踪题（`e1e3-d`）：「动力电池产业链近况跟踪一下」`run_20260819_164434_166829`（约 80s）

## 判定

| 条 | 读数 | 结果 |
|---|---|---|
| 题型 | `contract.question_type=theme_track`，`execution_kind=continuous_episode` | 过 |
| E1 接线 | `repair_goal.missing_answer_elements` 含 `track_quad_or_baseline` / `track_ttl` / `track_next_watch`（与 `change_summary` 等槽并列）。`repair_attempts=1` `repair_cycles=1` | **过** |
| E1 收口 | 修后 `track_contract.missing_outputs=[]`。本发同时有 required-output 缺口，故走进度修复（`remaining_calls=2`），不是 contract-only delivery——分流单测锁住 | 过 |
| 无基线 / 四态 | draft：「无上期基线，本期建立基线」「既有判断对照：信息不足」；收据 `prior_verdict_check=信息不足` `baseline_declared=true` | 过 |
| TTL | draft `复核期限：2026-09-18`；收据 `valid_until=2026-09-18` `ttl_status=current` | **过** |
| E3 过期降级 | 同用户 `judgments.jsonl` 写入过期条后，`render_for_prompt(..., as_of=2026-08-19)` 保留「扩产逻辑仍在」并标注「已过期，待复核」。路径即 foresight 次日注入 | **过** |
| 公开稿 | 降级模板「现有证据不足」（episode 证据 0，judge `unavailable`）。私有 draft 有契约段。不是本刀回退 | 不挡 |
| 生产 | 8792 仍 `441c60f2` | 过 |

## 测试 / 合并探路

- 定向：`test_track_contract.py` + `test_repair_coordinator.py` + `test_judgments.py` + `test_user_memory.py` → **80 passed**。`env -i` + umask 022，收据 `~/.finance-runtime/test-receipts/20260819T084708Z-aaba343c.json`（rev=`aaba343c`，dirty=false）。
- adapter / foresight / repair 回归另一次 168 passed（含 `test_continuous_turn_adapter.py`）。
- merge-tree：`git merge-tree --write-tree gitea/main HEAD` → `28aa748a`，exit 0。

## 残留 / 非本刀

- 公开稿仍可被门禁收成「现有证据不足」；本发是零证据 + 复核超时，不是 track 收据丢了。
- 本发不是「只缺四态」的纯 contract-rewrite 现场；那种分流由 `test_contract_rewrite_candidate_uses_tool_closed_delivery_not_progress` 锁。
- C（E2）未出分支。本枝避开 `conversation_orchestrator`。

## 产物

- 私有审计：`~/.finance-runtime/e1-e3-repair-ttl/q-fresh/continuous-episode.json`
- E3 渲染：`~/.finance-runtime/e1-e3-repair-ttl/e3-foresight-render.txt`
- sidecar 已停（收工时停）
