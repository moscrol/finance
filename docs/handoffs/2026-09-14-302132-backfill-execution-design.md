# 302132.SZ 历史回填·执行实现交审（fix/backfill-302132-scoped @ efe2d28b）

按 `2026-09-14-302132-prep-review.md` 的两条 P1 与「执行前合同」实现并全链演练；后经 `2026-09-14-302132-execution-review.md`（QC 分支 docs/qc-backfill-302132-1b936486）五项退修，已全部修复并重新演练。**本轮未写生产**；生产授权另行申请。

## 第二轮（efe2d28b）：复审五项修复

| 退修 | 修复 |
|---|---|
| P1-1 报告写出绕过 canonical 护栏（--report-path 可截断数据库文件） | 所有报告/收据只经 `_guarded_write_json`：O_EXCL 不可覆盖 + 拒绝符号链接 + realpath 与 {target, parquet, canonical 候选集} 别名隔离；默认名按 run_id 派生；护栏不过 → rc=2 不发布（反例测试：canonical 见证库字节不变） |
| P1-2 保留日源行缺失 → LAG 跨日、错误昨收/涨跌被放行 | 写前校验完整依赖日期集：并跑表段源日期集合与市场历**逐日相等**（缺日/多日都拒绝，含 adjusted 过滤口径一致）；parquet 段同；逐回填日证明前驱=前一市场交易日；源值有限且必填非空。oracle 前驱改按市场历取，不再共享 SQL LAG |
| P2-1 verify 给损坏行签绿（分母按 source 自筛、只验三字段、09-11 无 updated_at 保护） | 验收分母 = spec 精确键集（54 键）逐键 LEFT 取行；全字段比对（名称/OHLC/昨收/涨跌/额/量/turnover=NULL/来源标签）+ 有限性；标签守恒副查；目标股保留 10 行全列快照**含 updated_at** 写后逐列相等 |
| P2-2 window「精确集合」只验跨度计数（非交易日起点仍过） | 按市场历索引构造全部合法 (as_of, start, end) 黄金三元组（161 个）与实际集合双向相等；各期计数由三元组索引距离推导再对钉值 |
| P2-3 证据未绑定代码修订、重跑覆盖 apply 报告 | 每轮两份不可覆盖收据：子进程 `…backfill-report.<run_id>.json`（revision/dirty/interpreter/run_id/spec/两源指纹/验收摘要）+ 父模式 `…repair-backfill-execution.<run_id>.json`（另含备份身份 path+sha256 与子报告全文）；git 解析不出即拒绝执行；删除不实的 run_class 注释 |

复审探针（7 条误放行复现）已逐条翻转为必须拒绝的单测，与原 10 条共 **19/19 通过**。

## 第一轮（ef90ea7d）：P1-1/P1-2 原始修复（合同来源）

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
- 第一轮全量 pytest：收据 `~/.finance-runtime/test-receipts/20260914T023634Z-ef90ea7d.json`，9,627 passed / 0 failed / 77 skipped，revision=ef90ea7d，dirty=false（已被上方 efe2d28b 收据取代）。
- **真实父流程完整副本演练 ×2**（第二轮代码，`MARKET_FEATURE_STORE_DB` 指向生产 CoW 克隆）：
  - run3（apply）：run_id=dc6d8a7a174f，克隆→子进程→验收→备份→原子换库全链 OK，执行收据绑定 revision+备份身份；
  - run4（verify 幂等重跑）：run_id=de751020ba23，零写入 verify 模式 OK；两轮收据并存不覆盖。
- **外部独立验收 v2 13/13 PASS**（`~/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/dryrun-acceptance-v2.json`）：生产 sha256 未变；他股主表全列双向 0；**保留 10 行（9 旧 + 09-11）全列含 updated_at 逐字节相等**；54 行键集分母全字段 oracle；两派生表保护切片全列（含 calculated_at）双向 0；window 黄金三元组集合相等；technical 精确 39 日期集；09-11 四值+四窗钉；fact_market_daily 不变；两轮收据绑定 revision/dirty/备份身份/spec/源指纹且 verify 模式正确。
- 第一轮演练（已被第二轮取代）：run1=dbfd8291f271、run2=492bd1c16751，验收 15/15（`dryrun-acceptance.json`）。
- 全量 pytest：收据 `~/.finance-runtime/test-receipts/20260914T035247Z-efe2d28b.json`，**9,636 passed / 0 failed / 77 skipped**，exit 0，revision=efe2d28b，dirty=false。ruff 全仓通过。

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
