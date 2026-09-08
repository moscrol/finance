# fix/deploy-ledger-port-check

## 这个分支做什么

W6 部署账本的 `check` 按端口过滤账本行。修的失败形状（2026-08-19 实测）：
账本是全端口共用的（sidecar 也自报 startup），`last_relevant_row` 取「最后一行」不分端口，
8796 sidecar 的启动行把 8792 生产对账顶成假 `rev_mismatch`（exit 1）。

## 改动

- `intelligence/runtime/deploy_ledger.py`：`last_relevant_row` / `check_against_health` 加可选 `port` 参数。
  `port=None` 的行（旧版 switch 未记端口）计入任何端口——宁可误报生产切换，不因缺字段漏报失败的重启。
- `scripts/audit_deploy_ledger.py`：`check` 从 `--url` 推导端口传入；报告新增 `port` 字段。
- 测试 +3：sidecar 行过滤（复现现场）、portless 行计入任何端口、CLI 从 URL 推导端口。

## 已验证

- `pytest intelligence/tests/test_deploy_ledger.py`：16 passed（收据 `20260819T152323Z-72b99d99.json`）。
- live 复验：`FINANCE_WS=主仓 check` 对 8792 实跑，修复前 `rev_mismatch` exit 1，修复后
  `ok=true`（尾行正确落在 8792 startup `30f98d73`，忽略同账本里 4 条 8796 行）。

## 边界

- 不改写入侧：`deploy_workbench_runtime.sh` 现版已带 `--port`，旧行的 `port:null` 靠兼容规则消化。
- 未合未推（等用户确认合并）。
