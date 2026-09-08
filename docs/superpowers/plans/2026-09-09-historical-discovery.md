# Historical Discovery Implementation Plan

> **For agentic workers:** Use subagent-driven-development to implement the following checked tasks. The user has authorized execution; do not repeat a design approval gate.

**Goal:** 在真实 Workbench 中完成历史行情重建、可复算特征、相似案例和完整条件样本比较，并保存可以继续研究的原件。

**Architecture:** 复用 TaskFrame → ResearchRunContext → ResearchToolRegistry → Episode。历史计算由只读的有类型 `history_query` 承载，复用 `finance_query` capability 授权；既有 finance_query 是单表查询，不能容纳成员联立、时间特征、完整比较分母，因此采用独立工具。完整原件只经 RunStore 写入，模型看到限长摘要与引用。

**Tech Stack:** Python、DuckDB、现有 Episode/Workbench、pytest；不引入另一套 loop、数据库写入链或任意代码执行器。

## 范围与依赖

按批准 spec 的 S0→S1→S2 交付第一条可用闭环；S3/S4 接现有版本/评价合同，任何没有评价器认证的输出均 `research_only`、`decision_eligible=false`、`promotion_eligible=false`。不把严格 PIT、独立样本统计、生产恢复、受限新算子沙箱的依赖偷偷算成本轮已实现。L2/晚间卖方/晨汇保留 pending_sync，未排期。

## Task 1 — S0 收据

Files: `docs/handoffs/2026-09-09-historical-discovery-implementation.md`；外部只读探针原件 `/Users/a77/.finance-runtime/historical-discovery-20260909/`。

- [x] 记录当前线上 revision、真实 UI 自然问题和结果；不要用 CLI 冒充 Workbench。
- [x] 对精确板块代码/交易日/成员/非空值核验，保留热度和事件时间缺口。
- [ ] 在相同数据与当前基线上验证新入口，区分线上旧 revision 的观察与可归因的回归。

## Task 2 — 受限历史计算

Create: `intelligence/services/historical_research/__init__.py`, `query.py`, `features.py`；test `tests/test_historical_research_query.py`。

- [x] 先写最小 DuckDB fixture：同名异代码、值为 NULL、成员缺股票行、成功/失败/不可判、重叠日期与 25 条以上样本；测试截止与取消。
- [x] 实现以下接口，from_arguments 严格校验字段/操作/窗口和成本，未知定义返回明确错误：

```python
spec = HistoryQuerySpec.from_arguments(arguments)
result = HistoryQuery(db_path).run(
    spec, information_cutoff=cutoff, deadline=deadline, is_cancelled=cancelled,
)
assert result['returned_count'] <= result['total_matched']
assert result['decision_eligible'] is False
```

- [x] `inspect_history` 联立精确实体日轴/当日成员/股票/市场；`compute_history` 仅既有内置算子并输出定义版本；`find_analogues` 区分整段与触发时点；`compare_cases` 对声明全集计算四格和不可判，先冻结特征条件再读取未来结果。
- [x] 每份返回含 query_id、source_refs、definition_refs、coverage、完整 records、摘要截断元数据、声明宇宙和相关窗口簇。未知维度不以零代替；不输出独立置信度或金融因果断言。
- [x] Run `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_historical_research_query.py`，应通过所有边界断言。

## Task 3 — 不可覆盖的研究原件

Modify: `intelligence/services/run_store.py`；test `tests/test_run_store_history_artifacts.py`。

- [x] 验证同 run 同 payload 幂等、修改条件产生新文件、路径穿越/未知 run/未登记原件/内容篡改被拒、既有通用 artifact 行为不变。
- [x] RunStore 实现 `add_history_artifact(run_id, kind, payload)` 和 `read_history_artifact(run_id, filename)`；采用 canonical JSON+sha256 文件名与不可覆盖创建，登记到既有 RunRecord，禁止另建 writer。
- [x] Run `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_run_store_history_artifacts.py`，预期通过。

## Task 4 — 意图、授权与真实工具装配

Modify: `intelligence/services/task_frame.py`, `episode_factory.py`, `episode_tools.py`, `research_tool_registry.py`, `intelligence/api/app.py`；create `intelligence/services/historical_research/episode.py`, `intent.py`；test `intelligence/tests/test_historical_research_episode.py`。

- [x] 为“这一波怎么走出来”“事后发现特征”“之前是否类似/失败”传递 typed purpose 与范围；普通单日查询不扩大历史授权。旧 TaskFrame 反序列化保持兼容。
- [x] 新工具只在历史语义+finance_query capability 均成立时注册；解析模型参数不赋予用途权限。实际 app factory 注入同一 RunStore/run_id，工具成功返回前完整结果即落盘，取消不吞已完成结果。
- [x] 研究原件读取只在当前用户和关联会话 run 范围，支持追问修改条件新引用；不接受模型自报任意磁盘路径。
- [x] Registry metadata/schema/contract/reachability 同步。断言工具真正出现在 Workbench adapter factory 装配结果，而非只测独立 helper。
- [x] Run `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_historical_research_episode.py intelligence/tests/test_task_frame.py intelligence/tests/test_episode_factory.py intelligence/tests/test_episode_tools.py`。

## Task 5 — 领域研究策略及版本衔接

Modify: `intelligence/services/research_harness.py`；create `intelligence/services/historical_research/research.py`, `methodology.py`；test `intelligence/tests/test_historical_research_harness.py`。

- [x] Prompt 允许完整路径发现、提出相互竞争解释、选择最有区分力查询、主动找反例，明确记录支持/反对/未知和停止原因；不固定农业因果树。
- [x] ResearchCase / HypothesisDraft 作为版本化产物记录来源案例、观察/检验用途、已暴露样本、替代解释、未支持定义和候选去向。修订保留旧版本与失败样本；不自动申请 R 号或晋升规律。
- [x] finish 检查可核查的工具引用、研究用途和结论资格；数据不足交付部分事实和下一步，不伪称完成多样本确认。
- [x] Run `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_historical_research_harness.py`，策略测试覆盖农业与迁移题材；未来结果不改变触发匹配的差分在 query 测试中。实际 Episode 的证据驱动分支另补专项，真实模型表现由 Task 6 验收。

## Task 6 — 验收与交接

- [ ] 真实 Workbench 运行农业复盘→相似样本/失败案例→改条件追问；再运行至少两个异题材场景。保存 run、trace、完整原件引用与数据/revision。
- [ ] 独立 spec review 后 quality review；修复发现后重跑相关回归。
- [ ] Run 定向 pytest 与改动文件 ruff；不以混合树/未执行全仓检查声称合并就绪。
- [ ] 文档记录确切已实现项和 S3/S4 依赖；同步 product door/capability graph，按 pathspec 提交并写在途 handoff。不合 main、不启动数据同步、不部署替换当前服务。

## S3 候选桥接的准确边界

`prepare_methodology_candidate` 复用既有 Rule builder / validator / compiler，产出 private candidate 的纯函数草稿。缺明确 predicates / success 返回 unsupported_definition；缺窗口返回 needs_data。它不写入方法、不分配实验号、不运行评价、不晋升；窗口内最大双红连续值不自动映射为观察日双红连续值。正式评价和跨会话方法记忆消费仍按基础依赖另验。
