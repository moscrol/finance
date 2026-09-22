## 这个分支做什么
把 Knevo 原料按「材料→吸收决定→实现/回归→证据」收口；Q14/Q18/09-17 三包、44 轮和风远恢复索引已归档，真实入口失败照实留证。

## 决策与边界
- 用揭盲回归与 reviewer-only 判据；不把原答当金标、不改冻结 28 题，因无配对盲样本。
- Q14 只吸收事实/解读/情绪结构；不吸收数值信源权重、情绪溢价公式、交易窗口，因未回测且越界。
- Q18 先测材料解释；不把代理升级真实存储、权限、身份隔离、跨轮能力，因真实前置未接。
- 公开 report 与私有 Episode 分证据；不把脱敏 D 日缺失写成模型输入损坏，因 sanitizer 可复现且 pack3 无私有轨迹。
- 保留失败、PR 保持 WIP；不关审稿闸/改题凑绿，因 completed 不等语义通过。

## 当前状态
- 代码提交 `85bff6326`；报告/观察提交 `61ebccc88`；本 handoff 的 docs-only 修订均已推 Gitea。
- PR **#877 WIP**：当前 head 以 PR 页面为准，平台 `mergeable=false`。不合 main、不部署 8792、不回补行情、不写生产画像。

## 已验证
- 代码提交全仓 **12567P/85S/2X/0F**，定向 325P，Ruff/diff-check 绿；之后在 docs-only closeout revision `82b7493e9` 重跑同一组定向测试，收据 `~/.finance-runtime/test-receipts/20260922T194629Z-82b7493e.json`（clean、325P/0F）。其后仅文档提交，不能把该收据冒充最新 HEAD 全仓验证。
- 前端绑定 `61ebccc88`：lint/typecheck、Vitest **110**、build、E2E **34P/2S** 全绿。它们是工程门禁，不是语义验收。
- 12 题：9 completed/3 failed；作者文本仅 G1c/G2a 代理层有限满足，端到端 **0/12**；G3b 查库、pack2 越界工具、Q14 通用题型、pack3 只有公开脱敏 frame。
- packet 为 `prepared_not_run`；inspect 在 `~/.finance-runtime/knevo-absorption-20260923/inspect-final-85bff6326/summary.json`。提交 61 后全仓 gate 因共享并发长时间无收据中止，不计通过或失败。

## 未验证 / 下一步
- 未验真实台账存在/空集/权限、身份隔离、跨轮继承、Q14 正门投递及出稿/判官修复；无质量增益、胜率、top3、完整消融或成本前沿证据。
- 后续沿 E2 线修材料范围，再修 Q14 路由与 invalid finish；原题不改、不放松闸门，修后同一正门复验，再接 Q18 真前置。
- 公开 frame 缺字段不能证明输入被删或零 IO；共享 KB 可读，用户根隔离不是 OS 沙箱。风远恢复不等于画像批准。合 main、部署和画像写入另等确认。

## 踩过的坑
- `frame_source` 必须区分 `private_episode`/`public_report`；缺 audit 不是零调用。
- 分支未 rebase，且与 `gitea/main` 仍有基线差异；不要接管他人 worktree。

日期背景快照：`docs/handoffs/2026-09-23-knevo-absorption-closure.md`。
