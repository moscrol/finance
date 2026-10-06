# 研究 harness 修复：最终复验与八项承接

2026-10-05。本页补充[决策快照](../handoffs/2026-10-05-research-harness-rebuild.md)，以已发生动作更正其中“交接后再验”的计划语句。结论：**本地工程合同通过；自然模型投研质量、GitHub CI、合并与部署未验/未执行。** 本页及证据归档是验收后的文档提交，不把旧收据移签为新 HEAD。

## 版本与授权

- 原型：`a96c1fef8c21d9a61f226c160d88ea5ea341205f`；初审不通过。
- 生产代码修复：`72a95fe4751efdd51aa6b1c398a4fa96aaf2de13`；删除未接线原型，沿既有工具/计算准入补保护。
- 合同测试与变异定义：`07f4523b8063df3be4c75347855728e07f9b7d8c`；没有进一步放宽生产代码。
- **最终全量受测版本：`458fd9de3c13f4293587f969bc733e136079ef53`**。比 07f 只多两份交接文档，仍重新执行了 Python、前端、E2E、注册表和变异检查。
- 本轮只在 `/Users/a77/finance-clean` 本窗路径工作，未改他人主工作树、运行服务、生产配置或数据根；没有 push、合并、部署、强推或历史重置。外部 Agent Memory 项目索引本轮未写，项目决策和承接落在本仓。

## 初审八项分别如何承接

以下“已有复验”不是本轮新增能力；所有用例均为本地合成/脚本化输入，不代签真实模型质量。新增测试集中在 `intelligence/tests/test_research_harness_slice_regressions.py`。

| 初审问题（被删原型） | 正式承载点与本轮动作 | 核验与仍有限制 |
|---|---|---|
| 1. 增量无条件写 SUPPORTED，空/失败/反证/未来都说符合预期 | **已有复验**：`judgment_maintenance/assess.py` 按知识截止与版本链给 `unknown`/`requires_review`/`observed`；**新增**：失败工具结果不可入账 | `test_existing_maintenance_does_not_call_missing_or_changed_evidence_support`，以及真实 `ContinuousAgentEpisode` 的旧证据保留/失败增量隔离。版本变化只表示需复核，不是通用主张的语义反证裁决 |
| 2. 返回可变 MemoryRecord，可直接改 confirmed 绕门 | **已有复验**：`memory_gate.MemoryCandidate` frozen、`MemoryGate` 和 `promotion_metadata` 来源依据门；不另造记忆库 | `test_candidate_mutation_cannot_bypass_existing_memory_gate` 与旧 memory gate/candidate-loop 测试。改 kind 或复制候选不能凭空获得来源依据；没有真人记忆写入实验 |
| 3. 引用 ID 合法就放过错主体/错数字；固定词误杀否定句 | **已有接缝复验**：结构 verifier 与 `SemanticEpisodeVerifier` 分开，原证据表送入 judge | 新错主体/错数字两例及否定句对照。judge 是脚本替身，生产语义 judge 仍默认 off；**不能宣称任意事实语义已经正确**，也未新增关键词判官 |
| 4. 忽略披露日，把所属期当作当时可得 | **已有复验**：`financial_report_contract.select_reports()`、正式财报 runner、信息截止与证据账本 | `test_financial_contracts_r5.py` 的未确认披露拒收、较新披露缺口保留、已知截止后报告与合法 pair、重复版本等；不把该财报合同外推为所有 provider 都具有可靠发布时间 |
| 5. 新包没接正式入口，测试靠插入 src | **撤除** `src/finance_harness/` 六文件与自身测试；只在 `ResearchToolRegistry`/`ToolRunResult` 等现役边界改动 | 普通仓根全量执行；真实 Episode + 脚本模型走 registry/project/ledger。Workbench E2E 为隔离服务测试；没有这次补丁的自然模型真实问题验收 |
| 6. 非空 dict 一律成功，业务失败/空/stale 混淆 | **新增**：`provider_result_error()`、`ToolRunResult.__post_init__()` 准入、`ToolObservation.result_status_fields()` 一致投影；legacy tuple 走同一适配器 | 已知失败、未知、矛盾 empty、partial/stale/empty 正控，模型/审计与原 gaps、私有 trace 分离。处理返回的业务状态；**没有重写全部抛出异常的分类**，不能宣称任意 PermissionError 已被统一重分类 |
| 7. 局部修复可替换成无关主张，不复验 | **已有复验**：语义接缝使用原 evidence registry、有界删除后再审 | 两轮 judge 请求的证据相同，错句删除、正确句保留、原 outcome 不变。只证明接线与有界修复，不保证自然 judge 能定位每个错误 |
| 8. NaN/∞ 可成功；相同商值丢分子分母溯源 | **新增**：参数、当前/恢复输入快照、完整结果树有限 JSON 校验；**已有复验**：calc_id、原脚本、输入哈希与 params | 非有限/非 JSON、legacy/v1/嵌套字段；0/False/None 正控；1/2 与 100/200 同结果但不同 calc_id。保留精确错误码。未改 sandbox prelude v5 或历史归档读取；身份正确不证明脚本用了输入、算术正确或源数据真实 |

## 三条全量红如何解决

第一次完整运行 `72a95fe47`：**20484 passed / 3 failed / 75 skipped / 2 xfailed**。三条都来自 `tests/test_history_tool_diagnostics.py`，不是“旧仓本来红”。随后在独占、干净的原型 revision `a96c1fe` 对该历史文件作基线，**23 passed**；没有修改该基线或拿混合树证明通过。

旧夹具调用 `_finance_query_failure_result()` 得到 `parse_error` + 空证据，再用 `dataclasses.replace` 手工塞入日期合格的事实，期待保留。正式失败 producer 本身不返回那些事实。新增准入在日期过滤前清除失败 payload，所以原断言与新合同冲突。

本轮明确改变的是**准入合同**，不声称旧测试本来断言错误：

| producer 状态 | 日期合法子集 | 全部未来 | 可信诊断 |
|---|---|---|---|
| `partial` | 按原历史授权/截止筛选，保留合格子集 | 无证据并保留 `future_of_cutoff` 告知 | 保留，但不可引用为事实 |
| `parse_error` / `request_error` | 无证据；日期不能挽救失败 payload | 保留原失败状态，不洗成查询成功 | 保留，但不能恢复事实 |

测试由原 7 个日期组合扩成 21 个状态×日期组合（净增 14 条），不是删除日期反例或放松准入求绿。新相关四文件组合 194 passed；两份变异用例文件合计 105 passed。最终完整运行比首红多 17 个 passed：3 条合同冲突转绿 + 14 条新增状态组合；各轮读数不相加。

## 实测收据与成立条件

原始日志、JSON、JUnit/XML 与必要 diff 已逐字节复制到 [证据目录](research-harness-rebuild-20261005/)；文件名用 `类别--原文件名`，原 `.log` 追加 `.txt`。`sources.json` 记录源路径、归档名、大小与 SHA-256，`sha256-manifest.txt` 覆盖归档全集。文件内的 revision、路径、dirty 不改写；复制不是重新执行。没有归档临时数据库、测试 basetemp 或部署台账。原 `/tmp/finance-harness-rebuild/` 保留，但复核不再依赖其生命周期。

原始 pytest/JUnit/diff 带有尾空格及空白上下文行；归档目录用 `.gitattributes` 将这些字节证据按二进制处理，未为消除展示警告而修剪，也未改写哈希。新增说明与 inflight 单独通过 `git diff --check`；不把原件的展示警告冒充代码回归或宣称全归档零警告。

### 最终受测版本 458fd9de3

环境：Python **3.12.13**，解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，依赖指纹 **e1c50cb821a30f00**，Node **22.23.3** / pnpm **10.12.1**。测试树 `/Users/a77/finance-clean`，干净、依赖门禁未绕过；进程环境按既有隔离门运行。

| 检查 | 实测结果 | 归档定位 |
|---|---|---|
| Ruff + 完整 Python | **20501 passed / 0 failed / 0 error / 75 skipped / 2 xfailed / 0 xpassed**；17 warnings | `verified-full-green--pytest.json`、`verified-full-green--pytest.log.txt` |
| 收据自证 | collected=20578 对平，无 ignore/k/m/deselect/maxfail/last-failed；full-scope、target、精确 revision、解释器/依赖/dirty 核验通过 | `verified-full-green--receipt-check.log.txt` |
| 前端 | install/lint/typecheck/Vitest/build 全 exit 0，**22 文件 / 210 tests passed** | `frontend--frontend.json` 与六份原始日志 |
| Playwright E2E | **52 passed / 2 skipped**；三视口，隔离服务，不是生产用户实跑 | `frontend--frontend-5.log.txt` |
| 注册表五项 | 五项分别 exit 0；台账反向链接 **101 条 warning**，按现有规则不阻断 | `registry--registry.json`、`registry--0.log.txt` 至 `registry--4.log.txt` |
| 六组变异 | 全部检测到预定保护被撤除，恢复后通过；没有 collection error/timeout | `mutations--results.json`、逐组 diff/JUnit/日志 |

前端 receipt 的六份日志大小/哈希已与实际文件逐项核对；起止 revision 相同、`identity_stable=true`、`dirty=false`。Python 75 skips 与 2 xfails 不算通过，也不据此宣称全部条件依赖功能可用。注册表返回 0 不等于没有 warning。

### 六组变异的准确读数

变异测试在独占临时 worktree 上每次只撤一处保护，执行后恢复；不是另一个模型/人员的独立评审。baseline/restored-full 各执行 105 条，全过；下面失败数是用例数，不是独立缺陷数。

| 变异 | 撤保护失败/执行数 | 恢复后通过/执行数 |
|---|---:|---:|
| 失败 payload 可入账 | 6/6 | 6/6 |
| 未知状态默认成功 | 2/14 | 14/14 |
| 回执丢业务状态 | 7/7 | 7/7 |
| 工具参数允许非有限数 | 3/3 | 3/3 |
| 输入快照允许非有限数 | 2/3 | 3/3 |
| 完整结果树允许非有限数 | 21/21 | 21/21 |

生产守卫已恢复，runner `complete=true`、`final_status=""`，临时源码 worktree 已移除。复用 `scripts/review_probes/run_extraction_mutations.py`，只新增本领域定义 `research_harness_admission_mutations.json`，没有复制第二套测试运行器。

### 其余保留读数

- `prototype-review--*`：原型原 2 条 + 审计补测 18 条合跑 **6 passed / 14 failed**；原审计探针以 `prototype-review--probe.py.txt` 原字节封存，避免已删除包的测试重新进入当前 pytest 收集。
- `first-full-red--*`：72a95fe47 首次完整 3 红，原件保留；不是被最终绿覆盖。
- `code-full-green--*`：07f4523b8 完整 Python 20501P/75S/2X；与后继 scope 重叠，不累计。
- `history-baseline--*`：a96c1fe 历史诊断文件 23 passed 的窄基线；不是全仓基线。
- 文档手工 pre-commit 首次因遗漏 `FWP_WORKBENCH_PYTHON` 失败，显式设置后通过；本次回写文件实际暂存后再次通过，包括 inflight 预算 hook（2092 字节，1834→2092，仍未超过3K）。这不是缺包或绕过门禁。

## 复现与后续准入

在独占树检出上述受测 revision，按 `scripts/run_main_gate.sh` / `scripts/run_frontend_gate.py` 的环境合同执行；不要在他人脏主树重跑再移签。Python 用项目 venv，并显式设置 `FWP_WORKBENCH_PYTHON`；Node 对齐 22。原 pytest 命令/范围见收据与日志。

变异复现（`<新目录>` 必须不存在）：

```bash
"$FWP_WORKBENCH_PYTHON" scripts/review_probes/run_extraction_mutations.py \
  --revision 458fd9de3c13f4293587f969bc733e136079ef53 \
  --output '<新目录>' \
  --definitions scripts/review_probes/research_harness_admission_mutations.json \
  --tests intelligence/tests/test_research_harness_slice_regressions.py tests/test_history_tool_diagnostics.py
```

归档提交后，可核验完整 Git blob 集合，而非只核本地文件：

```bash
"$FWP_WORKBENCH_PYTHON" scripts/check_evidence_archive.py \
  docs/verification/research-harness-rebuild-20261005 --revision HEAD
```

下一步是对提交做评审/CI 与获授权的真实入口质量验收，而不是继续添加金融词规则或默认打开语义判官。合并、部署须用户确认并核对实际运行 revision。测试接线成功、计算完成、语义通过、产物保存和用户收到是不同层级；本页只签明示的工程范围。
