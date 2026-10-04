# Harness 四片集成收尾：版本、CI 与临时树清理

## 背景与收尾目标

本轮不是发布验收，而是从 `origin/main@06198093eb7d4cf57ff20e26a2fa7a7df9df8726` 集成 Harness 四片，并把“产品代码验收 pin”和后续文档头部分开留证。产品代码 pin 是 `d09e3b08d3b7b8ee49c27b6fb6c00c8cec464fc8`；其最后生产补丁是 `46d9875c6`。后续文档提交只允许修改 handoff，不把新文档头的本地结果冒充产品 pin 收据。

## 发现与裁决顺序

1. 保留主线冻结材料引用预检、来源/绑定身份检查、纠错分类和拒绝顺序，再叠加根请求/解释投影。否决全选候选实现，因为会削弱主线合同。
2. 自动合并后的路由必须同时同步 `required_outputs`、`output_requirements`、来源身份和 `merged_origins`。否决只改字符串或删除来源，因为用户义务见证会丢失。
3. `causal_chain`、`counterpoint` 是 canonical 必需义务；`cause_attribution` 是 `origin="heuristic"` 的可选额外提示。否决恢复第二个硬槽，也否决删除断言；缺少真正因果答案仍必须拒收 `completed`。
4. adapter 在知道阶段语义和交付检查两类来源的位置合并诊断，并去重；否决在 coordinator 无差别并集旧裸 claim index，因为旧索引可能已不属于当前稿。
5. 每个受验 revision 独立执行全量门禁和变异审计。否决以旧候选结果转签，保留早期失败与不完整审计原件。

## 最终工程证据

- `d09e3b08` Python 全量 `20558 passed / 76 skipped / 2 xfailed / 0 failed`，`collected=20636`；收据、解释器、依赖指纹、dirty 状态和完整收集范围审计 exit 0。
- 前端 frozen install/lint/typecheck/unit/build 全绿，22 files / 209 tests；Playwright `52 passed / 2 skipped`，身份首尾稳定且干净。
- registry 五项均 exit 0；台账仍有 102 条反向回指 warning，保留为 warning，不解释成零 warning。
- 变异最终审计完整且还原哈希一致：PLAN 归属/请求解释/输出溯源/表达建议为 `9/12/13/14`，历史诊断 `8`，交付边界 `16`；产品 Workbench 真实模型调用为 `0`。
- 文档头部 `60ff5ba76` 的旧 GitHub runs `37137218464`（workbench）和 `37137218453`（registry）均 success；本快照提交后必须按新 head 重新查 required checks。

## PR 与授权边界

PR #30 已更新为当前范围说明，保持 Draft / OPEN / CLEAN，无 auto-merge。未合入 `main`、未部署、未启动真实 Workbench 对照、未扩大 P1b。最终生产补丁尚无独立静态审查；此前只读审查覆盖 `5266b5f8`，实际模型记录为 `glm-5.2`，`costBasis=unknown`，不能称 Claude 审查或真实账单。R17、R19、正式 240 格继续封存。

## 临时树收口

先用完整 PATH（含 `/usr/sbin:/sbin`）做安全采样；初次 PATH 缺少 `lsof` 的失败原件保留，不将其当成无占用证明。随后逐棵核对：四棵可重建、detached、无未命名提交的门禁树已移除；前端树含 260 个测试残留、3 个数据库，先由 `worktree_closeout.py` 归档 residue/clones 并推送 Gitea archive ref，再移除。未合入的命名分支 `fix/harness-integration-probes-1003` 仍保留，不能按已完成门禁树删除。没有全仓 `--apply`。

收据：`~/.finance-runtime/reviews/harness-integration-20261003/worktree-closeout-20261004-gitea/apply-20261004T011337.json`、`gate-tree-cleanup-20261004/final-result.json`。最终索引和 `closeout.json` 位于同一证据根；旧失败、旧绿色、cleanup dry-run 和归档原件均不覆盖。

## 未被本轮证明的事项

工程门禁、E2E、离线脚本和变异捕获只证明工程合同及测试敏感性，不证明真实金融回答质量提升。题型/主体/时间窗在线修订、完整 HTTP 新计划交付、SDK 跨进程恢复和真实模型对照均未由本轮验收。若继续，必须另批模型身份、配置、预算/费用上界、物理调用帽、停止规则和盲审口径。
