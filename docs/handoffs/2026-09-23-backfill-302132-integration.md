# #83：302132 回填整合与副本验收

记录时点：2026-09-23 13:27Z。此文是决策快照，不把未来测试预写为通过。
当前门禁状态只看仓外 `~/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json` 及其指向的原始收据；必须匹配 PR #813 的实际 head。本文中的 b9b59a9a 读数不得移签后续提交。

## 背景与范围

工单：`docs/superpowers/specs/2026-09-23-backfill-302132-acceptance-integration-workorder.md`。
主树为他人脏树，本轮只在 `/Users/a77/fwp-wt-backfill-302132-0923`、分支 `fix/backfill-302132-0923` 工作。
从 `gitea/main@626d8a508c1c988ff094110b371987e6afdcdd15` 整合 #813 原 head `5994230dadcf23ec0a17c0b27e3a649d782ecf94`，合并提交 `10642b9af69a72e1203b23cdf8e40a3564db6d0b`，无冲突。
源码修复提交 `b9b59a9afa001f036d98baa6b9a19bd9f9b48e34` 已推进 #813，保留 WIP。

只处理 302132.SZ 原合同：2026-06-15 至 09-11 窗口，53 INSERT + 06-23 空壳 UPDATE，重建窗内 technical/window。未执行生产回填、未合入 main、未重启 8792、未改 launchd、未补其他股票。

## 发现与决策

1. 初始整合的旧定向集 105P。只读查生产后发现目标股已有 09-21/09-22 合法行情，旧验收器却要求窗外空集，还把窗外行计入窗内保留行数。
2. 新增正常窗外行及 amount/delete/insert/timestamp 四种变异测试，得到预期红灯；改为窗内保留行限定窗口，窗外做全列双向 EXCEPT ALL，时间戳也在比较内。
3. 并跑源表已覆盖到 09-22，旧缺口护栏把应由冻结 parquet 供应的 09-09/09-10 又算进并跑缺口。新增来源推进且后续 amount 不同的测试，先复现拒跑 `(26,2)`，再把并跑计数上界固定到 `max(gap_parallel)`，仅用 `adjusted='none'`。
4. 新增 `scripts/review_probes/rehearse_302132_backfill.py`：干净提交、新建仓外目录、原始 parquet 哈希、无 WAL/只读锁快照；两轮父命令、独立验收、异常数值对照、真实父备份恢复、生产前后身份及完整 SHA 核验。只有全通过才删除本次创建的整库副本，保留报告/冻结 parquet/manifest；失败保留现场，超时终止自己启动的进程组。

| 方案 | 评价 | 结果 |
|---|---|---|
| 要求目标窗外始终无行 | 与正常日更冲突，会拒收不越权的历史回填 | 否 |
| 不检查目标窗外数据 | 无法发现越界增删、值变化、时间戳改写 | 否 |
| 窗外全列双向差集为零 | 允许已有合法日线，仍严格保护窗口外 | 采用 |
| 随源表增长扩大 gap_parallel | 改变授权写入来源与键集 | 否 |
| 固定来源分段边界 | 后来的采集不能替换已批准的冻结输入 | 采用 |
| 沿用 #813 旧收据给新提交背书 | revision/基线/真实输入身份均不相同 | 否 |
| 原位复制生产库做演练目标 | 有混淆或覆盖生产的风险 | 否；只在新建隔离目录克隆 |

## 已完成的证据（仅 b9b59a9a）

证据根：`/Users/a77/.finance-runtime/reviews/backfill-302132-0923/`。

- `focused-gate.log.txt` / `focused-receipts/gate-kkAhvMnD/pytest.json`：全仓 ruff 通过，定向 118P/0F，91.92s，`dirty=false`。一轮迭代测试曾在 120s 工具上限中断，不计为通过。
- `registry-b9b59a9a.log.txt`：finance-only 注册表通过，跨仓缺席项明确跳过。
- `merge-tree-b9b59a9a.json`：对冻结 main 的预合并干净。
- `rehearsal-b9b59a9a/summary.json`：完整库副本演练 `ok=true`，apply=`c153700e86f8`，verify=`422500332011`。
- 错误 parquet：父命令 rc2，副本未发布、无换名前备份；apply/verify 各 rc0；独立验收 37 检查全部通过；注入 amount=1e15 后 rc2，唯一失败项 `keyset_fullfield_oracle`。
- 窗内从 11 行（close/pct_chg/amount 各 10 非空）到 64 行（各 64 非空），三元值相邻整行相同日期为空；technical=39，window=161（5/10/20/60 日分别 59/54/44/4）。他股、窗外与源表全列双向比较通过。
- 冻结 parquet：`51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17`。
- 冻结生产基线及恢复副本 SHA：`5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`。
- 演练前后生产 size=3855626240，mtime_ns=1790168645608937291，inode=216161353，完整 SHA 与各 fact_* 最新日期不变。夜跑此前曾改变生产 mtime，因此没有沿用开工时的 stat，使用本轮重新冻结的观测。
- 四个整库演练文件已按工单删除，摘要列出删除前完整 SHA；冻结 parquet 和所有小型证据仍在。
- #802 已关闭，接替评论 6446 指向 #813，`close-802.json` 留证；两个历史分支均保留。

## 工程门禁与边界

截至记录时点，首轮前端 lint/typecheck/build 通过，单测 116P/4F（3 个 5s timeout，1 个 getCredits 调用断言）；浏览器 E2E 尚在跑。候选与 main 的 `intelligence/webapp` Git tree 均为 `ec81f32060cfab8f586ff6af1c0a607e0c0329f8`。一致只证明本轮没改前端，不能替代复测，也不能把红灯判作纯设施问题。

本机同期两路他人全仓 pytest；10 核 / 16 GiB，观测负载曾到 291.84，可用磁盘曾降到 8.1 GiB。没有停止他人任务。重任务串行优先，不以环境压力豁免验收；Python 全量、前端、E2E、registry 四项齐全且身份正确才能申报就绪。

后续提交须冻结最终 head 再跑最终门禁；`CURRENT.json` 不存在、收据缺失、红灯或 head 不一致都视为未就绪。需要再次演练时用新目录，不能覆写旧报告；生产基线若推进，应重新核对固定合同，不扩大回填范围。

## 待授权生产操作

完整草案：`~/.finance-runtime/reviews/backfill-302132-0923/production-authorization-draft.md`。以下均未执行，不构成授权。

父命令（不能附带父模式 `--db`）：

```bash
cd /Users/a77/fwp-wt-backfill-302132-0923
MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m market_feature_store.cli repair-backfill-302132 --parquet /Users/a77/.finance-runtime/reviews/backfill-302132-0923/rehearsal-b9b59a9a/frozen.parquet
```

回滚命令模板，必须填本轮真实父收据，不可取“最新备份”或演练备份：

```bash
BACKUP='<本轮生产父收据 backup.backup_path>'
EXPECTED_SHA='<同一收据 backup.backup_sha256>'
PRODUCTION=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
RESTORE=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb.authorized-302132-restore
[ -f "$BACKUP" ] && [ ! -e "$RESTORE" ] && [ ! -e "$PRODUCTION.wal" ] && [ "$(shasum -a 256 "$BACKUP" | awk '{print $1}')" = "$EXPECTED_SHA" ] && cp -c "$BACKUP" "$RESTORE" && mv "$RESTORE" "$PRODUCTION"
```

前提：对命令、日期范围、回滚点另获逐字授权并记录来源；无活跃读写者、无夜跑换库、回填后无须保留的新业务写入。发现 WAL 停下，不删除。要求提前钉死备份文件名时，先只读冻结新审批基线，再把路径与 SHA 交用户确认，不能编造未来 run_id。生产 CLI 没有 `--record` 参数；合入记录使用 `gitea_pr.py merge --record`，生产授权另存 JSON，不能混为一种授权。

## 沉淀

重复演练已脚本化并入仓，不只留临时命令。脚本依赖单股固定合同，属于本项目量具，不提升成跨项目 harness 工具。通用原则是范围约束应比较保护区不变，而非假定保护区永远为空；来源数据自然增长不能扩大已授权迁移键集。
