# Benchmark 公开证据编号适配（2026-09-22）

## 背景

全量 Python 门禁发现 `test_run_agent_runtime_benchmark.py::test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 在本分支回归：生产公开引用开始保留完整证据身份，同标签但不同证据不再被错误合并；benchmark 仍按旧的“标题/来源/日期唯一”假设断言一条引用。另查出 benchmark 的 blind projection 会把绑定证据按 hash 排序后重新编号，过滤首条证据后可能把正文 `E2` 错映射成 `E1`。

## 选择与被否方案

- 选择让 `RuntimeArmResult` 兼容并保留公开 `evidence_id`，只接受 `E1..E999`，继续丢弃 `content_hash` 等内部字段；否了继续只存三元标签，因为它无法表达同标签不同证据的身份。
- 选择让 `_runtime_sources` 使用 `evidence_ordinal_table(outcome.evidence)`，按完整账本首次出现顺序去重；否了按 hash/tool/date 排序后从 `E1` 重编号，因为过滤后会破坏正文、公开引用和数值 claims 的绑定。
- 选择只把 benchmark 旧测试改成真实公开投影语义；否了撤回生产身份修复或把固定输入硬编码为单条引用，因为那会重新打开已修复的证据混淆风险。

## 验证

- 提交 `1e2ce06e4a9c300b23e5f0458cc087ed66fcea7f`，pre-commit 全部通过。
- 全量 Python：`12673 passed / 0 failed / 85 skipped / 2 xfailed`，收据 `/Users/a77/.finance-runtime/test-receipts/20260921T194841Z-1e2ce06e.json`，`dirty=false`。
- 前端门禁完整通过：pnpm install、lint、typecheck、组件测试、build、E2E；组件 `110 passed`，E2E `34 passed / 2 skipped`，收据 `/Users/a77/.finance-runtime/reviews/research-contract-citations-0921/frontend-fixed-1e2ce06e4/frontend.json`。
- 注册表 parseability/check/backfill/generate-views 与 ledger-spec crosswalk 均 exit 0；crosswalk 的 98 条反向回指是既存 warning。
- 边界变异收据 `/Users/a77/.finance-runtime/reviews/research-contract-citations-0921/boundary-probes-1e2ce06e4/results.json`：baseline/restored 各 77 项通过，10 个变异均在预期断言处失败，`source_unchanged=true`。

## 限制

这些是工程协议和回归结论，不是金融语义验收。分支未推送、未合并、未部署；相对 `gitea/main` 仍 behind 5，未做最新主干组合验证。真实模型识别率、独立 reviewer verdict、金融事实外核和生产 8792 装配仍未验证；冻结三题、原件、配置和生产服务保持不动。
