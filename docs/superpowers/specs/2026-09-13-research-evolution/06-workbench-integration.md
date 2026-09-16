# 06｜Workbench 集成：让六份优化进入真实用户路径

日期：2026-09-13。类型：执行型集成 spec。先读 [总合同](README.md) 与 01–05 各自的交换 schema。本轨承担最终产品验收，不能用模块测试或静态截图代替。

用户应能在现有研究会话里看到需要复核的旧判断、选择下一项研究、留下处理结果，并在之后查看带依据的个人诊断；研究实验与使用测量保持独立状态。

## 1. 默认选择与首版边界

保持现有 Workbench 对话、研究项目面板和产物查看器。新增“待复核”“下一步研究”“我的复盘”三个内容区；03 实验收据和 05 测量收据由原件查看器进入，不占普通用户的默认主屏。

本批默认受信本机单用户使用。现有 API 的 user 查询参数与目录隔离不等于互联网用户认证：新增接口的有效 owner 必须来自部署允许的用户上下文；没有认证层时固定为服务配置的用户，拒绝客户端任意换 user。01–05 的库函数继续支持显式 owner 以便隔离测试，但本批不宣布可开放匿名多用户 SaaS。

不新增自动外发提醒或定时服务。用户打开面板或点击“检查变化”时计算报告；刷新读取不自动改原判断、不登记完成，不触发模型调用。用户点“继续核查”才启动既有研究对话。已注册的确定性回检可按原写入者执行，本批不接管原夜跑和数据同步。

## 2. 真实现状与复用入口

在 5fb13a8c 已读取：

- intelligence/api/app.py::create_app 内 GET /api/conversations/{conversation_id}/research-project，先调用 conversation_or_404，再由 research_project.load_project 投影。
- intelligence/services/research_project.py 有 load_project、prior_for_turn、find_related_conversation、continuation_for_run；已提供轮次、当前判断、触发点、下一问。不可新造第二套“研究会话”。
- intelligence/webapp/src/components/ResearchProjectPanel.tsx 已展示研究轮次/触发点/下一问；App.tsx 加载其投影，api.ts 提供现有请求封装。
- intelligence/services/run_store.py::RunStore 提供原件与 run；conversation_store.py::ConversationStore 提供会话范围。用户路径由 userspace.user_space 解析。
- intelligence/webapp/playwright.config.ts 已有隔离用户目录与本地服务器 E2E 配置，test:e2e 已存在。测试根清理只限配置明确的 test-results 目录，不能将真实用户根塞入它。

这是源码定位，不代表 8792 已完成这些规格；线上状态只认部署收据和健康接口的 revision。

## 3. 所有权与实现单元

本轨独占新增 intelligence/api/research_evolution.py 和 intelligence/services/research_evolution/，建议内部拆 adapters.py（原件读取/边界适配）、store.py（管理动作与测量单 writer）、facade.py（调用 01–05）、access.py（范围与归属）。facade 只组装，不重写领域算法，也不成为第三条问答引擎。

本轨可薄改 intelligence/api/app.py、intelligence/services/research_project.py、intelligence/userspace.py；前端写本功能组件与其测试，薄改 App.tsx、api.ts、types.ts、ResearchProjectPanel.tsx、相关样式。新 API 合同测试独占 intelligence/tests/test_research_evolution_*.py 与 intelligence/tests/fixtures/research_evolution/06/；前端独占本功能组件测试及 intelligence/webapp/e2e/research-evolution.spec.ts。

公共文档仅本轨写 docs/learning/ledger-map.md、docs/agent-product-door.md、UBIQUITOUS_LANGUAGE.md，并按能力图谱规则回写实际新增能力。API app 的改动若与原部署修复分支冲突，按真实最终代码重新适配，不覆盖对方修复。

不修改 01–05 目录内实现；错误或字段冲突交对应 owner 修补。公共数据表、market_feature_store/schema.sql、交易日历、LLM 模型/预算、全局路由/注册表不在本批白名单。若新需求无法由现有入口实现，登记最小依赖并先完成不受影响部分，不绕过统一问答正门。

## 4. 用户流程与最小 API

### 4.1 建立可维护对象

旧 judgment/checkpoint 可能没有证据 hash。面板显示“原记录没有完整依据，尚不能比较变化”，并提供“从现在开始跟踪”。用户选择自己有权读取的证据引用后，服务端解析真实 hash/版本，创建 01 定义的 DependencyBinding；保存真实 created_at 与 baseline_cutoff，保留原判断日期，不追溯补成当时已知。

新研究输出若有完整的结构化对象、引用、版本与用户确认，可使用 verified_structured_output 绑定；只剩 Markdown 文字或无权访问引用时不自动绑定。引用只能通过受控 id 解析，不能收任意绝对路径/URL 后直接读取。

### 4.2 检查变化与复核

同一会话的“待复核”卡显示：原判断、原依据、当前依据、变化类型、触发条件或待审原因、数据截止与必要缺口。语义 hash 变化仅提示复核，不写“已证伪”。普通用户看中文业务标签，调试 hash/内部版本通过详情页查看。

允许操作：开始复核、稍后处理、继续核查、核对后判断未变。继续核查生成携带原对象/维护项/来源版本的 continuation，经现有 POST 消息入口进入 TurnOrchestrator.run_turn；记录新 run_id。请求被接受不等于研究完成，后台失败、取消、降级保持真实状态。

已有判断变更需要新判断或原写入者的新版本，管理动作不能冒充它。用户选择“核对后判断未变”必须针对当前 before/current 版本并保留复核收据；过期页面提交返回 conflict，重新展示变化。重复提交用同一 idempotency_key 返回同一动作；该键绑定 owner、对象、动作和 payload hash，载荷不同不得复用。

### 4.3 下一步研究与诊断

02 返回 selected/deferred/blocked，三者都能展开；默认展示三项，并提示未入选的关键项与未知耗时。用户点击候选时精确携带 task_id 与范围，不用自然语言标题猜目标。

04 报告只展示带证据的流程问题和可读原因；缺少证据显示“暂无法诊断”。用户判断、Agent 判断、辅助后修改分列。练习标明历史数据、模型和用户已见程度；练习完成后才揭示后续事实，不能进入个人投资方法有效性统计。

揭示练习答案/后续事实或读取本批实验结果前，先经03的record_exposure按底层结果身份/区间原子登记曝光，再返回可读内容。更名题包、换study不能绕过同owner记录。旧入口或外部渠道的历史访问无法证明完整时，相关实验保留unknown/exploratory；不能因本批有访问日志就宣称用户从未看过这些结果。

### 4.4 API 合同

新增端点放独立 router，由 app.py 注入既有 store 与资源：

| 方法与路径 | 行为 |
|---|---|
| GET /api/conversations/{id}/research-evolution | 返回 01/02/04 当前投影与可访问的03/05收据引用；读取无业务写副作用 |
| POST /api/conversations/{id}/research-evolution/bindings | 用户明确建立从现在开始的证据依赖；校验原对象和证据的同用户访问 |
| POST /api/conversations/{id}/research-evolution/actions | 处理 01 管理动作、02 任务选择，校验版本和幂等；原判断事实仍走既有写入者 |
| POST /api/conversations/{id}/research-evolution/events | 接收已同意记录的05前端测量事件，只允许列出的事件/字段，服务端补可信时间与owner |

响应封套：schema_version=research-evolution-view/v1，owner_user_id、conversation_id、generated_at、maintenance、priority、diagnostics、receipt_refs、module_status、gaps。各模块内容保持自己的 schema，不压成一个含糊总分。缺模块为 unavailable，缺输入为 unknown/pending，服务错误为 error；无关模块能显示其有效结果，但错误不能被空数组掩盖。

新请求的校验错误给稳定业务码；未授权/不存在返回不泄漏他人对象存在性的错误；版本冲突为 409，重复同载荷操作返回原结果。GET 的报告摘要稳定，generated_at 可更新。

## 5. 存储与测量接缝

所有新增用户态落在已解析的 UserSpace.root/research_evolution/。06 先在 ledger-map 登记：

| 数据 | 责任 |
|---|---|
| dependency_bindings 与 maintenance_actions | 新增管理元数据；06 单 writer，原 judgment/checkpoint/verdict 只保存引用 |
| product_value_events | 05 合同的原始产品测量，06 单 writer；用户操作、客户端时间与服务观察时间分开 |
| 01/02/04 报告 | 可重建投影；如缓存，绑定输入摘要与版本，过期不冒充当前 |
| 03 实验收据与引用 | 03 实验模块拥有唯一 writer；06 传入已解析的私有存储端口并登记受控引用，不复制第二份可编辑实验事实 |
| 05 协议、任务分配、测量收据与总结 | 06 单 writer 保存冻结协议/输入摘要、原事件及不可变 MeasurementReceipt/PilotSummary；计算调用05纯函数 |

单 writer 仍需跨进程幂等与并发保护：复用现有事务/锁工具，写入采用原子方式，重试不重复追加。两个动作基于同一 expected_version 竞争时至多一个成功；文件损坏拒绝继续业务写入并返回可见错误。任何动作失败都不应留下“已关闭”却缺新判断/核查原件的半状态；通过中间 pending 动作和可恢复引用提交保持可恢复性。

测量事件按照 05 的英文 event_type 与 F/S/M 来源白名单产生，provenance 区分 observed/imported/synthetic。前端发送允许的动作，服务端观察 run 生命周期，不依赖前端自报成功。隐藏标签页只暂停“应用内活跃时间”，端到端任务时钟和模型等待仍继续；切到原资料查阅的主动时间由受控补录记录。端到端耗时只扣冻结协议允许的暂停，不能因离开页面变短。用户主动、模型等待与人工帮助分列，重叠时间按05合同处理。关闭测量不影响核心研究；关闭前后的分母与缺口都可解释。

未经用户真实参与，不生成 observed 试点成功或付款事件。无收费服务接入，付费事实只能按05协议导入可核验记录，仍需权限与原始凭据；本批不处理支付。

### 5.1 原流程与配对试点的登记入口

单靠研究会话点击无法测量原流程。06 在独占目录提供受控本地入口 `python -m intelligence.services.research_evolution.pilot_io`，通过同一 writer 支持 `register`、`import-events`、`rebuild`、`show`。参数显式给 owner、输入文件及已解析用户根；默认 dry-run，`--apply` 才保存。它不发送邀请、不联系参与者、不创建付款。05 离线 CLI 仍只处理显式文件，不能成为生产第二个 writer。

| 输入 | 来源与约束 |
|---|---|
| protocol、case/version、case_pair、assignment | 用户认可的冻结本地协议；注册真实时间，开始前绑定 task_id、条件、参与者和完成判据。迟登照实标记，不能纳入事前配对 |
| 原流程计时、产物、外部查阅、人工帮助 | 按05的M来源导入，带导入者、原证据hash及时间；允许没有run，不伪造模型执行 |
| assisted执行与费用 | 服务端核对同owner真实run、所有attempt与可用费用事实；缺费用留unknown。任务终态与run终态分开，重试不新造分配任务 |
| 独立盲审、人工费用、同意及撤回、已发生付款 | 受控M导入及证据校验；没有相应授权/凭据不得生效。客户端不能升级来源或自报质量、收入 |

本地导入先校验全部引用、同意范围、版本和幂等键，返回逐项错误；整批验证失败不留半批有效测量。原件或凭据按权限保存为受控引用，不从任意路径/URL自动读取；命令行显式指定的输入包须限定到本次允许的本地根。协议变更生成新版本/队列，不改旧分配的判据。

`rebuild` 按协议hash和原事件摘要调用05，生成不可变收据与总结，重复输入复用同一内容ID；新事件产生新版本并保留 supersedes 引用，不覆盖旧结论。`show` 与研究会话收据查看共用验权读取器；与会话无关的原流程记录只在该试点授权范围读取。缓存可清除，原协议/事件/收据可在重启后重建与对账。

### 5.2 真实前向实验的受控入口

06 在同一独占目录提供 `python -m intelligence.services.research_evolution.study_io` 的 `freeze`、`register`、`settle`、`evaluate`、`show`，调用03公开函数与其唯一repository writer；不复制评分和冻结逻辑。显式传owner/协议或预测输入文件，服务端取now与解析后的用户根；禁止输入包覆盖登记时钟。读取默认无写入，登记/结算须显式 `--apply`，既有实验原件保持其原writer。

接线后可按03规则冻结首个合格日协议并登记人工或确定性预测；未到交易日、资料不鲜或PIT不足则清楚返回pending/gap及下次检查条件，不倒填。settle读取已授权源，未来未到不提前结算；无新增调度，执行人或用户按明确命令回检。show与Workbench收据入口共用03读取与曝光规则。

## 6. 切片实施与并行收敛

1. 任务 0：记录最新基线、各模块分支/commit、公共文件所有权、真实与测试用户根、spec schema。检查已有 8792 修复由谁负责，避免串改。
2. 可并行准备：实现只读资源适配、访问校验、UI 组件与合同夹具，module_status 标 synthetic/unavailable；不能此时宣布 product_verified。
3. 接入 01 真模块，完成显式绑定→数据变化→复核→后续 run；管理动作与原判断按各自 writer 落地。
4. 接入 02/04 真模块；接 05 事件、原流程登记、成本读取与不可变收据；接 03 收据，未来未到照样显示 pending。
5. 运行下面全链 E2E，修改数据/动作后重新加载并重启隔离服务，验证持久化与重建。
6. 收集最终组合 revision 上等价 CI、registry、E2E 收据，更新产品门/台账地图/能力图谱；形成部署候选与回滚说明，提交供用户确认。

进度与接线矩阵写 docs/superpowers/plans/2026-09-13-research-evolution/06/PROGRESS.md；跨模块缺陷列 BLOCKED.md，列 owner、最小复现、影响场景和已完成不受影响项。

## 7. 全链验收

在隔离 Workbench 上调用真实 API、真实 01–05 业务函数和临时用户态。市场与原件输入可以固定，LLM 可用确定性传输桩以验证流程；必须标 synthetic，并另列实际模型内容质量未验。本批不以它替代原材料题 PK。

| 编号 | 用户可见场景 | 必须证据 |
|---|---|---|
| I01 | 已有判断缺证据绑定 → 从现在跟踪 | 原ts不改，binding创建时间真实，旧历史不被补成strict |
| I02 | 来源仅版式/hash变 → 待复核 → 判断未变 | needs_review而非refuted；用户核对当前版本后关闭；原判断不改 |
| I03 | 明确放弃条件触发 → 排序置前 → 继续核查 | 01真实item进入02；scope与source跨入真实会话/run；错误状态不伪装完成 |
| I04 | 两次点击同动作、两个页面用旧版本操作 | 幂等一条；冲突409；旧页面不能关闭新变化 |
| I05 | 资料未到、缺轨、条件unknown | 01保留gap；02等待区；04无法归因；无“0”“已解除” |
| I06 | 另一用户同id/越界路径/任意改owner | 不泄漏、不能跨用户读取写入；本机未认证模式拒绝任意换用户 |
| I07 | 前向实验尚未到期，已有回放很好 | 03仍pending；普通面板没有概率承诺或方法已验证徽章 |
| I08 | 真实点击/失败run/重试产生05事件 | 失败保留分母；来源去重；已知/未知成本可对账，不只收success |
| I09 | 用户查看04诊断并完成练习 | 区分过程错误与结果输赢；答案揭示前不出现未来证据；练习不进方法统计 |
| I10 | 服务重启、输入版本更新、局部模块异常 | 绑定/动作不丢；缓存失效；module_status与错误可见，其余合法结果正常 |
| I11 | 关闭使用测量后继续研究 | 核心流程可用，05标缺测范围，不声称用户未使用 |
| I12 | 新增功能前后原研究会话/项目/下一问/日报 | 既有测试与真实入口回归通过，用户历史记录逐字节不变（新合法写入除外） |
| I13 | 冻结配对分配→无run原流程→辅助失败后重试→人工盲审→05汇总 | 同一writer保存输入与不可变收据；全部任务/尝试入账；重启重建一致；synthetic配对不升级为真人效果 |
| I14 | 切到后台读原资料或等待模型，再返回完成 | 应用内活跃时间可暂停，端到端耗时保持完整；无许可暂停理由不扣总时长 |
| I15 | 经受控命令冻结/登记→未来未到→到期结算→查看03收据 | 可信时间、真实repository持久化；未到期pending；重启读取同一原件，输入包不能回填now |
| I16 | 04揭示某案例结果→换名/换study用于03 holdout | 先记录原结果曝光再揭示；新实验仍识别已见，不能因为练习不进统计就洗成未见样本 |

至少做三项反向证伪：断开真实01调用只回固定报告，I03必须失败；去掉scope检查，I06必须失败；将失败run过滤掉，I08必须失败。不能仅验证页面出现静态标题。

检查命令以本仓现役配置为准：Python完整 Ruff/pytest；前端 pnpm lint、pnpm typecheck、pnpm test、pnpm build、pnpm test:e2e；registry按AGENTS现役命令运行。新worktree指定 WORKBENCH_PYTHON 为主树 .venv-workbench 解释器，隔离端口先检查未占用，不能接8792真实服务当测试服务器。所有叶子有明确结果才可签最终候选；skipped需逐条有基线说明，不通过增skip绕行。

## 8. 完成条件与交付

硬条件一：I01–I16从用户界面及受控本地登记入口到真实模块/原件/用户态走通，01–05每轨都有最终SHA与接口合同，重启后仍能对账；工程路径可报 product_verified。

硬条件二：原生产数据与未授权用户记录未改，私有隔离、unknown、幂等和反向证伪均成立；03/05的真实前向和用户效果状态与证据一致，可以仍是pending。

交付包含：组合分支SHA、各模块SHA、检查收据、隔离E2E的原始trace/截图、台账地图变更、状态矩阵、部署候选与回滚步骤。合并main及实际部署仍由用户最后确认，不能把“分支代码完成”写为“8792已上线”。
