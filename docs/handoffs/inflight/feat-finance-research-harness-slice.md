## 这个分支做什么

把研究 harness 原型撤回正式入口，补工具结果/计算准入；不新造循环、权限或验证器。

## 决策与被否方案

- 正式 `ResearchToolRegistry` 准入 / 否未接线原型：避免两套规则。
- 失败证据清除、诊断单独保留 / 否按日期捞回：诊断不证明事实。
- 合法子集要求 `partial` / 否把 `parse_error` 当部分成功：producer 必须声明资格。
- 未知状态 fail-closed / 否默认成功：固定公开码且不泄露私有 trace。
- 既有精确计算错误码优先 / 否通用码遮蔽：保持兼容。

## 当前状态

已提交 `07f4523b8063df3be4c75347855728e07f9b7d8c`，树干净，未 push、未合并、未部署。决策与完整收据见 `docs/handoffs/2026-10-05-research-harness-rebuild.md`。

## 已验证

完整 Python：20501P/0F/0E/75S/2X；Ruff与全范围收据校验通过。前端 install/lint/typecheck/Vitest/build/E2E 全绿（210 Vitest，52 E2E+2S）。六组变异均撤保护变红、恢复变绿；194条历史诊断定向回归通过。

## 未验证 / 已知边界

未验证 GitHub Actions、真实 CLI/Workbench、真实 provider/自然模型答案、生产服务 revision、财务语义质量；语义 judge 仍默认 off。Python/前端都是本机收据，不能替代部署验收。

## 下一步

用户确认后再 push/开 PR；以新 revision 重取 CI 与真实入口收据，随后另做合并/部署验收。若继续改代码，先重跑绑定新 SHA 的全量门禁。

## 踩过的坑

完整收据必须看 `revision`、解释器、依赖指纹、dirty 和 collected 对账；定向绿不能覆盖全量结论。历史失败状态夹具不能暗示部分证据，合法子集要显式 `partial`。不要把脚本 judge、结构 verifier 或变异绿读成自然模型质量。
