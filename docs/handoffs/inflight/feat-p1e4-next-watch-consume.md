# feat/p1e4-next-watch-consume

## 这个分支做什么
P1-E4 消费端（spec `docs/learning/spec-continuous-depth-gap-r1.md` §三 P1-E「下一刀·E4」）：从跟踪题答案里 parse 可证伪的「下期关注」子弹（要有若/则/阈值/日期，丢「持续关注市场情绪」类空话和契约补全 stub），写入**已有** `checkpoints.jsonl`（`category=下期关注`，`source=track_next_watch`），未结案同 claim 去重；次日 foresight 在系统提示词里强制对照。ask 与 continuous 两条回答路径都登记；test/default 用户不写。不新开台账——接现有 checkpoint 使 [V] 块和夜间回检直接复用（单一真本源取舍）。

## 当前状态
1 笔 `3e58aa1e`（424 行：`track_contract.py` 新建 178 行 + orchestrator/ask/foresight 接线 + 两个测试文件），从 `a7e2d74f` 长出，已推 gitea。树 `~/fwp-wt-p1e4-next-watch`（原名 fwp-wt-p1c-causal-hypothesis，2026-08-19 已更名）。与后续 main（#224 verifier/factory、#225 docs）零文件交叠，merge 预期干净。**未合 main、未跑 live。**

## 已验证
- 定向 50 passed（`test_track_contract.py` + `test_foresight.py`），收据 `~/.finance-runtime/test-receipts/20260819T065109Z-3e58aa1e.json`。

## 未验证 / 已知边界
- sidecar live 未跑：验收必须用 1 道**真 `theme_track`** 题（读 run.json 确认 question_type，别拿 theme_analysis 充数——spec §四.3 教训）+ 1 道无基线跟踪题。**禁止**套第五轮隔夜预测题。
- 合并需用户确认；合并与部署按 `docs/workflows/acceptance-workflow.md` 走。

## 下一步
派单 `docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 轨道 B（验收方独立复算，不抄本文数字）。

## 踩过的坑
- spec 分支与 main 上的同名 spec 文件一度两处分叉（R4 vs 第六轮补记），已在 R5 收敛——判据只认 main 上那份。
