# Spec 审查证据说明

审查对象 `/Users/a77/fwp-wt-nightly-review-0917`，分支 `fix/nightly-review-0917`，固定 HEAD `6356ffd5e703b30948f687baaaf60102bf97f0a5`。代码终点 `5204bb32`；候选链还含 `679007b3`、Sina 恢复、IPO、CDR 修复与日期交接。固定主线 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。`identity-before.json` 保存 merge-base、提交列表、三点 diff stat、全部 worktree 列表、SessionStart 与 code_map 查询；`candidate.diff` 保存精确代码范围。代码地图为空，审查结论来自源码追踪，不以空图作架构证据。

设计来源是本候选 `docs/handoffs/2026-09-17-local-review-recovery.md` 的第 16–37、98–119 行、对应 inflight，以及 `skills/duckdb-backfill/references/backfill-runbook.md` 的日期和派生合同。没有把 merge-base 之后全部文档当成代码范围。当前主线只用于集成条件对照。

## R1：刷新请求没有本轮完成证明

位置链：`scripts/recover_local_review.py:73–79,120–126` → `market_feature_store/cli.py:605–631` → `sync_local_sector_members.py:390–409,418–439,446–479`。

`probe_spec.py::completed_refresh_no_baseline` 使用候选真实 schema、`SectorUniverseStore`、成员 writer、stitch 函数与 CLI。种入 03-01 的真实供应商基线、09-17 已完成的 3 个板块与旧成员行；将 09-17 底表其中一股改成价格 12。恢复命令明确限定 180 日基线，3 个候选全部 `no_baseline`，但 CLI rc=0，旧完成审计为 `success=3/3, audit_complete=true, mismatch=-`，旧价 10 保留。**这不是“当时实际基线已过期”的断言，是该拒绝分支的确定性反例。** 合法可用基线对照使用 365 日测试参数以激活相同 fixture 的正常分支，3 个板块重建后价为 12；不建议生产放宽 180 日边界。

最小修复位于恢复/刷新完成判据：重用摘要中已有的 `skipped`、`failed`、`pending_for_provider` 与 `candidates/stitched` 信号，要求本轮请求刷新的候选完成；跳过/失败应明确阻断本轮恢复，而非靠旧 `success` 作证。不需要另造 freshness 台账或重写 completion audit。普通日更的默认 skip→provider 补齐流程保持原合同。不得用未经验证的新名单填补缺基线。全发布路径没有用此 fixture 验成“坏库已发布”，因此报告限定到已证实的错误成功信号。

## R2：业务日与写入时刻混用

原定义：`sync_eastmoney_stock_snapshot.py:61–76` 将 `f297` 定义为行情交易日；`recover_local_review.py:38–40` 先验证该日期。回放通过原 parser，`sync_eastmoney_stock_snapshot.py:205,238` 将 `datetime.now()` 作为实际 `updated_at`。这些定义互不冲突。冲突来自 `qa_backfill_align.py:189–205` 把 `CAST(updated_at AS DATE)=trade_date` 当来源真伪要求，而恢复 `:133–139` 必须经过它。runbook `:40` 已明确否定这种日期比较，允许凌晨/周末补前一交易日。

`probe_spec.py::dated_replay` 对 **同一份原始 bytes** 作成对回放：09-17 22:00 与 09-18 00:01。两个时刻均先通过真实 `validate_inputs`，原 parser 均报告实际快照日 09-17；同日来源检查无 FAIL，跨午夜为 1 个 `source-semantics FAIL`。输入保存在 `dated-replay-snapshot.json` 与 `dated-replay-history.jsonl`；两个结果都记同一个 SHA-256。只冻结测试时钟，不改生产时钟、业务日或真实数据。后者 fail closed，因此不把它归为实际污染发布。

若落实跨日回放，必须让既有日期证明与真实写入时刻都保留。另需注意本候选只对参数 `history_day` 传 `--no-caps`；旧 `snapshot_day` 跨日后仍会启用即时市值抓取。当前 alignment 会挡发布，本审查不单独计为污染发现；不要只删除时刻检查便宣布跨日恢复完成。

## I1：主线吸收后的可选叶子合同

冻结 `main-run_review_sync.py.txt:357–377,395–403`：四个 `HITHINK_STEPS`，缺 key 返回 `status='skip'`，是原计划明示的合法跳过。`integration-plan-simulation.py.txt` 只在 main 本地指数命令上添加候选 `--no-fupanhui-fallback`。

合流探针取冻结 main 的 **3 个 AST 节点**（常量 `HITHINK_STEPS`、函数 `sync_hithink_step`、`build_local_plan`），加入候选 sync 模块；其余候选代码未改变。它是函数级合同预演，不是解决所有冲突后的完整构建。缺 key 由确定性 stub 返回，未读取或使用真实凭据；捕获到 `2026-09-16 hithink-stock-daily failed; no publish`，无成功状态。有 key/各叶子成功对照 rc=0，保留 no-fallback flag。最小修复只能针对计划声明可选的并跑源，必需步骤失败与质量门失败必须继续阻断。

父审已有 `../identity-and-integration.json` 的两处 Git 冲突没有覆写。本探针不改变旧分支在 09-17 时的执行事实，也不要求新增平台或调度器。

## 正常路径、失败路径与收据边界

- `related-tests-command.json` / `related-tests.log`：新 **36 passed in 1.23s**。3 个候选新测试文件、成员刷新对照，以及 7 个既有 staging/publisher 针对测试。解释器始终是 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。候选 conftest 的环境门照常运行；`spec_receipt_redirect.py` 仅把收据输出重定向到本目录并拒绝 sockets。使用 `-p no:cacheprovider`、`PYTHONDONTWRITEBYTECODE=1` 与本目录 basetemp，未写候选 pytest 缓存/字节码或共享 latest receipt。
- `pytest-receipts/20260920T051009Z-6356ffd5.json`：新收据；保留真实工作树的 2 份既有产物状态，不冒称 clean tree 的全量验收。
- `probe_spec.py` / `probe-command.json` / `probe.log` / `probe-results.json`：真实输入校验、东财 parser、Sina validate/write；真实 recovery child 的计划循环、release 控制与状态输出。叶子子进程由确定性 stub 代替，不触网；正常分支写绑定当前 run_id 的成功状态，必需 index 步骤、同日门、跨日门、对齐门失败都不写成功状态。不能用这些 stub 通过声称全数据质量通过。
- 真实子进程发布安全由上述 7 个现有测试另证：正常换库/收据、未写状态崩溃、SIGKILL、备份、上一轮成功状态、错误 run_id、运行互斥。恢复 child 的失败“不产 status”与公共 publisher 的“不产 status 不换库”是分层证据，不冒充一次真实全链运行。
- 原历史 114P、两日 19/20 表和 L2/生成成功仅按固定交接记载；本轮未读取生产大库、未重跑线上取数、未重新认证旧产物。未跑全仓 pytest、前端、E2E、registry，未合并/部署。
- `probe-attempt1-*` 保留量具第一次失败：直接装入 main 整模块缺候选尚无的 `PLAN_CHOICES`，是跨树导入上下文问题，改为精确 3 节点的函数级预演。`probe-attempt2-*` 保留第二次失败：首次 fixture 未种板块日线，审计正确因 `daily_identities` 缺失拒绝；补齐“原本已完成”的 fixture 后重测。两次均未计成业务通过或候选缺陷。

`identity-after.json` 保存候选最终 HEAD、status 与所有 diff 文件哈希对比；`artifact-manifest.json` 绑定本目录交付物。源码、索引、两份未跟踪 quality 产物、生产/launchd/8792/L2/uchg 均未修改。
