# 2026-09-22 同花顺板块新池收尾：两个静默缺陷与口径归位

分支 `fix/hithink-sector-closeout-0922`，基座 `a2c8d1f90`（gitea/main）。
本文记背景、被否方案与理由；在途状态见 `inflight/fix-hithink-sector-closeout-0922.md`。

本轮只做离线修复与验证：未写生产库、未发布新池、未合并、未部署、未取真实行情、未 push。

## 为什么开这棵树

「同花顺复盘接线」的代码已合入 main（#795），但整链验收未完成。这棵树只查板块新池一侧的三个
问题：名单批次是否混用、计算前后输入是否一致、换供应商时同日是否会暴露两版「正式名单」。
第二、三个问题的答案都是「会」。

## D1：预览跨快照拼接

`preview_sector_calculation` 原本发 3～4 条独立 SELECT（指数收益 / 目录 / 成员 / 个股行情）。
DuckDB 在自动提交模式下，**每条语句各取一次快照**。夜跑写者在两条语句之间提交，这次调用就会
返回「旧名单 + 新价格」的报告。

危险不在于它错，而在于**它不会报错**：每个数字都真实存在过，只是从未同时成立。
实测（`test_preview_uses_one_snapshot_when_writer_commits_between_reads`）：并发提交后
amount 600→1200、diff_ratio 20→140，`calculation_ready` 仍为 true。

修法：新增 `db.read_snapshot()`，用 `BEGIN TRANSACTION READ ONLY` 把全部读取绑定到同一快照。
选它而不是普通事务，因为 DuckDB 的 MVCC（多版本并发控制）下读不加锁——**不会阻塞写者**；
同时它从引擎层面禁止写入，比「约定不写」更硬。

### 被否方案（D1）

1. **复用调用方已开的事务**。否。那等于允许预览读未提交、可能回滚的行，而预览输出会被当成
   证据保存。改为 fail-closed。
2. **读两遍、比对指纹、不一致就重试**。否。无界重试会活锁；而且它严格弱于引擎免费提供的
   MVCC 快照——用应用层的乐观重试去模拟数据库已经做对的事，是自找麻烦。
3. **把输入拷进临时表再算**。否。要往一个我们承诺「只读」的连接里写；且拷贝过程自身仍非原子，
   问题原样保留。

### 一个必须留在代码里的代价

DuckDB 的 Python API **没有暴露事务状态**（`dir(con)` 里没有任何 `trans*` 属性），所以无法
「先检测、再决定」，只能试着 BEGIN。而事务内任何语句报错都会把该事务置为 aborted——
调用方未提交的改动就此丢失。

也就是说：**fail-closed 的拒绝不是无副作用的**。这点写进了 `read_snapshot` 的 docstring 和
`test_preview_refuses_to_read_inside_callers_uncommitted_transaction`，否则下一个人会把它
当成「只是报个错」。

另外不放任 `duckdb.TransactionException` 冒泡：它是 `duckdb.Error` 子类，会被 CLI 归因成
「数据库不可用 / schema 不匹配」——**错误的归因比没有归因更难排查**。故包成
`SnapshotUnavailableError(ValueError)`，走既有的 `invalid-preview-options` 通道。

## D2：同日两版「正式名单」

「一个交易日只有一个已发布名单」这条不变量，系统里有三处读者按**日**强制：

- `SectorUniverseStore.published_snapshot(date)`：headers 数 ≠ 1 就抛错；
- `fact_sector_daily` / `fact_sector_stock_daily` 视图：模块 docstring 明写「只暴露某个交易日
  唯一已发布代际，因此读者不会跨代际混池」；
- `db.get_published_snapshot_id()`：按日取一个。

但写者 `publish_snapshot()` 把它收窄成了每 **(日, provider)** 一个——前置检查、supersede 更新、
后置检查三处 SQL 都带 `AND provider_source = ?`。

后果链：fupanhui 已发布的日子再发 hithink → 两条 `published` 表头都留下 → 视图的
`EXISTS (... status='published')` **没有 LIMIT**，于是同时暴露两池的板块行情；
`get_published_snapshot_id()` 则静默按 `captured_at DESC LIMIT 1` 挑晚的那个，后续写入挂到
哪一代际取决于时间戳。`dim_sector` 里两池身份也会同时 `is_active`。

即：**写者能造出读者拒读的状态**。这不是我新立规矩，是把写者对齐到系统里已经写明的契约。

修法：三处收回按日；换源必须显式声明换掉谁。

### 被否方案（D2）

4. **布尔开关 `allow_provider_switch=True`**。否。它只能表达「我确认要换」，拦不住
   「以为在覆盖 A、实际在覆盖 B」。改为 `supersede_provider=<当前在位 provider>`：
   调用方必须写出它以为在位的那个源，写错即拒。同 `check_test_receipt.py --expect-revision`
   的思路——**让调用方陈述预期，由系统核对**。
5. **同日换源直接静默 supersede**。否。恢复期一次静默切源，会让跨日对比混分母而无人知情
   （见 `runtime-and-pitfalls.md`：跨日名单变化须有记录）。

### 刻意的非目标

换源仍**绕过 95% 名称连续性闸门**：`_adjacent_name_continuity` 按 provider 比前一日，换源后新
provider 没有前一日快照，闸门直接跳过。跨源的板块名称本就不同，我没有可辩护的阈值，因此只
留痕、不设闸。要设的话需要先有跨源名称映射合同。

未做 schema 变更：换源留痕靠旧表头转 `superseded` 即可查（`provider_source, status` 都在表里），
不值得为此动生产库 DDL（模块 docstring 记着那 37 个对象是与生产库逐对象校验过的）。

## 验证

- 新增 10 个用例，先红后绿。
- **删保护变异 3/3 见红**，还原全绿：拆 `read_snapshot`（红 5）、supersede 退回 provider 作用域
  （红 1）、前置检查退回 provider 作用域（红 8）。
- 变异 2 只红「显式换源」这条**正向**用例——如果只写拒绝用例，把换源彻底做死也能全绿，
  这个洞会漏过去。正向用例在这里是承重的。
- 全量 `pytest -q -p no:randomly`：12528 passed / 85 skipped / 2 xfailed，用时 35 分钟。
  注：这轮跑于**提交前的脏树**（脏的只有本次改动，代码内容同 `f900c1f31`），故**无收据**。
  1 failed = `intelligence/tests/test_rag_worker.py::test_warm_worker_survives_first_timeout_...`，
  与本改动无 import 依赖（已 grep 核），单跑 3/3 绿。事后查 `uptime`：本机 **load average ≈ 50**
  （当时至少还有 `fwp-wt-runtime-entry-identity-0922`、`fwp-wt-mutation-timeout-evidence-0922`
  等多棵工作树在跑）——负载导致的计时假红，非本次引入。同一负载下重跑全量被迫在 11%
  处超时中断（>3000s），故改为出**目标收据**。
- 干净树收据（`dirty=false`，`revision=f900c1f31`，`check_test_receipt.py` 判「可采信」）：
  `~/.finance-runtime/test-receipts/20260922T112608Z-f900c1f3.json`，**196 passed**，
  target = 5 个板块/预览测试文件。**它是目标收据，不是全量收据**，不得当全量绿引用。
- `hithink_stock_preview._read_inputs` 只有一条 `con.execute`（单条 UNION 查询），天然单快照，
  **无 D1 同类缺陷**——已核实，不是推测。

## 合入结果（事后补记）

- PR #851（`fix/hithink-sector-closeout-0922` → `main`）已经用户逐字授权后合入，合并提交
  `53bd332c1`。合后核验三项全过：base 指向合并提交、head 是双亲、合并树 == 合前预览树；
  授权记录 `~/.finance-runtime/merge-records/851-hithink-sector-closeout-20260922.json`。
- **合并后的那棵树另跑了一次**（`merge-tree` 只能证无文本冲突，语义冲突正是这么漏的）：
  收据 `20260922T121855Z-53bd332c.json`，**143 passed**，`dirty=false`，revision 绑 `53bd332c1`。
  另一份 `20260922T114039Z-078f7eb4.json`（143 passed）绑 PR head。三份均为**目标收据**。
- 设计文档 `2026-07-29-daily-sector-universe-root-repair-design.md` 的 `(trade_date,
  provider_source)` 口径已同步为按日，并写明换源时 95% 闸门不适用。
- 按交接规约（「做完、合并、归档的事从 inflight 里删掉，只留在快照」），
  `inflight/fix-hithink-sector-closeout-0922.md` 已删，状态只留本快照。

## 下一步

1. ~~复核 D2 口径、push / 开 PR~~ —— 已完成，见上方「合入结果」。
2. 真实验算前先签：名称来源合同、换手率来源合同、停复牌对统计与板块分母的政策。
   → 三份合同的选项、各自的失败形态与待裁建议，已整理成**决策请求书**：
   `docs/superpowers/specs/2026-09-22-canonical-projection-contracts-decision-request.md`
   （含查证过的九条硬事实：同名异义的 turnover、同花顺无任何个股名称源、
   无全市场股本故换手率无法自算、停牌处置四处不一致）。**未签，不得引为已定。**
3. 再验板块名单版本（generation）、正式 canonical 投影，最后才是真实产物。
4. 写库须另获授权并分阶段：隔离 staging → 逐表回读 → 日历最后写 → 全质量门 → 原子换库。
