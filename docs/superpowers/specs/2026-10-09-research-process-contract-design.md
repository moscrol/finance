# 研究输入、结果交付与作者合同收口

用户批准的方向：沿既有研究流程统一职责，研究视角更全面而答案可以简洁；多找根因、不叠末端补丁；优化先上线再验。生产基线为`origin/main@bd66de25085e`；本枝继承已审普通作者纯接口`f5847f33`，设计起点为干净`59eb4c19e`。不把这些未部署代码与生产质量混账。

## 问题与选择

真实首答仍全文NOT_PASSED。已证的合同冲突是system教旧draft、工具另教parts；已送达方法和数据仍被误读为去重数/连续日/指数贡献。另查得Codex headless网关单独组结果，丢了GLM路径已传的query_basis。Knevo方法资产与本仓已有母本一致，已有KB引导与主体记忆预取；零调用不能论证全项目缺接线。

三案原件在运行目录`research-control-1009/design/`：

| 方案 | 取舍 | 选择 |
|---|---|---|
| 三入口重建ResearchInputs及只读DeliveryLedgerView | 可以集中知识，但要迁移大量caller与账本投影 | 不增加这一公共Interface |
| 深化现有Harness，沿开场/观察/完成接缝统一 | 最常见caller少学合同，可复用已审作者Module | 采用 |
| 通用ResearchView/qualify、多题型扩展 | 资格能扩展，易变成重复框架；发现headless真实投影缺口 | 仅采用共享结果交付与保守资格，舍弃扩展平台 |

不新建总控、计划、状态机、工具、台账、判官、开关或预算。`research_contract.ResearchPlan`的owner检索投影与`research_plan.ResearchPlan`的模型意图保留不同身份。原loop管理调度/预算/停止/恢复；输入视图不拥有这些权限。

## 完整切片

一次完整交付包含A结果上下文、B实际作者消费。可以分提交和独立审查，不只上线初始prompt半片。

### A：由结果owner说明含义，经同一投影交付

继续使用`ToolRunResult`、`ToolObservation`、`ToolResultProjection`。可以在前两个已有类型尾部增加默认空的`source_context`安全JSON字段，既有位置参数不变；原源缺该字段时省略，不能补写成已验证资格。它是输入语义，不是授权、证据或评分，不进事实账本或evidence_type_floor。

字段规范是版本化`research_source_context_v1`，由已知结果owner生成，内容只包含：资料角色、原结果状态、原查询/群组/日期/预览范围、度量含义、已知与未知的计算资格、方法来源索引。原始事实值仍只在原evidence/query_basis中；不复制第二份行情，也不解析Markdown猜事实、日期或方法来源。

第一版只深化两个真实产品：D4 snapshot及FinanceQuery。D4保持原`D4_SOURCE_DESCRIPTOR`、v1 query_basis、source hash/ref规则不变；新增资格在独立envelope。历史day_count是本表窗口内不同观测日期数，first/last是跨度，完整日期集合/交易日连续性尚未给出时保持未知。群组行数是主题×板块记录，预览不等于全集成员；跨组唯一实体数/互斥性未建立时不提供去重资格。量价不提供指数权重贡献或资金因果。方法保ReadingRule原来源，不能成为市场事实卡。

FinanceQuery的结果owner从已经执行的spec、dataset声明及字段聚合定义生成所选字段的含义；聚合、返回组数、成员归属、跨日重复与候选全集分别说明。题材热度可能重叠，不将组内股票家数相加升级为唯一股票数/集中度。未取得成员身份或贡献资料就明确未知，不增加SQL/网络读取。资格描述是一般数据合同，不按本题医药/新能源或错误句子硬编码。

Harness共享投影同时用于GLM accumulator与headless gateway，传入各自已有evidence/context，保留query_basis/source_context与真实empty/partial/stale/error。headless不再用“有证据=success、无证据=empty”覆盖领域状态。transport预算与事件身份仍归原网关；确认送达只能在实际消息/响应已记录后，不能提前ACK。新资料角色不扩大授权，unknown源不获得硬资格。

开场既有原问、EvidencePlan、method候选、baseline、观点、材料与个人先验沿原字段交付。将它们的角色政策集中在既有输入owner；不额外复制全文或强制每题KB/记忆/PLAN。资料的提供、送达、引用、支持四个结论分别记录。程序只能证明前几种结构事实，任意自由句是否被来源蕴含另验。

### B：所有新请求使用唯一作者合同，旧回合保留旧身份

复用`finish_author_contract(context)`与`compile_finish_authoring`两个已审纯入口。新普通回合开场system不再独立教旧draft-only；动态输入交同一finish_format，模板可只含自由parts，不强选ref。材料格式仍由原material owner，用户题设/旧证据/缺口basis原合同不变。

工具结果、unsupported/invalid修订、repair、finalizer和恢复提示消费同一作者描述，移除重复模板/“提交完整draft”的矛盾指令。原合法legacy payload仍可入场，free-only无owned receipt；有限程序片段不认证相邻自由解释。终局仍走原source/binding/floor/截止/当前许可检查。

旧native事件与旧未终态回合按原保存的格式恢复，不因当前新默认静默迁移。格式选择从已有原生prompt/描述证明，不新增独立author状态或override事件。source_context缺失不补“历史上已送达”；授权仍来自当前恢复规则，保存的格式与资格不能授予源或预算。缺durable源不能补事实账本。

## 依赖与删减

纯角色/格式/资格计算在services，不import runtime。DuckDB、用户ledger、RAG、模型读取仍用已有reader/adapter，角色视图无IO。现有KB optional overlay、subject/date memory预取、adaptive/progress配置保留；不在这个切片扩自动检索。

消除三类重复责任：网关自己重建工具结果；system/tool/repair/finalizer各教作者形状；消费者自由猜计数、日期与覆盖含义。原权限、预算、原生账本、source版本、ACK和恢复不搬到第二总控。只有真实Interface行为测试覆盖后才替换重复浅测试，不机械删除守卫。

## 验收与质量边界

用真实ContinuousAgentEpisode/GLM捕获client和headless原gateway替身，检查实际第一前缀、工具响应、修订/finalizer/restore，不能仅验helper字段。最少覆盖：成功/空查/partial/stale/error、方法/先验角色、未来及材料限制、剪裁后范围、重复群组、日期跨度、量价资格、当前撤权/收截止、未ACK、旧archive和缺durable源。自由文本错误不能由资格envelope或completed自签正确。

正确引用和跳过相关/不相关KB、日期内/外个人记忆先用既有Adapter/临时用户ledger验消费者，不新建自动读取策略。整篇收益必须在候选工程绿、独立Spec→Standards、正常发布后，用新登记的唯一首答验证。保持原问、GLM身份、judge off和原预算；先固定同版源与RAG，保存全部物理attempt、前缀、拒稿/修订/公稿。原bd66的88件与旧118件不改、不重抽。n=1不证明胜Pi/Knevo或长期记忆收益。

若首答仍未正确消费相关需求，下一步先定位首次失真，再评估具体取证策略；不把新视图存在当作整个质量目标已达成。
