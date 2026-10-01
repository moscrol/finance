# semantic-consistency / 2026-10-02

## 目标/授权
纠偏62498cc2e02b：通用harness放大弱强模型，不追已知坏例堆路由；撤回固定逐句默认计划。权威docs/verification/2026-10-02-harness-goal-correction.md，评论5937624672勿重复。
持续GLM开放授权preservation_e2e含必要修复；分批预注册、留全失败、不选优。其它模型未自动授权。PR14 draft，默认off，不合main/部署/改生产模型。今日01~09均closed，勿重启；累计76物理，无在跑模型批。

## 候选/工程
实现f4c9a5dc66bf4a09c27b18dc29b0714a49087c03：evidence_read只补本Episode已交付title/detail，flag+显式授权，不改cap地板/ASGI默认。E8/E9尾部缺失不是旧语义错的因果证明。新展示字符独立计量、不是新来源；跨Episode不共用E1缓存。
clean11文件391P/14.80秒，receipt20261001T185257Z-f4c9a5dc-73036e90e007已校验；7变异6杀1存活。完整CI36910144597/36910144590五绿，19276P167S2xfail/1579.59秒；checkout3b469762 tree等于f4c，并非合并。证明根evidence-reread-candidate-20261002/ci-f4c。文档f9/019e最后workbench仍跑、registry绿。

## 06~09结案
06/07各1HTTP401、0准入、inconclusive/身份2。撤回“选错真实key”：私有shlex未展开shell；原生两个引用相同。08同入口bash环境15预检+绕入口负向红，不输出凭据。
08 glm5.3：11请求/11准入，B恢复2/2但全文1/2，主假设refuted。新增“交付与验收均未发生”中未交付无据；不加专门规则。A诚实缺口；B输入/输出32082/361、34.04秒；A13319/548、16.34秒。
09 flash只换配置：10请求/10准入，B恢复/全文均2/2，限定confirmed。A两题未完成，测量A“该材料中未包含”范围歧义且漏已交付日期，未认证全文保真。B26118/426、31.64秒；A13319/580、22.83秒。成本增加；不覆盖08失败，非新留出/强弱标定/净收益。两批low均未验证。
09独立acceptance/integrity/model-admission/isolation后检齐；raw summary不回填。零模型审计初版忽略HTTP追加runtime_budget，失败保留；修正仅允许该附加键，其余逐项相等。

## 下一步/证据
报告docs/verification/2026-10-02-evidence-reread-candidate.md；06/07/08/09私有根依次evidence-reread-live、evidence-reread-live-fixed-auth、evidence-reread-native-env、evidence-reread-flash（均-20261002）。下一批未占号/未启动：冻结新题/真实来源，加入无需补读对照，按全文保真/完成/恢复/成本验，不再刷旧两题。
09前后main3a2718c6、生产healthy@2c394978/match=true及模型、队列7521/hash、DB0444/hash一致。
04行为refuted/全文0/4；05焦点限定confirmed非全篇。R18失败、R26仅接口、R25 off门、R19 955+11/旧exit2保留。真实任务/ASGI/完整review-repair、独立强模型、正式四格、PR8门未过；四格先于240。
