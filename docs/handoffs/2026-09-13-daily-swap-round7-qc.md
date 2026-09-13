# daily-swap 六轮修补的第七轮独立审查

## 范围与裁定

输入 `fix/daily-swap-lock-all-callers@dfb6ce87`（代码最后变更 a42cbc5c）；独立树 `/tmp/daily-swap-qc-dfb6ce87`，审查分支 `docs/qc-daily-swap-dfb6ce87`。未修改施工分支、未合并、未运行生产换库或数据同步。

**六轮点名的 P2 删除异常修补、P1 首次建库 no-clobber，以及三项口径修订通过本轮复核。但公共链暂不放行：独立探针新增发现「探针已见旧库 → 删除 → 当成首次建库」的 P2 合同遗漏。合并门禁也不能由旧分支测试直接外推。**

这是针对具体 revision 的结论；不把本轮检测不到外部任意文件操作说成全面安全，也不把旧缺陷称为本轮新回归。

## 已通过

- clone 的收据字节数从 staging 获取，删掉了无用的来源 stat；clone 中/后真删除均 rc=2、swapped=False、不重建 target。独立探针在真实 cp 调用两侧注入 unlink。
- 锁外单次 stat 的删除拒绝、probe exists→connect 删除拒绝、损坏库不被误分类：现有定向回归通过，代码转换范围与其说明一致。
- bootstrap 在真实 link 前插入另一个 DuckDB 写者，提交、关闭并只读读回确认后恢复发布：rc=2，target SHA256 逐字节不变，staging 留证。不是只检查表名或返回码。
- 现有测试覆盖四种目标占用、收据、WAL 前置条件、link 后 unlink 失败仍承认已发布及下一轮删名不伤数据。
- 额外注入 link 的 EPERM / ENOSPC / EOPNOTSUPP：三条均结构化拒绝，target 不创建、staging 留证，os.replace 调用次数为零。建议施工方迁入常规 tests；现有名为 never_falls_back 的测试实际只注入了 WAL 前置拒绝，没有注入 link syscall 失败。
- 三把锁、非协同恢复路径、边界测试不是措辞门禁，均已收窄；既有库 check→replace 最后窗口仍按已声明限制处理，不要求本轮全仓协议重构。

## 发现（按审查动作排序）

### P2：已经观察到既有库，却在删除后重新归类为首次建库

位置：`market_feature_store/sync/sync_daily_full.py:514-520`、`557-560`；相关 helper `market_feature_store/db.py:311-338`。

真实时序（仅临时 DuckDB）：

1. target 有已提交的 2026-08-14 / 10000；真实 `probe_no_active_writer(target)` 成功完成。
2. helper 返回后、`source_exists = target.exists()` 前，注入真实 `target.unlink()`。
3. `source_exists=False`，跳过克隆和旧库基线；子进程建立新库，写 2026-08-15 / 12345。
4. 真实 os.link 成功。返回 **rc=0 / swapped=True / copy=None**；只读读回 target 仅剩 `[('2026-08-15', 12345.0)]`。

探针：`scripts/review_daily_swap_round7.py::test_target_deleted_after_successful_opening_probe_is_not_bootstrapped`。断言失败在行为 `0 != 2`，不是新符号缺失、mock 签名或注入未命中。旧代码 7c89ca81（独立审查树 e15379f5，源码未改）同红，故属于既有遗漏，非六轮回归。

**严重性不夸大**：旧文件是外部 unlink 删除的，不是本轮 link 覆盖了仍在的第三方提交；本程序的问题是把已观察到的「库消失」静默降格为首次初始化，重建缺历史的库并报成功。六轮「目标删除归一到整条链」的合同因此仍不成立。它发生在初始存在性观察与分支选择之间，不是已接受的最终 identity-check→replace 窗口。

建议最小修补：在第一次探测前固定本轮的 existing/absent 选择，或让第一次观察的存在性/身份结果显式向下传；已经观察为 existing 的轮次，后面缺失只能拒绝，不再重新降为 bootstrap。**不是再在发布前追加一次 stat**。无法保证观察前已被删的文件曾经存在，声明应限定到本轮首次观察，不能承诺防御任意时间删除。

验收：本探针转绿、target 不重建、给出可定位 reason；原本缺席仍能首次发布；首次检查后普通写者创建仍原子拒绝；现有 71 条无回归。

### P2（合并证据）：三份文件零漂移不等于合并后全量门禁绿

位置：`docs/handoffs/2026-09-13-daily-swap-round6-fixes.md:131-133`；dfb6ce87 提交说明也保留此断言。

本轮 fetch 后 `gitea/main=631786ab362f`，与 tip 的关系 **main 独有 35 / 候选独有 18**（17 是 a42cbc5c 的统计，tip 多一份文档提交）。上游 601db6dd 没有包含它的远端分支。本分支合并范围为 15 文件、3723 插入 / 46 删除，确实含 hithink 重建，不只是最后两处运行时修补。

三份所指文件在 main 侧无改动是真的；但 main 侧累计改变 48 个路径，包括 `market_feature_store/trading_days.py`、`intelligence/runtime/codex_headless_runtime.py`、registry 脚本和测试、测试基础设施。源文件字节相同不代表依赖、测试集合、宿主条件相同。merge-tree 只验证可组合文本，不执行行为。

`git merge-tree --write-tree gitea/main dfb6ce87` 的唯一文本冲突确为 `.claude/lessons_learned.md`，本轮只模拟、未实际合并。原始输出见 runtime 目录 `merge-tree.log`。

裁定：a42cbc5c 收据可用于代码未变的 dfb6ce87 快照审查，**不得宣称覆盖尚未测试的整合候选**。后续需清楚授权整体 hithink 合并面，组装干净整合候选并跑适用门禁；本轮未代用户选合并范围或执行合并。

### 非阻断本轮补丁的已知债务：clone 一般 IO 仍裸抛

位置：`db.py:258-308`、`sync_daily_full.py:525-547`。

独立注入 cp 失败后 copy2 抛 EPERM / ENOSPC：原始 OSError 确实逃出编排，target 字节完全不变。两条 characterization 测试绿仅表示**如实复现这项旧债**，不是期望错误出口已经合格。

裁定：允许另开小提交，不夹带进本轮竞态修补。它是错误出口/可观测性 P2，不是已证明的数据覆盖 P1。后续在编排边界输出 rc=2、swapped=False、stage、异常类型/errno 和保留取证路径，不应把权限/磁盘满伪装成 SwapTargetReplacedError，更不应把全链宽 except 都贴成「生产未动」（发布后的失败需要不同语义）。

### 小型交接修补

施工 inflight 的六轮报告链接是裸仓内相对路径，但该文件不在 dfb6ce87 中；实际在审查分支 `docs/qc-daily-swap-7c89ca81@e15379f5`。应带上分支/提交或可解析位置，避免新树接手读不到原审查。

`remove_stale_staging` docstring 仍说「收据从未写入、生产库未动」，与本轮已发布但 staging 清理失败的合法残留不符；行为没错，只需同步说明。`_run_daily_full_staged_locked` 的概览仍只写 os.replace，可顺手同步两种发布方式。

## 独立收据与证据边界

统一解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

- **新增审查文件之前的干净 dfb6ce87**：三文件定向 **71 passed / 9.51s**。收据 `~/.finance-runtime/test-receipts/20260913T090414Z-dfb6ce87.json`；日志 runtime `targeted.log`。
- 干净 dfb6ce87 `ruff check .` 全过；新增审查脚本后脚本单独 Ruff 亦过。
- 独立 9 探针：**8 passed / 1 failed / 0.72s**，其中两绿是一般 IO 旧债 characterization。收据 `20260913T090811Z-dfb6ce87.json`（有新增审查脚本，非干净树全量收据）；日志 `probes.log`。
- 旧版对照只跑新增红项：**1 failed / 8 deselected / 0.36s**；日志 `pre-fix-control.log`。确认 import 来自 `/tmp/daily-swap-qc-7c89ca81/market_feature_store/`，没混用施工代码。
- 核验施工方原始收据 `20260913T084405Z-a42cbc5c.json`：dirty=false、9517 passed、0 failed、77 skipped、exit 0、解释器正确。tip 相对它只差两份 handoff。**这是核验他方收据，不是本轮独立重跑全量**；收据格式不记 xfailed 和耗时，本轮不伪称核验了这两项。
- 本轮未独立重跑全量、sandbox 项、前端、E2E、registry 门禁，未重做 hithink 数据端到端对账。不能签发完整分支 merge-ready 或生产换库许可。

原始日志目录：`~/.finance-runtime/reviews/daily-swap-dfb6ce87/`。专用探针已归档 `scripts/review_daily_swap_round7.py`，是显式调用的审查证据，红项不伪装成常规 tests 已通过。修补方迁回 tests 后应保留 desired-behavior 断言。

## 下一步与工具沉淀

1. 单独修 existing→missing 被降为 bootstrap；迁入回归，红→绿独立复验。
2. 删除「门禁可外推到合并后」断言，修交接指针；一般 IO 出口单列工作，不要求夹带修。
3. 公共链复审通过后，再由用户裁定完整合并范围；整合候选全绿后，合并和生产换库仍须分别授权。

本轮未建新通用工具或措辞扫描门禁。探针是这一 revision 的阶段边界注入，归档到仓内即可；可迁移的是「已观察为既有对象后，缺失不能静默重新解释为首次初始化」原则，补入既有知识页。harness-reference 当前有他人改动，未触碰。
