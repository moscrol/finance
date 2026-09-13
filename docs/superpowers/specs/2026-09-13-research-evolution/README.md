# 时间长河后续优化：并行执行总合同

日期：2026-09-13。状态：用户已要求编写并行执行规格；本文冻结本批首版范围，供执行 agent 开工，不代表代码已实现或产品效果成立。

## 1. 目标与本批选择

让用户已有的研究判断得到持续维护：知道哪些依据变了、先核查什么、自己重复错在哪；同时建立方法增量、概率预测和真实用户价值的独立验证。最终通过现有 Workbench 入口交付。

本批按用户“写几份 spec，交给 agent 并行优化执行”拆成六份。以下是本轮默认设计选择，可由用户以后调整，执行时无需重新采访：

- 首批使用者是已经复盘、已有粗略框架、愿意记录判断的个人；团队只做需求验证材料，不建设多租户团队系统。
- 默认单用户私有，市场数据库只读；维护动作由用户在产品中明确执行。
- 概率验证先在研究实验中运行，手动登记或已有可信预测输入均可；不把试验概率自动放进普通答案，不改现有观察剧本合同。
- 默认无新增定时任务、无消息外发、无自动交易；打开工作台或用户点击刷新时计算变化。可复用当前导入资料和只读快照。
- 本批按依赖收敛，不以“六个 agent 都写完代码”作为用户路径验收完成。

## 2. 六份规格与并行关系

| 编号 | 规格 | 本轮可交付结果 | 依赖与开工方式 |
|---|---|---|---|
| 01 | [判断持续维护](01-judgment-maintenance.md) | 可追踪的变化项、复核动作、缺口状态 | 独立开发；既有判断与证据由只读适配器输入 |
| 02 | [下一步研究排序](02-research-priority.md) | 有依据、受时间预算约束的研究清单 | 先消费冻结的 01 JSON 夹具；随后用 01 真产物联测 |
| 03 | [方法与概率验证](03-method-validation.md) | 消融对照、前向登记、概率评分与诚实状态 | 独立开发；真实未来未到时返回 pending |
| 04 | [个人错误诊断](04-personal-diagnostics.md) | 可举证的流程诊断与针对性练习 | 可独立消费旧台账；01 的变化证据先用合同夹具 |
| 05 | [用户价值与商业试点](05-product-value-pilot.md) | 测量与成本工具、四周试点材料、团队访谈材料 | 独立开发离线测量；真实产品事件由 06 接入 |
| 06 | [Workbench 集成与验收](06-workbench-integration.md) | 同一用户入口完整使用 01/02/04，查看 03/05 收据 | 可先做页面与适配器，最终验收必须接真实模块 |

依赖图：01 → 02、04；01/02/03/04/05 → 06。箭头表示最终联测依赖，不阻止按冻结合同并行编写。06 的夹具阶段只能报“接线开发中”。

若只有三名执行者：先做 01、03、05；空出后做 02、04；06 可以先准备界面与适配器，最后集中联测。分支的合并顺序由集成人按依赖安排，不让领域 agent 互相修改对方代码。

## 3. 现状证据与避免重复立项

代码基线是新建干净工作树的 gitea/main，提交 5fb13a8c。执行开始时重新 fetch 并记录实际基线；已经同等实现的项改做符合性验证，不能再造一个平行系统。

| 基线已存在 | 入口或符号 | 本批增量 |
|---|---|---|
| 研究项目投影、触发点、下一问、研究先验 | intelligence/services/research_project.py::load_project、prior_for_turn；GET /api/conversations/{id}/research-project；ResearchProjectPanel.tsx | 加有证据版本的持续维护与操作结果，保留旧研究轮次 |
| 判断、可证伪点、回检 | judgments.py::record_judgment；checkpoints.py::register_checkpoint、record_verdict | 旧字段缺证据绑定时明确 unknown，不编原始依据 |
| 证据角色与差分 | intelligence/services/judgment_delta.py | 复用角色、去重思想；补明确对象依赖和更新失效边界 |
| 两种情景树实现 | scenario_trees.py 是持久化条件树；scenario_tree.py 是表达合同 | 分清实际数据对象，不互相冒充 |
| 日报研究队列、主动问题排序、补数请求 | research_queue.py::build_research_queue；foresight.py::rank_questions；data_requests.py::build_requests | 按可改变判断的证据与研究时间排序，不再建第二张日更队列表 |
| 相关样本统计与历史演练 | methodology_backtest/stats.py::block_bootstrap_readout、combined_verdict；已有 replay 与概率评分函数 | 核验适用输入与增量价值，建立前向冻结实验谱系 |
| 真实 run、自用成熟度、上下文用量 | run_store.py::RunStore；self_use_maturity.py::verify_run_binding；context_growth.py | 分开产品使用、学习效果、方法有效性与全口径成本 |

上述是代码阅读证据，不是生产部署证明。主工作区在本轮有大量他人未提交改动，本批不接管。主工作区 09-06 统一 spec 与 BP v1.2 比 main 中对应版本更新；本批按用户后续决定保留“大盘、板块、题材研判；不荐股、不提供个股买卖建议”，不因旧稿措辞倒退为禁止一切研判。旧 BP 收入、免费数据与成本数字不能作为已验证事实。

代码地图 query 在主工作区长时间无返回，本轮停止了自己发起的进程，改为按能力图谱、精确文件与符号定位；未以地图无结果断言能力缺失。后续执行仍按 AGENTS.md 核对地图状态。

## 4. 文件所有权

以下为本批实现时的所有权，不是说这些新路径今天已存在。每份 spec 自带测试、离线夹具和进度目录；代理只能写自己的区域。

| owner | 独占业务代码 | 独占检查与产物 |
|---|---|---|
| 01 | intelligence/services/judgment_maintenance/ | intelligence/tests/test_judgment_maintenance_*.py；fixtures/research_evolution/01/ |
| 02 | intelligence/services/research_priority/ | intelligence/tests/test_research_priority_*.py；fixtures/research_evolution/02/ |
| 03 | intelligence/services/research_validation/；intelligence/eval/research_validation/ | intelligence/tests/test_research_validation_*.py；fixtures/research_evolution/03/ |
| 04 | intelligence/services/research_diagnostics/ | intelligence/tests/test_research_diagnostics_*.py；fixtures/research_evolution/04/ |
| 05 | intelligence/services/product_value/；intelligence/eval/product_value/ | intelligence/tests/test_product_value_*.py；fixtures/research_evolution/05/；docs/research-pilots/research-evolution/ |
| 06 | intelligence/api/research_evolution.py；intelligence/services/research_evolution/；现有 API/UI 的薄接线 | intelligence/tests/test_research_evolution_*.py；fixtures/research_evolution/06/；前端本功能测试 |

表中 fixtures/ 均指 intelligence/tests/fixtures/。06 是 intelligence/api/app.py、intelligence/services/research_project.py、intelligence/userspace.py、intelligence/webapp/src/ 公共入口、docs/learning/ledger-map.md、docs/agent-product-door.md、UBIQUITOUS_LANGUAGE.md 的本批唯一修改者。能力图谱更新由 06 统一申请路径变更并按现行图谱规范登记，不让六人同时改共享记忆。01–05 可以读这些路径。

01–05 的服务接收已验证的 owner、输入对象及注入的资源，不从 cwd 推断生产根。若需公共源模块修改，在本轨 BLOCKED.md 写最小补丁诉求及复现；06 处理接线，领域规则仍由对应 owner 提交。不得因白名单限制把复制旧模块当成绕行。

## 5. 共同边界与交换合同

各输出 JSON 的详细 schema 由所属规格定义。跨轨共有规则：

1. 归属统一名 owner_user_id，来自经验证的用户上下文。请求正文的 owner 不能替代访问控制。用户态路径统一由现役 userspace.user_space(user).root 解析，执行环境必须显式核实 FORESIGHT_USERS_DIR。
2. schema_version 带命名域与版本；报告有稳定 id 与输入摘要。generated_at 是生成时间，不混作事件发生日、首次知道时间，也不进入可复现的内容摘要。
3. 引用保留 kind、对象 id、版本或不可变 hash、来源命名空间；相关 conversation_id/run_id 作为范围约束。不同用户相同 id 不能碰撞。同一主题名不等于同一判断对象。
4. 市场日 as_of、知识截止 knowledge_cutoff、事件时间与记录时间分开；复用现有 river 的实际粒度和 pit_grade，不能给日频源补一个假盘中时间并称严格可知。
5. 新字段无法从旧记录证明时，输出 null + reason/gap。缺记录不等于事实为假，UNKNOWN 不得变成零、失败或已解除。
6. 原始判断及 verdict 仍以既有台账为唯一事实源。本批新对象存管理动作、实验登记或使用测量，不再复制一套可编辑原判断。新台账由 06 在 ledger-map 登记格式、唯一写入者、派生视图和用户态路径后才启用。
7. 01/02/04 核心处理确定性、无模型；03 的评分与门禁确定性；05 的测量计算确定性。模型解释、语义建议只能作为另标的候选，不能替判定器出结果。
8. 夹具统一标 synthetic，只作工程验收；field 用户效果、方法支持和付费状态不得从夹具生成。report 可下载不等于获准公开用户数据。

本批不发明共享 Python 基类作为所有轨的硬依赖。可以用结构化 JSON 与各模块自有类型先并行，06 在边界做严格适配和合同测试；字段调整先更新本目录合同与受影响夹具，再改提供方/消费者。

## 6. 执行、收据与断点续跑

每名执行者先读本文件与自己的 spec，然后按本仓 AGENTS.md 建独立工作树。进度固定到 docs/superpowers/plans/2026-09-13-research-evolution/<编号>/PROGRESS.md；问题写同目录 BLOCKED.md。先登记开工基线 SHA、spec 来源 SHA、实际用户态根、现有实现映射、计划修改路径；每完成一个可验证单元立刻更新。

代码只在已认领路径上提交，git add 与 git commit 都带 pathspec；保留所有既有有效测试。新测试验证真实函数或隔离真实链路，不能通过删断言、改 frozen case、跳过失败、mock 被测主体、只生成文件或只看 exit 0 达标。外部 IO 可以使用固定夹具，但报告必须带 synthetic 标签。

各 spec 的“新验收命令”是要求执行 agent 实现并运行的接口，不代表本轮已存在。本轮没有写实现代码；现役解释器按 AGENTS.md 的 .venv-workbench 路径获取，新 worktree 可用主树绝对解释器。测试结果须绑定最终 SHA、命令、退出码、通过/失败/跳过数与原始输出位置。

定义三个完成状态：

- engineering_complete：模块真实计算、合同/负例/边界通过，可由其他模块调用。
- product_verified：06 在隔离 Workbench 的真实 UI/API 与真实模块上跑完全链，并保留产物/版本收据。
- field_evidence：用户试点或真实前向样本已实际产生；可以是 pending/insufficient/unsupported，不要求强行变 supported。

01–05 完成不能替 06 签字；产品工程成功不能替方法有效或商业成功签字。原第二/第三轮材料题、数据补齐、8792 部署、L2、工单 #50/#740 等原任务仍由原负责人推进。

合并前执行现役等价 CI 与 registry/e2e 门禁，按 AGENTS.md；合并 main、部署生产仍等用户确认。本批只准备独立分支与可审验产物。03 产生的真实实验若需 R-号，走现有 claim_ledger_id 原子领号，不手工编号。

## 7. 本批之外的方向

事件定价继续沿已有 event-pricing 与 pricing_split 线路，本批不立重复大改。团队权限与采购、基金经理能力评价、持仓暴露与决策归因、对外验证接口、方法市场暂列后续选项；05 只形成需求证据与进入条件。多个客户购买同一流程、数据权利和交付成本可证后，再各立独立 spec。

来源：用户本轮授权及前轮战略讨论；[统一终局设计](../2026-09-06-personal-research-calibration-endstate-design.md)、[事件定价设计](../2026-09-07-event-pricing-slice1-calendar-reaction-design.md)、[历史发现设计](../2026-09-09-historical-discovery-research-design.md)。本目录是首版优化执行合同，不把待验证商业假设升级为既成事实。
