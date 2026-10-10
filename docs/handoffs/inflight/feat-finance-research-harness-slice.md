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

已合入 #59（main `d5d7c5f6017e`，树与 PR 头 `3826f011a` 相同）；10-06 14:38 记录切到 8792，历史完整验收有证据缺件，见 `docs/verification/2026-10-06-cutover-post59.md` 的 10-07 补查。本分支不续改，新工作从最新 origin/main 另开。决策见 `docs/handoffs/2026-10-05-research-harness-rebuild.md`。

## 未验证 / 已知边界

真实 provider 真值、自然模型投研质量未验收；长电探针 n=1。白名单外状态清证据，新 producer 状态串须同步白名单。d5 历史汇总受账单阻断；10-07 当前 ea217 的 main CI 已绿。切换 readiness / 三份 health 原件缺失；旧完整模型准入 exit 2，候选解析器重读原件 exit 0，不代表修复已部署。语义 judge 默认 off。

## 下一步

真实问题验收另冻结模型/材料/预算。新部署留齐原始切换与三读产物。新增状态值时同步 `provider_observability` 白名单与反例。

## 踩过的坑

完整收据必须看 `revision`、解释器、依赖指纹、dirty 和 collected 对账；定向绿不能覆盖全量结论。合并后 main 是新提交号，旧收据不移签，批次门禁须在 main tip 重跑。合法子集要显式 `partial`。不要把脚本 judge、结构 verifier 或变异绿读成自然模型质量。

## 已验证

历史 PR 头 `3826f011a` / main `d5d7c5f6`：Python 20693P/0F/0E/75S/2X，full-scope 对账通过；复核绑定完整 d5 SHA，不用浮动 origin/main。前端210P、E2E52P/2S、registry过、PR CI齐绿。部署记录称 readiness13/13、health三读；原件未留齐。账本与长电产物保留，10-07 完整模型准入复核收据见回执。旧底座收据见 `docs/verification/2026-10-05-research-harness-rebuild-results.md`。
