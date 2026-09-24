# 302132 生产回填授权稿（未执行，未获授权）

本稿只供核对。合入 #813 不等于授权执行。执行前必须将用户逐字原话、消息来源、最终代码 SHA、完整命令、范围、冻结输入 SHA、换库前基线 SHA 和回滚点写入执行记录；不能用本稿冒充用户原话。当前 CLI 不接受 `--record`，该标志属于 `scripts/gitea_pr.py merge` 的合入记录，生产授权须另存 JSON，不能把未知参数传给父命令。

## 固定范围

- 仅 `302132.SZ`；主表 INSERT 53 个授权缺失日（并跑源 51 日，冻结 parquet 的 09-09/09-10 两日），UPDATE 2026-06-23 空壳。
- 数据窗口为 2026-06-15 至 2026-09-11；09-11 钉值保留。重建窗内 technical/window，不改其他股票、目标股窗外行或其时间戳。
- 冻结 parquet SHA256：`51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17`。
- 09-24 ca4 副本演练的生产基线 SHA256：`5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`。这是历史观测，不保证未来仍是该值；生产前重新冻结、核对漂移并请用户确认。

## 待授权命令

当前固定候选为 `ca4b33316c47862ecd3ec71a535a51d540ada986`，作者四叶工程门禁及本版本整库演练已通过，#75 独立审查和用户授权仍待完成，尚不可执行生产回填。完成审批并取得逐字授权后，从固定候选树执行父命令；任务分支的后续交接提交不是被验版本。候选 SHA 若变化，先更新验收与授权稿，不能移签旧收据。不能加父模式 `--db`，也不能直接调子模式。

```bash
cd /Users/a77/.finance-runtime/reviews/backfill-302132-0923/forward-01/tree && \
  test "$(git rev-parse HEAD)" = ca4b33316c47862ecd3ec71a535a51d540ada986 && \
  test -z "$(git status --porcelain)" && \
  MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m market_feature_store.cli repair-backfill-302132 --parquet /Users/a77/.finance-runtime/reviews/backfill-302132-0923/rehearsal-b9b59a9a/frozen.parquet
```

## 回滚点与回滚命令

真正的回滚点只能取本次父收据 `backup.backup_path` 和 `backup.backup_sha256`，不能取“最新一个备份”或演练备份。父命令在原子替换前自动生成该备份；执行授权须明确允许以该带本轮 run_id 的备份为回滚点。若要求预先写死绝对文件名，应先在无活跃写者时只读冻结一个新的审批基线，再把其绝对路径和 SHA 写入最终授权卡。本稿不编造未来 run_id。

下面是待填入本轮真实备份后的模板，**不是现在可执行的授权命令**：

```bash
BACKUP='<本轮生产父收据中的 backup.backup_path>'
EXPECTED_SHA='<同一父收据中的 backup.backup_sha256>'
PRODUCTION=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
RESTORE=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb.authorized-302132-restore
[ -f "$BACKUP" ] && [ ! -e "$RESTORE" ] && [ ! -e "$PRODUCTION.wal" ] && [ "$(shasum -a 256 "$BACKUP" | awk '{print $1}')" = "$EXPECTED_SHA" ] && cp -c "$BACKUP" "$RESTORE" && mv "$RESTORE" "$PRODUCTION"
```

前提：已单独确认回滚授权、无活跃读写者、无夜跑换库、回填后未产生应保留的新业务写入。出现 WAL 必须停下调查，不能直接删 WAL。恢复后核对完整 SHA 与只读值审计。不得为执行本稿自行重启 8792、调整 launchd 或扩到其他股票。
