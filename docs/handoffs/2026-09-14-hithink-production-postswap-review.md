# 2026-09-14 · hithink 生产换库独立只读复核与下一步边界

## 结论

**第 1 项当前生产数据验收通过，不需重跑修复。** 落账提交 `958f49c9` 只改交接；实际执行代码应认干净 `1fef3d27` 候选树，不认落账分支为执行版本。本审查分支从落账提交检出，只增加复核工具/证据/文档，不是新的运行时候选。

本轮没有调用修复/换库父子入口、没有写生产/备份、没有外呼、没有历史回填或并跑表补齐、没有删备份、没有合并或部署。主工作区有别人未提交改动，使用独立 worktree。

## 按发现顺序

1. 确认落账树与候选树均干净；`e9a824bf..1fef3d27` 仅 3 个落账/证据文件，代码同一。本轮不复跑四叶全量门禁，也不把历史绿冒称本轮结果。
2. `prod-repair-report-20260914.json` 的 `target_db` 是 `.staging`，没有 run_id 或发布后核对章节。因此它是**子进程修复报告**，单独不能证明已换库。`ops_sync_run` 实际只有 steps/rows 摘要，没有 derived 段；派生细节仍在子报告。
3. 以生产文件本身与指定换前备份 READ_ONLY 开库，用独立脚本逐项验证，持久化新报告，补齐发布侧证据。
4. 初版时间判据误红：父开始 `02:19:35.313767`，子开始仅记录 `02:19:35`。子时间源码截断至秒，不代表子早于父；改为父开始同精度比较。第一次运行另因输出父目录不存在未落盘；随后补 mkdir 并复跑，保留时间误红报告，再修比较。此误红不归因生产。
5. 只读查看后续任务的本地覆盖与端点代码，发现下述范围陷阱；未做交易日级完整缺口审计，更未开始补数。

## 本轮证据

工具：`scripts/verify_hithink_postswap_readonly.py`（所有数据库连接 read_only，无修复调用）。

- `docs/handoffs/evidence/20260914-hithink-postswap-readonly.json`：**24/24 PASS，exit 0**，含脚本 SHA256、输入路径/文件身份/哈希、版本、每项实值。
- `docs/handoffs/evidence/20260914-hithink-postswap-wrong-round.json`：只修改仓外 receipt 副本 run_id 的负控，**backup_identity FAIL，exit 1**，证明不是固定报绿。
- `docs/handoffs/evidence/20260914-hithink-postswap-readonly-timestamp-probe.json`：旧时间判据的 FAIL，保留，不被后续 PASS 覆盖；其脚本哈希不同，原因见上。
- `.venv-workbench/bin/python -m ruff check scripts/verify_hithink_postswap_readonly.py` 通过；未运行全仓 pytest / frontend / E2E，不作合并许可。

| 独立实查 | 结果 |
|---|---|
| 主表行数/来源 | 5,553 = hithink 5,547 + eastmoney 6 |
| 302132 全价量钉值 | open/high/low/close = 64.01/64.66/62.82/63.42；pre_close 64.35；pct_chg −1.45；amount 5.9863 亿；volume 94,471 手；换手率 NULL；名字中航成飞 |
| 共同行与保留行 | 6 保留行含时间戳完整相等；共同行除 source/updated_at/amount 外逐字段相等；amount 唯一差 600176 113.6007→113.6006 |
| 非目标日期 | 三张主/派生表 EXCEPT ALL 双向 0（连 NULL 日期也覆盖）；fact_market_daily 全表双向 0 |
| 派生 | technical 5,529 / window 22,115；302132 两表当日 0；600176 窗口唯一 amount 漂移 93.1063→93.1062 |
| 拼接 | dry_run + fetch_caps=False + include_completed=True + max_baseline_age_days=180：403/403，值源行 5,550。是特定参数的只读可拼接证明，不是已写入板块表 |
| 同轮与发布绑定 | 最新 ops=1ef953440995，kind/plan/date/ok 正确；receipt 同轮；该轮仅新增 1 条 ops，其他 ops 全等；生产当日数据指纹等于子报告 |
| 文件指纹 | 备份 sha256=c44a0f50…f9ca，与固定换前指纹及 receipt 一致；生产 sha256=76a32fac…f168；parquet=51f9ee9c…8d17 |
| 验鲜与无副作用 | 主表/两派生表/市场表最大日期均 09-11；生产和备份均可读到 66 张表；输入文件 stat 前后相等 |

**证据范围**：本轮直接证明当前文件状态及同轮绑定，不追认过去显式环境变量、完整持锁时序、历史 CLI exit 0、1.684s 换名耗时或当时别树 E2E 配置；这些是实施记录。本轮也没复算每个技术指标、更没比较全库 66 表所有内容。原 `fact_market_daily` 的复盘会口径继续保持，与主表差 +1 跌家/+5.99 亿的声明保留。

### 复现（仅审查，不重跑生产修复）

在本审查树内，`PY` 指向主树 `.venv-workbench/bin/python`；`PROD` 指向 canonical 文件；`REPAIR` 指向 `~/.finance-runtime/db-repair/hithink-20260911`；`CODE` 指向仍干净的执行候选 `1fef3d27`。输出必须是新路径：

```bash
"$PY" scripts/verify_hithink_postswap_readonly.py \
  --production "$PROD" \
  --backup "${PROD}.bak-20260914T021947-1ef953440995" \
  --receipt "${PROD}.bak-20260914T021947-1ef953440995.receipt.json" \
  --child-report "$REPAIR/prod-repair-report-20260914.json" \
  --parquet "$REPAIR/daily-k-10d.parquet" \
  --code-tree "$CODE" --output /tmp/postswap-recheck-new.json
```

这是本事故的固定钉值验收器，不是通用日期回补器。生产发生合法后续更新后需重新定义比较范围，不能用旧基线硬判回归。

## 下一步指示（建议用户转交；不是本轮执行授权）

### A. 第 1 项收尾

第 1 项标记通过；将本独立发布侧报告链接到执行交接，保留子报告/备份 receipt 各自身份。不重跑 `repair-stock-daily-hithink`。

备份暂留到下一轮范围确认和必要消费侧只读抽查完成，再单独批准清理。APFS clonefile 是共享数据块的写时复制：3.6GB 是逻辑大小，删除备份**不保证回收 3.6GB 实际空间**。磁盘仍约 10Gi，后续容量判断以 df 和实际增量为准，不凭逻辑文件大小预算。

### B. 第 2 项先做只读缺口清单与副本方案，生产再批

限定 `302132.SZ`，先优先复用本地数据，无需先访问外部服务：

- canonical `fact_stock_daily` 在 09-11 前仅 **10 行，06-15～07-09，且已稀疏**；07-09 后至 09-10 全无行。不能把旧方案「07-10～08-28」当主表实际缺口范围。
- `fact_stock_daily_hithink` 已有该股长期历史，最近到 09-08；冻结 10 日 parquet 覆盖 08-31～09-11，可作为 09-09/10 补充候选；先交叉核对重叠日、代码身份、复权事件及 OHLC/单位，不能默认拼接可信。
- 窗口要从消费者倒推：technical 需要 **26 个有效连续交易观测**；stock windows 为 5/10/20/60，其中 60 日收益用了 `LAG(close,60)`，需要 **61 个观测含当日**。因此不能「补够 26 行」就声称所有派生恢复；也不能 ROWS 数满足却跨历史缺口。
- 第一份交付：准确交易日缺失清单、停牌/代码变更解释、每段来源、字段映射、主表将写的日期×代码、派生将改的日期×代码、仍保持置缺的指标。交易日历与证券停复牌分开核验。
- 副本验证必须检查：09-11 已验钉值不变、他股不变、批准范围外日期不变、值非空/量纲正确、除息日昨收口径正确、派生重算影响闭包明确。若调用按日全市场重算会刷新其他股票 calculated_at，也属于变化，不能口头称“只改一股”。
- 技术窗口恢复与更早历史治理分开立范围；需 61 根但只获 26 根授权时，60 日继续置缺，不把扩大日期藏进实现。
- 副本结果交审后，再单独授权经正式 staging 父流程落生产；保留备份与同轮收据，禁止直接子进程写 canonical。

### C. 第 3 项另行按端点制表授权，不并入 B

先列 `端点/表/日期范围/重叠重写范围/额外写表/空结果语义/数据源/验收`，结束日 ≤09-11。

本地观察：多数并跑日表到 09-08；跌停池 max 为 09-07，不能仅凭 max 判 09-08 漏采——天然稀疏需核 ops/源响应 empty。benchmark 与 snapshot 都到 09-08；复权事件 max(ex_date)=09-16 但 updated_at 全为 09-08 22:08:19，不代表已同步至 09-16。

执行前钉三处代码边界：

1. `sync_hithink_stock_daily.py:332` 无 end_date；`INSERT_DAILY_SQL` 不裁日期。`--incremental` 只选择近十日 dump，不保证 ≤09-11。优先固定本地已验 parquet，按实际 min/max/日期集合验收；新下载必须先冻结、裁剪/校验，再进入副本。
2. `sync_hithink_sector_kline.py:521` incremental 是结束日之前 5 个自然日窗口（09-11 时为 09-07～11），不只是缺的 3 天；`skip_constituents=True` **仍调用 `_upsert_dim` 写当前板块目录**。历史 K 与当前目录刷新必须分别明确授权；否则先提供跳过目录写入的受测路径。禁止当前成分贴历史日戳。
3. 历史回补显式跳过竞价终态 snapshot 与当前成分；风向标 benchmark 可按其历史接口补。复权事件按事件日期和采集时间双口径管理，不机械截 ex_date≤09-11。

每端点验收不只 count：记录源头 empty 与错误的区别、关键字段非空、来源与量纲、范围外双向差异，以及增量覆盖旧日期的实际集合。上游请求与生产换库各自需用户授权。

## 决策与被否方案

| 选择 | 被否 | 理由 |
|---|---|---|
| 只读生产+备份独立对账 | 再跑修复验证退出码 | 已成功操作不重复，避免一次审查变成第二次生产写入 |
| 补发布侧持久证据 | 子报告 ok 当发布成功 | staging 内容与发布状态是不同事实 |
| 按记录精度比较时间并留误红 | 删除红报告 / 把精度误差当生产故障 | 防伪拒收，也不漂白审查过程 |
| 第 2 项本地数据优先、按消费窗口定范围 | 只补 26 行 / 照旧缺口区间直接施工 | 60 日收益需 61 根，主表真实缺口更长 |
| 第 3 项授权日期与额外写表分别列出 | 统一 incremental 或一个 end_date 覆盖所有端点 | 各端点日期合同不同，跳成分不等于跳目录 |
| 备份保留待单独清理 | 按 3.6GB 逻辑大小承诺回收空间 | clonefile 共享块，实际回收不等于文件长度 |

工具已入 `scripts/`，而非仅留临时命令。此复核器固定本事故，未作为通用 harness 工具推广；共享 harness-reference 树脏，本轮不动它。通用方法沿用现有 evidence-hygiene 记忆，不另建能力清单。
