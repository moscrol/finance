# 研究 harness 准入修复：决策与证据

日期：2026-10-05。本文记录 `feat/finance-research-harness-slice` 的本地修复收口；它不是合并、部署或自然模型质量报告。

## 背景与发现顺序

1. 父提交 `a96c1fef8c21d9a61f226c160d88ea5ea341205f` 新增了 `src/finance_harness/` 原型。初审在合成反例上为 14 失败 / 4 通过，且正常仓根不能导入、没有正式入口；所以没有继续修这套平行循环。
2. 按正式接缝核对 `FinanceResearchHarness`、`ResearchToolRegistry`、`ToolRunResult`、证据账本、派生计算和既有 verifier。原型删除，反例迁到真实工具结果边界；不另造循环、权限系统或验证器。
3. 提交 `72a95fe47` 增加：业务状态与 transport 状态分离；失败/未知/`empty` 夹带证据在入账前隔离；可信诊断独立于事实证据；参数、输入快照和完整计算结果树拒绝非有限/非 JSON 值；保留既有精确错误码和计算身份。
4. 该提交的完整 Python 门禁发现 3 条历史诊断测试失败。原因不是准入闸应放宽，而是夹具把 `parse_error` 伪装成带有合法子集的结果。合同明确为：合法子集必须由 producer 声明 `partial`；`parse_error`/`request_error` 的诊断不能恢复任何事实；截止日过滤仍在 `partial` 之后执行。提交 `07f4523b8` 将测试拆成这三种状态，并补了反向边界。
5. 最终又加入六组可执行变异定义，验证撤掉保护会红、恢复后会绿；前端在同一 revision 上完成全套本地检查。

## 决策与被否方案

| 采用 | 被否 | 理由 |
|---|---|---|
| 沿正式 `ResearchToolRegistry` 准入边界修复 | 保留未接线的 `finance_harness` 平行实现 | 平行规则不会保护真实入口，且会制造两套语义 |
| 失败证据先清除，可信诊断仍可交付为诊断 | 按日期从失败 payload 中捞回“看起来合格”的证据 | 诊断说明失败原因，不证明 payload 中的事实可信 |
| `partial` 明确承载可用子集，`empty`/`stale`/`future_of_cutoff` 保留业务状态 | 把所有非 success 一律当执行异常 | 空结果、陈旧结果和截止越界需要让模型知道边界，不能伪装成同一种错误 |
| 未知 provider 状态 fail-closed 为稳定 `unknown_provider_status` | 未知状态默认成功或把私有状态原文投给模型 | 未知状态无法签发事实资格，私有 telemetry 也不是市场事实 |
| 保留既有具体错误码，再附加 JSON 完整性错误 | 用通用 `result_not_finite_json` 覆盖 `summary_non_scalar` 等稳定码 | 下游/旧调用方依赖精确码；新增检查不能制造兼容回归 |
| 语义判官继续默认关闭 | 用脚本化 judge 宣称自然模型语义质量已通过 | 本轮只证明证据送达、删错、复验接线，不证明模型判断能力 |

## 实测收据

以下是代码提交 `07f4523b8063df3be4c75347855728e07f9b7d8c` 上的收据；本次随后提交的交接文档只补回写，不改变代码。收据均绑定本地干净树 `/Users/a77/finance-clean`、项目解释器 Python 3.12.13、依赖指纹 `e1c50cb821a30f00`；没有用宿主 Python 替代：

- **完整 Python**：revision `07f4523b8063df3be4c75347855728e07f9b7d8c`，Ruff 通过，`20501 passed / 0 failed / 0 error / 75 skipped / 2 xfailed`，收集 20578；收据 `/tmp/finance-harness-rebuild/gate-mka74QL1/pytest.json`。`check_test_receipt.py --require-full-scope --expect-revision 07f4523b8` 已复核可采信。交接文档提交后会再跑一次绑定最终文档 revision 的门禁。
- **前端**：`/tmp/finance-harness-rebuild/frontend-07f4523b8/frontend.json`；install、lint、typecheck、Vitest、build、Playwright E2E 全部 exit 0；Vitest 22 files / 210 tests passed，E2E 52 passed / 2 skipped；起止 revision 一致且树干净。
- **变异**：`/tmp/finance-harness-rebuild/mutations-07f4523b8/results.json`，六组保护变异均 red，恢复后均 green，baseline/restored 各 105 项，`complete=true`、恢复树 clean。变异只验证合同反例，不是独立质量评审。
- **历史诊断定向回归**：194 passed；完整门禁已覆盖该文件。手工 pre-commit、`git diff --check` 及此前层级/生成目录/路径/路由/工具可达性门通过。

## 结论不成立的范围

- 代码仍只在分支本地提交，当前 `07f4523b8` 尚未 push、PR 合并或部署；不能据此说生产服务已生效。
- 没有完成真实 CLI/Workbench 入口、真实 provider 数据真值、自然模型投研答案、金融散文语义质量或真实服务 revision 验收。
- 合成 evidence、脚本化模型和离线 judge 只能证明结构合同与修复路径。`ASK_SEMANTIC_JUDGE` 的生产默认关闭策略未改变。
- 前端收据是本机 Node 22.23.3 环境结果；GitHub Actions 结果仍需在实际 PR 上单独读取。条件 data-quality 门本轮未因路径触发。

## 接手与后续

用户确认后再按 GitHub 协作规则推送/开 PR；任何代码变更后，必须重新生成绑定新 revision 的完整 Python、前端、E2E 和必要 registry 收据。合并/部署另按实际 revision、health、dirty 状态和运行收据验收。Agent Memory 外部仓本轮未修改，避免超出本窗认领路径；项目内正式事实以本文和 inflight 指针为准。
