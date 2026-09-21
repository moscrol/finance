## 这个分支做什么
离线修复研究清单保真、逐项回执、公开 E 号身份和有限修复边界；不重跑三题首答、不调用模型、不动 8792。

## 决策与被否方案
- 复用 `MaterialContract.questions/qN`；否决另造要求身份，避免写手、判官和修复链漂移。
- 只有研究引导+独立要求标题+连续顶层编号才识别清单；否决把材料/引用编号当控制指令。
- `explicit_requirements` 只证明送达；`requirement_checks` 才参与完成判断，缺题/缺项/假 witness 一律 fail-closed。
- 漏答与事实拒绝分开；否决用漏答覆盖事实失败或凭零证据补写。
- 最终公开投影后重验 witness；否决沿用旧草稿回执。
- 清单修复复用既有 admission，不增加工具、调用、时间或零证据权限。
- 完整证据账本先定 E 号再过滤；否决按公开列表位置重编号。

## 当前状态
代码与测试已提交：`ba18395ce`。工作树干净，分支未 push、未合 main、未部署；生产 revision `adcda94b5e40` 与本枝不同。完整背景与方案对比见 `docs/handoffs/2026-09-21-research-contract-requirement-receipts.md`。

## 已验证
- 固定提交定向回归：`1787 passed / 4 skipped / 0 failed`，收据 `~/.finance-runtime/test-receipts/20260921T163733Z-ba18395c.json`。
- 回执/投影/修复预算反向验证：基线与恢复各 `77 passed`，十组保护点均按预期触发断言，`complete=true`、`source_unchanged=true`。
- 只允许测试进程自建 loopback 临时服务的重入测试：`4 passed / 1 xfailed`；未访问 8792。
- Ruff、`git diff --check`、pre-commit 门禁通过。

## 未验证 / 已知边界
- 回执 witness 只证明回答位置被保留，不证明公司集合、`2+2+1`、A/B 各三信号、正反/第三解释、分母、期间或阈值语义正确。
- 未调用真实模型、未拿到本批 Knevo 原答，不能作三方优胜或自然质量结论。
- 未跑全仓 pytest、前端/E2E、跨仓 registry、独立审核；未验证生产装配和部署效果。
- 冻结首答、8792、数据库事实和生产运行记录均未改写。

## 下一步
先补独立审核与完整合入门禁，再等用户确认合并；本批 Knevo 原答待用户提供后做独立对照。真实模型复验须新授权样本，不重跑冻结首答。

## 踩过的坑
工程绿不等于金融质量绿；`requirement_checks` 的结构完整性不能替代语义判官。交接收据必须绑定提交 SHA，不能用旧 `8a892290d` 的测试读数代签 `ba18395ce`。
