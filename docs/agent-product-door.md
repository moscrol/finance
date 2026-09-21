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

夜跑收尾的运维入口仍是 `nightly_full_review.sh finalize`，不新增问答门或事实写入链。
生成段从 `FINANCE_GENERATION_CODE_ROOT` 的双根 launcher 调用原 `intelligence.cli daily --skip-sync`；
L2、外层质检与方法验证保留 `FINANCE_CODE_ROOT`，数据与外置用户态不迁移。
部署/回滚及验收边界见 [09-17 生成接线](handoffs/2026-09-17-nightly-generation-deployment.md)。

编码任务「仓库里有没有现成实现」走 `python3 scripts/code_map.py query "<问题>"`，不是本页，也不是问答门。空图不得写成架构结论。

### 夜跑日报生成（代码与数据分根）

收尾仍走 `nightly_full_review.sh finalize`，不是另一条数据写入链。其内部以绝对路径启动
`$FINANCE_GENERATION_CODE_ROOT/scripts/run_daily_generation.py`（未配置生成根时回退
`FINANCE_CODE_ROOT`），验证实际 import 位置后调用现有
`intelligence.cli daily`。子步骤继承同一解释器与固定代码搜索路径，脚本用代码根绝对路径；
工作目录、DuckDB、exports 和复盘 HTML 留在数据根。缺代码根/包、写入位置落进代码根时拒绝生成。
生成启动器失败后外层立即返回，KB 接收只在成功后运行；拒绝后的提示使用现有进程输出与桌面通知。
运维告警写入前会解析最终日志路径，拒绝写入配置的 L2 代码根和生成代码根（含文件、父目录软链接）。

已配置的 `FORESIGHT_USERS_DIR` / `FORESIGHT_EPISODE_STORE` / 数据库覆盖保持原位，不迁移存量；
相对覆盖统一按 `FINANCE_DATA_ROOT` 解析。生成启动器不改变独立 L2 分支的环境或同步守卫。
启动器在导入项目模块前核验代码面及嵌套脚本软链的真实归属；摘要等参数只由原 CLI 完整解析一次，
校验与执行共享同一解析结果。运行前检查已启用告警的真实日志目标、用户实例、日期目录、质量状态、增量归档及具体输出文件，
已有子目录/文件软链指入代码根也拒绝；合法外置用户态软链不迁移。目录检查只读元数据，不读文件正文。

这层是启动前的静态路径校验，不是 OS 沙箱：不防运行期间恶意换链、不认证未枚举的新增写入或外部 KB
接收器代码。它不保证当天数据齐全、模型网关可用或生产已经部署；不改变其他直接 daily 调用的合同。

### Workbench 终态与交付

`Run.status` 是终态仲裁结果，不保证随后写入的报告已齐。单进程执行器在
`GET /api/runs` / `GET /api/runs/{id}` 投影 `delivery_pending`：已 completed
但执行器仍在收尾时为 true；UI 继续轮询/接收 SSE（服务器推送事件），恢复会话亦然。
执行器退出后再取 run 快照，SSE 排空尾部事件才发最终 `run`。取消/失败不等待
不合作的 worker。它不修改持久化状态机，不是跨进程交付协议；多 worker 前须替换。
同会话新消息也使旧加载代际失效，迟到的上一轮快照不得抹掉新追问。

直答车道的生成器返回 `fallback_reason` 时，即使一般知识检索兜底拿到了引用，
本轮消息、Run 与报告仍保留生成降级记录；检索失败与生成失败分别记账。
`completed` 只表示回合已结束，不能据此把资料摘要当作正常生成的综述。
正常生成和确定性回复不因此增加降级标记；本规则不增加重试、调用或检索权限。

### 计算表格的两参形式

`fincalc.table(name, rows)` 在一次迭代中逐行保存当时的键和值，包括嵌套 JSON 值。
生成器复用同一个行对象时，后续赋值不会覆盖早先行；字典列仍按首次出现顺序取并集，
序列按最大宽度补 `None`，不补零。显式列名的三参形式保持原行为。
沙箱内置辅助代码版本 `PRELUDE_VERSION = "5"` 进入 `calc_id`，不复用初版 v4 的计算身份。
这只保证本地计算及产物一致性，不证明输入行情或公司财务事实真实。

### 专项研究纪律（Knevo 增量，2026-09-17 已合 main）

`research_workflow_guidance.workflow_guidance` 给财报、事件推演、观点审查、事实核对、历史类比
五类既有题型补分析纪律；连续 Episode 的动态规则与 ask 合成共用，不增加产品门、工具或权限。
旧 ask 保留信封已识别的专项意图，显式 override 优先；不代表所有自然语言路由已经准确。
默认开，`FINANCE_RESEARCH_WORKFLOW_GUIDANCE=0` 可关。它是生成指令，不是新增语义审稿器；
权限、材料范围、证据绑定与写侧门保持原合同。代码/对账与效果状态见
[逐项吸收记录](learning/knevo-distill/workflow-absorption-2026-09-16.md)，未据此宣称部署或质量增益。PR #774 已于 2026-09-17 合入 main（`c67413c7`），部署状态仍以运行服务 `/api/health` 的 revision 为准。

### 用户题设计算与行情口径

Workbench 对明确的虚构算例 / 情景计算，在受保护的顶层指令编译中记录
`MaterialContract.premise_calculation`，与真实性及读取范围两轴分开。
这个布尔值只表示输入来源和计算授权，不表示已获得程序化数学证明；只有能生成本项目
有限静态市盈率程序表的题型，才打开题设计算的无外部证据出口。其它题设计算不借这个
标记绕过事实证据，也不把模型心算当程序证明。
计算按 `user_premise` 绑定，不再强加当前主线检索；真实行情请求仍要求外部证据。
“沿用上一轮”只能继承已保存的完整用户消息合同，助手原答不能恢复题设权限。
旧确定性管线不能接管这种合同；未声明计算模式的普通金融题保持原证据要求。

`finance_query.market_breadth_daily` 只读聚合同日 canonical 个股截面，返回涨跌平盘
及覆盖信息，不以返回行数上限截断统计，空涨幅或重复代码不能伪装完整计数。
板块证据自动携带 `.FP` 复盘会 / `.TI` 同花顺清单口径；数值加工来源另列 `source`。
格式错误触发终局恢复时，`FinanceResearchHarness.recovery_evidence_priority` 会保留
未通过草稿引用的真实证据，避免工具均分截断丢掉后续查得的关键行；草稿本身不直接
交付，伪造编号不进恢复视图，恢复结果仍走原校验。题设数字与文字解释的一致性另在
语义审核中明确要求；这不是程序化财务正确率保证。

明确的单公司财务算例且请求静态市盈率时，`premise_financial_calculation` 从完整用户
原文编译年度、实际/预测/假设性质、单位及来源坐标，复用 `sandbox_fincalc` 的换算和
除法函数。历史用户输入单独持久化，助手旧答不进入计算；只有明确更正才替换旧值。
计算快照随 `ResearchTaskContract` 保存，恢复时从原文重算并核对，不接受篡改结果。
当前消息用 `current` 加原文哈希/TaskFrame 定位，历史消息保留实际 message_id。
继续追问同时继承仍有效的计算要求和最近明确的利润变化情景，不只继承金额；
新的完整情景定义替换旧情景，明确取消情景或仅算静态市盈率可收窄范围。
范围指令只识别有限的肯定子句，“不要只算”不能触发收窄；同轮混合退出与新情景
留待澄清，后续完整重述可解除这类范围冲突。“再加”保留多情景缺口，不暗中覆盖。
继承的情景比例仍绑定最初提供它的用户消息，旧缺口不能因一句“继续”消失。
主体只剥离有限的指令前缀后精确比较，禁止因一个公司名包含另一个而合并输入。

模型在 draft 放置 `[[PREMISE_CALCULATION]]`，公式表由程序插入并硬校验；已识别的数字
复述按指标、年度、方向、单位及精度核对，确定矛盾拒绝。未解析的自由表述交原有语义审核，
不因“暂时无法解析”直接拒绝，也不冒充程序证明；最终工件 `premise_calculation_review`
分别记录表格一致性、矛盾与未程序校验的数字片段。它不是整份答案的财务正确性证书。
输入齐全的纯算例即使没有外部证据，也可经 harness 的 `finalization_materials` 进入既有的
单次、无工具终局恢复；恢复与主轮共用同一份计算表输出合同，仍过计算与证据准入，
不放宽 deadline、不为缺输入或事实证据不足的任务补造材料。表格校验仅容忍空行折叠，
不容忍非空行、公式或数值变化；公开出口及适配器脱敏保留 Markdown 表格边界，避免解释被吞成表格行。
完整题设的程序表明确标注输入未作外部事实核验；该来源声明上的限制条件按既有 caveat 规则
移至顶层 gaps 保留，不冒充未完成输出。只有此声明由程序拥有，其他无哈希输出和缺输入任务不借道。
公开脱敏复用已知工具的公共名称，将行内来源代码译成中文；不因 `finance_query` 同句出现而
丢掉日期或涨跌家数。控制字段、未知标识和不透明哈希仍隐藏，单独的工具名也不当正文发布。
计算降级与正常交付都走统一
`session_projection.view`；`prime_quote` 接受 `market_data/finance_query`，但不能由此被历史
合约增强器扩成 `history_query/read_history_result`。
终局准入和语义审核最终出口都核对表格；后者发现改写时保留失败草稿、公开计算表并
降为 partial，不让判官 passed 覆盖程序错误。数字不是外部事实，不进入事实证据账本。
解析边界为显式年度、带单位行内数值、单公司、明确替换及单个次年利润变化情景；
多主体、缺基数、非完整年度、未知单位/表达、缺少百分号、缺少改值单位、未消费金额和冲突均留缺口，不猜补。
历史有效输入不会替代缺单位的改值；补充带单位的明确更正后才恢复该字段。
这不是通用自然语言财务解析器，也不保证所有定性解释的正确性。
这是代码能力说明，不代表 8792 已部署或已完成独立验收。

### 研究求证意识（候选，默认关闭）

`research_reasoning.guidance` 提醒研究型问题从现象追问机制、寻找区分性证据，接受反证并可放弃解释；
视角不是封闭菜单，不指定宏观/流动性优先，不新增步骤、回答栏目或完成门。
`FINANCE_RESEARCH_REASONING=on` 显式启用，未设、off 或未知值均不注入；查数、定义等题型保持原状。
连续 Episode 先走动态题型规则，再通过已有 `tool_budget_state.runtime_budget.research_reasoning`
在工具返回后送达短提醒，随原事件保存，不额外发起模型/工具调用，不依赖进展账开关。
ask 的 AnswerSpec 合成、旧复盘合成及 `prepare_existing_answer` 回退共用初始规则，但不能改变已完成的检索。
v2 补统计对象/分母/时间窗/变化量对齐，以及“相同观察能否容许另一机制”的反例检查；
区分成交与净入金、行业与市值、订单与交付、毛利率与利润总额，不把不确定扩大为全盘拒答。
仍只增加生成指导，不证明模型执行了求证，不授予权限、证据资格或完成状态；原知识门控保持不变。
未接入日报离线生成、未合 main/部署 8792，也不依赖未合入的 `feat/adaptive-research-loop`。
测试场景和效果边界见 [研究求证意识验收](verification/2026-09-20-research-reasoning-awareness.md)。

本分支 09-21 的配套修复独立于上述开关：共享判读基线改成按待证主张选用，
不再要求所有问题先判市场阶段，也不把盘面证据全局排在产业事实之前。
`只分析以下材料` 冻结材料读取上限；顶层 `复核刚才的解释` 可延续可信用户条件，
明确允许重查的普通续问保留日期锚点。`只用已取得的数据` 比 local_only 更窄，
编为 material_only，不能再查本地库；引用行不能声明权限。旧 E 编号仍仅限原轮，
新提示不授予旧回答事实资格。这些修复不是开关 off 时的字节级回滚范围。
零检索与研究交付已拆开：明确材料任务走 research、needs_retrieval=false，读取能力仍为空。
同会话明确要求“复核刚才解释、仍只用已取得数据”时，`prior_evidence` 可从上一轮已完成的
local_only 原始 Episode 恢复输入。RunStore 校验用户、会话、登记工件路径/大小/SHA256；
恢复器核对原问、消息、TaskFrame/contract/outcome 身份及日期，拒绝未知 schema、重复身份，
排除非白名单本地工具、缺日期、越截止日及派生计算证据。本轮重新编 E 号，保留原 run/hash 映射；
旧答案、覆盖/完成状态及权限不继承。仅复用已登记私有原件，不查 DuckDB 或外部资料。
当前只支持有完整可信历史、无新显式日期/转题的单跳复核；不做跨会话、多层复核链或任意窗口重筛。
数值预检对句首短日期另核已绑定证据的 source_date，避免把 `9-11` 的撤回句当新阈值删掉；
仅日期句首形状适用，带单位的区间、未绑定/未知日期不获此资格，句中其他数值仍检查。
这只保证句子能送交语义审核，不证明日期使用、归因或撤回成立；独立于求证提示开关。
虚构材料的前提绑定仍未解决。V3 真实复核恢复14条、零新工具且能撤回部分断言，
但原答仍过强归因、复核仍把成交占比写成增量集中，不能宣称求证质量已验收。
历次原件见 [输入边界复验](verification/2026-09-21-reasoning-input-boundaries.md) 和
[旧证据复核 V3](verification/2026-09-21-prior-evidence-review.md)。未合、未部署。

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
元陈述豁免不能洗白；公开稿删句/脱敏后重验，题号不重新编号。判官不可用保持
`unavailable/pending_rejudge`，不伪造成功，也不为暂扣稿再烧补写轮。
备忘录只由明确题意触发，与该题共用一个槽；T3 q8 上限200字（保守计入正文
所有非空白字符和标点/Markdown，不含题标题，引用不可藏超长）。真漏答可获有界
零工具补写，不靠降 optional 或假增证据数量；已交代缺口不触发空转修复。
前置同时修了题内案例弱分区吞题、验收采集 followup 错开会话/误收旧答。
公开稿的两处再出口（投影后复验、判官拒绝重开）只经 `session_projection.view()`
并已登记，不另开拼串路径。证据：离线反例与定向回归（`docs/handoffs/2026-09-16-e2-delivery-p4.md`）；
精确提交上的四叶等价 CI 与删保护变异（`docs/handoffs/2026-09-16-e2-delivery-p4-verification.md`）。

P5/P6 候选在 `fix/e2-material-closeout` 集成：跨轮前提按内容与作用范围去重，
保留最早轮次；材料原文与历史助手陈述分目录冻结，事实句绑定材料身份与逐字引用。
引用只证明来源身份，支持关系和计算仍交语义判官；判官删句同时撤去该句的绑定，
不撤销其余来源检查。无编号材料题及范围声明槽也按冻结的 `material_only` 合同获得
有界零工具补写，不以有无 `qN` 判断资格；来源违规、未知输出、待澄清合同不获许可。
最终公开稿在最后一次投影后按同一范围复核，无编号题删掉答案不能仍标完成。
修复可满足性层也使用同一输入交付集合，不能因零工具把无编号必答项降为 optional；
终止协议已拒绝的来源/哈希完整性错误必须保留，不能在正文清空后被外层当作普通漏答重写。
作者测试覆盖真实 GLM runtime 的续轮与上述拒绝路径；模型与判官在这些测试中仍是替身。
候选另支持已确认 `material_only` 的显式 `render_from_claims=true` 终局：`draft` 留空，
正文仅由逐句绑定与公开缺口生成，避免双写漂移；旧格式仍严格核对原句与原始引用，不自动改绑。
材料判官对每条绑定须回传 `material_claim_checks`，遗漏、重复、类型错误均不算核验完成；
逐条拒绝只能收窄全局结论。计算句只能用自身引用的全部输入，不能借邻句或目录中未绑定的材料。
支持理由、原句与引用在私有工件留存；有记录不等于语义一定正确，同源判官也不等于独立验收。
材料轮的终局字段骨架由冻结合同提供；分句保留句末 Markdown 收尾符号，不改正文和引用。
已知材料 ID/消息坐标只留私有绑定：终局误写按格式错误回灌，最后公开投影过滤后重验交付；
声明重复事实数字仍须本句锚点，不能因 `premise_declaration` 标签豁免。判官必须返回支持类型
与本句锚点序号；不存在的锚点不能形成有效核验。候选对 `nonfactual` 通过项做一次无邻句、
无材料目录、但保留本句原锚点的隔离复核，共用原判官绝对时间窗，不可用时不沿用首判通过；这不是独立审查，
仍有模型误分类风险，不以数字正则代替语义。材料必答输出另需 `material_output_checks`：
区分事实支持与回答完整性，逐题列实际回答句；漏答只撤完成状态、不删正确输入事实。
最终公开投影删除回答句时重新打开对应槽。材料判决以结构化回执及显式拒句索引执行，
不再从 issues 理由文字提取句号当拒绝，避免把正面说明误删。原句、两次判决与调用状态留私有工件，普通问答协议不变。
material_only 使用材料专用判词，保留冻结来源但不向判官发送作者终局模板；完成回执只认
material_outputs 清单，工具定义同步限制 ID 与数量，解析仍严格拒收额外项。纯范围声明
不因附带锚点而被拒绝；“材料未给日期/口径”属于可证伪缺项陈述，须本句引用核验，
不能以 nonfactual 豁免，也不能从局部片段推断全部材料缺失。
`python -m scripts.material_claim_support_probe --live` 是限次判官对照，不是 Workbench/P7 验收。
这些规则有作者回归，语义蕴含仍需真实判官复验，不代表 P7 验收、合入或部署。

**本阶段不是材料题全链完成**：`local_only` 仅已审定 runner 的局部路径，未覆盖所有
本地工具。D4 四组九类注入路径已逐条对账收口（矩阵与定性判断见
[P3 注入面核查](handoffs/2026-09-15-e2-p3-injection-surface-audit.md)，payload 卫生
钉测试锁现状）；判读基线/题型规则等方法文案留在 material_only 输入里，定性为
「非事实、无 IO」不越 P3 红线，答案质量影响归 P4/P6 再议。引擎 B 内部仍无合同
意识，不得绕过 P3h 两道门直接调用；注入式 registry_factory 内部读取不可撤销
（P3c 声明）。local_only 原题号槽、材料题真实模型交付及可信跨轮继承五格全链
仍待验收；纯度与材料锚点已有上述候选实现，普通上下文不是按来源过滤后的安全输入。
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

- **`llm`（代码默认，行为与此前一致）**：A 的终稿判官 `_run_judge` 调第二模型（无 `LLM_JUDGE_*` 时落回写手自审，`correlated_judge=true`）；B 的合成判官走 `synthesize_messages`；判官不可用时 A 扣稿（`judge_status=unavailable`）、B 走带告示的瞬时放行。
- **`off`（须在服务启动环境显式设置，不能从代码默认推断生产状态）**：A 的 `_run_judge` 返回合成的全过报告，**零模型调用**，判后机械门（数值 / 材料缺口 / 元陈述 / 表外 E）与删句修复照常跑，V11 引导回检索记 `skip_reason=judge_off`；B 的判官段不发调用、`GroundedComposerShadow.status=deterministic_only`、不带掉线告示；检索侧证据判官另由既有 `ASK_EVIDENCE_JUDGE=off` 关。

读收据别读反：`judge_status` 闭集不变（`passed / repaired / rejected / unavailable`），两种模式下都表示「过了门 / 门删了句并修好 / 修不好 / 结构守卫未放行」；**谁在判**看私有块 `semantic_verifier.judge_mode`（`llm` | `deterministic`，落在 `continuous-episode.json`），公开 `gate_receipt` 键集未动（`RECEIPT_KEYS` 是被钉死的 schema v1 合同）。判官此前抓到的两类绑定错误的去向：句内日期与所引证据日期全不符 → 机械探测器 `evidence_date_mismatch` 删句（两种模式都生效）；引用了别的槽绑定的 E → 只记 `sentence_verdicts[stage=census]` 与 `cited_outside_slot_count`，不删（R-20260821-06）。B 侧健康度多一桶 `deterministic_only`，不冒充 `full_pass`。默认翻转与判官专属路径退役见工单 #56。

判官独立性另计：`deterministic` 不曾调用模型判官，公开 `correlated_judge=null`，不能把机械门的 `passed` 当成独立审核。方差评测优先读取私有 `judge_mode`，将其计入 `no_judge`（包括修复前公开误写 `false` 的样本），不进入 `independent_n`；只有新公开收据而无私有块时记 unknown。旧收据若既无模式又无私有原件，无法追溯是否关闭，不能据此给关闭实验背书。

写手连接由 Workbench「模型连接」或内置 provider 链选择，不受 `continuous_glm` 历史引擎名限制。K3（精确模型名 `kimi-k3`）的 Chat Completions 请求统一不传 `temperature`，因为现有网关会拒绝该参数；其余模型保持原采样参数，工具、流式与 token 上限不变。部署中的首选/兜底、判官模式以启动环境及实际 run 自报模型为准，不在本页写死。

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

### 知识库证据过滤（2026-09-18 已合 main，未部署）

`kb_rag.retrieve` 消费知识库 query 的 `--receipt`（实际执行条件回执）。请求了等级、
硬度、来源或 `as_of` 时，必须核对封套、逐条元数据与可得日；缺回执/旧 CLI 不支持即
不交付该次 W 证据，不删除约束后冒充成功。`filters` 保留请求值，`applied_filters` 与
`filter_verification` 才表示已核验执行；旧索引元数据待迁移的空命中不等于没有事实。
有过滤的块不再被金融端原页重摘录、整节深读或 stale 恢复替换，避免新正文继承旧等级。
无过滤查询保留旧列表兼容与现有深读；本次不宣称该路径的等级/时点已核验。
回执结果不复用未绑定源文件状态的结果缓存（模型/索引常驻缓存仍保留）。
负能力缓存与 worker 都绑定 CLI/RAG 包的内容指纹；代码变更先结束旧进程，响应再核对
加载身份，查询中途变化则丢弃结果。发布仍需不可变检出与服务重启，不支持逐文件热部署。
部署可用 `KB_RAG_CODE_ROOT` 将预热、能力探测、CLI 与常驻 worker 统一绑定到冻结的 KB
代码检出；资料仍由 `kb_wiki` / `KNOWLEDGE_WIKI` 决定。普通索引走原 `RAG_INDEX_DIR` /
`VECTOR_INDEX_DIR`，全文模式的 `.rag_index_full` 可由 `KB_RAG_FULL_INDEX_DIR` 绑定到同代
全文索引；配置目录不存在就拒绝，不回退资料树中的旧全文索引。其他显式索引路径保持原意。
显式 `retrieve(code_root=...)` 优先于环境配置；指定代码根失效就拒绝，不回退旧资料树代码。
worker 的资料根按调用参数传递且纳入进程复用键，不继承无关的 `KB_VAULT`；未配置代码根
保持原目录约定。这是候选部署接线，不代表生产已经切换。
受管代际由 `KB_RAG_GENERATION`（manifest SHA）、`RAG_GENERATION_MANIFEST` 与
`RAG_GENERATIONS_ROOT` 三个核心键识别；worker 创建时固定代码、资料、普通/全文索引和
解释器身份，进程池键也包含这份固定绑定。readiness 的 `status` 只读固定 manifest、
`current.json`、marker 与目录身份：同一 root 切代、路径缺失/损坏/替换时立即非 ready，
不启动/终止进程或安排恢复；另一独立 root 的合法环境不会给旧实例改名。退役身份使用专用
错误停在消费者边界，不回退旧 CLI；普通进程/协议故障仍保留原 CLI 回退。
这只是检索积木的协议：未给所有产品问句自动加截至日期，也不代表生产索引已迁移。
跨仓合同见 `docs/handoffs/2026-09-18-kb-filter-receipt.md`；金融 #784 / KB #151 已合入，
合并验收与生产边界见 `docs/handoffs/2026-09-18-kb-retrieval-merge-acceptance.md`。部署与索引迁移另行。

### RAG 能力探针诊断

`/api/readiness` 与 `/api/health/ready` 的 `rag` 对象增加 `elapsed_ms`、
`timeout_seconds`、`failure_kind`：记录整次探针单调时钟耗时、传给 subprocess 的超时预算、
固定失败分类。耗时含路径检查和子进程回收，不是 CPU/导入耗时，也不是严格的端到端截止时间；
未测量的手工构造收据保留 null。`os_error` 不进一步断言是启动还是通信失败。
默认仍执行一次 `query --help`、预算 5 秒，无重试或成功缓存；失败仍非 ready，
不公开 stderr、命令路径或异常原文。legacy 缺可选参数不作为失败。
这些字段不能证明真实检索成功，也不能倒推出历史间歇超时根因；候选代码尚未部署。

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
