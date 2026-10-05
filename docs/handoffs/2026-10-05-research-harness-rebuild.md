# 研究 harness 准入修复：决策与证据

日期：2026-10-05。本文记录 `feat/finance-research-harness-slice` 的本地修复收口；它不是合并、部署或自然模型质量报告。

## 背景与发现顺序

1. 父提交 `a96c1fef8c21d9a61f226c160d88ea5ea341205f` 新增了 `src/finance_harness/` 原型。初审在合成反例上为 14 失败 / 4 通过，且正常仓根不能导入、没有正式入口；所以没有继续修这套平行循环。
2. 按正式接缝核对 `FinanceResearchHarness`、`ResearchToolRegistry`、`ToolRunResult`、证据账本、派生计算和既有 verifier。原型删除，反例迁到真实工具结果边界；不另造循环、权限系统或验证器。
3. 提交 `72a95fe47` 增加：业务状态与 transport 状态分离；失败/未知/`empty` 夹带证据在入账前隔离；可信诊断独立于事实证据；参数、输入快照和完整计算结果树拒绝非有限/非 JSON 值；保留既有精确错误码和计算身份。
4. 该提交的完整 Python 门禁发现 3 条历史诊断测试失败。原因不是准入闸应放宽，而是夹具把 `parse_error` 伪装成带有合法子集的结果。合同明确为：合法子集必须由 producer 声明 `partial`；`parse_error`/`request_error` 的诊断不能恢复任何事实；截止日过滤仍在 `partial` 之后执行。提交 `07f4523b8` 将测试拆成这三种状态，并补了反向边界。
5. 最终又加入六组可执行变异定义，验证撤掉保护会红、恢复后会绿；以实现提交 `07f4523b8` 为代码验收点、以仅补交接文档后的 `458fd9de3` 为最终复验点，重新完成 Python、前端、E2E、注册表和变异检查。

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

收据分两层：`07f4523b8` 是最后一个实现代码提交；`458fd9de3` 是只增加两份交接文档后的干净 tip，也是最终完整复验绑定的 revision。后续本页、八项承接和原始证据归档仍只改文档，不把文档提交移签成已全量重跑的代码版本。收据均绑定本地干净树 `/Users/a77/finance-clean`、项目解释器 Python 3.12.13、依赖指纹 `e1c50cb821a30f00`；没有用宿主 Python 替代：

- **最终完整 Python**：`458fd9de3c13f4293587f969bc733e136079ef53`，Ruff 通过，`20501 passed / 0 failed / 0 error / 75 skipped / 2 xfailed`，收集20578；收据 `/tmp/finance-harness-rebuild/gate-HFDkHJlM/pytest.json`，`check_test_receipt.py --require-full-scope --require-target /Users/a77/finance-clean --expect-revision 458fd9de3c13f4293587f969bc733e136079ef53` exit 0。
- **前端**：`/tmp/finance-harness-rebuild/frontend-458fd9de3/frontend.json`；install、lint、typecheck、Vitest、build、Playwright E2E 全部 exit 0；Vitest 22 files / 210 passed，E2E 52 passed / 2 skipped；起止 revision 一致、树干净。
- **变异**：`/tmp/finance-harness-rebuild/mutations-458fd9de3/results.json`；六组撤保护均按预期变红，恢复后均变绿，baseline/restored 各105项，`complete=true`、恢复树 clean。变异只验证合同反例，不是独立质量评审。
- **注册表**：本地同款五项检查全部 exit 0；台账反向链接仍有101条既有 warning，未改规则、未当作零警告。
- **历史诊断基线**：在独占干净 `a96c1fef` 上单独跑旧文件为23 passed；72的3红是新准入合同暴露的夹具混用，不是旧基线红。最终相关定向回归194 passed。
- 手工 pre-commit、`git diff --check`、层级/生成目录/路径/路由/工具可达性门均通过；初次文档 hook 缺 `FWP_WORKBENCH_PYTHON` 的环境错误已按同一解释器修正重跑，不是缺包或绕过门禁。

初审八项的正式承接和收据原件见 [最终复验与承接](../verification/2026-10-05-research-harness-rebuild-results.md)；原始日志/JSON 已归档并带 SHA-256 manifest。归档是证据封存，不代表复制时重新执行。

## 结论不成立的范围

- 仍只在分支本地提交；未 push、开 PR、合并或部署，不能说生产服务已生效。当前全量受测对象是 `458fd9de3`；其后的文档/证据提交不改变代码，不能冒充新 revision 的全量门禁。
- 没有完成真实 CLI/Workbench 自然模型投研、真实 provider 数据真值、金融散文语义质量或生产服务 revision 验收。前端 E2E 是隔离服务测试，不是生产用户实跑。
- 合成 evidence、脚本化模型和离线 judge 只能证明结构合同与修复路径。`ASK_SEMANTIC_JUDGE` 的生产默认关闭策略未改变。
- 前端收据是本机 Node 22.23.3 环境结果；GitHub Actions 结果仍需在实际 PR 上单独读取。条件 data-quality 门本轮未因路径触发；Python有17条warning，不能说零警告。

## 接手与后续

用户确认后再按 GitHub 协作规则推送/开 PR；CI、真实入口、合并/部署另按实际 revision、health、dirty 状态和运行收据验收。若再改代码，必须绑定新 SHA 重取完整 Python、前端、E2E 和必要 registry 收据；文档-only更新不移签旧收据。Agent Memory 外部仓本轮未修改，避免超出本窗认领路径；项目内正式事实以本文、最终复验页和 inflight 指针为准。
