# 同源计算结果的文字所有权

用户连续授权推进回答质量优化，并明确要求先查根因、避免错句补丁。此设计接续已部署PR76及固定首答诊断；采用三案中结果文字所有权的有限保证，不承诺自动证明任意自由正文。

## 已证根因与本次目标

固定首答的免疫治疗金额349.327、严格双红false及输入完整已真实送达；模型首稿写true，有效修订仍保留。完整原件回放真实核验函数，错误公稿原样passed。错误源头在合成，既有核验没有识别这类对立陈述。

本次改变“已有计算结果成为公开文字”的接口：程序生成确定性结果片段，作者选择引用、排列和自由分析，不能覆写获证片段的值/日期/对象/定义/范围。来源身份、结构完成与全文语义继续分账。原件仍NOT_PASSED；新接口只对采用它的生成片段提供可检验保证。

## 选择与范围

| 路线 | 结果 |
|---|---|
| 增提醒/错句词表 | 不采用；正确false已经送达 |
| 作者再填真假声明 | 不采用；声明false而正文true仍可绕过 |
| 更清楚的ResultView | 作为同源输入表示复用，但不代签蕴含 |
| 程序持有结果文字 | 采用；已完成的离线原型13组控制/24实际信号证明局部可行 |

先支持已有D4三类结果：每条同日板块的canonical严格双红资格、其本地规则定义、本表主题/行数/预览省略范围。未覆盖板块的唯一/无、医药完整最高高度、指数贡献等不发证书，不隐式补SQL。未来资格族须由实际结果owner提供同源纯计算，不造通用DSL。

## Interface与稳定来源

新增一个services内纯计算module `owned_results.py`。其主要入口是从已获授权的tool source编译只读catalogue，以及按refs/free blocks生成正文与覆盖回执。没有新网络port、工具入口、预算或用户开关。

来源用当前实际ToolObservation：真实tool/dataset、既有evidence hash和independent_key、完整query_basis、canonical定义身份。稳定digest只覆盖来源/输入/范围/定义，不覆盖整个Episode日志、模型内容、runtime_budget或后续事件。追加模型/finish不会改变已发ref；另一日期、对象、输入、范围或定义不能移绑。模型只见短opaque ref及它对应的结果文字，私有来源身份不进正文。

`d4_mainline_snapshot_v1`按三个事实键连接signal与源卡；标题仅展示。先检查有限数、inputs_complete/missing_inputs和None，再调用唯一canonical is_double_red。缺数为unknown，不因底层函数返回false冒充否定。已声明资格与重算不一致是source conflict，不渲染已获证结果。

catalogue在共享harness投影时派生；只有实际送达后由现有acknowledge_tool_result登记到本回合。允许一个尾置的、默认空的私有context来源缓存，或等价回合内既有对象；不得用全局可变缓存、不得修改AgentEvidence v5 atom字段。恢复时从原获准tool_result重建，重新检查当前授权/cutoff与source identity，缓存本身不是授予权限。

保留现有project_tool_result签名：其不带context，None仅用于已dispatch观测的纯显示派生，不授权、不缓存、不赋receipt。只读取成功观测的公开已允许源卡及其同源query_basis；每条信号须有匹配事实键的已批准卡，过滤项和私有telemetry不能补回来源。只有counts或无批准明细时不发ref；部分批准时仅认证该部分。ACK用真实context重编译后登记；准入、恢复和公开重核还须检查当时当前权限，未ACK的ref为未知，旧token/receipt不授新用户或run权限。

原生tool_result可能已落盘而私有evidence checkpoint仍是派发前的旧集。恢复可在原configure授权、entry identity及当前contract/cutoff均通过后，只用同一durable Episode的成功公开D4卡和同源query_basis重建source视图；必须对上实际保存model_content、其hash及已发布的refs投影。这个来源缓存不补EvidenceLedger/Outcome或证据floor，不恢复过滤项/私有字段。semantic有实际outcome.evidence时只取交集，缺完整证据的finish仍由原绑定检查如实拒收。

## 同一次finish中的选择

普通finish允许一个可选`answer_parts`：数组成员为字符串（自由文字）或封闭对象`{"result_ref": "…"}`。refs由程序发布，模型不提交value/truth/unit或手写来源。parts存在时draft必须空，且不能同时render_from_claims；有且只有一个正文生成者。旧None/缺字段沿旧路径，普通和材料旧schema消息/字节保持；材料authoring不被新分支绕过。

程序把parts按独立文档块拼接，不把片段插入自由否定/因果句法。一项结果可以只有一句；没有固定章节、长度或遍历catalogue要求。所有原来源/required-output/evidence-floor/材料合同仍在生成正文后执行。

准入返回可选的私有ownership receipt，记录原parts、稳定source/ref身份、生成文本/范围、整draft摘要及每个owned block的精确区间。程序重算/生成该receipt，忽略或拒绝作者自造receipt。旧路径receipt=None且不新增序列化键。

## 全链路与公开校验

主finish、有效repair、finalizer恢复，以及带稿carry路径必须保留与被采用draft对应的receipt；不能把新稿receipt盖在旧稿或将旧receipt套新稿。利用已有native events和finish payload持久化，不新建结果账本，不强迫新增AgentOutcome字段。恢复/后续重核必须从同源来源再派生，不能从旧公共文本反推refs或补造资格。

semantic verifier消费实际被接纳的receipt及原draft，检查owned blocks的值与区间。仅对应精确owned区间的程序定义/计算文字可避开自由条件数字标注；绝不把它们放进通用观测数池。自由相邻条件、未来持续阈值、作者同义复述不获豁免。R20历史集合基数与未来持续天数保持区分。

最终公开出口再次对账实际保留的owned内容。已被其它合法处理删除的片段不算送达；若被改写或移入另一范围，资格不能继续标已保真。覆盖回执分别记录owned/fragments与free/unassessed，不把schema/basis/refs存在或合成passed当全文语义认证。已有judge off、完成状态及用户分析能力保留；只有真实来源/协议/所有权违例按原有修订机制处理。

## 必须通过的验收

1. 真实冻结小片段走ToolObservation→共享投影→同次finish→真实semantic/public出口，免疫false保持false；真实创新药/AI医疗/化药true正确。定义有本地code来源，不是dated L4行情卡。
2. NULL未知、金额500/501、diff10严格边界；异日期/对象/单位/定义/范围/未授权来源、未知ref和同身份输入冲突拒绝。读原实际24/68不发全市场唯一、医药无高标、指数贡献证书。
3. 原seq44/49/57、公稿及旧None archive原样保留；legacy自由稿仍unassessed/原全文NOT_PASSED。旁有正确false片段不认证错误自由文字，改kind/basis不升级。
4. 用真实SourceEvent、原context许可和已有store验证refs在模型事件追加后稳定、repair/carry/finalizer/重开恢复保留同源选择；新上下文收窄及换用户/run不复用旧权限。
5. 明确渲染次序、拒第二draft/材料混用；旧普通/材料/None消息payload与公开字节相同。source/catalogue的私有locator/digest不进入模型日期投影或公开正文。
6. 程序片段不被误标10%/500亿“无出处”，R20自由未来条件仍不能借相同数字过关。最终删改与原receipt不一致时不报保真。
7. 提交前按实际改动范围跑有意义的模块与撤接线控制，独立Spec/Standards；准确head/main完整门禁、CI绿后才发布。新部署后原题只一次新首答，完整保存物理账/前缀/首稿/修订/公稿，再独审全文；不重抽、不预写市场结论。

Pi的river/history合同和ask_synthesis归属不变。本任务不接管其计算/在途文件；领域结果之后可复用本机制，但不在本轮合流。
