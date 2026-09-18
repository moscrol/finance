# baseline/runtime-absorption-audit-0918

## 这个分支做什么
对照 pi/dsh 固定源码审金融 runtime 吸收程度；只读审计，不改 runtime、不切生产。详报 `docs/handoffs/2026-09-18-pi-dsh-runtime-absorption-audit.md`。

## 决策与被否方案
- 继续按行为合同吸收，否两套框架叠加：金融证据/权限/发布仍归 ResearchHarness。
- 分开「实现/产品接线/效果」；否拿 pi 新 AgentHarness 规格当现成功能：此 revision 执行方法仍 NotImplemented，成熟 AgentSession 另看。
- 保存失败/恢复沿既有 OPT-08；否另立重复架构。只审不修，保留旧测试合同作为证据。

## 当前状态
报告与观察脚本已提交 `e251d30a`；本次交接单独归档。分支基线 `gitea/main@0a1cb8c4`；未 push、未合 main、未部署。8792 健康为 `bf662e93`，该版与产物基线的 runtime/services/API/Composer 相同。原树他人产物未碰。

## 已验证
- 干净被审树 `/private/tmp/finance-runtime-audit-bf662e93`，workbench Python 3.12.13：263P/3S/1X（12.91s）；补测90P（2.03s），有重叠不加总。
- 收据：`~/.finance-runtime/test-receipts/20260918T065717Z-bf662e93.json` 与 `20260918T070538Z-bf662e93.json`。
- 三探针实测：保存失败仍completed而restore=retry_model；折叠后重查被duplicate_query拒；length截断调用仍执行。`scripts/audit_runtime_absorption.py` 用假模型/工具与内存store，无外呼。
- 脚本ruff、diff检查及提交钩子通过；非全仓验收。

## 未验证 / 已知边界
未做真实模型同题对照、生产kill/restart、Workbench浏览器插话验收、外部工具取消排空；未查生产折叠开关；未跑上游JS测试。无质量胜负结论。已有restore仅给计划，API重启是原题重排队；repair resume不等于崩溃续跑。
记忆仅加项目行索引（0da827cf）。vault_lint前后均19个既有错误、集合相同，不能报通过；其作者白名单尚不接受pi，正文留项目报告，不假署名或越权改白名单。

## 下一步
用户授权修复后：P0保存失败语义与停止原因贯通；再接跨进程driver、子研究独立存储、原文回读、Workbench插话。先核最新main/在途，报告是固定快照不是常驻能力清单。

## 踩过的坑
P4已合但不等于自动恢复；inbox/CLI steer已做，不能说没有插话。read_history_result与evidence_lookup不等于任意E号回读。受限历史产物保存已有事务/版本保障，不泛化成所有工具只读。工具已落scripts，不把临时探针当永久门禁；通用形状复用contract-vs-delivery-mismatch。harness-reference树脏且底旧，本轮不改。
