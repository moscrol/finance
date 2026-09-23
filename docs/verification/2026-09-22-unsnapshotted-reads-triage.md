# 2026-09-22 未绑快照读取 54 候选逐条裁定（#857 / 工单 #74）

分支 `fix/report-reads-single-snapshot`，裁定基座 `086d99962`（= PR #857 head，落在 `gitea/main@f24a61a8a` 上，零漂移）。
审计器 `scripts/audit_unsnapshotted_reads.py market_feature_store` 在该 revision 的读数 **[实测]**：
发出 ≥2 条 SELECT 的函数 75 个，已绑快照/事务 21 个，**未绑 54 个**——工单 #74 写的是「52 未裁定」，
差的 2 个是 `_start_day_confirmation`（死代码）与 `completion_audit`（#857 已定「不改」），本表照样各给一行，不靠口径把它们藏掉。

本文只裁定、不修：能编出错误结论的行全部登记到占位单
`docs/superpowers/specs/2026-09-22-unsnapshotted-reads-followup-workorder.md`（#78），与 #857 的形态决策一致（只修能演示错误结论的点，且不在同一 PR 里扩面）。

## 判据（审计器 docstring 四条 + 本轮补一条）

1. 多条读取拼成一个**对外结论**吗？顺序执行几条无关查询不算。
2. 读取之间有**跨表依赖**吗（前面读出的数被后面拿来比 / 当参数）？
3. 全部读取是否以同一个**不可变键**为锚（`snapshot_id` / `capture_id`）？是则不算同类。
4. 是**写者自己**吗？写者若持事务，`read_snapshot` 会 fail-closed 并把事务置 aborted；不持事务的写者，绑只读快照会禁掉它随后的写。
5. **（本轮新增）一次调用里是否多次 `connect()`**？这是跨进程唯一能混代际的形态（见下「跨进程边界」），`read_snapshot` 只绑一条连接，管不到它。

结论三值：**A 修（占位）**= 能编出**静默**的错误结论（数字看起来正常、无报错，且是对外产物或写进库的值）；
**B 不修（记录）**= 能拼出不一致但方向是 fail-closed 误报 / 只影响写者进程内的诊断字段 / 退化为空；
**C 不算同类**= 单锚 / 互斥分支 / 写者 / 上层已覆盖 / 死代码。

## 跨进程边界（工单第 3 步「多进程阳性对照」的实测结果）

工单要求「第二个进程在两条读取之间提交，未修版本红、修后绿」。**这条在引擎层面做不出来** [实测，DuckDB 1.5.4]：
同一个库文件的跨进程并发打开三种组合（RW+RW / RO+RW / RW+RO）一律 `IOException: Could not set lock on file … Conflicting lock is held`。
生产写者也从不与读者共用文件——`daily-full` 写 staging 副本再 `os.replace` 换名（`market_feature_store/db.py`）。
于是把对照改写成三条断言，落 `tests/test_report_reads_cross_process_boundary.py`（5 passed）：

| 断言 | 结果 [实测] | 含义 |
|---|---|---|
| 持有中的连接 + 第二进程 connect 同一文件 | 三种组合全部 REFUSED | 「多进程用例先红后绿」不可满足，不是没做 |
| 持有中的 RO 连接跨越第二进程 `os.replace` | 同连接仍读旧代际；同进程再 connect 同路径也读旧代际（实例按路径复用）；全部关掉后重开才见新代际 | 单连接函数（`health` / `collect_daily_review`）对换库天然免疫 |
| 每读一次重新 connect 的读者 vs 单连接读者，中间换库 | `[1, 2]` vs `[1, 1]` | 多次 connect 的函数会跨代际拼接，且 `read_snapshot` 绑不住 |

所以 #857 修的那类（同进程第二连接在两条读取之间提交）真实暴露面是：同进程多线程写者。全仓 `ThreadPoolExecutor` 三处
（`fupanhui_source` / `sync_fupanhui_sector_stock_daily` / `sync_eastmoney_fund_flow`）的 `pool.map` 目标都是网络抓取函数
（`_safe` / `_fetch_cap_batch` / `_one→fetch_flow_history`），没有线程内写库 [实测 grep，未逐函数追到底]。
8792 只读多线程无写者；`daily-full` 子进程单线程顺序执行。**这不否定 #857**：编得出错误结论就该修，且它是给人看、会被存档的产物；
但它决定了 A 类的优先级都不高于 P2。

## #857 绑定的独立复验 [实测]

拆 `collect_daily_review` 的 `with read_snapshot(con):`（sed 替换 1 处，`PYTHONDONTWRITEBYTECODE=1`）→
`tests/test_report_reads_single_snapshot.py` **2 failed / 3 passed**（红的正是两条日报用例）；`git checkout --` 还原 → sha256 前后相同
（`ddc9aed7bb20625c`），5 passed。与作者交接里「拆日报红 2」一致。

## 54 行裁定表

| # | 函数（文件:行） | SELECT | 判据要点 | 结论 |
|---|---|---|---|---|
| 1 | `query.stock_highs`（query.py:215） | 3 | 一条 RO 连接：市场新高计数 / 新高个股 / 板块归属。`market_counts` 与 `stock_count`、个股与其板块可来自两个快照，输出是 CLI 报告。 | **A** |
| 2 | `query.sw_l1_signal_peaks`（query.py:387） | 3+2 | 日期窗（fact_market_daily）→ 两表窗日期（`_table_window_dates` 各 1 读）→ 涨停 / 新高行；峰值 = current vs history，跨表跨时。 | **A** |
| 3 | `query._interval_stock_rank`（query.py:886） | 3 | `rng` → `metadata_date` → 主查询三步依赖；板块 / 申万归属可整批退化为 `-` / `未映射` 而不报错。 | **A** |
| 4 | `query.strong_subtheme_trace`（query.py:515） | 2+1 | 自身一条连接读 3 次后关闭，再**逐日各开一条新连接**调 `sw_l1_signal_peaks`（默认 60 次 connect）。判据 5 命中：跨进程换库也能混代际。 | **A** |
| 5 | `query.limit_heat`（query.py:650） | 2 | 题材热度行 → 按其 code 取成分行（`with_stocks`）；题材与成分可来自两个快照。 | **A** |
| 6 | `models.market_stage.build_feature_frame`（market_stage.py:57） | 2（+DESCRIBE） | 市场行 + 个股宽度两读拼特征，`predict_stage` 据此写 `market_stage` 标签。写者进程内顺序调用，但读取不在事务内、可绑；写进库的值。 | **A**（低） |
| 7 | `compute_local_stats.core_leader_candidates`（compute_local_stats.py:1005） | 2+ | `_limit_flags` / `gain5` / `highs` 多读拼候选特征，写入本地核心龙头表。同上。 | **A**（低） |
| 8 | `quality.calendar_gaps`（quality.py:103） | 3 | 日历 vs 各表日期；拼接只能多报「缺档」（fail-closed）；`_connect_ro()` 与写者进程互斥。 | B |
| 9 | `quality.row_count_anomalies`（quality.py:142） | 2 | 当日 vs 历史中位数；拼接只能误报收缩，方向 fail-closed；本来就是查半截同步的。 | B |
| 10 | `sync_daily_full.validate_daily_data`（sync_daily_full.py:174） | 2 | staging 子进程写完后顺序调用；拼接只会把 `ok` 推向 False。 | B |
| 11 | `maintenance.db_shape`（maintenance.py:87） | 6 | 换名前后对账；维护操作持 RW，引擎锁排除其他进程；不一致只会让 `compare_shapes` 拒跑。 | B |
| 12 | `maintenance.shell_row_report`（maintenance.py:52） | 2 | 同上，`rows_total` 与 `shell_by_source` 是账目读数，事务外顺序执行。 | B |
| 13 | `sync_hithink_sector_kline.map_fp_names`（:443） | 5 | 写者进程内的映射诊断（`matched / gaps / ti_name_diff`）；`dim_sector_hithink` 读两次是冗余读，不是快照问题。 | B |
| 14 | `sync_hithink_stock_daily.compare_recent_close`（:244） | 3 | 写者进程内的对账率（`result["compare"]`），顺序执行。 | B |
| 15 | `sync_hithink_limit_pools.compare_boards`（:356） | 2 | 同上（`boards_compare`）。 | B |
| 16 | `compute_local_stats.sector_theme_map`（:713） | 2 | 历史归组 + 申万兜底 `setdefault`；拼接只影响兜底覆盖面。 | B |
| 17 | `compute_local_stats._mainline_membership`（:978） | 2 | 两读都锚 `td`；该日行只被同一写者顺序写。 | B |
| 18 | `sync_local_sector_daily._prev_sector_amounts`（:85） | 2 | `MAX(prev)` → 该日 amount；prev 是历史行，只有重跑该日才改写。 | B |
| 19 | `sector_alias.resolve_sector_codes`（:367） | 2+ | 别名 / 现名 / 历史名逐级回退；拼接最多退化为 `matched_by="none"`。 | B |
| 20 | `repair_hithink_stock_day.build_plan`（:179） | 19 | 在 staging / 克隆库上先物化 TEMP 表再全部对 TEMP 表读；需 CREATE TEMP，只读事务不可用；私有库无并发写者。 | C 写者 |
| 21 | `sector_universe.completion_audit`（:997） | 8 | #857 已定不改：首条读出 `snapshot_id`，其后全按它过滤。补一句：`ops_sector_member_sync_daily` 状态行会被写者更新，但只能把 `complete` 从 False 推向 True 且要全部条件同时成立，编不出假 True。 | C 单锚（已定） |
| 22 | `sector_universe.published_snapshot`（:486） | 3 | `snapshot_id` 锚 + 行数 / 合计 / 内容哈希三重自校验，不符即 raise。 | C 单锚 |
| 23 | `hithink_sector_capture._read_capture`（:66） | 2 | `capture_id` 锚 + manifest sha256 自校验（`capture-manifest-mismatch`）。 | C 单锚 |
| 24 | `sector_universe._adjacent_name_continuity`（:361） | 2 | 表头 → 该 `snapshot_id` 的名单，内容寻址不可变。 | C 单锚 |
| 25 | `sync_local_sector_members.identity_delta`（:95） | 3 | stitch 写者路径；今日行要求唯一 published，prev 为历史行。 | C 写者 |
| 26 | `compute_local_stats.carry_forward_universe`（:65） | 4 | 发布快照 + UPDATE。 | C 写者 |
| 27 | `sync_mootdx_stock_daily.sync_fact_stock_daily`（:207） | 4 | 批量 upsert 写者。 | C 写者 |
| 28 | `fill_stock_daily_fallback.fill_stock_daily_fallback`（:51） | 3 | upsert + UPDATE 写者。 | C 写者 |
| 29 | `sync_eastmoney_stock_snapshot.sync_fact_stock_daily_snapshot`（:175） | 3 | 写者；三条读全是写后统计。 | C 写者 |
| 30 | `sync_fupanhui_sector_stock_daily.sync_fact_sector_stock_daily`（:208） | 3 | 写者（`record_member_result`）。 | C 写者 |
| 31 | `sync_fupanhui_sectors.sync_dim_sector`（:115） | 3 | 发布快照 + 写 payload。 | C 写者 |
| 32 | `models.market_stage.predict_stage`（:203） | 2 | UPDATE 写者（其读侧见第 6 行）。 | C 写者 |
| 33 | `sync_fupanhui_limit_advance_daily.sync_fupanhui_limit_advance_range`（:270） | 2 | 逐日调写者，末尾两条是写后统计（各自新连接）。 | C 写者 |
| 34 | `sync_fupanhui_market_deviation.sync_market_deviation`（:151） | 2 | UPDATE 写者。 | C 写者 |
| 35 | `cli.cmd_sync_fund_flow`（cli.py:475） | 2 | 两条 SELECT 分属互斥分支，各自单连接单条。 | C 互斥分支 |
| 36 | `cli.cmd_sync_fupanhui_public_assets`（cli.py:604） | 2 | 同上。 | C 互斥分支 |
| 37 | `query._date_range`（query.py:489） | 2 | 互斥分支；`end` 由 `_latest_date` 给出后结果是 ≤end 的一致子集。调用方是第 4 行，随 #78 一起处理。 | C 互斥分支 |
| 38 | `sector_universe.member_generation_row_count`（:1188） | 2 | 互斥分支。 | C 互斥分支 |
| 39 | `sync_fupanhui_limit_advance_daily._resolve_range_dates`（:66） | 2 | 互斥分支（days / range）。 | C 互斥分支 |
| 40 | `sync_fupanhui_market_daily._resolve_range_dates`（:265） | 2 | 同上。 | C 互斥分支 |
| 41 | `sync_fupanhui_sector_daily._resolve_range_dates`（:78） | 2 | 同上。 | C 互斥分支 |
| 42 | `sync_fupanhui_stock_high_daily._resolve_range_dates`（:159） | 2 | 同上。 | C 互斥分支 |
| 43 | `sync_fupanhui_sector_daily._load_sector_dim`（:32） | 2 | 命中即返回，第二条只在第一条为空时执行。 | C 互斥分支 |
| 44 | `sync_hithink_stock_daily.table_fingerprint`（:211） | 2 | 按表名互斥分支，各一条。 | C 互斥分支 |
| 45 | `sync_hithink_sector_kline.coverage_old_ti`（:351） | 2 | 首条是 `information_schema` 存在性检查，数据读只有一条合并查询。 | C 单条数据读 |
| 46 | `sync_hithink_sector_kline.compare_pct_chg`（:392） | 2 | 同上。 | C 单条数据读 |
| 47 | `sync_akshare_sw_l1_daily._target_dates`（:44） | 2 | `MAX` → ≤end 的日期列表，结果是一致子集，不构成结论。 | C |
| 48 | `backfill_review_hot_data._backfill_one`（:83） | 2 | 编排脚本：写者是它自己起的、已结束的子进程；两读只做循环控制。 | C |
| 49 | `sync_daily_full._db_shape`（:348） | 2 | 自开 RO 连接读私有 staging 文件的形状收据。 | C |
| 50 | `reports.daily_review._sw_l1_double_red_matrix`（:388） | 5 | 唯一调用点 1118 行，在 `collect_daily_review` 的 `with read_snapshot(con):`（966–1434 行）内。 | C 上层已覆盖 |
| 51 | `reports.daily_review._stock_high_sw_l1_matrix`（:520） | 2 | 唯一调用点 1119 行，同上。 | C 上层已覆盖 |
| 52 | `reports.daily_review._limit_up_sw_l1_matrix`（:556） | 2 | 唯一调用点 1120 行，同上。 | C 上层已覆盖 |
| 53 | `reports.daily_review._coverage`（:853） | 2 | 本模块唯一调用点 1410 行，同上；审计器列出的其它 `_coverage` 调用是别的模块里的同名函数。 | C 上层已覆盖 |
| 54 | `reports.daily_review._start_day_confirmation`（:704） | 5 | 全仓零引用；#857 已定「只记录不删」。 | C 死代码 |

**A 类 7 行 == 占位单 #78 的 7 条。** B 12 行、C 35 行。

## 未验证 / 边界

- 线程内写库只 grep 到 `pool.map` 的目标函数名，没有逐函数追到 DuckDB 调用；「无同进程并发写者」是 **[实测 grep + 推断]**。
- 判据 5 只对 54 行里显式 `connect(` 的函数看了一眼（`connect_calls` 列由脚本统计）；被调助手里的 connect 未展开，`strong_subtheme_trace` 是唯一确认的多连接读者。
- B 类的「fail-closed 方向」是读代码得出的 **[推断]**，没有逐条写并发用例去证。
