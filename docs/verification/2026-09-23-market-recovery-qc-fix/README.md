# 行情恢复 QC 修复验证

## 身份与范围

- 代码分支：`fix/market-recovery-qc-0923`。
- 代码提交：`4fa70046f`（F1/F2/F3）、`981c4d629`（尝试日志与重试保留）。
- 原组合基座：`c57a4d019bd0bfa0a8f552590ec13f8ef4349de0`，含 PR #861/#871。
- 最新定向验证基座：`gitea/main@5f35da1723f74663a4803c4d1490c402a1d6db40`。
- 组合预览提交：`44a82a4eb883e5e71dec60baa2e4ad82e17eae3a`。
- 组合 tree：`9e23a5d3c227cbeb698b68a3da1c6b01368a8e1a`。
- 干净验证树：`/Users/a77/fwp-wt-market-recovery-qc-preview-0923`。
- 解释器：主检出树 `.venv-workbench/bin/python`。

组合通过 `git merge-tree --write-tree` 构造，无冲突；临时提交没有移动 main，也不是 PR 合并、推送或部署。

## 修前反例

| 收据 | 结果 | 含义 |
|---|---|---|
| `20260923T043306Z-c57a4d01-89fadf999a3e.json` | 55 passed / 18 failed | 仅新增测试、业务代码未修：旧计划覆盖、缺 canonical bar、实际 local 接线和新 CLI 守卫等断言失败 |
| `20260923T044719Z-4fa70046-182deb6d7074.json` | 1 failed | 尝试结果在内存中，但实际 runlog 丢失来源失败记录 |
| `20260923T044816Z-4fa70046-e84c8fee9cf5.json` | 27 passed / 1 failed | runlog 修复后，重试仍覆盖前一轮尝试；最终补丁合并尝试历史 |

这些红收据的 dirty_paths 是当时新增的测试，属于本地红绿对照，不是可移植的准入收据。失败来自实际断言或新 CLI 尚不存在，不把测试退出码 1 误读成修复已经通过。

## 最新组合定向结果

`targeted-receipt.json`：**429 passed / 1 skipped / 0 failed / 0 error**，完整执行指定的 16 个测试文件，不是全仓 pytest。跳过项是显式 opt-in 的 `test_real_codex_headless_smoke`，本轮未授权真实模型调用。

`targeted-receipt-check.txt`：revision、解释器、依赖指纹、干净树、收集与执行数量均一致；校验时基座漂移 0。

```bash
cd /Users/a77/fwp-wt-market-recovery-qc-preview-0923
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_bridge_hithink_stock_daily.py \
  tests/test_compute_local_stats.py \
  tests/test_review_sync_hithink_wiring.py \
  tests/test_consumption_registry.py \
  tests/test_review_plan_alignment.py \
  tests/test_recovery_refresh_integration.py \
  tests/test_recovery_coverage.py \
  tests/test_audit_recovery_metadata.py \
  tests/test_hithink_recovery_candidate.py \
  tests/test_hithink_stock_preview.py \
  tests/test_mootdx_source_health.py \
  tests/test_write_path_guard.py \
  tests/test_daily_full_preflight.py \
  tests/test_review_sync_export_release.py \
  tests/test_review_sync_sw_l1_timeout.py \
  intelligence/tests/test_codex_headless_runtime.py --tb=short
```

静态检查也在该组合树执行：

| 检查 | 证据 | 结果与范围 |
|---|---|---|
| `python -m ruff check .` | `ruff.txt` | 全仓通过 |
| `python -m market_feature_store.cli registry-check` | `registry-check.txt` | 消费注册表通过，local 的顺序与实现一致 |
| `python scripts/build_registry.py check` | `build-registry-check.txt` | 本仓通过；知识库不在该预览环境，跨仓项明确跳过，不代签跨仓登记 |
| `python scripts/build_registry.py check-parseability` | `parseability.txt` | 该预览树中的 39 个 SKILL.md 可解析 |

## 两项沙箱失败的路径对照

对照提交固定为 `a7a9635d523f3255da6c750f39753666277145b2`，基座是此前 `4315d9d5`。与最新预览之间只有主线文档变化。

| 探针 | `/tmp/qc-market-recovery-fix-4315d9d5` | `/Users/a77/fwp-wt-market-recovery-qc-preview-0923` |
|---|---|---|
| public_tcp | denied | denied |
| loopback | denied | denied |
| unix_socket | denied | denied |
| live_root_read | unexpected_success | denied |
| status | unproven | proven |

原件：`qc-market-recovery-sandbox-tmp.json`、`qc-market-recovery-sandbox-users.json`。

两项正式测试在同提交的 `/Users` 树为 **2 passed**，见 `20260923T045253Z-a7a9635d-371007f639f9.json` 和 `sandbox-receipt-check.txt`；在最新组合的 429 项中也通过。没有删除测试、修改沙箱实现、放宽断言或增加权限。

结论只限当前 Codex `0.155.0-alpha.9.2` / macOS 环境：临时目录内的仓库被 minimal 文件读取权限覆盖，不符合该测试对 live repository 的拒读前提。不能把 `/tmp` 下的两条红灯归因于行情补丁，也不能把本次两项转绿当全仓门禁通过。后续验证树应放在 `/Users` 下。

## 较早基座的扩大回归

在 `a7a9635d5` 的干净 `/tmp` 组合树执行：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests intelligence/tests/test_codex_headless_runtime.py --tb=short
```

结果：**2631 passed / 63 skipped / 2 failed**，2696 项已全部收执对账，耗时 742.39 秒。失败仅为上文两条路径相关沙箱测试，根目录 `tests/` 没有失败。见 `broader-receipt.json`、`broader-tests.txt`、`broader-receipt-check.txt`；收据可采信，但仍是红收据。

该命令没有覆盖其余 intelligence 测试，不是全仓 pytest；其基座也不是最新定向验收的 `5f35da17`。两个预览间仅主线两份文档变化，但仍分别保留收据，不拼成一张全仓绿色门禁。PID 72293 已退出，无遗留本轮测试进程。

## 仍不成立的结论

- 没有最新组合的全仓 pytest 绿色收据，未独立验收，不放行合并。
- 没有运行实际 nightly、数据库 staging、换库或生产写入；内存/临时数据库的回归不代签生产恢复。
- 没有决定 5553/5565 范围、三份合同、五问或 53 只除权/送转缺口。
- F2 仅加固显式 `recovery_members` 模式，未擅自启用恢复参数或改写默认分母；恢复 CLI 的参数合同仍待确认。
- F3 复核目标日存在性与覆盖策略；不是完整输入指纹、签名计划或任意并发调度认证。
- 不认证供应商全集、未知停牌声明、分红差异、名称/换手率来源或 mootdx 部分 flush 合同。
- 未改前端，前端/E2E 不适用本次补丁；跨仓注册检查的跳过必须保留。
