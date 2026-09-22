## 这个分支做什么
把 Knevo 原料按「材料→吸收决定→实现/回归→证据」收口；Q14/Q18/09-17 三包、44 轮和风远恢复索引已归档，真实入口失败照实留证。

## 决策与被否方案
- 选揭盲回归与 reviewer-only 判据；不把 Knevo 原答当金标、不改 28 题，因无配对盲样本。
- 选 Q14 事实/解读/情绪生成指导；不吸收数值信源权重、情绪溢价公式、交易窗口，因未回测且越过研究边界。
- 选 Q18 材料代理先测解释；不把代理升级真实存储/权限/跨轮能力，因真实前置未接。
- 公开 report 与私有 Episode 分证据；不把脱敏 D 日缺失写成模型输入损坏，因 sanitizer 可复现且 pack3 无私有轨迹。
- 保留失败、PR 保持 WIP；不关审稿闸/改题凑绿，因 completed 不等语义通过。

## 当前状态
- 代码 `85bff632610d0b0861d6afae7f410cc498392f11`、报告/观察/交接 `61ebccc88073690252abf57253e5f031ca96e4b4` 已推 Gitea；PR **#877 WIP**，平台 `mergeable=false`。
- 本 handoff 的状态修订已随 `82b7493e9` 作为 docs-only 提交推送；不合 main、不部署 8792、不回补行情、不写生产画像。

## 已验证
- 固定代码：定向 325P；全仓 12567P/85S/2X；Ruff/diff-check 绿；前端同 revision lint/typecheck/Vitest 110/build/E2E 34P/2S 绿。收据见 `~/.finance-runtime/test-receipts/` 和 `~/.finance-runtime/knevo-absorption-20260923/frontend-gate-61ebccc88-v2/frontend.json`。
- 12 题：9 completed/3 failed；作者文本仅 G1c/G2a 代理层有限满足，端到端 0/12；G3b 查库、pack2 越界工具、Q14 通用题型、pack3 只有公开脱敏 frame。
- packet 为 prepared_not_run；inspect 汇总在 `inspect-final-85bff6326/summary.json`。提交 61 后的全仓 gate 因共享机器并发长时间无收据已中止，不计通过或失败。

## 未验证 / 已知边界
- 未验真实台账存在/空集/权限、身份隔离、跨轮继承、Q14 正门投递及出稿/判官修复；无质量增益、胜率、top3、完整消融或成本前沿证据。
- 公开 frame 缺字段只能归脱敏/保真问题；无私有 Episode 不证明输入被删或零 IO。共享 KB 可读，用户根隔离不是 OS 沙箱。
- 风远恢复不等于找回筛选稿或批准画像；生产切换和合 main 另等确认。

## 下一步
1. 提交并推送本 handoff docs-only 修订，复核 clean、远端 head 和 PR #877。
2. 保持 WIP；沿现有 E2 线修材料范围，再修 Q14 路由和 invalid finish，原题不改、不放松闸门。
3. 修后同一正门复验，再做 Q18 真实台账/权限/身份/跨轮前置；合 main、部署和画像写入另等确认。

## 踩过的坑
- completed/非空消息/内部 completed 都不是语义通过；缺 audit 不是零调用。
- `frame_source` 要区分 `private_episode`/`public_report`，不可从公开 report 反推模型输入。
- 分支相对 `gitea/main` ahead 3 / behind 52；不要 rebase 或接管他人 worktree。

日期背景快照：`docs/handoffs/2026-09-23-knevo-absorption-closure.md`。
