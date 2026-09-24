# local 日报计划对齐

## 这个分支做什么
同步器、同日门、跨日门、intelligence daily 与 HTML 内部门共用计划解析，不改变资金口径。

## 当前状态
代码提交 `4fbc8c42`；树 `/private/tmp/fix-local-plan-gate-alignment`，基线 `gitea/main@1fef3d27`。未 push/合并/部署/补跑。原数据树他人 WIP 未动。

## 决策与被否方案
- 显式 --plan > REVIEW_SYNC_PLAN > full；auto 按目标交易日解析。日报 options 冻结实际档位，各门显式传递。
- theme_flow 保留 local 豁免；否了填本地篮子资金凑门，口径不同。
- 旧 daily-update 不支持 local/cheap，选中同步时拒绝，先匹配同步再 --skip-sync；不新造生产写链。
- 代码根问题不半修：按已有 #50 分别验 import/用户态/episode/报告落盘。
- 详情：`docs/handoffs/2026-09-14-local-plan-gate-alignment.md`。

## 未验证 / 已知边界
全量 Python 仍红：两条已安装 Codex 沙箱隔离测试 unproven；基线同名同因复现，不是本轮新增，但仍禁止合并。没跑 frontend/e2e；技能 registry 只验 ws，跨仓跳过。没在生产库跑同日/跨日/L2 门，也没补生成，不得称日报恢复。

## 下一步
1. 处理沙箱既有红门，补齐完整 registry/frontend/e2e 叶子；用户确认后才合并。
2. 工单 #50：`docs/superpowers/specs/2026-09-12-generation-stage-code-root-workorder.md`，部署代码根与数据根分别验。
3. 真数据/L2 门过后再补跑生成；本轮不请求复盘会、不写资金兜底。

## 踩过的坑
- main 已有 local 与两道门裁剪，缺的是日报传计划；不要重复搬脏树代码。
- 连板、新高、主线、核心股已有 local producer，不能照旧笔记豁免。
- HTML 渲染会再次质检，只修日报前置门不够。
- 所有 bash 显式 cd 隔离树；解释器用主树 `.venv-workbench/bin/python` 绝对路径。

## 已验证
- 针对性 144P（含新增39）；撤掉跨日 --plan 的变异 9F，恢复 144P。
- 干净代码提交：ruff 绿；pytest **9654P/2F/77S/2x**。收据 `~/.finance-runtime/test-receipts/20260914T160652Z-4fbc8c42.json`。
- 基线 detached 树同两项 2F，收据 `20260914T160726Z-1fef3d27.json`；未跑基线全量。
- registry 本仓一致；CLI --dry-run local 两道门和 HTML 带同档位。
- 临时库验证缺实际应产行/NULL 仍红，历史题材资金返回 Gap，不伪装当日。
