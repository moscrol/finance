# #831 小片先行

## 这个分支做什么
只前向移植API测试Timer归属与code-map有界别名，不携领域运行代码。

## 决策与被否方案
只等待当前夹具登记的Timer；否扫描全局线程/改生产shutdown，避免误等别人的工作。
原问句加最多一次别名；否覆盖原问句/无限变体，保持检索语义与成本上限。
细节：`../2026-09-21-research-tail-forward-integration.md`。

## 当前状态
WIP #831固定ea5c3a94618a15e37f914c8b1a13e271875e4337，基于main f783f19c8，已推、源码clean。三领域#833/#834/#835依赖它。本交接在docs/research-tail-closeout-0921，不在固定源码树。
独立Codex/sol一个session分Spec/Quality两节均PASS；根QC接受PASS_WITH_LIMITS，不当双独立审、不视为合并授权。旧host/容量失败原件保留。

## 未验证 / 已知边界
未独立调真实code-review-graph后端；不签历史/财务/runtime领域功能。后来main f2c3e9e1含#830，未验该组合。未合main/部署。

## 下一步
等待用户合入决策；若更新基座，重验实际组合并补审增量，不移签旧绿。领域独立审容量失败另办。

## 踩过的坑
独立probe首跑SyntaxError是装置错；最终probe只有两条结果且先release Timer，强限额/回调挂起证据来自独立重跑的正式回归。报告末身份命令stdout空，操作员随后回读同SHA/净树；外层未留CLI rc，不补造0。

## 已验证
固定全量12444P/87S/2X，Ruff/四registry/crosswalk0（98既有警告）；前端110P、E2E34P2S，六步0、首尾净树。精确收据20260921T084809Z-ea5c3a94.json。
独立105P/1S、Ruff0、离线probe PASS；events含turn.completed。
封档：`docs/verification/2026-09-21-research-tail-forward/author-and-small-review/`，先读small-sol-review/operator-qc.md。
