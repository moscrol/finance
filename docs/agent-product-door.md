# 金融 Agent：产品门 / 两条引擎 / 积木

评接口深浅、找「入口」、宣称「我们没有 X」之前读本页。
能力有哪些节点仍以能力图谱为准，本页不抄工具表、不写死个数。

**深模块** = 调用方每学一单位接口能驱动多少行为。接口包括签名、不变量、必须知道的配置。数参数个数当深浅，会把测试旋钮当成生产门。

## 先分四层，不要压成一句「架构」

| 层 | 人话 | 代表物 | 是不是门 |
|---|---|---|---|
| **产品门** | 人/UI/脚本真正走进来的地方 | 见下一节 | 是 |
| **引擎** | 进门之后怎么跑一轮研究 | A 连续 Episode；B 写死流程 `answer_query` | 不是门 |
| **组装** | 把零件接到引擎上 | `GLMAgentRuntime`、`episode_factory.build_episode_context`、`episode_tools`、`default_registry` | 不是门 |
| **积木** | 引擎内部的零件 | `ResearchToolRegistry`、`llm_refine`、`perspective_lab`、数据块注册表 | 不是门 |

删掉积木，复杂度会散到每条引擎；删掉门，人会找不到入口。两件事不要混着打分。

## 产品门（当前该走的入口）

| 谁 | 走哪扇门 | 合同 |
|---|---|---|
| 人 / 编码 agent 一次性提问 | `python3 -m intelligence.cli ask "<问题>"` | 默认只收问题字符串；`--wiki-rag-mode` 等是逃生口 |
| 同一会话追问 | `python3 -m intelligence.cli chat` | 首轮仍是 ask 管线 |
| 显式要模型自己选工具 | `python3 -m intelligence.cli agent` | opt-in，默认不影响 ask/chat |
| Workbench 对话 UI | `POST /api/conversations` → `TurnOrchestrator.run_turn` | 有 `conversation_id` / `run_id`；不要用 CLI 冒充这套 id |
| 维护旧判断 / 选下一项研究 / 看个人诊断 | `GET /api/conversations/{id}/research-evolution`（+ `POST` 的 `bindings` / `actions` / `events`） | 挂在**既有会话**下的内容区，不是第三条问答引擎：判定全部回调 01–05 的真函数，本层只取数与授权。`?user=` 不是认证——未配认证层时只认服务配置用户与 `RESEARCH_EVOLUTION_ALLOWED_USERS` 白名单。管理动作**不能冒充新判断**：关闭维护项要指到原写入者写下的新判断行 |
| 研究跑到一半插一句话 | `python3 -m intelligence.cli steer <episode_id> "<文本>"` | 运行底座 P3 收件箱（INV-R5）的跨进程门：写 durable 目录投递槽 `<episode_dir>/inbox-spool/`，loop 下一次模型请求前认领；`--list` 看在跑的、`--wait N` 等回执。store 根必须与 Workbench 进程同一套 `FINANCE_WS` / `FORESIGHT_EPISODE_STORE`，否则是另一个家（CLI 会拒投并打出看过的路径）。Workbench 端点等 Alpha（母单 §12 第 4 题） |
| 复盘写入（另一条面） | `python3 -m market_feature_store.cli daily-full` | 飞书 Bitable 写入已退役 |
| 飞书 IM（已退役，不是门） | `python3 -m intelligence.cli feishu-bot` | exit 2，不连 WebSocket。与 Bitable 写入退役是两件事 |

编码任务「仓库里有没有现成实现」走 `python3 scripts/code_map.py query "<问题>"`，不是本页，也不是问答门。空图不得写成架构结论。

### 专项研究纪律（Knevo 增量，2026-09-17 已合 main）

`research_workflow_guidance.workflow_guidance` 给财报、事件推演、观点审查、事实核对、历史类比
五类既有题型补分析纪律；连续 Episode 的动态规则与 ask 合成共用，不增加产品门、工具或权限。
旧 ask 保留信封已识别的专项意图，显式 override 优先；不代表所有自然语言路由已经准确。
默认开，`FINANCE_RESEARCH_WORKFLOW_GUIDANCE=0` 可关。它是生成指令，不是新增语义审稿器；
权限、材料范围、证据绑定与写侧门保持原合同。代码/对账与效果状态见
[逐项吸收记录](learning/knevo-distill/workflow-absorption-2026-09-16.md)，未据此宣称部署或质量增益。PR #774 已于 2026-09-17 合入 main（`c67413c7`），部署状态仍以运行服务 `/api/health` 的 revision 为准。

### 研究答案保留（当前分支候选，未部署）

两条引擎将普通质量诊断与内容交付分开：已生成的同任务安全分析保留，数值、日期、
引用、语义和完成度疑点追加「核验批注」，修订与补写追加到原稿，不以新稿覆盖旧稿。
`delivery_mode=preserved_analysis` 不是 `judge_status=passed`，展示成功也不代表任务完整。
证据身份、授权、跨任务隔离与公开脱敏仍独立承重；安全清洗后只剩凭据占位符不算答案。
先判可公开正文，再加核验/来源批注；纯密钥或纯引用标记不能被程序附注重新撑成正文。
B 的 Grounded 合成遇此情况记 `no_public_analysis`、不调用判官，沿用确定性短答出口。

Episode 修订组合检查 E 编号是否改指、同 hash 证据语义元数据是否变化、输入是否重复；
完整性冲突不得硬拼。材料题按可无歧义解析的原题段嵌套补充，旧疑点仍须重判，
两版内容均计入备忘录字数。原调用额度与绝对截止时间不变，保留 AnswerSpec 不增开影子调用。
终局恢复已返回合法正文但结算超时，可保留该正文，仍标 partial/恢复失败，不追加调用。

准入前保留续片：`FinishAdmission.candidate` 独立表示同任务安全分析，不改变拒收，
也不授予完成资格。只识别完整信封或独立行正文加唯一末尾信封；身份、证据语义、
重复 JSON 键和 E 号改指仍硬拒。连续 Episode 按错误码分别纠正格式，研究缺口在原预算内
继续取证；正常/恢复提示取消统一 1000/1200 字要求，用户篇幅和资源上限仍在。
连续 Episode/进程内 SDK 的续修与 benchmark-only headless 的一次恢复均合入已保留候选，
顺序为原分析在前、补修在后，候选仍附待核验说明。取消后已返回的安全正文可留存，
取消仍记 failed/cancelled，不再调用工具。无正文的来源/协议/核验附注不撑成答案。
连续恢复送入完整候选与全部实际绑定/引用的证据卡，E 号不变；12卡/360字符仅约束
无关观察的紧急兜底投影，普通工具900/240预览未改。SDK不自建隐藏重试池，headless仍只
允许一次禁工具恢复，隔离失败不借保留绕过。
边界：候选保存在同进程账本；尚未接入 `EpisodeState` 的跨进程正文恢复。旧 helper
动态兼容链未全审，也不是任意模型消息都可发布。独立金融认证未完成。
2026-09-18 固定 `5f3b5b59` 的一次隔离真会话证实：已准入的 979 字终稿完整保留，
数字疑点以批注追加，核验仍 rejected、报告仍 partial；但此前两次 finish 因
`not_json_object` / `history_missing_comparison` 拒收后被恢复稿替换，早先分析未保留。
因此端到端保留验收未过，不是全面完成或 8792 已上线；
[原件、测试收据及未验边界](verification/2026-09-18-research-answer-preservation/README.md)。
准入前续片 `35ee8a5c` 的固定原件回放现保留四部分原文，仍 partial/unavailable；
[新工程收据与回放范围](verification/2026-09-18-finish-candidate-preservation/README.md)
不改原真实会话判定，也不表示跨进程恢复或新版真模型交付已验。
随后 `35ee8a5c` 的GLM隔离首发（1次、零重发）在历史查询缺结束日期被拒后，因进展
记账的只读Mapping JSON异常中断；已有3轮模型响应，但尚未到finish，保稿路径未触发。
新旧live均未通过，不能将凭据可用或邻枝局部离线修复通过当成交付认证；
[新真实失败、原形状诊断与关闭收据](verification/2026-09-18-finish-candidate-glm-live/README.md)。

### 材料题边界（E2，分阶段接线中）

D1 分类器已独立复核；P2 把完整题组/原题号、前提真实性与数据范围接入
`TaskFrame.material_contract`，随任务序列化和哈希保存。无新语义的普通问题不增加该字段。
虚构前提标注与旧 `user_premises` 分开；仅范围声明槽使用前提资格，不能替事实背书。
续轮基底未接入前载体明确 `state_unavailable`，不从助手旧答猜权限。
P2 不将此未就绪状态接成全局澄清闸；普通研究追问仍走原路由。
预取前澄清必须与 P3 权限及可信基底恢复一同接线，不能据此阶段宣称安全执行。

P3a 已接明确 `material_only` 的 Episode 装配：同一冻结合同生成空读取授权、空证据计划、
原题号 `answer_q{i}` 槽；恢复/替换合同不得重新加读权限。注册表在根路径、市场日期、实体
与开场预取之前短路；现有 dispatch 拒绝并记事件。工厂不读静态 KB，丢弃未分型的历史、
视角、stance 与检索阶段背景。这是装配层局部约束，不是整个入口的零读取保证。

P3b 在 Episode 装配层接入 `local_only` 的实际 IO（输入/输出行为）上限：
`material_permissions` 收窄能力、全部证据要求及输出工具类型；已审定的 DuckDB 查询、
主线、JSON 证据索引及已解析身份的用户记忆保留。工具实现由装配点声明 `io_effect`，
未知/混合 runner 不凭 cost/freshness 放行；菜单与执行授权共用上限，注册表副本只能
继续收窄。受限注册表不带预取/计算恢复加载器，工厂跳过未按能力分类的静态 KB 预检，
不装默认外呼工具、不为它们做全局实体解析；未审定历史附加工具暂不挂，普通本地
finance_query 的历史窗口约束保留。此处是可信装配声明与回归测试，不是操作系统网络沙箱。

P3c 将同一读取上限绑定到运行器实际持有的注册表，而不只约束 EpisodeScope 内的副本：
Episode 车道在消费预取做升档判断、可满足性预检、配置快照、提示词与证据账本播种前收窄；
批工具菜单/定义/执行和内存修复续轮也重新绑定，原始 full 注册表不被修改。
这防止外部预取先进入模型、未知 IO 工具先被列出后才在 dispatch 拒绝；不是清洗历史消息，
也不能撤销注入式 registry_factory 内部已经发生的读取。独立反例指出修复续轮同名工具替换后
Scope 可能仍授权旧实现；返修让批菜单/执行及续轮重绑 Scope 视图，保留调用/诊断历史与
既有更严读取上限，拒绝事件使用当前 runner 的判据。P3b 与 P3c+返修已在固定 `301dcd9e`
获同型号独立上下文复核通过，均仅限本片；[完整报告与原失败证据](verification/e2-boundary-closeout/qc-301dcd9e/README.md)
已归档。晚结果唯一红针判为测试二次进入过期适配器，修正保留原断言与超时；不是产品修改。

P3d 小片在 `TurnOrchestrator` 拿到本轮 TaskFrame 后，对明确 `material_only` 停止读取
旧答案产物、stance pack、研究项目先验及视角提示；使用同一 material_contract 的数据范围，
不等这些生产者读取之后才在 Episode 工厂丢弃字段。full/local_only/普通问题保持原路径。
固定 `1f6ebc5d` 已获独立复核通过，但仅限 controller 之后、Episode 之前这四个生产者：
独立探针16P，material_only四类禁止尝试0/0/0/0，正例各实际读取1，项目先验异常验证了先计数后吞错。
报告与日志见 [P3d 独立归档](verification/e2-boundary-closeout/p3d-1f6ebc5d-independent-qc-20260915/)。
不声明 controller 历史输入、确定性/legacy 回落或交付阶段已经安全。

P3e 候选在 `QueryResolver.resolve` 的词典读取前复用 D1/D2 材料合同编译；明确
`material_only` 时仅走既有文本理解，不访问实体/题材词典、证券名单或其缓存，也不注入
词典验证出的锚点/候选/比较实体。普通、full、local_only 保持原解析；不新造禁令词表，
不把未知边界或“继续”一律澄清。作者36针通过，撤闸恢复23F/13P，服务层452P/1项排除，
均不能替代独立QC；独立审查已在固定 `0b83e14f` 通过（focused 41P、相关347P，修正版禁止尝试0；首次启动器误拒41次的失败证据保留），仅限本片词典早读闸门。
[本片收据与覆盖限制](verification/e2-boundary-closeout/p3e-query-resolver-20260915/README.md)。
仍未关闭静态路由配置/日历先验、controller历史、可信继承、注入式resolver和其他旁路；
本片不宣称整个 `understand_query` 零IO或完整入口安全。

P3f 的“明确 material_only 就清空 controller 历史/旧 intent”候选已被作者反证并撤回：
它会丢掉上轮用户材料，也把已知缺材料误当未知上下文（候选两条正例2F，恢复原代码2P）。
当前应用未增加这道闸，新增正例只锁住兼容行为；不是历史来源过滤或可信续轮已经完成。
[候选原件、反例与撤回对照](verification/e2-boundary-closeout/p3f-rejected-history-clear-20260915/README.md)。

P3f1 改为**只绑定历史材料来源**：当前轮明确 `material_only` 时，从真实 completed
用户消息、材料内容身份与 message_id 构建不可变投影；只取既有上下文窗口内完整消息，
不解析正文角色字样、标题或 summary 来授予来源身份。投影经默认 controller 到 TaskFrame，
已知空投影不回退猜测；旧注入 controller 签名兼容，legacy frame 重建使用同一投影。
普通/full/local_only 等其他路径保留旧行为。这不是 controller 模型提示词过滤，
pending恢复/旧frame重验、跨轮权限及 Episode 历史正文交付尚未覆盖。
作者最终回归249P、禁止尝试0；三种撤线分别6F/27P、2F/31P、2F/31P。
相邻测试110P但100次禁止尝试、启动器exit3的失败保留；无审计复跑不能洗掉它。
**尚无独立 QC，不代表 P3/E2 完成**；[范围与完整作者证据](verification/e2-boundary-closeout/p3f1-source-binding-20260915/README.md)。
独立复核固定a819ecde的首次启动被服务并发限制中断，未运行测试/无报告，CLI exit0不算通过；
[中断原件](verification/e2-boundary-closeout/p3f1-a819ecde-independent-qc-blocked/README.md)保留，未自动重试。
用户授权后的第二次全新有界复核也被服务过载阻塞：工具调用0、测试未执行、无报告，
禁止IO次数未测而非0；自动重试关闭，未再次启动或换模型。
[第二次原件与终态](verification/e2-boundary-closeout/p3f1-a819ecde-independent-qc2-blocked/README.md)单独归档。
用户再授权的[第三次有界复核](verification/e2-boundary-closeout/p3f1-a819ecde-independent-qc3-blocked/README.md)
同样首响应过载、0工具/无测试/无报告，未自动重试；仍无独立裁定。
**用户随后纠正：独立审查可关闭，本轮关闭该可选步骤，不作为后续开发前置。**
撤销93ad74a8及历史中断归档中“先等服务恢复”的后续要求；归档原件不改写。
下一步直接冻结历史提示词/正文送达小片，保留作者验证要求；关闭不等于审查通过，
也不取消下述未完成项、合入测试门禁或用户合并/部署授权。

P3f2 接通已知缺失基底的前置澄清与续轮材料链保持：TaskFrame 已判「缺失且不可恢复」时，
运行时不再丢弃该状态让续轮落回普通解析器/模型路径，而是送达默认 controller，在
resolver/模型之前发起澄清；旧注入 controller 按签名探测兼容，不加必需参数。材料链只在
「带来新材料、或不指代材料的新问题」时重置，「这篇」式指代续问与 material_only 轮保留
既有链；material_only/待澄清轮同时跳过昵称解析与日历先验注入（D4 同源过滤补齐）。
这是把既有缺失状态送达 controller，不是 controller 历史提示词过滤/改写，也不新增
运行时澄清文案生成器。7 个真实入口反例（run_turn→真实 decide_turn→Episode 装配）
覆盖注入旧 frame、基底缺失五态与材料链续问，先红（7F/16P）后绿；作者回归：聚焦三文件
×10 连跑 50/50，e2+改动模块选集 683P/4S，审计启动器 50P/禁止尝试 0，Ruff 通过。
间歇性 `root budget already exists` 判为测试侧固定 task_id 撞 WeakValueDictionary
注册表（GC 时机依赖），修为每用例唯一 id，不改产品弱引用语义。独立审查按用户决定
保持关闭，本片为作者自验；提交 `e1fc53a7`，决策留痕
`docs/handoffs/2026-09-15-e2-p3f2-frame-delivery-and-material-chain.md`。
未覆盖：歧义（非缺失）的预取前澄清、D7 跨轮权限继承、最终答案质量（P4/P6）
与全仓合入门禁；pending 恢复重验由 P3g 接续收口（见下段）。

P3g 收口材料类澄清挂起的恢复重验——「用户回答了 P3f2 那句澄清之后」的四个真实入口
bug：material clarify 决策未挂 pending_task_frame（回答绕过恢复走普通路由，材料被丢、
权限声明被当主体名）；顶部材料分支抢在恢复前重建 frame（题组丢）；
`resolve_task_frame_clarification` 无材料合同分支（needs_clarification 合同残留仍放行
research）；装配层只按 data_scope==material_only 收窄（state_unavailable 轴 None 被当
full 执行 8 能力）。修复三层：clarify 挂 pending 快照；材料类澄清挂起时顶部分支让路
（结构化判定合同状态，不比文案）；恢复用同一 D1/D2 编译器重编译回答——显式声明成为
新合同（D7.2），裸材料并入且合同如实保留待澄清、由装配层 `_material_restricted`
（material_only 或 needs_clarification）按最严收窄执行与提示，不猜 full、不二次采访。
6 个真实入口反例先红后绿（含两轮 run_turn 全链）；文件×10=290/290，选集 689P/4S 零
破坏；变异验证三层各有独立承重针（6/6、3/6、3/6）。提交 `f05d0681`，决策留痕
`docs/handoffs/2026-09-15-e2-p3g-pending-clarification-recovery.md`。旧类型澄清
（entity tristate、主体归一）走原路径未动；歧义（非缺失）预取前澄清与 D7 继承仍未盖。

P3h 收口确定性旁路——约束轮禁入无材料合同意识的执行面。三个掉落口实测可达：
adapter 对五个确定性 owner 题型（external_market/dated_market_review/market_watch/
watchlist_digest/disclosure_scan）主动让路给引擎 B；`ASK_CONTINUOUS_RUNTIME` 缺省
off 时全部 research 轮掉入引擎 B；knowledge lane 的 fallback 检索直调 answer_query。
引擎 B（skill 路由+Ask 管线）对 material_contract 零引用，约束轮进入即整体失效
（实测「只用本地数据，美股隔夜表现如何」编出 local_only+external_market 被让路进
外盘 owner）。修复为两道正交防线共用一个谓词：adapter 对约束轮不让路（留在 Episode
收窄执行）；orchestrator 掉落总闸在 skill 路由/Ask 管线之前 fail-closed（诚实降级+
degrade+trace，零外呼）。分界：material_only/local_only 恒拦，boundary_uncertain
恒拦，state_unavailable 仅带材料语境（题组/材料/可信历史）时拦——「继续检索」类
日常追问声明的是基底未知而非受限边界，保持既有引擎 B 行为（全量回归实测过误伤后
收回）。20 个 adapter 反例（4 合同×5 题型）+3 个 run_turn 全链反例先红后绿；
813P/4S 零破坏；变异撤防线1→20红、撤防线2→2红，完全正交。提交 `50687c0b`，
决策留痕 `docs/handoffs/2026-09-15-e2-p3h-contract-blind-pipeline-gate.md`。
本片不给引擎 B 内部加合同意识（被挡在门外≠免疫），fictional×full 的前提标注
送达仍属 P4/P6 纯度范围。

P4（D5）在 `fix/e2-delivery-closeout` 补齐 `material_only` 逐题交付：原题号保持
`answer_qN` 唯一必需槽；已回答沿用 `fulfilled`，公开交代具体缺项才是 `legal_gap`，
遗漏/重复/空壳/超长仍是 `missing`。合法缺口只能 `partial`，全缺口加顶部说明；
它只证明结构已交代，不证明材料真缺失，仍实际送判。判官拒绝会重开原题，普通
元陈述豁免不能洗白；公开投影/脱敏后重验，题号不重新编号。当前答案保留候选不再
因普通质量疑点删句；判官不可用保持 `unavailable/pending_rejudge`，不伪造成功，
也不因复核故障再烧补写轮。
备忘录只由明确题意触发，与该题共用一个槽；T3 q8 上限200字（保守计入正文
所有非空白字符和标点/Markdown，不含题标题，引用不可藏超长）。真漏答可获有界
零工具补写，不靠降 optional 或假增证据数量；已交代缺口不触发空转修复。
前置同时修了题内案例弱分区吞题、验收采集 followup 错开会话/误收旧答。
公开稿的两处再出口（投影后复验、判官拒绝重开）只经 `session_projection.view()`
并已登记，不另开拼串路径。证据：离线反例与定向回归（`docs/handoffs/2026-09-16-e2-delivery-p4.md`）；
精确提交上的四叶等价 CI 与删保护变异（`docs/handoffs/2026-09-16-e2-delivery-p4-verification.md`）。

**本阶段不是材料题全链完成**：`local_only` 仅已审定 runner 的局部路径，未覆盖所有
本地工具。D4 四组九类注入路径已逐条对账收口（矩阵与定性判断见
[P3 注入面核查](handoffs/2026-09-15-e2-p3-injection-surface-audit.md)，payload 卫生
钉测试锁现状）；判读基线/题型规则等方法文案留在 material_only 输入里，定性为
「非事实、无 IO」不越 P3 红线，答案质量影响归 P4/P6 再议。引擎 B 内部仍无合同
意识，不得绕过 P3h 两道门直接调用；注入式 registry_factory 内部读取不可撤销
（P3c 声明）。local_only 原题号槽、材料题真实模型交付、可信跨轮继承五格全链、
纯度与材料锚点待后续阶段；普通上下文不是按来源过滤后的安全输入。
不得把局部短路当成真实入口已经零外呼，也不得运行正式 T2→T3/Knevo 对照。Grok CLI 已做过回顾性语义判卷试跑，但有效返回来自关闭系统沙箱的配置（不再沿用），且输入未含完整原题/材料，结果仅作试跑证据，不是隔离验收或正式评分；Knevo 有已登录浏览器的 CDP 回贴入口，但本轮未发新题、没有未揭盲成对答案，故没有正式 PK；详细状态见 [判官/Knevo 记录](verification/e2-boundary-closeout/llm-judge-knevo-status-20260915.md)。设计与阶段证据见
[设计 v10](learning/knevo-distill/recheck/2026-09-12-t23-nogrok/E2-DESIGN-material-contract-2026-09-13.md)
及 `docs/handoffs/inflight/fix-e2-boundary-closeout.md`；是否部署看实际服务 revision。

### 研究过程中的实际工具菜单

引擎 A 在开放工具的模型请求前记录 `tool_menu.visible`，与该步交给模型的工具定义同源，
已经过合同授权、动态装配、时间窗与去重筛选；不从更早的 `configure` 或静态注册表猜。
`episode_progress` 把名字映射成既有中文标签，经 RunStore 持久轨迹和 SSE（服务端事件流）
进入研究过程 / 运行详情；API 只放行固定句及封闭标签语法，不外露内部名、参数或提示词。
授权菜单、开始调用、取得资料是不同事件；**菜单不证明上游可用**，模型首轮失败仍可看到
请求前菜单，未装配的子研究不会被报成可调用。收口阶段不计算未交给模型的工具菜单。

这是过程投影，不是 `session_projection.view()` 的金融答案出口，也不是新的权限表。
无菜单记录的旧 run 不反推授权。覆盖两条 loop 与公开边界的测试在
`intelligence/tests/test_tool_menu_progress.py`、`test_harness_reference_loop.py`；
本段接线已合入 main `0758a423`（PR #760，2026-09-16）；线上是否已有仍看运行 revision，
切 8792 的记录在 `docs/handoffs/2026-09-16-8792-switch-0758a423.md`。

### 会话使用计时（分支候选，非试点效果）

研究检查器提供「同意并开始本次计时」，默认关闭。经既有 `research-evolution/events` 保存同意后，`ResearchActivityControl` / `startResearchActivity` 记录可见与隐藏区间；使用单调时钟量经过时间，前端不自报服务端时钟或任务完成。停止、切会话和 `pagehide` 结束采集并尽力保存末段与撤回；保存失败在当前页显示缺口，异常退出不能保证送达，也不自动恢复采集。

这里只产生 `workbench:<conversation_id>` 自用事件，`task_id=null`；优先队列候选不是冻结试点分配，不能拿它填身份。可见时间不等于键鼠操作时间；隐藏原因 `tab_hidden` 不代表获准扣减端到端时间，也不推断外部查阅。真正的配对效果仍需授权、冻结分配、任务终态和05测量收据，不由计时按钮创建。当前接线和隔离测试不等于生产部署。

### 历史发现研究

入口仍是 Workbench 对话，例如「这一波农业怎么走出来的，找出值得检验的特征」→「以前有没有类似，失败案例也看看」→「把观察窗口改成……」。`TaskFrame.history_intent` 区分事后发现与历史比较，随 `TurnIntent` 跨轮传递；普通概念解释与明确取消历史研究不会继承该权限。用户明确限定日期时，历史计算、普通结构化查询与原件读取共用范围门。

`historical_research` 是引擎 A 上的领域应用：有类型 `history_query` 负责精确代码的日轴、受支持的时间特征、类比及声明窗口全集比较；`read_history_result` 读取原件；`save_history_research` 保存候选、失败与修订。它们复用 `finance_query` capability，预算、工具循环与取消仍由 Episode 管理。完整分母与模型预览分离，原件只经 RunStore 写入；案例修订与普通取消/产物写入均有并发保护。

修订优先提交 `previous_result_ref + patch`：模型只传变更项，服务端保留未提及假设及旧来源、失败、反证、已暴露样本，并自动递增版本。案例摘要按假设分页，完整原件不因摘要预算被改写。重复保存幂等；未知引用、过期父版本和跨会话读取仍被拒绝。

`FinanceResearchHarness.assess_publication` 给出领域完成度上限和必须公开的缺口，通用 adapter 机械执行；语义润色不能把未完成的历史比较升级为完成。异常恢复仍走既有 EpisodeFinalizer，领域仅提供已有证据的优先序；恢复保持原引用编号与条数上限，并说明“投影省略不等于源数据缺失”。独立数值核对用 `scripts/audit_historical_research_artifacts.py` 读取研究原件，输出已核验、跳过和错误项；它不读取主库、不调用原计算引擎，也不颁发统计认证。

当前结果均是探索研究：相似案例不等于独立验证，重叠窗口不当作独立样本；不支持的组合定义明确返回缺口。L2、晚间卖方与晨汇未同步目标范围为 `pending_sync`，没有安排同步。严格时点认证、样本独立性与正式方法晋升继续消费基础评价器合同；本工具不颁发认证。

实现和分期验收见 [历史发现 spec](superpowers/specs/2026-09-09-historical-discovery-research-design.md) 与 [执行计划](superpowers/plans/2026-09-09-historical-discovery.md)。部署状态以运行服务 `/api/health` 的 revision 为准，仓内存在代码不等于线上已更新。

### 质量消融评测：结论只覆盖 legacy CLI ask

`scripts/run_quality_ablation.py` 与 `scripts/rejudge_quality_ablation.py` **不是产品门**，是评测工装。它们经 `run_ask` 调 `python3 -m intelligence.cli ask --compose`，走的是引擎 B 的 legacy CLI 问答路径；**跑出来的分差只覆盖该入口，不代表 Workbench Episode（引擎 A）**。拿消融读数论证「Agent 质量」之前先问这一句。

出实验结论的**唯一资格门**是 `intelligence/eval/judge_validity.py::validate_judging_batch`（纯函数、无 IO）。`aggregate_components` 每次调用都重新验证原始记录与 manifest，不采信传入的 `valid=True` 或旧 `decision`——补评、完整重评与主评共用这一扇门。资格不成立时保留描述性分差与覆盖率，但组件决定降为 `no_call`。

三条容易被读反的边界：

- `decision=callable` 只表示**越过当次判官的噪声门**，不是合并授权，也不证明跨任务或未来效果；`baseline_absolute` 只是该批次的描述性统计，配置同名不能证明跨批次可比。
- 分母以 `run_quality_ablation.batch_coverage` 为唯一来源（人读报告与 JSON 收据共用）：登记数取**事前冻结的题臂数**而非 `len(answers)`，产品未交付的样本留在分母里，不能靠身份门重归因成「实验条件失效」。
- 判官身份来自本次响应的结构化字段。CLI 没有该字段就记 unknown，**不从自然语言自述或当前环境配置补齐**；响应自报身份只支持「按对端声明相同/不同」的审计强度，不等于已认证真实模型。

方案与验收矩阵见 [判官身份与校准有效性 plan](superpowers/plans/2026-09-14-judge-calibration-validity.md)，取舍见 [handoff](handoffs/2026-09-14-judge-calibration-plan.md)。

## 两条引擎（调度器后面）

一个调度器（`conversation_orchestrator` / `TurnOrchestrator`）+ 两条引擎。两条都调 LLM，差别是**流程谁定**：

| 引擎 | 实现 | 何时用 |
|---|---|---|
| **A**（Workbench 生产默认） | `continuous_turn_adapter` → `ContinuousAgentEpisode` | 模型按契约自选只读工具 |
| **B** | `ask.answer_query` | CLI `ask`/`chat` 的固定管线；Workbench 里两种情形（见下） |

**B 在 Workbench 里接两种题，别只记住第一种**（2026-08-30 修正，此前本行写「仅三条确定性题型」，三处都已漂）：

1. **确定性题型 → D 块流水线**：`DETERMINISTIC_OWNER_TYPES` 实为**五条**——`external_market` / `dated_market_review` / `market_watch` / `watchlist_digest` / `disclosure_scan`（`continuous_turn_adapter.py:111`，个数以该常量为准，勿写死）。**`quick_fact` 已被明确移出**（`:108`，R-20260828-05：排名/过滤/区间取值必须进 episode 才碰得到 `finance_query`）。
2. **ownerless 长尾 → `generic_research_owner` 循环**：`research_task_contract` 非空时 `_answer_query_impl` **整条早退**、D 块一次不跑（`ask.py:3055-3059`）；契约只在 `conversation_orchestrator.py:2809` 设上，条件是「研究题 + 无专属椅子」（`:2245`）。这一条是 `run_agent_loop`，**不是写死流程**——把 B 整体说成「写死流程」会把它接长尾的能力漏掉。

A 与 B 的门禁不对等：语义判官（`episode_semantic_verifier`）、结构门、修复轮**只在 A**；B 有 `gate_receipt` / `CompletionReport` / `evidence_judge` / 输出质检。差的成因是分层——判官在 `runtime/`，B 在 `services/`，不得反向 import。现状与并轨计划见 `docs/superpowers/specs/2026-08-30-engine-b-into-a-strangler-design.md` §1.3。

### 判官模式：`ASK_SEMANTIC_JUDGE=llm|off`（工单 #55）

用户 2026-09-12 撤掉独立 Grok 判官（改 kimi-k3 自审）、2026-09-17 进一步决定**不用 LLM 判官**。一个共享开关（`intelligence/services/judge_mode.py::semantic_judge_mode`）同时管两条引擎：

- **`llm`（代码默认）**：A 的终稿判官 `_run_judge` 调第二模型（无 `LLM_JUDGE_*` 时落回写手自审，`correlated_judge=true`）；B 的合成判官走 `synthesize_messages`。当前候选在判官不可用时保留安全正文并说明未核验，不将故障改记通过。
- **`off`（生产启动器记录值，部署仍看 revision）**：A 的 `_run_judge` 返回合成的全过报告，**零模型调用**；机械检测（数值 / 材料缺口 / 元陈述 / 表外 E）仍运行，当前候选改为记疑点和批注而不是删句。V11 引导回检索记 `skip_reason=judge_off`；B 的判官段不发调用，`deterministic_only` 不冒充 LLM 独立审稿；检索侧证据判官另由 `ASK_EVIDENCE_JUDGE=off` 关。

读收据别读反：`judge_status` 闭集仍为 `passed / repaired / rejected / unavailable`；
历史 `repaired` 可能来自删句后复判，当前候选的原文保留使用独立 `delivery_mode`，不伪造 repaired。
**谁在判**看私有块 `semantic_verifier.judge_mode`（`llm` | `deterministic`，在 `continuous-episode.json`），
公开 `gate_receipt` 键集不变。句内日期与所引证据日期全不符仍由 `evidence_date_mismatch`
检出，记 `demoted_to_issue` 并追加批注；引用别槽的 E 仍记 census，不自动删除。
同句可有预检和判官两条记录，记录数不等于拒句数，更不等于删除数。
B 侧 `analysis_preserved/released_unverified` 与 `accepted` 分开。模式默认翻转和旧判官路径退役仍见工单 #56。

不要把 `ask.answer_query` 写成「金融 Agent 的唯一深模块」。它是引擎 B。也不要为「少学零件」再加 `answer_door` / `EpisodeBuilder`：组装已经在 `GLMAgentRuntime` 和 `episode_factory`。

### 生产里谁在拼 `AskOptions`（为什么不加 `answer_door`）

不含测试。再加一层 `resolve_answer_door(query)` 通不过删除测试：删掉它，调用方仍要自带策略字段。

| 调用方 | 怎么进 | 是不是「只传 query」 |
|---|---|---|
| `cli ask` | `AskWorkflowOptions` → `run_ask` → 再填 `AskOptions`（浅拷贝还在） | 否，经 CLI 默认填充 |
| `cli chat` / `cli agent` | 直接 `AskOptions` | 否 |
| 飞书 IM | `feishu-bot` **exit 2**；文件里还留着 `_run_ask_workflow`，`run()` 到不了 | 已退役，不是门 |
| `research_owner.py` | 直接 `AskOptions`，带 `compose` / `deadline` / `question_type_override` 等 | 否，策略调用方 |
| Workbench `app.py` `_run_ask` | 直接 `AskOptions` + `answer_query`，走 run/store | 否，UI 合同 |

问金融问题走上一节 CLI `ask`；问「仓库里有没有现成实现」走 `python3 scripts/code_map.py query`。仓库里没有第四套 Python `answer_door`。真浅的若还要收，是删掉 `AskWorkflowOptions` 那次字段拷贝，不是再加转发。

## 积木（常见误判）

这些可以很深，但**调用方不是人，是引擎**：

- `ResearchToolRegistry`：授权、参数规范化、同 key 只跑一次、截止日期过滤。不是 `{name: runner}` 字典。超时/重试在 Episode 批次循环，不要搬进注册表（`services/` 不得 import `runtime/`）。
- `llm_refine`：传输（重试/流式/预算）+ 任务提示词焊在一个文件。不要合成万能 `generate(task_type)`。
- `perspective_lab.active_runtime_prompt`：视角注入门。模块里还有路径 helper，不要把整文件当成四方法闭环。
- 数据块（D0/D6/D9…）：意图门控在块自己的 `applies()`。调用方若要关某一块，只传 `AskOptions.enabled_providers`（或 `evidence_registry.without_providers(...)`）。**不要**再给每个块一个 `include_*_block`。

`force_moneyflow_block` 是「日报强制取 L2」，不是允许开关，仍留在 `AskOptions`。
`include_scenario_guidance` / `include_track_guidance` / `include_ranking_guidance` 是表达契约，不是数据块（排序与情景契约见 `intelligence/services/ranking_contract.py`：多对象排序题的公司矩阵、改判条件表与机械再排序）。

## 失败形状（本页要挡住的）

对着积木的公开方法数打「浅」、建议再包一层工厂、建议把超时重试塞进注册表——都是把积木当成了门。先问：调用方是人、是调度器、还是引擎内部？

把 `feishu-bot` 当问答正门，或把「飞书 Bitable 写入已退役」写成连 IM 长连接也没了——两扇门不是同一件事。IM 入口现在 exit 2。
