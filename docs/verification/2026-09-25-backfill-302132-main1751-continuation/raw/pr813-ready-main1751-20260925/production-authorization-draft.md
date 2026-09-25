# #83 / PR813 受控生产执行草案

状态：未授权、未执行。本草案不触发写入，不重启 8792，不修改 launchd。

## 固定范围

- 代码候选：`ae3f812e1c1e142953b657ba41f30fce23e7c14a`，整合基线 `1751e21e0fd30642e0b223604b64b30e38c46f41`。
- 仅 `302132.SZ`，`2026-06-15..2026-09-11`；53 INSERT、06-23 空壳 UPDATE，09-11 主表钉值及其余保护行不变。
- 冻结尾段 parquet：`/Users/a77/.finance-runtime/reviews/pr813-ready-main1751-20260925/rehearsal/frozen.parquet`，SHA256 `51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17`。
- 本轮演练的原库 SHA256 为 `5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`，不是未来生产授权的自动有效基线。执行前必须重新冻结、验鲜和确认输入未变。

## 待逐字授权的父命令

只有独审、工程门禁、PR 合并授权分别成立后才可申请生产授权。执行树必须保持下列完整 revision 且干净；如执行树换成合并后的新快照，命令和代码身份需重新列入授权，不移签旧收据。

```bash
cd /Users/a77/fwp-wt-backfill-ready-main1751-0925
MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb MARKET_FEATURE_STORE_PRODUCTION_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m market_feature_store.cli repair-backfill-302132 --parquet /Users/a77/.finance-runtime/reviews/pr813-ready-main1751-20260925/rehearsal/frozen.parquet
```

不附带父模式 `--db`，不直接调用 child，不手工写生产 SQL。生产 CLI 没有 `--record` 参数；授权来源、完整命令、日期范围、冻结输入和基线写独立授权 JSON。

## 本轮备份与验收

父编排先在 staging 写入，通过子验收后、发布前取得本轮 pre-swap backup。必须从本轮 `market_feature_store.duckdb.repair-backfill-execution.<run_id>.json` 读取 `backup.backup_path` 和 `backup.backup_sha256`；不得拿演练备份、旧 run 的备份或“最新文件”代替。未来 run_id 尚未生成，不能编造一个已存在的父备份。需要预先确认固定回滚文件名时，先单独冻结本轮审批备份，再申请授权。

生产后再运行 verify-only 父命令，外部验收脚本以本轮父备份作为 `--production` 不可变基线、实际生产库作为 `--clone`，绑定真实 apply/verify run_id 和代码完整 SHA。必须达到主表 64 行且 close/pct_chg/amount 各 64 非空，technical 39、window 161，并保持保护行全列多重集不变。

## 待授权回滚模板

下列模板尚不具备可执行的备份身份，不能直接运行。先确认无活跃读写者、无夜跑换库、无须保留的后续业务写入；发现 WAL 停下，不删除。恢复前再次核对本轮父收据、备份哈希和目标身份。

```bash
BACKUP='<本轮生产父收据 backup.backup_path>'
EXPECTED_SHA='<同一收据 backup.backup_sha256>'
PRODUCTION=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
RESTORE=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb.authorized-302132-restore
[ -f "$BACKUP" ] && [ ! -e "$RESTORE" ] && [ ! -e "$PRODUCTION.wal" ] && [ "$(shasum -a 256 "$BACKUP" | awk '{print $1}')" = "$EXPECTED_SHA" ] && cp -c "$BACKUP" "$RESTORE" && mv "$RESTORE" "$PRODUCTION"
```

回滚只恢复本轮已确认的数据库备份，不是第二条回填写入通道。恢复后核对完整 SHA 与本轮审批基线相同。
