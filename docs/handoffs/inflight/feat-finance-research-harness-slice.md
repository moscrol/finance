## 这个分支做什么

把研究 harness 原型撤回正式入口，补工具结果/计算准入；不新造循环、权限或验证器。

## 决策与被否方案

- 正式 `ResearchToolRegistry` 准入 / 否未接线原型：避免两套规则。
- 失败证据清除、诊断单独保留 / 否按日期捞回：诊断不证明事实。
- 合法子集要求 `partial` / 否把 `parse_error` 当部分成功：producer 必须声明资格。
- 未知状态 fail-closed / 否默认成功：固定公开码且不泄露私有 trace。
- 既有精确计算错误码优先 / 否通用码遮蔽：保持兼容。

## 当前状态

实现提交07f4523b8；最终受测tip为干净458fd9de3。其后仅有文档/收据归档，不移签旧收据为新HEAD。未push、合并、部署。决策见`docs/handoffs/2026-10-05-research-harness-rebuild.md`；八项承接/原件见`docs/verification/2026-10-05-research-harness-rebuild-results.md`。

## 已验证

458fd9de3：Python20501P/0F/0E/75S/2X，全范围/身份校验过；前端210P、E2E52P/2S，lint/typecheck/build过；registry五项过（101条反链warning）。六组变异均红→绿，恢复105P。a96c1fe历史诊断基线23P，首次3红为新旧合同冲突，不是既有红。

## 未验证 / 已知边界

未验GitHub Actions、真实provider/自然模型研究答案及生产revision；E2E虽启隔离Workbench服务，不证明自然模型质量。语义judge默认off。外部Agent Memory未回写，本轮认领仅finance-clean；跨仓项目索引仍待维护。

## 下一步

先审本地提交；推送/PR另确认，CI须绑定实际候选。真实问题验收另冻结模型/材料/预算；未授权不合并部署。续改代码则重取新SHA完整门禁；文档封存不宣称新HEAD全量重跑。

## 踩过的坑

完整收据必须看 `revision`、解释器、依赖指纹、dirty 和 collected 对账；定向绿不能覆盖全量结论。历史失败状态夹具不能暗示部分证据，合法子集要显式 `partial`。不要把脚本 judge、结构 verifier 或变异绿读成自然模型质量。
