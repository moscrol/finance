# R-20261001-26：启用思考的同次函数输出观察

## 授权与限定结论

用户在`ask_user bound_tool_output_budget=approve_enabled_two`独立批准：GLM-5.3 **允许启用thinking**，请求low强度；回包若未证明low生效必须记未验证。固定历史→未来各一次，最多2次物理HTTP，无重试/选优/扩题，不跑整篇修复，不改生产放行、不合并部署。旧27次预算不复用。

本单`confirmed`只指**本次两案的指定工具信封、同次绑定、原生core保留和预写角色/来源判据**。不是关闭thinking实验，不是low实际生效证明，不是稳定率、泛化或端到端修复。

受验仓库源码 **fe648215608a7d4d8a8cffed489a7dc2fb1ce542**；没有改仓库服务/探针实现，只新增私有冻结实验与正式文档。

## 发送前冻结的协议变化

- 保留原`_judge_system_prompt`全文前缀与完整native request，角色定义沿用R24；增加明确的函数报告要求。不是未改提示词的原生实绩。
- 只提供`submit_bound_grounding_report`，tool_choice指向它。参数内仍有完整`grounding_report`、`quantity_roles`、schema与review_id；本次ID在工具schema中列为唯一允许值。
- 工具仅报告，不执行任何外部动作。不接受普通正文回退、多个工具、其它函数或混杂说明。arguments原文交给未改动的R25观察适配器解析、再走R22绑定/core/roles检查；不插入、截短或修补ID。
- **不假设供应商执行了enum约束**，未使用或宣称支持供应商strict生成标志。请求schema加约束与本地严格校验是两件事。
- 输入、角色预期、原生/实验system、schema模板及参数均事前冻结；只有每次唯一调度的新nonce/review_id，以及schema内相同ID枚举槽在出站前实例化。完整实际请求在HTTP前落盘。
- 这是新的enabled配置，不伪造支持off的能力声明，也不把R25 disabled专用门改成放行。检查最终wire必须enabled/low；回包显式控制矛盾、传输或模型身份失败停止后案。low回显缺失按用户批准记未验证，不冒充证明。

Plan SHA256：`5dc0a10b17b55399c30e1aacac51875aaa0c77e1b20fb0953f8c2145f3814511`。
Runner SHA256：`274c7cc1eab796d632e3749298269c745c71e0fdb55d327d6cdc56c9461eaf1a`。

## 唯一一轮实绩

| 案 | HTTP/响应 | 身份准入 | 工具调用/绑定 | 角色判据 | 原生拒句 | 用时 |
|---|---:|---:|---|---|---|---:|
| 历史 | 1/1 | 0 | 1个指定函数，64字符ID与请求及唯一枚举逐字相同 | 两处历史集合基数2，E10/E11、09-29/30 | 16、18、20 | 34.035s |
| 未来 | 1/1 | 0 | 1个指定函数，64字符ID与请求及唯一枚举逐字相同 | 未来持续条件，历史来源空、基数null | 18、20 | 14.988s |

两次finish_reason均为tool_calls；原始函数arguments、观察记录response_text逐字相同，解码对象与保存response一致。原生拒句数组与实际进入native parser后的报告一致，均passed=false；没有为角色成功而抹掉拒绝或补造通过。

**2请求2响应，新预算2/2已关闭，系列累计29。**没有第3次HTTP、没有重试或选优，也没有执行报告函数以外的工具动作。

请求thinking enabled、reasoning_effort low、temperature=0、max_tokens=4096，单案50秒硬超时，不跟随重定向。物理额度在出站前持锁预占并fsync，STARTED_ONCE阻止再次启动。

## low没有被证实，原生内容也没有过关

回包未明确回显low，两案均`effort_status=unverified`、`effective_low_verified=false`。回包推理元数据为历史4689字符/1506 tokens、未来1808字符/556 tokens；只公开计数，不公开推理正文。不能用token多少倒推出low档位，也不把同一组字段当供应商内部计算的认证。

原生报告仍提出问题：历史案16的主线日期/窗口证据、两案18的交易日历断言及20的未交付字段被说成不存在。这里只记录模型提出的拒绝，不把所有拒句理由额外认证为真值。

core与角色来自同一模型同一次输出，不是两个独立判官互证。两案目标14均未被原生报告拒绝，但这不是未来阈值有证据或历史句已保真的证明。两案对16的处理不同，也不能据此次结果宣称附加角色任务不影响core。数量角色保持diagnostic_only、release_authorized=false、model_identity_verified=false；**不参与生产豁免**。

本次仅经真实`_invoke_injected`入口各调度一次，没有执行`verify`的整篇修复/交付循环。R18正确句最终保真、机械待核消除、PR8内容门、生产默认provider接线及四格先于240均未因此解除。

## 离线检查与限制

- 26项零网络预检：固定顺序/预算帽、工具ID唯一枚举与回调组合、坏角色保留原生拒绝、错误ID不修补、实际序列在控制矛盾/超时后停案、无/多/错工具及正文回退拒绝、身份缺失/错配、重定向拒绝、low仅自报不作隐藏计算证明。
- 18项实响应后验控制：66字符错误ID、跨案、交付文本变化、矛盾core、坏角色、多个/错名/混杂正文工具，以及结构仍成立但由冻结金标识别的错角色。
- 所有后验在副本上进行，原live、summary、计划/输入/runner的hash不变；无新增模型或网络。没有把后验构造当新增真实响应。
- 只验证已知两案，每案一次。未来原稿仍有自解释角色的句15；不能据此推泛化。相对R24同时改了输出协议与思考配置，且nonce本就应刷新，不是单变量A/B，不作稳定性、速度或成本收益结论。R24仍refuted，R21仍partially_confirmed，不回写旧失败为成功。

## R25 CI实绩补收

fe6482156对应workbench **36880087581**、registry **36880087639**五检查success。Python **19241P/167S/2xfail/1251.10s**；实际checkout **a3bc35ffaf533df733ba882369ee3243e1fce2cc**与fe完整tree均 **9e9fba397b8c3f0d918f8a362c9281cb40f5f479**，父包含fe；fe相对b4实现仅4份docs变化。临时合并树等价，不是实际合并。该CI覆盖仓库实现，不包含本单私有runner，不替代模型/内容验收。

## 证据与隔离

私有根`~/.finance-runtime/bound-tool-output-20261001/`：claim/authorization/plan、冻结prompt/schema/template、preflight、唯一live账本及两份request/response/arguments/events/observer-records/result、summary、postresponse-controls、acceptance、postcheck。原始私有全文及凭据不入Git。

GitHub main3a2718c6、生产healthy@2c394978/code_matches_repo=true；队列7385/hash、冻结DB大小/hash/0444与R25一致。新预算关闭，未合并、未部署；任何后续真实模型请求均需独立授权。后续首先按既有内容与保真门验收，不把这个受限接口成功接成生产放行。
