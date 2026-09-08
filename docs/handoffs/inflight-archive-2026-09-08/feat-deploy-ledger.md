# feat/deploy-ledger

## 这个分支做什么
W6 部署切换账本：启动自报 startup，链切/rsync 后 switch，`audit check` 对账 health rev。账本落 `FINANCE_WS/state/`（跨快照），不跟 snapshot。

## 当前状态
已提交待合。未推未合。live 未切 8792。

## 未验证 / 已知边界
- 未 kickstart sidecar；未对 8792 跑 `check`
- rsync 脚本仍不换 symlink；真切换是 §4 `ln -sfh` + 新 record 行
- pytest 默认不写账本（除非 `FINANCE_DEPLOY_LEDGER`），防污染夹具

## 下一步
1. 合入后链切：`ln -sfh` 后必跑 record；kickstart 见 startup 行
2. 夜间回检挂 `audit_deploy_ledger.py check`（mock 已覆盖，live 打 8792）
3. G1b 等无关本单

## 踩过的坑
- 账本若写进 snapshot，切一次就丢历史 → 必须 `FINANCE_WS` 优先
- lifespan 抛错 + KeepAlive = 10s 崩溃循环 → 账本 IO fail-open
- `scripts/` 无 `__init__.py`，测试 `sys.path` 插入仓根再 import

## 已验证
`pytest intelligence/tests/test_deploy_ledger.py` 13 passed @ b42a82d6 dirty。layer_audit ERROR 0。ruff 绿。收据 `20260819T080959Z-b42a82d6`。

## 工具沉淀盘点
`scripts/audit_deploy_ledger.py` → `~/harness-reference/TOOLKIT.md` A 档（exit-code，夜间可挂）。不另建清单。
