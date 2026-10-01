# semantic-consistency / 2026-10-02

## 最高目标/授权
纠偏62498cc2e02b：通用harness放大弱/强模型，不追坏例堆硬路由；固定全句核验默认计划已撤回。权威docs/verification/2026-10-02-harness-goal-correction.md；PR14评论5937624672已发勿重记。质量、保真、恢复、时延/成本跨题跨模型验收，工程绿不替代。
PR14 draft，不合main、不部署、不改默认off。持续GLM开放授权glm_open_budget_scope=preservation_e2e含必要修复；分批预注册、留全部失败、不选优，无需逐批问额度；其它模型未自动授权。旧批及本日01~08均closed不准重启。累计66物理；09已claim未启动。

## 候选实现与工程
f4c9a5dc66bf4a09c27b18dc29b0714a49087c03已push：evidence_read仅补本Episode已交付title/detail，默认关闭+显式授权，不改capability地板/ASGI默认。旧E8/E9尾100字确在整份请求缺失，非旧语义错因归因。新字符不计新来源，防误判停滞；旁支E1不串缓存。
clean11文件391P/14.80秒，收据20261001T185257Z-f4c9a5dc-73036e90e007通过checker，非全仓。7变异6杀；去重复授权闸1次仍被注册表挡住，按存活留档。

## 06/07/08已结案
06/07各1请求/401/0获准模型回包，inconclusive，身份exit2。撤回“选错真实key”初判：shlex未展开shell表达式，原生两个引用相同。08改用同一launch.sh原生环境，15预检+绕入口负向红；凭据不落文档。
08 GLM5.3四案11HTTP/11回包/身份0，low未验证。A两题诚实缺口；B恢复2/2但全文保真1/2。交付B新增“交付与验收均未发生”，未交付无据；原预注册两题皆无新错refuted，不加针对这句的规则。B输入/输出32082/361，A13319/548；时长B34.04秒/A16.34秒，不能称整体净收益。

## 09下一步
根evidence-reread-flash-20261002：仅换glm-5.3-flash，代码/材料/问题/提示/四案次序/判据不变。两题A→B/B→A，≤24物理/500秒/单次50秒；每案≤6请求、4工具/120秒、不升档。freeze/preflight后唯一启动。非新留出集/强弱标定/正式四格；不按模型名生产分流，不回填08。
权威docs/verification/2026-10-02-evidence-reread-candidate.md；工程根evidence-reread-candidate-20261002。06/07/08根分别evidence-reread-live、evidence-reread-live-fixed-auth、evidence-reread-native-env（均加-20261002），原件/失败/acceptance完整。

## 历史门槛与隔离
04 renderer7fe24b0f5工程成立、行为refuted/全文0/4；05焦点限定confirmed非全篇，均不放行。报告docs/verification/2026-10-02-mainline-scope-rendering.md。R18旧失败、R26仅接口、R25 off门、R19 955+11/旧exit2不变；正式四格先于240；PR8/生产默认/全文保真未过。
80e/d22 CI成功不覆盖候选；f4c最后python在跑，e2e/frontend/registry绿。08前后main3a2718c6、生产healthy@2c394978/match=true、队列7521/hash、DB0444/hash一致；09另后检。
