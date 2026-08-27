# E2 live：修订版在前（2026-08-19）

> 派单：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 轨道 C  
> 判据：`docs/learning/spec-continuous-depth-gap-r1.md` R5 §三 P1-E「E2（其后）」  
> 代码：`feat/e2-revise-first` @ `441c92da`  
> sidecar：`:8815`，`source_revision=441c92da` dirty=false  
> 生产 `:8792` 未切，仍 `441c60f2`  
> 入口：`POST /api/conversations`（真 `theme_track`；`live_probe ask` 没有这一档）  
> **结论：过。可合。不切 8792。**

## 为什么走会话口

派单写 sidecar live 一发。生产研究题走 `_complete_continuous_turn`，不是 `/api/runs`。轨道 B 已证明 `live_probe ask` 会落到别的题型。本刀验收同样用会话口。

## 题目（非隔夜预测题）

「陶瓷纤维最近一个月有什么新变化」  
`run_20260819_164656_600170`（239.4s，用户 `e2-revise`）

## 判定

| 条 | 读数 | 结果 |
|---|---|---|
| 题型 | `turn_intent.question_type=theme_track`，`execution_kind=continuous_episode` | 过 |
| 修订正文在前 | 终稿先写跟踪结论（无上期基线 / 信息不足 / 复核期限 2026-09-18 / 下期关注） | 过 |
| 审查进附录 | 正文之后才是 `## 输出质检`；issue 格式仍是「检查名 + note」，不是 Knevo 四件套 | 过 |
| snapshot | `verified_draft` 无附录；终稿 snapshot 有附录 | 过 |
| 不改六项 | 未改 `output_review.CHECK_ORDER` | 过 |
| 生产 | 8792 仍 `441c60f2` dirty=false；sidecar 已停 | 过 |

本发 `judge_status=unavailable`（R-06 形状：`semantic judge transient provider error`）。开头「本次未完成独立复核」是既有 transient 投影，不是本刀。本刀只把这条 issue 接到正文后面的「输出质检」附录。

Engine B（legacy compose 合成后再回灌）由单测覆盖：`test_research_compose_revises_on_warn_and_keeps_review_as_appendix`。本发 live 走 Engine A，没有再打 `/api/runs`。

## 测试 / 合并探路

- 定向：`test_conversation_orchestrator.py` + `ReviseSynthesisOnWarnTests` + `test_output_review.py` + `test_session_projection.py` → **127 passed**。`env -i` + umask 022，收据 `~/.finance-runtime/test-receipts/20260819T084606Z-441c92da.json`（rev=`441c92da`，dirty=false）。
- merge-tree：`git merge-tree --write-tree gitea/main HEAD` → `80a41f72`，exit 0。

## 产物

- 拷贝：`~/.finance-runtime/e2-revise-first-live/q-warn/`
- sidecar 已 `stop-sidecar`

## 残留 / 非本刀

- 判官 transient 仍会给正文加「未完成独立复核」帽子（W2 范围）。
- W3 也改 `conversation_orchestrator`；后合方 rebase。
- 不切 8792。
