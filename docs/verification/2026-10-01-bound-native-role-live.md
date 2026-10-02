# R-20261001-24：同次原生结论与数量角色实测（refuted）

## 授权与预注册

用户在`ask_user bound_native_role_budget=approve_two`明确批准新的独立额度：GLM-5.3，历史→未来各1次，最多2次物理HTTP，请求关闭thinking；无重试、无选优、不扩题、不跑整篇修复，不改生产放行，不合并/部署。旧25次额度不复用。

受验源码 **cf2b86e4723f2a45034ffd1f7a99f75d45091ff3**；观察适配器实现851da2ec2。R24只新增私有实验runner与正式文档，未修改仓库生产或探针代码。

发送前冻结：两份完整原生请求、精确数量区间、原生system原文、实验system、联合输出schema、参数模板和验收预期；plan SHA256 `ef23707882ab242f8ae6498648d8ea2d65c76883e9feb810fe99eee9901e28b2`。本次唯一调度时由未改动的R23适配器生成新nonce/review_id，完整实际wire在HTTP前落盘。模型不接收case标签、金标、前次响应或manifest。

## 与原生提示词的差异

保留`_judge_system_prompt(request)`原文作前缀、完整原生上下文原样置于`native_request`。但追加数量角色说明，把原生输出包进`grounding_report`，另加`quantity_roles`与必须回显的`review_id`，没有提供原生tool call。**这是显式改过提示词/输出结构的实验，不是完全未改提示词的原生实绩。**角色说明也可能影响原生判断，不能用单臂推断它对core完全无语义影响。

每案只经实际`_invoke_injected`入口调度一次，不进入`verify`修复/交付循环。原生core与角色各自记录，不强迫core全通过；目标14是否被拒仅观察，不预设整份gold报告。

预写通过条件是**两案均**取得身份准入通过、有效绑定、原生core保留及角色/来源/基数合预期的同次响应。该条件未达成，结论为`refuted`，不是拿“角色看起来对”替换判据。

## 执行结果

13项零网络预检通过；真实出站前持锁预占并fsync，STARTED_ONCE防重复启动，单案50秒硬超时，不跟随重定向，不内部重试。请求`temperature=0`、`max_tokens=4096`、`thinking.type=disabled`。

| 案例 | HTTP/响应 | 模型身份准入 | 原生入口结果 | 角色记录 | 时长 |
|---|---:|---:|---|---|---:|
| 历史 | 1/1 | 0 | 保留passed=false、拒句18及事实越证码 | 两处历史集合，E10/E11、09-29/30、基数2；绑定成立 | 19.705s |
| 未来 | 1/1 | 0 | 严格入口ContractError→unavailable，没有core可交还 | failed，不得借历史案补位 | 22.939s |

**2请求2响应，新增预算2/2关闭，系列累计27。没有第3次请求。**身份准入0只说明既有模型身份规则通过，不证明thinking控制落实，也不使角色成为放行依据。

## 未来案不止一个格式问题

1. 实际响应有一层JSON Markdown围栏。冻结runner使用严格`json.loads(content)`，因此在传给适配器的入口就失败。生产原生parser本来支持“恰好一个JSON围栏”，这属于实验传输入口兼容差异，不能说生产parser也不支持。
2. 离线仅借用已有`_STRICT_JSON_FENCE_RE`去围栏，**仍无法通过绑定**：请求review_id为64字符，模型回显为66字符，中间多插了字符，严格检查报`response belongs to another dispatch`。没有替它修ID、补nonce或重新发问。
3. 未接纳正文中可读到`future_duration_condition`、空历史来源及null基数；嵌入的core只拒18。但这些是**未绑定正文的观察**，不是未来案已获得有效原生报告，更不是已授权未来阈值。未挽救该core参与交付。

第一次离线检查曾假设“去围栏即足够”，实跑被错误ID推翻；失败脚本和记录保留。后验10项控制覆盖前后杂文/多对象拒绝、有效历史响应的异请求/上下文/矛盾core拒绝，及一个只有金标而非结构协议能发现的错角色。没有从已经无效的未来信封制造必然失败的伪负控。后验控制不是新增模型验收。

## 必须更正：请求关闭不等于实际关闭thinking

两份实际wire都确实有`thinking: {type: disabled}`，但回包同时提供非空`reasoning_content`及推理token计数：

| 轮次/案 | 推理字段字符数 | 回报推理tokens |
|---|---:|---:|
| R24历史 | 2208 | 697 |
| R24未来 | 923 | 255 |
| R21历史（旧响应补查） | 132 | 55 |
| R21未来（旧响应补查） | 99 | 29 |

这里只公开控制元数据，不公开推理正文。**实际关闭thinking不能认定成立，因此R24不能作为关闭thinking配置下的成功实验。**

进一步源码复查发现，`intelligence/services/llm_refine.py:1228–1233`早已有GLM-5.3强制思考、部分端点对disabled报错或静默改enabled的备注。本次预检只核对请求字段，漏查了这条已有能力限制，也未在首案回包出现推理字段时阻断次案；这是实验预检缺口，不能仅归咎于临时网络问题。没有擅自改用`low`冒充`off`，也没有追加预算。

R21原有角色判据2/2仍是当时真实响应观察，但“关闭thinking”控制未落实；补充更正后R21整体记`partially_confirmed`，不再称完整实验配置通过。旧原始响应、summary及预算账不覆盖，新增审计与文档更正指针。

## 证据、隔离与下一道门

私有根`~/.finance-runtime/bound-native-role-20261001/`：authorization/claim/plan、冻结prompt/schema/template、preflight、唯一live账本与两份request/response/content/events/observer-records/result、summary、offline-framing-diagnostic、thinking-control-audit、acceptance、postcheck。保留所有成功与失败；未修改旧R21或本轮原始响应。

后检：GitHub main仍3a2718c6；生产healthy@2c394978/code_matches_repo=true；队列7385及hash、冻结DB大小/hash/0444均与R23一致；plan、runner、输入及物理顺序账核对通过。未合并、未部署、未去待核。

后续先解决**有效模型控制的准入检查**与**严格绑定下的输出可用性**，不能只加一个宽松JSON抓取器，更不能替模型重写ID洗绿。若模型无法关闭thinking，必须先向用户说明并另获配置与预算授权；低推理不是关闭。任何新真实调用都需独立授权。R18正确句保真、PR8内容、正式在线接口、四格先于240继续阻断。

## 同时收齐的R23 CI（不替代模型验收）

受验源码cf2对应CI五绿：workbench36871079095、registry36871079128；Python19182P/167S/2xfail/1578.50s，checkout86272e5f与cf2完整tree87879133等价。该CI覆盖仓库观察适配器，不包含本单私有runner，更不能抵消R24的refuted。此后本单只改文档，不把后续文档HEAD冒充重新跑过同一全仓。

## 后续R25离线门与本提交CI

2bdd的自动CI已收齐：36874956908/36874957019五绿，19182P/167S/2xfail/1478.23s；实际d72629c1与2bdd完整tree4da90d73等价。此前“另查”为当时状态，不能用这份工程结果抵消本单refuted。

R25新增可选控制守卫，回放本单两份原wire均在transport前阻断；围栏兼容后未来66字符ID仍拒，未补ID或改写本单结果。详见[观察控制准入](2026-10-01-observation-control-gate.md)。模型仍累计27，预算关闭。
