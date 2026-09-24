# 2026-09-15 · 同花顺分步接线与只读换池验算：作者验证快照

## 背景与权限

目标是恢复日报、研究队列、矩阵和市场快照的数据链。用户已明确允许采用同花顺自己的板块与成员，**不要求复制复盘会名单或双红入选集合**；但公式、参数、单位、复权、窗口必须明示并可验证。

本轮只修改代码并用隔离测试库验证：没有登录复盘会、使用密钥请求供应商、补跑行情或修改生产库。反复“继续”不扩大生产权限。这里的“作者验证”不是独立 QC（质量复核），也不是生产恢复验收。

- 作者树：`/Users/a77/fwp-wt-hithink-review-wiring`，分支 `fix/hithink-review-wiring`。
- 基线：`gitea/main@1fef3d27`。
- 第一片：`9621128a9982586f55883156415d3129df404fe2`。
- 第二片/被测组合代码：`dcee18f2a23673dc482401013eea61f619ff1b25`。
- 本轮未 push、合并或部署。主检出、其他任务 worktree 均未清理或切换。

## 按发现顺序：做了什么，为什么停在这里

### 1. 同步器存在，不等于分步夜跑会调用

既有 `run_daily_update()` 已有同花顺四步，但 `run_review_sync.py` 的 local 计划没有这些调用。第一片把个股、板块 K 线、涨停池、龙虎榜/热榜/竞价四个并跑步骤接到 local 的 `stock-daily` 后，仍在独立子进程执行。

有日期参数的后三步显式下传目标日期；个股近十日 dump 没有历史目标日参数，不伪造它。子进程继承 `MARKET_FEATURE_STORE_DB` staging（暂存库）环境，不传显式 DB 路径、不借 sidecar（旁路库）兜底。板块步仍带 `--skip-constituents`。

初始缺 key 是可见 `skip/no-key`，不代表数据更新。有凭证但失败、超时、部分成功，在本步骤按预算重试；未恢复即停止下游、导出与发布。尤其不能先拿旧 dump 日历运行涨停池等消费者，再到最后仅补上游；请求失败后重试变成缺 key 也不能把失败洗成成功。其他旧步骤的收尾重试逻辑没有全面重构。

**这些调用仅写独立同花顺表。local 的 canonical（统一事实表）板块链仍是 carry/stitch，没有因此切源。**

### 2. 当前成员接口不能用历史 K 线目标日回标

原实现用 K 线 `end_day` 写当前成员的 `captured_at`。第二片改用每次成员响应接收时的上海日期与时刻：`captured_at` 是真实接收日期，`updated_at` 是明确上海时区转换后的无时区时间戳。跨午夜按每次响应记，不把两天强塞成一天。目录抓取时间另记，成员落库不覆盖它。

普通 upsert 只加入/更新当前成员，无法清走同日已退出成员。现在 `_flush_constituents()` 在同一事务里按 `(captured_at, sector_ts_code)` 删除旧批、插入新批、更新目录成员计数与捕获时刻；插入或目录更新失败均回滚。

响应必须非空、为列表、行结构/代码有效且无重复；跨目录标签重复的板块请求去重。**合法但截短的响应仍可能内部自洽**，本片没有请求级独立完整分母。目录只有最新单一 category，成员只有每日最新批；请求去重不是多标签模型，也不是盘中多版本历史。

### 3. 先只读验算，再谈生产投影

新增 `market_feature_store/hithink_sector_preview.py` 与 CLI `hithink-sector-preview`。只读同花顺目录/成员、canonical `fact_stock_daily`；指数口径另读同花顺 `fact_sector_kline_daily`。无需复盘会板块/成员表，不建库、不发布、不取 key、不外呼。

必须显式选择类别和涨幅口径：

- `member_equal_weight`：成员当日 canonical 涨幅的等权均值。
- `index_close_return`：相邻计划交易日的同花顺指数收盘比值收益；缺数不得回退等权。
- 两种模式的成交额均为同一选定名单的 canonical 成交额之和，单位亿元；前日额也用这份名单重算，**不是不加说明地拼接各日不同名单的总额**。
- 复用 `sync_local_sector_daily.diff_ratio` 和 `signals.is_double_red`，不另造阈值；严格双红为涨幅 `>0`、边际量 `>10`、成交额 `>500` 亿元。
- 前一交易日来自共享计划日历，不由“库里最近有行的一天”推断。函数下沉到 `market_feature_store/trading_days.py`，旧服务路径重导出同一个实现。

校验目录与成员来源、真实接收日期/时刻、成员计数、身份唯一性、两日行情、数值有效性和前日分母。未来名单、未知年份/休市日、缺关键值均阻断；携带旧名单必须显式给年龄上限。部分可算行仅用于诊断，全池缺口存在时不输出全池双红候选。

`calculation_ready` 只表示选定目录/名单的输入可算；**`production_ready` 永远 false**。CLI exit 0 不是生产质量门，缺口/非法参数/缺库缺表 exit 2。

## 方案对比与被否方案

| 决策点 | 采用 | 否决/保留边界及理由 |
|---|---|---|
| 名单来源 | 允许同花顺自己的池；同输入核公式，换池另记来源 | 强制 `.FP` 映射或旧双红集合完全一致：混淆算法正确性与样本一致性，也违背用户选择 |
| 涨幅 | 调用方显式选择等权或指数收益 | 自动兜底、统一偷偷改等权：改变算法；正式分类映射政策仍待明确 |
| 日期 | 当前成员按响应真实时间，行情目标日独立 | 用历史 `end_day` 回标当前名单：造成未来信息泄漏 |
| 快照更新 | 单批删除/插入/目录头同事务 | 逐成员 upsert 留退出者；只有插入成功不保证目录头一致 |
| 缺口 | 阻断板块，全池不完整不发完整候选 | 静默删缺数成员/回落异口径：把数据缺失伪装成业务结果 |
| 接线次序 | 并跑→只读验算→请求完整性/版本审计→canonical 投影 | 直接写公开 VIEW 或生产旁路：绕过已有发布代际与原子换库 |
| 覆盖质量 | 分开验请求成功、行/字段覆盖、可算、可发布 | 成员计数来自同一响应，计数相等不能证明供应商没漏 |

## 验证与可追溯证据

原始输出与收据的归档目录：
[`docs/verification/2026-09-15-hithink-review-wiring-preview/`](../verification/2026-09-15-hithink-review-wiring-preview/)。
日志无损封装为 `.output.json`：`lines` 保留原始换行与行尾空格，拼接后按 `encoding` 编码即可还原原始字节，`raw_sha256` 对应 `/tmp` 原始输出。全部已与原文件逐字节比较；这样既不篡改测试输出，也不为归档关闭行尾空格检查。`SHA256SUMS` 校验 23 份归档文件的字节指纹；它证明归档完整性，不证明业务正确性。在该目录运行 `shasum -a 256 -c SHA256SUMS` 可复核。

### 正向验证（Python，不含前端/E2E）

解释器均为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，没有绕过依赖门禁。

| 对象/命令 | 实际结果 | 归档文件 |
|---|---|---|
| 干净 `9621128a`，`-m pytest -q` | 9629 passed / 79 skipped / 2 xfailed，exit 0 | `hithink-wiring-full-9621128a.output.json`、`20260915T042917Z-9621128a.json` |
| 干净 `dcee18f2`，`-m ruff check .` | exit 0 | `hithink-preview-ruff-dcee18f2.output.json` |
| 干净 `dcee18f2`，`-m pytest -q` | 9684 passed / 79 skipped / 2 xfailed / 17 warnings，exit 0 | `hithink-preview-full-dcee18f2.output.json`、`hithink-preview-full-dcee18f2.exit`、`20260915T053650Z-dcee18f2.json` |
| `check_test_receipt.py` 指定完整 `dcee18f2` SHA | revision、干净树、解释器与依赖指纹全部一致，exit 0 | `hithink-preview-receipt-check-dcee18f2.output.json` |
| 第二片变异树恢复原代码后，两测试文件 | 63 passed，exit 0；树干净 | `20260915T054112Z-dcee18f2.json` |

第二片提交前曾有 183 项定向回归通过；其收据文件名仍带父提交 `9621128a`，但当时含未提交第二片改动，**不是干净 `9621128a` 的结果**，不拿它替代上述干净提交收据。新增归档/交接不改变运行代码，但也不把 `dcee18f2` 的测试说成之后文档提交的全仓结果。

已覆盖真实 CLI 子进程、缺库不创建、只读前后 DB 文件 SHA256 不变、禁止初始化/取 key/请求的替身检查。另在真 schema 的内存库经 `SectorUniverseStore.publish_snapshot()`、`record_member_result()`、`replace_sector_daily()`、`sync_sector_daily_local(..., prefer_payload=False)` 对账同输入：2.5% 涨幅、600 亿当日额、500 亿前日额、20% 边际量，双红一致。它证明这个合成输入的计算一致，不是历史名单重建或生产切源。

### 反向验证（变异测试：故意删保护，检查测试能否见红）

均由作者执行，不是另一个审查者。第一片树 `fwp-wt-hithink-wiring-mutation-9621128a`；第二片树 `fwp-wt-hithink-preview-mutation-dcee18f2`。第二片每次单独修改，运行后 `git restore --source=dcee18f2 -- <目标文件>`，不叠加变异。

| 变异 | 测试范围 | 实际结果 | 归档输出 |
|---|---|---|---|
| 第一片：移除同花顺失败原位保护 | `test_review_sync_hithink_wiring.py` | 6 failed / 8 passed | `hithink-wiring-mutation-guard.output.json` |
| 第一片：删除日期下传 | 同上 | 1 failed / 13 passed | `hithink-wiring-mutation-date.output.json` |
| 第二片：成员日期改回 `end_day` | `test_hithink_sector_kline.py` | 2 failed / 17 passed | `hithink-preview-mutation-date.output.json`、`053519Z` 收据 |
| 第二片：BEGIN/COMMIT/ROLLBACK 替换成无事务操作 | 同上 | 2 failed / 17 passed | `hithink-preview-mutation-transaction.output.json`、`053859Z` 收据 |
| 第二片：去掉目录声明成员计数校验 | `test_hithink_sector_preview.py` | 2 failed / 42 passed | `hithink-preview-mutation-count.output.json`、`054009Z` 收据 |
| 第二片：指数缺口允许且回退等权均值 | 同上，`-k 'index_basis_needs or basis_is_required'` | 6 failed / 1 passed / 37 deselected | `hithink-preview-mutation-pct-fallback.output.json`、`054106Z` 收据 |

第二片失败收据 `dirty=true` 是有意记录被破坏的代码；不能把它们当正式 revision 失败率。失败来自预期行为断言（日期、旧批保存、计算就绪），不是语法错误。第二片最后恢复两文件共 63 项通过；第一片也已恢复并复跑其 14 项通过。没有声称所有保护都有独立变异覆盖。

### 注册表：两个环境分别报，不互相覆盖

按 `.github/workflows/registry-check.yml` 的五条命令执行：`build_registry.py check-parseability`、`check`、`backfill-tables --check`、`generate-views --check`，以及 `audit_ledger_spec_crosswalk.py`。

- 作者树位于 `~/` 同级三仓布局：parseability、文档表、视图、台账 crosswalk 通过；`check` 因 **7 个 KB 技能内容指纹漂移** exit 1。未重刷注册表、未修改 KB。第一轮 shell 因该失败提前停，后两条及 crosswalk 已分别补跑，并非没结论。
- CI 单仓布局：`~/.finance-runtime/gate-checkouts/hithink-review-wiring-dcee18f2/finance-workspace-private`，干净固定 `dcee18f2`，五条全部 exit 0。脚本按既有合同明确跳过不在场的跨仓条目，没有改判据或隐藏工作树。
- 证据分别为 `hithink-preview-registry-leaf-dcee18f2.output.json`、`hithink-preview-registry-leaf-rest-dcee18f2.output.json`、`hithink-preview-registry-ci-dcee18f2.output.json`。crosswalk 正向/重号无错误，96 条反向索引 warning 保留。
- 两片未改 `scripts/build_registry.py`、`skills.registry.json` 或该 workflow。单仓绿不证明当前跨仓环境全绿。

### 能力图谱与代码地图

更新的是同花顺节点，新增分支上的成员批事务、预览函数与 CLI 断言。最新审计前/后均 exit 0，后一次为 64 节点行、127 断言，74 条在途/未校验；这些数字仅属于归档时的对象集合。审计对象包含其他脏工作树，**不是合流/运行时全绿证明**。

较早一轮 E2 符号漂移造成的 exit 1 已不再出现在这次输出；期间 E2 维护者有其他修改，本轮未代改该节点，也不将其修复归功于本任务。代码地图重新 build/query 后仍回报 `vault=unavailable`、检索层 missing；定位依据直接源码/测试，不把空地图当完整架构结论。

## 明确未验/未实现

1. **独立 QC 未执行**；不能拿独立 worktree 里的作者测试冒充独立审查。
2. 前端 lint/typecheck/test/build 与 E2E（端到端）未在本分支跑；四叶门禁不齐，尚非 merge-ready。
3. 本轮没有真实供应商响应、请求级成功/失败回执、独立目录/成员完整分母或目标日关键字段覆盖验收。
4. `dim_sector_hithink` 是最新单头；每日成员批与目录头必须匹配才能预览。不支持可靠历史目录重建或盘中版本审计。
5. local 不自动采成员；canonical 个股与新板块成员/日线投影未接。`repair_hithink_stock_day.py` 仍受单日白名单合同约束，不能当通用日更器。
6. 正式投影还须核对 dump 元→亿元、股→手、复权、窗口、涨幅分类映射及同篮子/各日篮子序列政策。不能因为用户允许换池就省略这些决策。
7. 日报、队列、矩阵、market snapshot 未通过此链的当次产物验收。没有宣称恢复。
8. 相关 `fix/local-plan-gate-alignment`、`fix/generation-stage-code-root` 等分支未继承；其质量门、代码根修复和收据不属于本枝。

## 接手顺序与独立验收要点

先对固定两片组合做独立复核（隔离树、同一解释器）：

- 四步调用/目标日/staging 继承正确；初始缺 key 与失败后丢 key 可区分；失败重试在日历消费者之前，未恢复不发布。
- 历史 K 线目标日不影响当前成员真实日期；跨午夜正确；同日退出者被删除；插入或目录更新失败时旧批完整保留。
- 等权/指数算法选择明确且指数缺口不兜底；相邻计划交易日、同篮子金额、严格阈值与缺口处理符合声明。
- CLI 真只读；部分行不能变成全池候选；`production_ready` 不被错误升为 true。计数自洽不越级充当请求完整性证据。

下一生产接线片仍先在隔离库：请求完整性与版本审计→通用 canonical 个股投影→经 `SectorUniverseStore` 发布接口接新池→字段口径与产物验收。历史日期走 duckdb-backfill 技能，不把历史日期塞进取最新行情的流程。生产只能走 `daily-full` staging 校验与原子换库；获得明确授权后再 push/合并/部署。

**不要做**：恢复复盘会登录探测；直接 upsert `fact_sector_daily`/`fact_sector_stock_daily` 公开 VIEW；用异口径资金补原资金面板；复制昨天行改日期；跳过完整性门为了先出报表。这些都不能用“允许换池”作理由。

## 工具与知识沉淀盘点

- 检查已落项目 pytest；只读预览是正式 CLI，不依赖 `/tmp` 手搓 SQL。日期、事务、计数和算法兜底的洞均已补代码并反向验证。
- 归档复用已有收据校验器与 SHA256 工具；没有新增只留 `/tmp` 的检查脚本。变异是本模块的有界语义实验，不再制造第二套通用测试运行器。
- 可迁移方法补入 `~/agent-memory/10_knowledge/source-switch-coverage-must-be-reconciled-first.md`：采集时间与目标时间分离、样本/算法分开验、内部计数不等于外部完整性。业务能否换算法需人工决定，不能硬写一个恒真的自动门。
- 未修改 `~/harness-reference/BUILD.md`：它有他人 WIP，本轮也没有新增 harness 通用件；复用已有模式，不建第二份工具清单。
- 项目笔记仅留任务行与一行交接指针；短交接见 `inflight/fix-hithink-review-wiring.md`。
