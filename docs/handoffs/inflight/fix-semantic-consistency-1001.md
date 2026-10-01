# semantic-consistency / 2026-10-02

## 最高目标：纠偏62498cc2e02b
通用harness放大弱/强模型能力，不为弱模型追强模型堆硬规则语义路由。固定全句/子断言核验默认计划已撤回；焦点两案仅诊断。以跨题/跨模型质量、保真、完成/恢复、时延和成本验证，不拿工程绿代替净收益。权威docs/verification/2026-10-02-harness-goal-correction.md；PR14评论5937624672已发，勿重记。

## 授权/隔离
PR14 draft，不合main、不部署、不改默认off。持续GLM开放授权glm_open_budget_scope=preservation_e2e含必要修复；分批预注册、保留全部失败、不选优，不逐批问额度；其它模型未自动授权。旧批/本日01~05均closed，禁止重启；累计53物理。本轮06工程0模型，模型批尚未启动。

## 当前候选与下一步
R-20261002-06已claim：通用evidence_read只补读本Episode已交付title/detail，开关+显式授权才装配，不改capability地板/产品默认；模型自选，不是逐句检查。E8/E9原329/446字→240字，尾100字在旧实际请求整份messages确实缺失；不是旧语义错因归因。新展示字符与新证据分记，避免误判停滞；旁支E1不串缓存。
11文件391P/13秒为dirty工程读数；7源码变异6杀，删除重复授权闸1次仍被注册表挡住，原样保留，源码恢复。早期测试夹具cutoff source错误及失败日志保留。
详docs/verification/2026-10-02-evidence-reread-candidate.md；私有根evidence-reread-candidate-20261002含观测/失败/变异/claim。拟两合成题GLM5.3原生Episode A/B，固定4案≤24物理/500秒、单次50秒。须freeze/preflight后唯一启动；非ASGI全链/强模型/正式四格。模型净收益尚无结论。

## 04/05历史结论，不洗绿
实现7fe24b0f5仅改历史renderer，不改SQL/snapshot；12新测试、6变异、clean9文件752P/12.67s。04显式日期行为改善refuted：26预检、8HTTP/8响应/身份0，新旧均漏拒越界15，正确历史与方向保留；全文0/4。05焦点任务限定confirmed：11预检、2HTTP/2响应/身份0，原样64ID，越界false/历史true；同时改范围/任务/schema/token帽，非纯注意力因果/自动全篇/独立互证。04/05十回包low未验证。报告docs/verification/2026-10-02-mainline-scope-rendering.md；私有mainline-scope-rendering-20261002、focused-scope-diagnostic-20261002均closed。

## 未解除的门槛
01方向不等于全文；02提示refuted；03首50秒超时inconclusive。R18旧失败、R24 refuted、R21部分成立、R26仅接口保留；R25 off出站门不因enabled授权放宽；R19保持955+11/旧exit2。正式模型×harness四格先于240；PR8/生产默认/完整内容保真仍未过。
80e/d22 workbench最后仍in_progress，registry成功；旧CI不覆盖新候选。上次完整隔离：main3a2718c6、生产healthy@2c394978/match=true、队列7385/DB0444及hash未变；新批须独立后检。
