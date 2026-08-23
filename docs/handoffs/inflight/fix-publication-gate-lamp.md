# fix/publication-gate-lamp

## 这个分支做什么

发布门两刀减法，不换引擎、不追组件臂成稿：

1. **灯**：运输 `completed` 不再盖掉研究 `partial` / `degraded`。请求走完了 ≠ 题答完了。
2. **盘子**：公开 `answer.md` / `result.content` 不再拼 `## 输出质检`。审查意见留 `gate_receipt` / notes。

底是 `gitea/main` @ `3ac070a2`（与当前 8792 同 rev）。未合、未切端口。

## 当前状态

代码已写、定向测试绿、**待你确认后才能合 main / 切 8792**。

| 检查 | 结果 |
|---|---|
| 树 | `/Users/a77/fwp-wt-publication-gate` @ `fix/publication-gate-lamp` |
| ruff | 4 文件过 |
| 本单测试 | 13 passed（投影 + 编排器公开稿三条） |
| V8 / ceiling 夹具 | 干净 `3ac070a2` 快照同样红（判官夹具走成「复核服务超时」），**不是本单引入** |
| 8792 / 8796 | 未切 |

## 未验证 / 已知边界

- 未 live。合入后要用下午有色题空会话复跑 8792：公开稿无 `## 输出质检`；研究若 `partial`，`business_status` 不得再是 `complete`。
- `_with_review_appendix` 仍留给 V8/W1 单测拼内部附录；生产公开路径走 `_public_answer_text`。
- 不修判官 provider 重试、不补「个股+代码」契约、不切 8796。

## 下一步

1. 你确认后合 `gitea/main`（本机等价检查；那 4 条存量红需与 main 对照）。
2. 只切 **8792**。8796 是另一包 revision。
3. 有色题复跑一臂作验收。

## 踩过的坑

- 不要把 V8 夹具红当成发布门回归；先在同 SHA 干净快照复现。
- 组件臂 5/5 不当对齐目标：那是编码时冻住的 f-string，不走本门。
