## 这个分支做什么

把研究 harness 原型撤回正式入口，补工具结果/计算准入；不新造循环、权限或验证器。

## 决策与被否方案

- 正式 `ResearchToolRegistry` 准入 / 否未接线原型：避免两套规则。
- 失败证据清除、诊断单独保留 / 否按日期捞回：诊断不证明事实。
- 合法子集要求 `partial` / 否把 `parse_error` 当部分成功：producer 必须声明资格。
- 未知状态 fail-closed / 否默认成功：固定公开码且不泄露私有 trace。
- 既有精确计算错误码优先 / 否通用码遮蔽：保持兼容。
- 并入 main 用合并提交 / 否 rebase：a96c1fe 已推送，rebase 要强推。

## 当前状态

已合入 #59（main `d5d7c5f6017e`，树与 PR 头 `3826f011a` 相同）；10-06 14:38 CST 已切 8792 并验收，回执 `docs/verification/2026-10-06-cutover-post59.md`。本分支不再续改，新工作从最新 origin/main 另开。决策见 `docs/handoffs/2026-10-05-research-harness-rebuild.md`。

## 未验证 / 已知边界

真实 provider 数据真值、自然模型投研质量未验收；长电探针 n=1，只证明链路通、该题数字对。白名单外状态一律清证据：新 producer 若用新状态串会被静默判失败（现有 20 处 `ToolRunResult` 构造点已核对）。main 推送 CI 汇总任务因 GitHub 账单未启动，修好后 `gh run rerun 37422443444 --failed`。语义 judge 默认 off。

## 下一步

真实问题验收另冻结模型/材料/预算。修好 GitHub 账单后补跑 main 汇总检查。新增工具状态值时同步 `provider_observability` 白名单与反例测试。

## 踩过的坑

完整收据必须看 `revision`、解释器、依赖指纹、dirty 和 collected 对账；定向绿不能覆盖全量结论。合并后 main 是新提交号，旧收据不移签，批次门禁须在 main tip 重跑。合法子集要显式 `partial`。不要把脚本 judge、结构 verifier 或变异绿读成自然模型质量。

## 已验证

PR 头 `3826f011a` 与 main tip `d5d7c5f6`：Python 20693P/0F/0E/75S/2X，collected 对平，`--require-full-scope`、`--expect-revision origin/main` 均 exit 0；前端 210P、E2E 52P/2S；registry 5 项过；PR CI 五项全绿。8792：readiness 13/13、health 三读、账本 check、长电探针（判官 passed、degrade 0、数字与库一致）。旧底座 `458fd9de3` 的收据与变异见 `docs/verification/2026-10-05-research-harness-rebuild-results.md`。
