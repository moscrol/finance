# semantic-consistency / 2026-10-02

## 最高目标：纠偏62498cc2e02b
通用harness放大弱/强模型，不追坏例堆语义硬路由。固定全句核验默认计划已撤回，焦点仅诊断。按跨题/跨模型质量、保真、恢复、时延和成本验收，不以工程绿替代。权威docs/verification/2026-10-02-harness-goal-correction.md；PR14评论5937624672已发勿重记。

## 授权
PR14 draft，不合main、不部署、不改默认off。持续GLM开放授权glm_open_budget_scope=preservation_e2e含必要修复；分批预注册、保留失败、不选优，无需逐批问额度。其它模型未自动授权。旧批/本日01~07均closed，不准重启。累计55物理；08已claim未启动。

## 当前候选与08
实现f4c9a5dc66bf4a09c27b18dc29b0714a49087c03已push：evidence_read仅补本Episode已交付title/detail，默认关闭+显式授权；不改capability地板/ASGI默认。E8/E9原329/446字→240字，尾100字在旧整份messages缺失；未归因旧语义错。新展示字符与新来源分记，防误判停滞；旁支E1不串缓存。
clean11文件391P/14.80秒，收据20261001T185257Z-f4c9a5dc-73036e90e007通过checker，非全仓。7变异6杀，去重复授权闸1次仍被注册表挡住；源码恢复。夹具/预检错误留档。
06/07各首1请求/401回包/0获准模型回包、后3案未执行，均inconclusive/closed，身份exit2。撤回“选错真实key”初步归因：shlex未展开shell表达式，读到88/30字符，原生展开均49且相同；07只改顺序未修根因。零模型证据及失败留存，勿重开。
08已claim，另根evidence-reread-native-env-20261002：删私有解析，preflight/live同走launch.sh原生环境；15预检+绕入口负向红，出站前验展开配置。沿用两合成题A→B/B→A、4案≤24请求/500秒/单次50秒，每案4工具/120秒、不升档；enabled/low请求，实际low未验证。freeze后唯一启动。非ASGI/真实业务/强模型/正式四格。
权威docs/verification/2026-10-02-evidence-reread-candidate.md；工程根evidence-reread-candidate-20261002；06/07根evidence-reread-live-20261002、evidence-reread-live-fixed-auth-20261002均closed，08不得回填。

## 历史与未解除门槛
04 renderer实现7fe24b0f5工程成立，8HTTP行为改善refuted、全文0/4；05焦点2HTTP限定confirmed，非全篇/纯注意力/独立互证，不放行；04/05十回包low未验证。报告docs/verification/2026-10-02-mainline-scope-rendering.md。
01方向≠全文；02提示refuted；03超时inconclusive。R18旧失败、R24 refuted、R21部分成立、R26仅接口不变；R25 off出站门不因enabled授权放宽；R19保持955+11/旧exit2。正式模型×harness四格先于240；PR8/生产默认/完整内容保真仍未过。
80e/d22两CI成功，不覆盖候选；f4c9a5dc workbench在跑/registry绿。06/07前后main3a2718c6、生产healthy@2c394978/match=true、队列7521/hash、DB0444/hash一致；08另做前后检。
