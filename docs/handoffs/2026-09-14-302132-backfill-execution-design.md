# 302132.SZ 历史回填·执行实现交审（fix/backfill-302132-scoped @ ef90ea7d）

按 `2026-09-14-302132-prep-review.md` 的两条 P1 与「执行前合同」实现并全链演练。**本轮未写生产**；生产授权另行申请。

## P1-1 修复：专用父子入口（不再误用普通 daily-full）

- 新 CLI `repair-backfill-302132`（`market_feature_store/cli.py`）：父进程直接调 `run_daily_full_staged(trade_date=2026-09-11, kind="repair-backfill-302132", pre_swap_backup=True)`，child_argv 起 `repair-backfill-302132 --child` 子进程——锁/克隆/第三方写者守卫/同轮 run_id 状态/换前备份/原子发布全部复用父编排。
- 子进程模式写 `MARKET_FEATURE_STORE_DB`/`--db` 指向的 staging 副本；直写 canonical 被 `_refuse_production_write_direct` 拦死。**未新增直写 canonical 的通道**。
- 回填、scoped 派生、验收全部在父流程创建的 staging 副本内完成；任何失败 → 子进程 rc=2 + 不写 status.json → 父流程不换名。
- 准备副本（含他股派生漂移）不作发布源，已弃；演练从生产新鲜克隆重新开始。

## P1-2 修复：scoped + 预期置缺语义

新模块 `market_feature_store/sync/repair_backfill_stock_history.py`：

- **scoped 读/DELETE/INSERT** 全部限定 stock × 窗（06-15..09-11）× 两族（technical/window）；DELETE 与 INSERT 同一边界，不接受外部传入边界（「只筛 INSERT 不筛 DELETE」无从发生；反例测试 `test_widened_delete_counterexample_caught` 证明越权删除必被保护切片指纹抓住）。
- **预期置缺**：观测数逐日对照市场历，物化/置缺与 `rn>=26`（technical）、`rn>=p+1`（window）逐项核对；不符即 fail closed（输入异常/计算错误）。日更 `compute_features` 的非空保护未动。
- **存量处置**（spec 登记，护栏校验实况恰为登记集合才动手）：3 条窗内旧 technical（06-15/16/17）删除置缺；4 条旧 window（06-25/06-26/07-01/07-07 旧起点）删 key 重建；窗外 345 条 technical 由保护切片指纹（含 calculated_at）证不变。
- **重跑幂等**：护栏区分 apply（缺口=spec）/ verify（缺口已闭且回填行数相符）/ 部分态（拒绝）。verify 模式零写入：主表不动、派生只证「既有行==新鲜计算」（值列双向 EXCEPT ALL），连 calculated_at 都不刷新。
- **空壳 UPDATE 前提**：8 个拟覆盖值字段全 NULL 才允许（不是只看 close）。
- **字段映射**：与 `repair_hithink_stock_day` 写入表达式逐项同构（pre_close 分母先 CAST DECIMAL(18,2)）；验收另用 python Decimal ROUND_HALF_UP oracle 对 54 行独立复核；`test_oracle_matches_module_mapping` 锚定两者等价。
- **钉死验收**：窗内 technical 39 行精确日期集（= 市场历第 26..64 日）；window 161 行（5/10/20/60=59/54/44/4），每行跨度恰 p+1 观测且 end==as_of；09-11 technical 四值钉（59.8542/2.6845/61.9052/2.45）+ 四窗钉（起点+收益+均额逐条）；09-11 主表行全列钉值不变。
- **护栏拒跑**：非法代码 / 空清单 / 非法日期界 / parquet 哈希不符 / 缺口实况≠spec / 空壳非全 NULL / 回填日落除息事件 / 存量盘点≠登记。（演练中真实抓住两处：我初稿 spec 的 parquet 哈希与 09-11 OHLC 钉值抄错——fail-closed 按设计工作。）

## 证据（全部随库外运行目录 + 本提交）

- 单测 10/10：`tests/test_repair_backfill_stock_history.py`（happy/scoped/置缺/幂等/6 拒跑/反例/oracle 锚）。
- 全量 pytest：收据 `~/.finance-runtime/test-receipts/20260914T023634Z-ef90ea7d.json`，**9,627p/0f/77s**，exit 0，revision=ef90ea7d，dirty=false。ruff 全仓通过。
- **真实父流程完整副本演练 ×2**（`MARKET_FEATURE_STORE_DB` 指向生产 CoW 克隆）：
  - run1（apply）：run_id=dbfd8291f271，克隆→子进程→验收→备份→原子换库全链 OK；
  - run2（verify 幂等重跑）：run_id=492bd1c16751，零写入 verify 模式 OK。
- **外部独立验收 15/15 PASS**（演练产物 vs 生产只读对照，`~/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/dryrun-acceptance.json`）：生产 sha256 未变；他股主表全列（含 updated_at）双向 0；窗外目标股 0 行；11 条既有行逐字节相等；54 新行字段 oracle 全等；两派生表保护切片全列（**含 calculated_at**）双向 0；technical 精确 39 日期集；window 161 行 59/54/44/4 跨度精确；09-11 四值+四窗钉值全中；fact_market_daily 与板块生成表不变。

## P2 声明修正落实

- 「64 日全量」= 日期覆盖；9 条保留旧行 open/high/low/volume 全 NULL（不只 volume），amount 06-18 已为 4.1855 其余 8 条两位——旧行治理清单未授权不动。
- 整日重算不作为任何边界下的备选（09-11 他股 5,529+22,115 行时间戳会刷新）；执行只走 scoped。
- 漂移计数保留原始双向口径：technical 6,015/5,726、window 22,680/22,727（排除 calculated_at）。
- 06-16 可选除息昨收：原值 60.964 vs 修复模块口径 round→**60.96**；若未来批准修正须先统一口径，本轮不动。
- 准备阶段的 403/403 拼接为特定参数（dry_run=True, fetch_caps=False, include_completed=True, max_baseline_age_days=180）证据，非默认参数结论。

## 生产执行前提（待授权清单）

1. 代码评审通过并合入 main；执行从合入后的干净检出运行（revision 绑定）。
2. 生产若在此之前发生合法新写入（如 09-12 日更），基线变化 → 需重新副本演练（spec 钉值以现生产为准重核）。
3. 磁盘：演练实测 staging/备份均 clonefile CoW（0.004s/近零增量）；执行前仍按 df 实查 + 余量核算（当前 ~8.8Gi 可用）；备份不自动删。
4. 执行命令：`python3 -m market_feature_store.cli repair-backfill-302132 --parquet <冻结 parquet>`（MARKET_FEATURE_STORE_DB 指生产；默认即父编排，无 --direct 类逃生口）。

仓外证据目录：`~/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/`（run1/run2 日志、dryrun-acceptance.json、子进程报告）。
