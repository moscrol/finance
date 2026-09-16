# 02｜下一步研究排序：用有限时间核查最重要的判断

日期：2026-09-13。类型：执行型首版 spec。开工先读 [并行总合同](README.md)，本轨只负责研究任务排序，最后由 06 接入 Workbench。

用户收益：面对许多未解问题，先看到今天能核查、与已有判断关系明确的几项；每项说明为何在前、查到什么才算结束。技术顺序是来源真实 > 可解释 > 稳定 > 排得复杂。

## 1. 默认选择与范围

首版用确定性的分组与排序规则，结果标“研究优先级”，不称预期收益、不声称算出了信息价值的概率。理论上的信息价值是补充资料能改善决策的程度；本轮先让排序理由和实际结果可回检，05 再测它是否省时、减少漏检。

- 输入复用 01 的变化项、已有研究项目的未解问题与下一问、现役 research_queue/data_requests；不重建日更生产队列。
- 用户可以给分钟预算，省略时默认仅列前三项；前三项与每对象最多一项是首版界面约束，配置随 policy_version 记录，不是金融有效性阈值。
- 分析单元是需要补证据的任务，不是股票排序。不根据点赞、热度或用户喜欢某题材认定证据更可靠。
- 不执行抓取、补库、支付或发消息；点击执行复用既有研究对话正门。缺权限、等未来发布的任务进入等待区。
- 无预算时不捏造完成时间；成本未知始终可见。

## 2. 已有实现与本次增量

已在 5fb13a8c 阅读：

| 现有载体 | 现有职责 | 本次如何复用 |
|---|---|---|
| intelligence/services/research_queue.py::build_research_queue | 将日报结论分为 IMA、官方证据、等盘面、降级观察，并按现有优先级排序 | 只读适配到候选任务，保留原 queue/schema/来源 |
| intelligence/services/foresight.py::rank_questions | 按 novelty/relevance/diversity 与用户兴趣排序、文本相似去重 | 保留现役“猜你想问”；本模块产出另一种明确的研究任务排序，不覆盖原评分 |
| intelligence/services/research_project.py::load_project、_reorder | 同会话研究状态、触发点、下一问与失效先验 | 06 提供已过滤同用户同范围的项目输入，02 不再解析聊天正文 |
| intelligence/services/data_requests.py::build_requests、plan_resume | 收集窗口缺口、按消费者生成补数请求与恢复计划 | 引用已有请求 id/状态，不自行填库或伪造已恢复 |
| intelligence/services/ranking_contract.py | 多公司比较与改判条件表达 | 本任务不修改公司排序，也不把研究任务优先级转换成荐股顺序 |

增量是统一的可核验任务对象、按判断关系与可执行性排序、时间预算、结束条件及可回检选择记录。

## 3. 文件边界与任务 0

只写 intelligence/services/research_priority/、intelligence/tests/test_research_priority_*.py、intelligence/tests/fixtures/research_evolution/02/，以及本轨进度目录。建议模块 contracts.py（类型/校验）、adapters.py（只读转换）、ranker.py（排序与预算）、render.py（不损失理由的投影）；可以减少文件，不增加通用编排层。

公共 API/UI/用户路径、既有队列、原路由、公共注册表由 06 处理。若已有实现能够直接覆盖某项，提交符合性测试与映射，不复制代码。

任务 0：核对上述符号与实际 schema；列出 01 输入合同到本轨字段的映射。旧候选若缺 object_ref，就标 legacy_unbound，不能把同名主题当原判断绑定。记录基线与专属白名单到 docs/superpowers/plans/2026-09-13-research-evolution/02/PROGRESS.md；跨轨诉求写 BLOCKED.md。

## 4. 对象合同

服务对外提供两个纯接口：adapt_candidates(source_records, context) 与 prioritize(candidates, policy, budget, evaluation_at)。evaluation_at 是06注入的可信UTC评估时刻；包内不读系统时钟。名称可按仓内惯例调整，但参数语义与 JSON 固定；来源读取、资源授权与点击执行属于 06。

ResearchTask：

    schema_version: research-task/v1
    id, owner_user_id
    scope: {conversation_id?, entity_refs[]}
    source: {kind, id, namespace, version_or_hash, scope}
    object_refs[]: {kind, id, namespace, version_or_hash, scope}
    maintenance_item_ids[]
    question, discriminating_evidence, completion_condition
    effect_kind: abandon_or_downgrade | review_changed_evidence | verify_due_condition | fill_gap | explore
    effect_evidence_refs[]
    condition_result: true | false | unknown | null
    availability: actionable | waiting_release | missing_permission | missing_data | unsupported
    available_at?, due_at?, as_of, knowledge_cutoff, pit_grade
    effort: {seconds: number|null, kind: observed|user_estimate|unknown, source_ref?}
    gaps[], legacy_unbound: boolean

effect_kind=abandon_or_downgrade 只能从 01 明确登记的条件角色及已观测触发推导。source_hash 改变最多为 review_changed_evidence；不能按标题里的“利空”认定触发。

PriorityReport：

    schema_version: research-priority/v1
    id, owner_user_id, generated_at, evaluation_at, as_of, knowledge_cutoff
    policy_version, input_digest
    budget: {minutes: number|null, max_items: integer, max_per_object: integer}
    selected[]: {task, rank, group, reasons[], estimated_seconds}
    deferred[]: {task, reason}
    blocked[]: {task, reason}
    critical_not_selected_ids[]
    totals: {candidate_count, selected_count, known_seconds, unknown_effort_count}
    gaps[], limitations[]

幂等 id 与 input_digest 不含 generated_at，但冻结 evaluation_at；同输入/同策略/同评估时刻的 selected/deferred/blocked 内容与顺序一致。due_at/available_at 与 evaluation_at 比较，市场as_of和资料knowledge_cutoff另管数据可知性，不能充当当前时钟。历史重放显式给历史evaluation_at，不读当前时钟补当时排序。所有候选必须恰好在三组之一；过滤掉重复候选时保存 merged_source_refs，不静默消失。

## 5. 规则与预算

### 5.1 可执行性先行

先校验 owner、范围、版本、截止与引用。越权或未知 schema 拒绝整份输入并给具体错误；资料尚未发布、缺权限、缺数据或不支持的操作进入 blocked，仍展示该任务及解除条件。未观测的条件不能标已触发。

### 5.2 优先分组

只对 actionable 排序。以下组号是优先序，不是概率或收益分：

1. 已确认跟踪对象的放弃/降级条件被可核验数据触发，且尚未复核。
2. 跟踪对象所依赖的证据发生需复核变化；对象的结论是否仍成立尚待判断。
3. 到期或逾期的明确条件，当前资料已经足够核查。
4. 与某条已登记判断绑定、可说明“补到什么会改变判断”的缺口。
5. 其余探索任务，包括没有有效判断绑定的旧队列项。

同组按 due_at 从早到晚（无期限排后）→ 已核验受影响对象数从多到少（按 owner+kind+id 去重，不按引用条数）→ effort.seconds 从小到大（未知排后）→ id 字典序。用户显式置顶可作为单列 user_pinned 顺序呈现，不改证据或归入“算法更看好”。v1 可以不实现置顶，但不得从隐含兴趣推导它。

### 5.3 选取与解释

- 未给分钟预算：按上述序选择最多 max_items，默认 3；每个已绑定对象默认最多 1 项，其余入 deferred。
- 给定预算：按上述序扫描，已知耗时且在剩余预算内的任务入 selected；超预算入 deferred，继续考察后面的任务。预算为 0 时 selected 为空。该贪心选择不声称是最优分配。
- 耗时未知的任务不计为 0，也不自动塞进有限预算；入 deferred(reason=effort_unknown)，用户可先估时或单独执行。
- 总预算不足时所有被省略的第 1 组任务都列 critical_not_selected_ids，不能因前三项限制隐去关键变化。
- 同一证据可服务多个判断，优先合成一个“核查该证据”的任务，列全受影响对象；仅文本相似但对象或时间窗不同，不合并。
- 任务完成条件必须可检查，如“读到指定公告版本并核对字段 X”；“再深入研究一下”不是合格完成条件。无法机器判定的语义题标 human_review_required，保存待审表达，不能模型自行签完成。

解释直接由输入事实和规则生成：为什么排这里、依赖哪条判断、还缺什么、需要做什么、什么时候停止。解释不得包含预测收益、虚构概率或不存在的数据源。

## 6. 与 01、05、06 的接口

01 输出变化项，02 只读；缺 01 真模块时可使用带 synthetic 标签的合同夹具并行开发。最终必须拿 01 的真实输出跑一次，不得只验手写同形 JSON。

06 展示 selected/deferred/blocked；点击任务时带 task_id、source_refs、conversation_id 和原 scope 进入既有对话。用户选择与完成动作由 06 存储，02 不因“用户点了”就标原判断正确或任务成功。

05 用 task_id 关联曝光、选择、启动、完成、放弃与人工裁决。排序策略变更带 policy_version，评价“同等质量下完成时间/漏检/无效执行”时按版本分列；不能用点击率证明研究有效。旧研究队列继续保持唯一 canonical 输出。

## 7. 验收场景与反向证伪

以下必须成为可运行测试，每条使用可理解的固定输入与精确输出，不将被测 ranker mock 掉：

| 编号 | 场景 | 必须结果 |
|---|---|---|
| P01 | 一项已触发放弃条件、十项高热度探索 | 放弃条件在第 1 组，热度不改变证据等级 |
| P02 | 只有来源 hash 变化、没有条件判定 | review_changed_evidence，不得伪升组 1 |
| P03 | 明天才发布的资料与今天可查的条件 | 前者 waiting_release，后者可选 |
| P04 | 预算 10 分钟，优先序耗时 12/6/4 分钟 | 12 分钟项 deferred，6 和 4 被选；合计不超 10 |
| P05 | 预算 0、未知耗时、空输入 | 分别为空选择/未知不当零/结构完整的零项报告 |
| P06 | 同证据影响三个判断，同时重复进两份队列 | 一项核查任务、三个唯一对象、保留全部来源 |
| P07 | 相同问题文字、不同实体或时间窗 | 保持不同任务，不按文本相似误去重 |
| P08 | 前三项限制掩盖第 4 个关键放弃条件 | critical_not_selected_ids 有该项 |
| P09 | 其他用户相同 id、无权引用、未来记录 | 拒绝越权；未来对象不进入评分 |
| P10 | 重排输入、重复读取 | 在同去重后输入集合下输出顺序与摘要一致 |
| P11 | 没有 object_ref 的旧队列 | legacy_unbound 且第 5 组，不假装维护原判断 |
| P12 | 01 真输出跨到 02，返回含 gap/unknown | unknown 不升为触发，gap 保留，所有候选可对账 |
| P13 | 固定昨日as_of与同一cutoff，评估时刻跨越到期/发布时间 | 时间状态仅按evaluation_at改变，资料仍须可知；历史重放不受运行机器时钟影响 |

反向证伪至少两项：把未知耗时临时按零处理，P05 必红；把 hash 变化临时当放弃条件触发，P02 必红。变异放隔离测试过程，结束恢复代码并留红→绿收据。

新验收命令（执行者实现后运行）：在本树按解释器约定运行 python -m pytest -q intelligence/tests -k research_priority，并对本轨新文件运行 Ruff；另跑现役研究队列、foresight 与 research_project 相关测试。执行前用 --collect-only 证明确实收集到本轨测试，零收集不算成功。公共完整门禁由 06 在最终候选上执行。

## 8. 实施顺序、进度与完成条件

1. 任务 0 与现役源 schema 映射；冻结最小正/反夹具。
2. 写适配和合同校验，处理 legacy_unbound/范围/截止；先拿真实脱敏输入做只读转换。
3. 写分组、去重与预算，完成 P01–P11、P13；生成可对账报告。
4. 和 01 真输出做 P12，向 06 交付 JSON 样本、稳定调用接口和错误码；向 05 交 task_id 与 policy_version。
5. 在独立分支绑定最终 SHA 保存检查收据；PROGRESS 写实际完成，BLOCKED 写未接线项或“无”。

两条硬完成条件：所有候选、预算与理由都可由输入独立重算且反向证伪有效；01 真产物能被消费，旧队列/权限/用户状态没有副作用。至此可报 engineering_complete。用户真实省时、付费或更准由 05/03 另验，本轨不得提前宣称。
