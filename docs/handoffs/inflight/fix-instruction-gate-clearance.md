# fix/instruction-gate-clearance

## 这个分支做什么
将冻结指令迁移 b2d40776 与两项独立清障组成一个可验证候选；原树及历史证据保留。

## 决策与被否方案
- 沙箱源提交 6d709cfdba9786021eba63c9001163a2864b0718，集成 a22ad60a：取真实宿主解释器并记录失败输出；权限、时限与四项 denied 不变。
- 台账源提交 7d193f1c66ceef395a03672542c8e876b494f419，集成 864712e3：恢复真实原行、工单和两份历史依据；编号/pending 不变，检查器不改。
- 先提交交接依赖，再冻结运行。结果只写仓外，避免为回写读数改变被测 SHA。决策展开见 [日期快照](../2026-09-12-instruction-gate-clearance.md)。

## 当前状态
两项清障已接入，本交接随冻结准备提交；未推送、未开 PR、未合入。最终 SHA、命令、退出码、完整日志与收据唯一索引：`~/.finance-runtime/gates/instruction-migration-clearance-20260912/matrix.md`。读该文件判断后续运行是否完成，不以本文作为全绿声明。

## 已验证
提交前定向：沙箱整文件 31P/1S；gateway + orchestrator 138P；crosswalk 14P；Ruff 通过；crosswalk exit 0。均为清障过程读数，不代替最终干净树的完整门禁。原矩阵订正见 `~/.finance-runtime/gate-matrix-b2d40776-corrected.md`。

## 未验证 / 已知边界
watchdog 历史根因未定论；全量本次通过也不等于证明旧间歇缺陷已修。历史性能工单仍 pending，没有迁算法或执行旧实验。零计数收据不能证明全量测试通过。

## 下一步
按仓外矩阵完成 registry 五项、Ruff、全量 Python、前端四项和串行 E2E；任一红或无结论不合入。若需修改修复，另成新候选并保留本轮失败证据。全部完成后等待用户决定推送/PR/合并。

## 踩过的坑
主进程与沙箱子进程解释器要分别核对；不要用尾行管道的 exit 0 替代 pytest 退出码。纠偏 e8cd2c4477f1、ef420d4d6ec2 已撤销并退出活动召回，原记录保留。复现已写成现有测试回归，无新增通用 harness 部件。
