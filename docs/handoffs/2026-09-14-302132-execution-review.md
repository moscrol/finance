# 302132 回填执行实现独立审查（ef90ea7d / 1b936486）

## 结论

**退修：2 个 P1、3 个 P2。现有演练数据正确，但失败拒绝/写入安全/证据绑定合同尚未落实完整，暂不建议合入；不是生产授权。**

审查树 `/private/tmp/backfill-302132-qc-1b936486`，分支 `docs/qc-backfill-302132-1b936486`，基于交审 tip `1b936486`（执行代码 `ef90ea7d`）。主检出树有他人脏改动，未触碰。合同源 `/private/tmp/302132-prep-qc-742c3ff5/docs/handoffs/2026-09-14-302132-prep-review.md`「下一轮执行前合同」。

本轮文件库只以 READ_ONLY 对照；写入仅发生在临时合成库、审查代码/报告。未复制大库、未重跑生产/原演练、未清备份、未合并。

## P1-1：报告输出绕过 canonical 拒写护栏，可直接截断数据库

位置：`market_feature_store/cli.py:1235-1237,1257-1266`。

`_refuse_production_write_direct` 只检查 `target`。成功后 `Path(args.report_path).write_text(...)` 无条件覆盖另一个任意路径，没有检查其是否 canonical、staging、parquet、已有数据库或路径别名。

真实 CLI 函数探针：临时库 A 作为合法 staging，临时库 B 通过 `MARKET_FEATURE_STORE_PRODUCTION_DB` 明确指定为 canonical；传 `--child --db A --report-path B`。回填正常完成后 **B 被替换为 JSON 文本，CLI 返回 0**。测试完全没用真实生产路径。父命令也原样转发这个选项；末端版本守卫最多拒绝发布，不能撤销子进程已经造成的文件截断。

**要求**：副作用前校验所有输出路径，而不只是 DuckDB 连接目标。报告必须与 canonical 候选集、实际发布目标、staging、冻结输入及其别名隔离；推荐只允许受控目录下按 run_id 新建报告，拒绝已有路径，避免 `resolve` 检查后再 `write_text` 的覆盖窗口。加父/子真实入口负控（临时 canonical、symlink/hardlink、staging/parquet 冲突），确认全部文件指纹不变。

## P1-2：源数据缺一天时 LAG 自动跨日，错误昨收/涨跌幅仍被放行

位置：`market_feature_store/sync/repair_backfill_stock_history.py:254-274`，验收同源依赖 `:466-480`。

`bf_src.prev_close` 由 `lag(h.close)` 产生，但源集合只检查 `prev_day` 与 `gap_parallel`。**主表已经保留的日期不属于 gap，却仍是下一回填日的昨收依赖**。删掉这种源行不会改变缺口清单，LAG 会悄悄取更早的一天。最终主表日期仍齐；Decimal oracle 用同一个 `bf_src.prev_close`，会认可这个错误。

反例（无猴子补丁，只删合成输入行）：D2=2026-08-05 是保留主表日，close=11.0。删并跑表 D2 后运行，D3=08-06 本应 pre_close=11.0、pct_chg=4.55，实际写 **10.5 / 9.52**；`run_backfill_child` 正常返回 apply。均线/窗口不依赖这个 pct_chg，末日钉值也不会抓住。

**要求**：写前校验参与 LAG 的完整依赖日期集合（含所有保留日、空壳日、前一交易日），明确连续市场历/真实停牌口径；逐回填日证明前驱就是预期市场交易日，不仅“存在上一行”。源值必须有限、必填值非空。source md5 只是事后记录，当前没有固定期望值比较，不能替代此闸。补删除保留源日、改 adjusted 导致过滤掉前驱、异常值等负控。

## P2-1：54 行 oracle 与保留主表指纹不完整，verify 可给损坏行签绿

位置：`repair_backfill_stock_history.py:466-496,498-504,565-570,583-586`。

- SELECT 取了 open/high/low/close/pre_close，但 oracle 只比较 pct_chg/amount/volume；stock_name、turnover、source、完整 54 日期集合没有逐项断言。
- 待验集合按被验主表的 `source` 标签 INNER JOIN 选择，标签错了可能从验收分母消失，没有核对验收行数。
- 主表保护切片仅他股；目标股保留行/窗外没有全列指纹，09-11 快照也没有 `updated_at`。

已复现三种真实 verify 误放行：完成 apply 后把回填行 open 改 NULL、pre_close 改 -999、并跑源标签改为 parquet 源标签，各自 verify 正常返回。第三种仍满足来源总数，但对应日期不在 bf_pq，故绕过逐行验收。另在 `_apply_main` 后注入只改 09-11 `updated_at`，正常 apply 也未拒绝（这是护栏变异，不是声称现有映射自然改时间戳）。

**要求**：从 spec 的精确改动键集出发 LEFT JOIN 源/结果，要求每键恰一行，按完整字段映射验收并检查 NULL/有限值；拒绝靠输出 source 筛分母。为目标股所有未授权修改行保存全列见证，含 09-11 updated_at。

## P2-2：window 的“精确集合”实际只验跨度计数，非交易日起点仍过

位置：`repair_backfill_stock_history.py:526-537`。

`span=[d for d in cal if start<=d<=end]` 只数区间中的市场日，不要求 start 本身是市场日，也没有构造所有合法 `(as_of,start,end)` 的精确期望集合。

变异反例：派生完成后把一条非末日 5 日窗起点从周一改成前一天周日。区间中的市场日仍为 6、各期总数不变、末日钉值不变，验收成功。当前正常 SQL 产物正确，但“计算错误必拒绝、精确日期集合”合同未成立。

**要求**：按市场历索引构造所有合法期数×as_of 三元组，与实际双向精确比对；同量错误不能仅依赖计数检测。保留周日偏移/删一补一负控。

## P2-3：每轮证据未绑定代码修订，默认报告覆盖了 apply 证据

位置：`repair_backfill_stock_history.py:22-23,599-605`，`cli.py:1253-1276`；父编排收据核对 `sync_daily_full.py:312-330,676-693`。

新模块声称“代码 revision、源指纹、spec、生产版本由父流程 ops 收据绑定，run_class=repair 是既有语义”。实际读到的 `ops_sync_run` schema 无 revision/run_class，两个 repair 行 steps 仅 name/ok/39/161。生产版本可经 run_id 对应的备份收据追溯，**但代码修订没有自动绑定**。

并跑 md5/parquet/spec 只放在外部报告，默认报告路径固定为 `<staging>.backfill-report.json`，第二轮 verify 覆盖第一轮 apply；现场只剩 `run_id=492bd1c16751` 的报告。全量 pytest 的 revision 收据不等于数据库执行的 revision 收据。

**要求**：本次修复专用的每轮不可覆盖收据，绑定实际代码 revision/dirty、run_id、spec、两个源指纹、输入生产备份身份及验收集合摘要，并在 ops steps 或其他持久链接中关联。无需为此改造整个日更；删除不实的 run_class 注释。干净检出作为执行前提仍应保留，但不能代替记录。

## 独立核验（认可的部分）

1. 原单测 **10/10** 独立重跑；修改范围 Ruff 通过。
2. `tests/test_302132_execution_review_probes.py` **10/10**：7 个已确认误放行反例 + 3 个正向安全测试（真实父 CLI 子失败不发布；canonical 在 connect 前拒绝；父入口 wiring/备份开关）。**这里测试绿表示缺陷成功复现，不是修复绿。**
3. 上述两组 + 既有 staging/write_path/单日修复回归，**95 passed / 0 failed / 10.86s**。收据 `~/.finance-runtime/test-receipts/20260914T030959Z-1b936486.json`，证明对象为 `1b936486 + 本审查新增探针`，不是全仓合入门禁。
4. 新工具 `scripts/verify_302132_execution_readonly.py` 独立只读对照 **15/15 PASS**。证据 `docs/handoffs/evidence/20260914-302132-execution-readonly.json`：64 日期、54 全字段映射、technical 39 精确日期、window 161 精确三元组、末日全部钉值、他股主表/派生保护切片全列双向 0、市场表与两板块 generation 表全列双向 0。两个 ops run_id 真实存在且 ok=true。
5. 生产 sha256 仍为 `76a32fac9c8bcd542982e5f7ffd654ffcf0e8646f515487aeba3b74c3ceff168`；生产/演练库/parquet 在只读检查前后 sha256/stat 一致。
6. 交付全量收据实为 9,627 passed / 0 failed / **77 skipped**，revision=ef90ea7d、dirty=false；交审文档的“77s”无法由该 JSON 支持（没有 duration 字段），77 是 skipped。实查保留且逐列不变的旧主表行为 **10 条**（9 旧非空 + 09-11），不是“11 条既有行不变”；06-23 空壳属于第 11 条既有行，但已获批更新，不能算不变。

只读核验复跑（输出须新路径）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/verify_302132_execution_readonly.py \
  --production /Users/a77/finance-workspace-private/db/market_feature_store.duckdb \
  --clone /Users/a77/.finance-runtime/db-repair/hithink-20260911/backfill-dryrun-302132/fake-prod.duckdb \
  --parquet /Users/a77/.finance-runtime/db-repair/hithink-20260911/daily-k-10d.parquet \
  --output <新的审查JSON路径>
```

## 审查顺序、边界与下一轮

先隔离树/读合同 → 审父子写入链 → 原测试绿 → 独立输入异常/计算变异 → 只读实算现有演练库 → 真实 CLI 失败与输出路径反例。前序父编排的互斥、run_id、备份、原子换名机制本轮未发现新增回归；危险是本命令绕过它的报告写入，以及向它递交的成功状态可能是误判。

自有探针误差：首轮测试 import 漏 `tests.` 造成收集失败，已修；初版 source 反例用旧行代替而旧 pct 自身不符被正确拒绝，改为两个允许标签之间替换后稳定误放行。保留日志，不将这些初稿失败归因施工。

未跑全仓/前端/e2e/registry 合入门禁；没有再跑真实大库父流程（已有产物可读验证，没必要为了审查消耗磁盘与覆盖证据）。磁盘本轮 `df -h` 观察约 7.6 GiB，仍应生产执行前重查。

| 选择 | 不选 | 理由 |
|---|---|---|
| 现有产物认可，但实现退修 | 把 15/15 数据绿直接当安全合同绿 | 正确样本与错误输入拒绝是两种证明对象 |
| 源完整性 + 前驱身份验证 | 仅重算 Decimal/钉末日 | 两边共享错误前驱会一起算对错误答案 |
| 所有文件写出口统一限权 | 只拦 duckdb.connect | 报告 JSON 同样能毁坏生产文件 |
| 独立审查分支留下探针 | 直接修施工分支/代合并 | 用户只授权审查；修改与再验收由执行方交付 |

下一轮先修以上五项并把误放行探针改成要求拒绝，再干净修订跑原回归与完整副本演练。生产执行仍单独申请；备份不删、旧行 OHLCV 不扩授权、事项 3 不启动。
