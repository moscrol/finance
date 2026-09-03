# 2026-08-29 符合性缝普查 + 工具注册表套件工单

> 可独立分发。前置工单：`2026-08-29-runtime-conformance-suite-workorder.md`（运行时后端缝，可并行开工，两单各开各的分支）。
> 本单定位：把符合性测试从「一次性工程」变成**可复用资产**——用户自举其他 agent 时（同 harness skill / agent-run-triage skill / divergence-distill skill / 组件打分器的定位）直接搬走模式与判据。

## 背景

符合性测试的价值公式：**一套夹具 × N 个实现**。判据：一条缝后面 ≥2 个实现、且实现会各自演化，就值得建套件；单实现的组件用普通单测，不要过度设计。运行时后端缝（4+1 实现）已单独立单；本单做两件事：**普查还有哪些缝够格**（任务 A），并把已确认够格的**工具注册表缝**建起来（任务 B）。

## 任务 A · 缝普查（先做，产出决定后续工单队列）

**方法：走宏观理解路由的地图，不要通读代码。** AGENTS.md「宏观理解路由（六层地图）」那张表是入口：

| 地图 | 在本任务里查什么 |
|---|---|
| `python3 scripts/code_map.py query`（stale 先 build） | 搜 `Protocol` / `runtime_checkable` / ABC / 鸭子类型 `getattr(x, "方法", None)` 形状的接口定义点，及各自实现数 |
| `.agent-memory/10_knowledge/finance-agent-capability-graph.md` | 能力节点里哪些是「一名多实现」（先跑 `graph_audit.py` 拿当前数，别抄旧数） |
| `docs/agent-product-door.md` | 门/两条引擎/积木——积木层的可替换位 |
| `git -C ~/harness-reference show gitea/main:DESIGN-stack.md` | 六层骨架里哪些层声明了可替换 |
| `.agent-memory/10_knowledge/agent-system-closed-loop-first-principles.md` | 闭环回路上的多实现节点 |
| `docs/learning/ledger-map.md` | 多写入者/多消费者的台账契约（写入者是否守同一 schema 契约） |

**已知候选（普查时验证，不要只做这几个）**：providers 链（`detect_providers` 多家适配器 × `LLMProvider` 接口）、Episode 会话（`ResumableAgentRuntime` 已在前置工单覆盖）、判官链（`CONTINUOUS_VERIFIER_CHAIN`）、检索模式（`--kb-mode` / `--wiki-rag-mode` 的多后端）、技能桥（当前刻意只开一个——**如实登记为 N=1 不够格**，别为了凑数把设计约束当缝）。

**产出**：`docs/verification/2026-08-29-conformance-seam-census.md`，表列：缝名 / 接口定义处（文件:行）/ 实现数与清单 / 漂移风险（各实现是否独立演化）/ 已有散装断言（哪些单测已在测契约）/ 建议优先级（P0-P3）/ 一句话理由。**每行必须给代码出处，禁止臆测**；N=1 的候选也登记（标注「不够格及原因」），防止后人重新发现一遍。

## 任务 B · 工具注册表缝套件

缝：`research_tool_registry.py` 的 `_DEFAULT_TOOL_METADATA` 12 个工具 × 统一的 `ToolSpec`/`ToolObservation` 契约。工具个数用解析器数（AGENTS.md「数数别用固定行号”），不要写死 12。

不变量草案（执行时按代码校准，格式同前置工单 INV 表）：

| # | 不变量 | 出处线索 |
|---|---|---|
| T-1 | 返回形状守 `ToolObservation` 契约（公共字段齐全、类型正确） | `research_tool_registry.py` |
| T-2 | 只读保证：任何工具不产生写副作用（DuckDB 只读连接、无外呼写入） | agent 只读红线 |
| T-3 | 参数校验 fail-closed：坏参数抛 `InvalidResearchToolArguments`，不静默容错 | 同上 |
| T-4 | 拒绝时 `detail` 非空且可操作（哪个参数、错在哪、该怎么改） | `episode_tool_batch.py` ToolCallResult 注释，2026-08-12 事故（15 次失败 14 次同形状重复因 detail 恒空） |
| T-5 | 证据发射契约：产出可绑定的证据（带来源/编号），供 grounding 对账 | evidence ledger |
| T-6 | 尊重 stage deadline / 取消信号 | 批次共享窗口 |
| T-7 | capability 名与注册表元数据一致（门控裁剪后不可见即不可调） | `episode_tools.py` |

机制复用前置工单三件套结构：**参数表（逐工具）+ 能力声明表 + 棘轮 baseline**。同样零网络零 LLM——工具的下游（DuckDB/检索服务）用夹具替身；DuckDB 可用临时只读小库。

## 资产沉淀（本单的核心交付，不是附带品）

1. 套件建成后，把**模式本身**回写 `~/harness-reference/TOOLKIT.md`（审计件），条目格式按 BUILD.md 零件三问：**失败形状**（静默行为缺席，消融与覆盖率审计均不可见）/ **关键设计**（参数表 × 能力声明 × 棘轮 baseline 三件分离；「声明不支持」必须显式，静默跳过判红；阳性对照入 baseline）/ **移植要改什么**（换仓时重写 backends/参数表与夹具替身，判据与三件结构不变）。
2. 回写 `KIT.md` 指针一行，不另建清单。
3. 缝普查的**判据**（≥2 实现且独立演化才建套件；N=1 登记不建）一并写进 TOOLKIT.md 同一条目——判据是资产的一半。

## 验收

- [ ] 缝普查报告落盘，每行带代码出处；含「不够格」名单。
- [ ] 工具注册表套件跑通：`.venv-workbench/bin/python -m pytest`，逐工具参数化，红的入 baseline 带原因。
- [ ] TOOLKIT.md + KIT.md 回写完成（三问格式）。
- [ ] 普查发现的新缝：每条 P0/P1 各立一张后续工单占位（一段话即可），登进 backlog INDEX 的续表。
- [ ] 分支 `test/conformance-seam-census`，pathspec 提交，不合 main，交接文档登记。

## 红线

同前置工单：禁 `git add -A`；不改生产代码（发现缝设计缺陷登记 finding）；用 `.venv-workbench/bin/python`；台账号走 `claim_ledger_id.py`；IMA 通道不碰（与本单无关，防手滑）。
