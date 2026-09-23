# 行情恢复 QC 修复

## 这个分支做什么
修 PR #861/#871 组合中的 F1 夜跑桥接、F2 假覆盖率、F3 过期计划覆盖，并补正式回归。背景与被否方案见 `docs/handoffs/2026-09-23-market-recovery-qc-fix.md`。

## 当前状态
代码已提交 `4fa70046f`、`981c4d629`，分支 `fix/market-recovery-qc-0923`，树 `/Users/a77/fwp-wt-market-recovery-qc-fix-0923`。整体 HOLD；未合并、推送、部署、数据库 staging、换库或生产写入。

## 决策与被否方案
- local 的同花顺 dump 前置；桥接纳入同一 stock-daily 结果，否了只补另一个编排器。必需行情失败原位重试、再失败停下游；尝试和重试均落 runlog。
- F2 仅加固显式 recovery_members 路径，否了未授权启用新分母；成分身份逐一核 canonical bar，缺 bar 不写四张派生表。
- F3 在执行事务内重新验目标日与覆盖策略，否了只验 build 时状态；默认计划过期/重放拒绝覆盖。
- 新 CLI 复用生产守卫且无 direct/覆盖开关；不自动删除部分写入结果。

## 未验证 / 已知边界
没有最新组合全仓 pytest 绿、独立复验或真实夜跑验收。未知停牌身份、完整计划输入指纹/并发、供应商范围与 mootdx 部分 flush 合同仍待定。恢复 CLI 参数未擅自接线。跨仓 registry 项在预览环境跳过；未改前端，前端/E2E 不适用本补丁。

## 下一步
1. 用户确认五问、三合同、5553/5565 范围及 53 只除权/送转缺口处置。
2. 依确认合同补边界与独立复验；届时最新 main 在 /Users 下构造干净组合树，重跑全仓 pytest/Ruff/registry/收据门。
3. 明确授权后才可合并或恢复生产；旧授权换库是历史事实，不抹掉。

## 已验证
- 最新基座 `5f35da17`，预览 `44a82a4eb883`：429P/1S，Ruff/本仓 registry/解析通过，收据干净且基座漂移0。1S 为 opt-in 真实模型测试。
- 较早预览 `a7a9635d5`：扩大范围2631P/63S/2F，非全仓；2F 为 /tmp 沙箱读取测试。同 SHA 放 /Users 后2P，最新429项也通过。两种收据不拼成全量绿。
- 修前18F；落盘/重试遗漏分别1F，补丁后通过。提交 hooks 及能力图谱审计通过。
- 证据：`docs/verification/2026-09-23-market-recovery-qc-fix/`。扩大测试已退出，无在跑任务。

## 踩过的坑
沙箱 minimal 允许读取 /tmp 中的仓库，live_root_read 因而不是 denied；测试树用 /Users，不能删断言洗绿。早期中断测试无完整收据不采信。attempts 只进内存不等于写入 runlog；机械保护已进正式测试，不另造通用工具。
