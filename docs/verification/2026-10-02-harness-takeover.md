# Harness 发布接手：两项修复的工程证据

日期：2026-10-02。此文记录已经执行的操作与边界，不声明发布全绿，也不授权 push、main 合入、生产切换或实验能力启用。

## 身份与保全

- 合流源码基线：`cf17788fa523b24b59405be66b6272ea560c623c`。
- 接手起点：`e25381b24c2c9cbb11193b4b85711e4e9a3d489a`。
- 自有树：`/tmp/harness-opt/tmp/arena-harness-release-1002`；分支：`fix/harness-release-1002-takeover`。
- 证据修复提交：`beff372c6f56caf9de35b10d0f01cd513f6223e0`。
- 快照修复提交：`1f8a8efb3f5ae11610cbbbb35bea56a679618b34`。
- 原发布树、三个未跟踪交接/计划/处置文档、源分支、失败实验和生产均未修改。没有 push、部署、预测台账或业务数据库写入。

## 1. 已交付证据的阅读覆盖

### 有效 RED

先用脚本模型走实际 PLAN → 子研究回灌 → inbox claim → evidence_read 路径。对已经交付的 900 字符正文重读 offset=239/limit=100，旧实现错误奖励 100 新字符；300 字符前缀交付后 offset=250/limit=100，旧实现奖励 100 而不是 50。

- 有效失败读数：3 failed、1 passed；XML：`/tmp/arena-harness-validation-1002/evidence-red2.xml`。
- 更早一次测试支架遗漏 superclass 初始化，4 条均因缺 `_native_tool_schemas` 失败，未到覆盖断言；它不是 bug-specific RED，已修正且未拿它作修复证据。

### 实现

- `consume_sub_research` 仅积累证据；完成、入池、入队、保存都不等于交付。
- `_claim_inbox` 在返回的消息追加进模型输入后通知本 Episode accumulator；正常、finish 竞态、repair/retry 三条运行路径的四个认领点均传入同一个 Episode-local accumulator。
- 无 inbox 的旧直接追加路径只在 append 后记覆盖；新增参数可选，保留现有 conformance 调用兼容。
- 字符观察器只展开明确的 `SUB_RESEARCH_RESULTS.branches[].evidence[]` 投影，并沿用 E 编号/原文哈希及字面区间校验；不从摘要、完成事件或另一个来源推断已经展示。
- 覆盖预置不增加独立证据或补读进展。默认关闭、显式能力授权及模型自选工具保持不变。

### 回归

新增 `intelligence/tests/test_evidence_read_delivery.py`，覆盖全文重读 0、300 字符重叠只增 50、未见页增 100、同运行器跨 Episode 不串覆盖、仅保存未投递、错误队列、拒收、丢弃、持久化失败认领、直接追加、关闭开关及伪造正文/编号。

在锁版本环境下，证据及相关既有 runtime/sub-research/inbox 回归：242 passed。最后又与快照回归一起在干净源码提交执行，见下文 292 条专用收据。

## 2. 快照日期身份

### 有效 RED

新 `test_market_snapshot_date_identity.py` 在原快照代码上得到 15 failed、1 passed：休市/历史/未来仍会调用现货，未知日历被精确 DuckDB 认证，历史 exact 标 fresh，直接入口先导入 AkShare 且能接受不可能日期。

XML：`/tmp/arena-harness-validation-1002/snapshot-red.xml`。provider 全为 stub，数据库由测试在独立临时目录创建；零真实行情请求、零生产数据变更。

### 实现

- 两入口复用 `market_feature_store.trading_days.trading_day_verdict`，不新增假日表，不用缺行推断日历。
- 现货必须满足请求日期等于北京时间采集日且 verdict=TRADING。统一入口不创建/调用不合格 runner；直接入口在导入 provider 前返回显式 failed 状态，不动 canonical 数据文件。
- 有确证的历史 exact DuckDB 仍可交付，保留真实 served/source 日期；本轮生成文档与 attempt 诚实标 historical。
- future 请求的 prior cutoff 不超过采集日；历史候选也必须获交易日确证。请求日 UNKNOWN 不获精确观测认证，但可交付另一个已确认的历史数据日。
- 保持 source priority、只读 DuckDB 及完整 latest/meta 单调发布规则。格式 PASS 不单独证明 freshness。
- 旧正向测试补显式 `now` 与固定共享日历时钟，避免历史 spot 禁止之后让测试含义随机器日期变化。

### 回归

相关六文件最终 50 passed，XML：`/tmp/arena-harness-validation-1002/snapshot-boundaries3.xml`。覆盖国庆、周末、历史、未来、UNKNOWN、现货正常入口、历史 exact 元数据、未来 DB 排除、非法日期在导入前拒绝、canonical 字节保全以及历史请求不倒退更新较新 latest/meta；历史 exact 试验前后合成 DuckDB 字节未变。

## 3. 已执行的干净源码联合读数

- revision：`1f8a8efb3f5ae11610cbbbb35bea56a679618b34`；工作树干净。
- 独立本树 `.venv-workbench/bin/python`，Python 3.12.13；development/consumer lock 匹配，未绕过依赖门禁。
- 13 个明确测试文件联合执行：**292 passed in 6.09s**。这是 focused，不是 full scope。
- XML：`/tmp/arena-harness-validation-1002/core-final.xml`。
- 专用收据：`/Users/a77/.finance-runtime/test-receipts/20261002T053013Z-1f8a8efb-f33cb45dcc7f.json`。
- 全仓 `python -m ruff check .` 与两次源码提交的 pre-commit hooks 通过。
- 新建隔离 Python 环境且 doctor=ready，无依赖漂移。共享环境 httpx=0.25.2 未被升级。
- 为前端单独安装 Node 22.23.3；pnpm 10.12.1 与仓库一致；doctor --frontend=ready。默认全局 Node 26 未变。

联合命令的测试文件：

```text
intelligence/tests/test_evidence_read_delivery.py
intelligence/tests/test_evidence_read.py
intelligence/tests/test_agent_episode.py
intelligence/tests/test_sub_research.py
intelligence/tests/test_sub_research_persistence.py
intelligence/tests/test_sub_research_tool.py
intelligence/tests/conformance/test_inv_r5_inbox.py
intelligence/tests/test_market_snapshot_date_identity.py
intelligence/tests/test_market_snapshot_sync.py
intelligence/tests/test_akshare_market_snapshot.py
intelligence/tests/test_duckdb_market_snapshot.py
tests/test_market_snapshot_contract.py
tests/test_market_snapshot_reconcile.py
```

## 4. 后续最终候选的独立门禁产物

外置产物根预留为 `/tmp/arena-harness-validation-1002/final-candidate/`。后续整仓 Python/Ruff、前端/E2E、registry 与刷新结构图都必须绑定实际受测的最终候选 SHA、干净树及专用日志/收据。本文的源码 focused 读数不自动升级为后续文档提交的 full 读数。

- Python 使用 `scripts/run_main_gate.sh`，并用 `scripts/check_test_receipt.py --require-full-scope --expect-revision` 校验本轮专用收据，不回读共享 latest。
- 前端使用 `scripts/run_frontend_gate.py --expect-revision`；独立端口、测试用户态、合成市场库与外置 deploy ledger，不打生产服务。
- registry 按 `.github/workflows/registry-check.yml` 五项检查；不能把第一项通过当整组绿。
- 结构图用受支持 facade `build --full --postprocess none`，不生成 wiki，不向 Cognition 发私有源码。结构图成功不证明架构召回完整；本树私有记忆 vault/叙事缺层仍是边界。

本代理已经分别按规格与代码质量自审，但没有独立 reviewer 证据；仍须独立复核。真实六条多轮验收、2×2/留出题净收益及 GitHub Actions 尚未执行。本轮工程修复不允许激活默认关闭候选，也不证明整个发布可上线。所有最终门禁及上述验收齐备后，再请求用户确认 PR/main/生产切换。
