# fix/checkpoint-rule-id-bias-sync

## 这个分支做什么
接续用户授权的批次收口：将 PR #592 前向整合 main@1bcb1ebc，消除 INDEX 冲突并刷新跨仓注册表指纹。

## 决策与被否方案
- 独立树 / 不改作者树：作者分支及主检出现场原样保留；向原 PR 推送只做 fast-forward，不强推。
- INDEX 保留 main 的 #23 与 #592 的 #24；不整表选一边，不修改业务行为。
- 注册表按知识库 gitea/main@8a413cde5 重扫；七个源 skill 均无未提交改动，仅七个 computedHash 和生成时间变化。
- 不豁免基线红；不合 main、不切 8792。完整批次回执在 release-gate-closeout 分支，见下方指针。

## 当前状态
前向 merge 提交 fe733616；本提交仅注册表与本交接。PR 原 head 2a0fc382 的原始实现保留。
工作树 /Users/a77/fwp-wt-checkpoint-bias-sync。冻结门禁、push 结果与运行面收口见
`docs/verification/2026-09-15-release-gate-closeout.md`（fix/release-gate-closeout 分支）。

## 已验证
- fe733616：merge-tree 对 main@1bcb1ebc exit 0，ruff 全仓 exit 0。
- .venv-workbench 定向六个 checkpoint/methodology 测试文件 221 passed；收据 20260915T132757Z-fe733616.json。

## 未验证 / 已知边界
旧 09-05 bias-scan 83 条不冒充本轮复测。生产真实判断台账未写入。
人工 stage_manual、生产成本观察属于 #673/#593 的运行面，不在本枝代填。

## 下一步
按收口回执核实精确 revision 四叶门禁和 PR head；用户确认后才进入合并窗口。

## 踩过的坑
主干 Codex 解释器修复与 6d709cfd 的 runtime 文件逐字节相同；不要凭祖先关系再 cherry-pick。
