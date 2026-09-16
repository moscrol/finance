# Knevo 第 15-28 轮增量吸收与生产画像复核

日期：2026-09-16。分支：`feat/knevo-absorption-closeout`，基底 `c29a6401`。
本单补的是既有能力的工作纪律，不复制一套路由、工具或记忆框架。

## 1. 来源与判断边界

- 原始材料：`~/agent-memory/60_dialogues/knevo/2026-08-08-工具编排与step上限-44轮原文.md`，按轮次定位。
- 前次审计：`~/agent-memory/10_knowledge/knevo-44turn-rounds15-36-distill-2026-09-16.md` §2。
- 原文只留在私有资料库；这里记录改写后的决定和代码位置，不复制全文。
- “8 项未覆盖”是资料审计的分母，不是本仓缺 8 个产品能力。
- 以下代码交付不等于生产已部署，也不等于盲测证明了增益。

## 2. 八项逐项处置

| 原文项 | 已有承载 | 本次增量与处理 | 验收层级 |
|---|---|---|---|
| 18 财报复盘 | `research_owner.FINANCIAL_ANALYSIS`、`financial_data`、`financial_analysis` 槽 | 报告期/披露时间/币种/累计与单季；实际、上期与事前一致预期分列；利润质量交叉验证；缺预期不可称超预期；历史判断四态更新 | 双引擎提示契约接线，非财务真实性证明 |
| 19 事件推演 | `event_forecast`、`scenario_tree` | 事件判定与截止、决策者权限/历史/约束、互斥情景、发生概率与条件影响分开；无基准不编概率，赔率不等于真实概率 | 同上，不新增预测模型或赔率源 |
| 19 KOL/观点审查 | `kol_review`、Perspective Lab | 单段观点审查与历史画像模拟分开；不靠标题重建论证；激励有证据才陈述；保留矛盾和置信边界 | 同上，不自动写画像 |
| 19 事实核对 | `fact_check`、既有 evidence verifier / memory gate | 数值口径、实体、出处、逻辑、时效、完整性六维；未知不算通过；需要修订时正文与修订记录同时交付 | 六维为生成纪律，不冒充新增语义审稿器 |
| 19 联想 | `comparison_analog`、`graph_lookup` / `memory_lookup` | 产业链、竞对、宏观、事件、不同主体观点、历史模式按相关性取用；逐条讲关联理由、验证及失效；历史类比列差异 | 同上，不强凑六维、不将图边升格为因果 |
| 26 所谓消融 | 既有工具 schema、`_TOOL_CONTRACTS`、调用权限测试 | 判为同会话假设性重构，不是隔离后的 A/B 实验；吸收“工具描述管接口，工作纪律管使用策略”的分工。三个现有工具补防误用描述 | 描述真正送入 function definitions，有负例；不报消融分数 |
| 27 skill/harness 边界 | `ResearchToolRegistry`、`EpisodeScope`、finish verifier、`memory_gate` | 保留硬权限/参数/证据绑定与软分析质量的区别。拒绝用标题扫描宣称语义正确，拒绝“没发现问题就 PASS” | 权限/范围回归；未新增审稿器或写回通道 |
| 28 检索架构 | 已有 `graph_lookup` 与 agent 工具循环 | 归档为 Knevo 的“agent 编排单次图检索”自述；SQL-backed 描述不支持推断原生图数据库。不是本仓必须重建图引擎的依据 | 文档对账，不改本仓检索架构 |

前五项的单一实现为 `intelligence/services/research_workflow_guidance.py::workflow_guidance`。
`episode_protocol._question_type_rules` 与 `ask_synthesis._prepare_answer_spec_synthesis` 共用。
默认开启，可用 `FINANCE_RESEARCH_WORKFLOW_GUIDANCE=0` 关闭专项规则以复验。
关闭不撤销三个工具描述的更新，不改变既有证据/工具/输出槽契约。

旧 ask 的信封与最终题型可能不一致：真实研报样本的信封是 `kol_review`，最终计划却成
`financial_analysis`。本单只在规则投递处保留已识别的专项意图；显式题型 override 优先，
信封未识别时保留已有分类器的财报识别。没有增加关键词路由，也没有修复所有自然语言误路由。
测试覆盖这个真实样本，不只把手写题型喂给规则函数。

## 3. 其余重叠项与工具协议

| 来源 | 本地接法 / 决定 |
|---|---|
| 15-17 基础纪律、个股深挖 | 复用 `BaseFinanceMode`、`research_owner`、证据契约。快答不是免检索；不强制每题调用全部来源，不复制逐步固定流程 |
| 18 行业深度、行业跟踪 | 已有 theme owner、`track_contract` / 判断增量四态；不再建同名 skill。上下期无可比基线时保留缺口 |
| 20/24 注册表与参数 | `default_registry` 向模型公开实际授权的 schema；描述、参数校验、执行授权同源。不是把外部工具名抄进提示词 |
| 网页搜索与引用 | `web_search` 摘要只是线索，已授权时可用 `web_fetch` 取正文；引用由既有 evidence ledger/finish 绑定负责，不新造 `web_cite` |
| 财务数据 | `financial_data` 已支持报告期及多公司；描述新增“实际财报不等于一致预期、缺值不是零”。不虚构 consensus 能力 |
| 图谱 | `graph_lookup` 明示关系只作线索，空命中是覆盖缺口，不是无关联的证明 |
| 历史记忆 | `memory_lookup` 是先验；来源/日期与 write gate 复用既有实现，不引入 `finance_memory_write` 直写 |
| 子研究/后台任务 | 复用 `sub_research` 和 Episode 生命周期，不增加 `get_bg_task` / `wait_for_seconds` 自旋协议 |
| shell/代码/文件 | 只保留证据绑定的 `derived_calculation` 沙箱；不为工具名对齐开放通用 shell 或任意路径读写 |
| `read_skill_file` / workflow | 本次规则按本地题型投递，不授予任意文件读取。不复制外部 skill 路径、`terminal emit` 或 UI 协议 |
| Provider 状态 | 实际菜单与调用错误仍走现有观测链；本单没有新增 provider-status 工具，不能写成全部工具一一对齐 |

## 4. 风远：旧台账之后已有其他会话写入

复核对象为启动器指定的生产用户空间，不是仓内冻结存档：
`~/.local/share/finance-workbench/users/linxiaoqi5111/perspectives/profiles/fengyuan.json`。

本轮现场看到：

- `confidence.article_count=24`；`patch_history` 包含 09-16 四批评审，且 R61/R12/R65/R28 的批准记录已在。
- R27/R30/R35 等去数字版本及 7 张结构化字段卡有 `known_gaps` 归因记录；画像还记有另一会话用户授权终审。
- 这些是既有/并行成果，不计为本分支新增；本轮没有 ingest、生成候选、approve 或覆盖画像。
- 复跑现有 exam：2 道已知题 + 1 道报表审计边界题，全通过；API `/api/perspectives` 可见 fengyuan，24 篇。
- 旧考卷没有逐条考新规则，不能据此宣布全部新规则验收。未做新增真实行情问答或与 Knevo 成对盲测。
- 画像仍有需另审的强断言，例如把毛利率趋势直接等同定价权兑现、以正期望值直接推出入场。
  本单财报/事件规则保留因果与概率边界，但不覆盖用户在另一会话审定的画像。

因此 README 的“一条未写”仅能作为前次时点快照，不能继续用作当前生产结论。

## 5. 决策与仍待裁决

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 两条引擎共用题型纪律 | 新建八套平行 owner/skill | 原有能力已在，缺的是局部规则；避免第二套路由和权限表 |
| 缺数显式降级 | 每个情景强填概率、每份财报强给 beat/miss | 没有可比预期或校准依据就没有数字资格 |
| 保留现有硬门 | 复制 Knevo 的统一误差百分比、零问题直接通过、报告自动写记忆 | 数值单位/重要性不同，生成纪律不是授权或真实性判据 |
| 保留三组冲突证据 | 静默统一外部架构自述 | 风远是否是 finmemory 子集、直写与提案纪律、主 agent 是否二次压缩仍需裁决；不影响本仓维持只读和提案门 |

本单没有启用 W3 可靠性降权阈值，没有改冻结 28 题或接 q18 runner，没有批准暂停 B 线。
B/C 对照样本、语义审查的真实效果、全部自然语言路由覆盖仍不是已完成项。

## 6. 验证范围

- 最终相关回归合跑：575 passed，覆盖专项规则、Episode 协议/harness、工具合同、材料范围、既有定价与判断增量、ask/chat 与记忆链。收据：`~/.finance-runtime/test-receipts/20260916T141141Z-c29a6401.json`，对象为本分支当时的未提交改动，不冒充基底提交的收据。
- 全仓 `ruff check .` 通过；工具目录保鲜检查先报 `tools.md` 过期，再用 `scripts/gen_runtime_catalog.py` 正式重生成。
- 初次测试命令含不存在的 `test_research_tool_registry.py`，exit 4、0 tests；修正为实际测试文件后才得到通过收据。
- 本单未宣称全仓 CI、前端、端到端模型效果或部署通过。完整提交后收据见分支交接。
