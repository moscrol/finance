# feat/adaptive-research-loop 在途

## 这个分支做什么

修研究回路的计划、取证、修订与公开保真；本片收窄本地非命中的证据边界。

## 决策与被否方案

空查询只称本次条件/截止时点内未命中；历史回退保留原日期行，不认证现实退出或逐日覆盖完整。限制放观察前端与gaps，压缩/去重保留。
写手/分支/判官区分未查、非命中、事实为否；gap不是收据，直接零值可引用。用既有fact_beyond_evidence删除/重审，否决正则一律删否定句，避免误伤。
详见 `docs/handoffs/2026-09-21-adaptive-local-absence.md`；均值背景同目录 `2026-09-21-adaptive-amount-summary.md`。

## 当前状态

树 `/Users/a77/finance-worktrees/adaptive-research-loop`，代码 `81ff5e7da`；最终文档提交见git。未push/PR/合main/部署，未fetch新main，8792未探测/恢复。
local_only四只读能力冻结，未开derived_calculation；T=900/75秒单帽/150秒共享判官窗及全局HTTP400策略不变。静态写手契约指纹有意更新。

## 已验证

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
干净81ff5e7da相关709P、全仓Ruff/提交钩子绿；非命中六变异全红后绿（首尾15P），amount五变异全红后绿（首尾36P）。固定代码收据 `~/.finance-runtime/test-receipts/20260921T155657Z-81ff5e7d.json` 已校验。
证据根 `~/.finance-runtime/adaptive-absence-20260921/`；最终文档SHA收据另记README。仅证明观察修正、规则送达与脚本判官接线。

## 未验证 / 已知边界

本轮无新自然模型请求，未证自然选择均值/有效数、否定证据边界、无工具改稿partial重核、独立判官与正常长答不泄漏。判官失联/关闭/忽略规则时公开策略不变，仍可能发未审的否定事实。
旧run `run_20260921_203845_282895` 原件在 `~/.finance-runtime/adaptive-k3-plan-fix-live-20260921/`，仍partial，均值与“无涨停”错不改判。留档未见涨停池/龙虎榜匹配查询，gap最多支持尚未查证。

## 下一步

1. 新隔离会话预先约定单次真实验收上述自然行为，不选样重试/刷live状态词。
2. 最终基线整合、完整Python/前端/E2E/registry与独立Spec/Quality另签，局部绿不得替代；不自动推进生产。

## 踩过的坑

独占basetemp先建父目录；真实零值指标是limit_up。数据集最新日期不是目标主体覆盖证明，自报gap不能当查询收据。测试计数须绑定具体树/提交/解释器，不读共享latest。
