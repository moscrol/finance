# feat/p1e4-next-watch-consume

## 这个分支做什么
P1-E4 消费端（spec `docs/learning/spec-continuous-depth-gap-r1.md` §三 P1-E「下一刀·E4」）：从跟踪题答案里 parse 可证伪的「下期关注」子弹（要有若/则/阈值/日期，丢「持续关注市场情绪」类空话和契约补全 stub），写入**已有** `checkpoints.jsonl`（`category=下期关注`，`source=track_next_watch`），未结案同 claim 去重；次日 foresight 在系统提示词里强制对照。ask 与 continuous 两条回答路径都登记；test/default 用户不写。不新开台账——接现有 checkpoint 使 [V] 块和夜间回检直接复用（单一真本源取舍）。

## 当前状态
2 笔实现 `3e58aa1e` + 交接 `44e6ef42`，从 `a7e2d74f` 长出，已推 gitea。树 `~/fwp-wt-p1e4-next-watch`。`git merge-tree --write-tree gitea/main HEAD` 干净（`35f9d9e2`）。**未合 main。轨道 B live 打回，不切 8792。**

## 已验证
- 定向 50 passed，验收方独立复跑（env -i + umask 022），收据 `~/.finance-runtime/test-receipts/20260819T072325Z-44e6ef42.json`（rev=`44e6ef42`，dirty=false）。实现方 `…T065109Z-3e58aa1e` 不采信。
- sidecar live 两发均为真 `theme_track`（会话口；`live_probe ask` 规划器没有这一档）。读数 `docs/verification/2026-08-19-p1e4-next-watch-live.md`。

## 未验证 / 已知边界
- **打回主因**：live「下期关注」正文有若/则，但 `parse_next_watch_items` 零命中，`source=track_next_watch` 未入账，foresight 对照空。夹具只覆盖 markdown 次行 `-` bullet。
- 轨道 A（#227）已放行链切；本刀打回后 **不得** 因 A 绿就切 8792。
- 合并需用户确认；合并与部署按 `docs/workflows/acceptance-workflow.md` 走——当前不应进入该流程。

## 下一步
按 live 原文扩 parse（标题行内联 / 全角 `1）` / 句号分隔）+ 夹具，再开一轮 sidecar。在此之前不合不切。

## 踩过的坑
- spec 分支与 main 上的同名 spec 文件一度两处分叉（R4 vs 第六轮补记），已在 R5 收敛——判据只认 main 上那份。
- `live_probe ask` 走 ask 规划器，没有 `theme_track` 这一档；真题型只在会话口 `turn_controller`。`question_type` 在 `report.json` 的 task_frame，不在 `run.json` 顶层。
- 单测夹具的 markdown 次行 `-` bullet 过不了 live：模型把若/则写在「下期关注清单」同一行。
