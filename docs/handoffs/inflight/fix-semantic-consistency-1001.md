# semantic-consistency / 2026-10-02

## 最高目标：用户纠偏62498cc2e02b
优化通用harness，让弱模型发挥好、强模型发挥更好，不为弱模型追强模型添加硬规则语义路由。撤回“固定全句/子断言检查”为默认下一步；焦点两案仅诊断。改进信息、工具、反馈与模型决策空间，必要契约不替模型思考；以跨题/跨模型净收益验证。
权威说明：docs/verification/2026-10-02-harness-goal-correction.md。

## 授权/边界
PR14 draft，不合main、不部署、不改默认off。持续GLM总额度开放，glm_open_budget_scope=preservation_e2e允许必要修复；分批预注册、保留失败、不选优，不逐批问额度。其它模型不自动获授权。旧批及本日01~05均关闭、STARTED_ONCE严禁重启；累计53请求。本次纠偏0模型。新批可沿用授权，须新计划/停止条件。

## 04：工程清晰，行为改善refuted
实现7fe24b0f52e741ab73d82a3aa73e62fdaf07b918：ask_blocks历史行显式查询窗口/主题首末日期/截止日表内记录，不改SQL、snapshot/source_date，不把表内未见当市场不存在。12新测试；clean9文件752P/12.67s、6/6变异。收据20261001T174512Z-7fe24b0f-d995b79b6da7；图构建缺uvx，详报告。
26零网预检，固定越界旧→越界新→历史新→历史旧，8HTTP/8响应/身份0。新臂只换canonical E7内存视图/hash/bindings，原件不改。两对wire只差E7标题/正文。新旧均漏拒越界15，正确历史与方向14均保留；范围判据0/0/1/1、完整内容0/4。不可用工程绿放行。

## 05：焦点两案限定confirmed
完整native上下文、点名15、新短任务及函数输出。11预检；2HTTP/2响应/身份0，原样64ID。越界false/历史true，理由与E7/E8/E9相符。非完整verify，未接放行；范围/任务/schema/token帽一起变，非纯注意力A/B或自动全篇覆盖。04/05共10回包low未验证。
报告docs/verification/2026-10-02-mainline-scope-rendering.md；私有根mainline-scope-rendering-20261002、focused-scope-diagnostic-20261002含freeze/live/acceptance/postcheck。

## 下一步与历史边界
重新提出通用机制的最小干预与基线对照，再验未参与调试的题及模型差异；不预设硬路由、必跑逐句检查或反复核验，不重跑已关闭批次选优。日期表达改动保持draft候选，未证净收益。
01方向保真不等于整篇通过；02提示补充refuted；03大报告首50s超时/身份2无语义结论。R18旧失败、R24 refuted、R21 partially_confirmed保留；R26仅接口。R25 off门不因enabled授权放宽；R19保持955+11/旧exit2。
e7旧CI五绿不覆盖新12测试；80e及后续docs CI另收。main3a2718c6、生产healthy@2c394978/match=true、队列7385/hash、DB hash/0444未变。生产默认、完整内容/保真稳定性、PR8与原四格先于240未解除。
