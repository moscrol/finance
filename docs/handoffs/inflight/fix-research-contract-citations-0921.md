## 这个分支做什么
离线修研究清单、逐项回执、公开 E 身份与有限修复；固化语义反例。不重跑三题、不调模型、不动 8792。

## 决策与被否方案
- 复用 `MaterialContract.questions/qN` 与完整账本 E 号；不另造身份或按公开列表重编号。
- 清单限研究引导+独立标题+连续顶层编号；不把材料/引用当指令。
- 回执参与完成判断，漏答与事实拒绝分开；公开稿投影后重验 witness，修复不增权。
- 反例只入评测，不改线上关键词门/提示词；固定回执证明消费者行为，不证明模型能力。
- 合成 K3 的条件漂移标覆盖 partial，不伪造事实拒句；不推广为全部摘要错误的通则。

## 当前状态
本轮新增 benchmark 证据身份适配，提交 `1e2ce06e4`；未 push、合 main 或部署。工作树当前应保持干净。业务固定提交仍 `ba18395ce`，冻结答卷 `adcda94b5e40`，8792 不动。详细决策见 `docs/handoffs/2026-09-22-benchmark-evidence-ordinal-adapter.md`；反例背景见 `docs/handoffs/2026-09-22-research-semantic-counterexamples.md`。

## 已验证
- 全量 Python：`12673 passed / 0 failed / 85 skipped / 2 xfailed`；收据 `~/.finance-runtime/test-receipts/20260921T194841Z-1e2ce06e.json`，干净绑定提交。
- 前端 install/lint/typecheck/test/build/E2E 全通过；组件 `110 passed`，E2E `34 passed / 2 skipped`；收据在 `~/.finance-runtime/reviews/research-contract-citations-0921/frontend-fixed-1e2ce06e4/frontend.json`。
- 注册表四项检查、ledger-spec 对账、pre-commit、Ruff 均通过；对账 98 条反向回指为既存 warning。
- 边界变异 baseline/restored 各77项通过；10个变异均按预期断言失败，源码未变。冻结67文件及Knevo4原件哈希未变。

## 未验证 / 已知边界
- 工程协议绿不等于金融语义绿；无真实模型识别率、独立案例/代码 reviewer verdict、金融外核或自然修复质量。
- K3 位置 witness 仍不证明摘要条件正确；合成证据不是实际取证。真实闭环须新授权、新样本。
- 相对 `gitea/main` behind 5，未做最新主干组合验证；未做生产装配验收。socket audit 也不是通用外呼沙箱。
- 不把本批成绩写成研究规则，不重跑冻结失败，不访问 8792，不接管共享记忆他人改动。

## 下一步
独立审案例与代码；用户确认后再决定推送/合并。若需真实验证，先授权并使用新样本，分开记录事实漏判、语义误杀、任务覆盖和最终状态。

## 踩过的坑
完整证据账本先定 E 号再过滤；benchmark 不能按 hash 重编号。短 SHA 会被 frontend gate 当成不同 revision；门禁须传完整 40 位 SHA。旧67/200P是脏树开发态，不得代签干净提交；工程绿不等于语义绿。
