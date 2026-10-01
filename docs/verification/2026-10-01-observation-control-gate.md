# R-20261001-25：观察实验的控制准入与严格围栏解析

## 限定结论

实现 **b4cb98259411100f001caf82f9d2831e03fc7477**。用户要求继续推进；R24两请求已关闭，系列27。本单新增模型/网络请求0，`confirmed`仅指**显式装配路径的离线控制守卫与不修字段的格式解析**，不是已经证明某真实模型关闭了thinking，也不是原生在线角色质量或内容修复。

改动仅三文件：

- `scripts/review_probes/observation_admission.py`：思考关闭的实验前/后检查、失败停序列守卫、单JSON容器解析。
- `quantity_role_observer.py`：合并响应为文本时走该格式解析；仍走原R22完整绑定/core/roles检查，保存原始response_text。
- `tests/test_observation_admission.py`：59项新测试。

生产服务、默认、提示词、schema与数值门没有改；没有新HTTP实现，没有重写R21/R24冻结runner或原始结果。**并非所有既有模型出口已自动安装此门。新实验必须显式装配，不能绕过后声称受它保护。**

## 发送前：不再把请求参数当作能力证明

`check_off_request`检查最终wire，而不是只看环境变量：

1. model必须与预注册目标一致，thinking必须严格是disabled；enabled、遗漏、low/none等reasoning_effort、其它控制入口或嵌套extra_body均不拿来冒充关闭；本接口只支持非流式。
2. 已知GLM-5.3/GLM-5.3-FLASH强制思考限制，在任何transport调用前阻断；大小写及同名namespace形式不绕过。调用方即便提供“支持”的声明也不能覆盖该负面知识。依据是既有llm_refine备注及R21/R24真实回包，不声称发现了新供应商能力。
3. 其它未知模型也不默认通过。必须提供`OffCapability`，精确绑定模型及端点指纹，supported只能是布尔true，且有非空审阅来源引用。缺失、不支持、scope不符均阻断。

**OffCapability是调用方审阅声明，不是模块自行发现或认证的供应商能力，source_ref不等于验真。**本单没有批准任何新的真实模型/正向能力记录；正向通过用例均明确是合成fixture。

## 回包：矛盾和证据不足都停，不只检查model名

`audit_off_response`只提取控制元数据，不把推理文本写入诊断：

- 非空reasoning_content/其它推理载荷，或任一已识别推理token计数为正，即`contradicted`；请求或回包声称disabled不能覆盖反证。
- 模型缺失/不符、形状不合、计数为bool/字符串/负数等，不能当作配置一致。
- 缺少明确关闭回显、明确空推理字段或明确零计数，均`unverifiable`。空字段/缺字段不等于已证明关闭。
- 三组自报信息齐备且一致才记`reported_consistent`。这依然只是服务自报一致，不是对内部计算的证明。`effective_disabled_verified`、`model_identity_verified`、`release_authorized`始终false；既有模型身份准入、预算及内容门仍须独立执行。

`DisabledThinkingGuard`串行保护整个预注册序列：任一预检、回包或传输失败后永久停止当前实例；后续案例、并发及重入都不能抢在失败检查前继续。无重试、复位、换模型或修改控制档位。transport收到不可变JSON bytes及原timeout，诊断不保留任意异常消息。

同一序列必须共享一个guard；逐案重建不能冒称跨案停机已生效。逻辑调度上限不是物理HTTP授权/账本，transport仍负责exact bytes、无隐藏重写/重试、身份原件、物理预占与硬期限。本单没有实现或授权新付费transport。

## 围栏兼容不等于修复绑定

`decode_combined_content`复用生产原生parser的“裸JSON或恰好一个JSON围栏”匹配规则，不搜索正文中的JSON片段。前后说明文字、多对象、数组、重复键、非有限数均拒绝。

只去容器包装，不改字段、句号、nonce、core、角色或review_id。随后仍用原R22检查当前完整请求与同次绑定；角色内容坏时保留已核验当前core的既有策略不变。

R24未来案的原响应经新解析器可得到对象，但其ID仍是**66字符≠原64字符**，绑定检查继续拒绝，没有core挽救或原结果升格。历史案仅在其**原历史快照绑定**下确认拒句18不丢，不冒充一次新的模型调度。

## 验证记录

- 54项新测试先对占位API全红（54F/0.63s）。首次实现137P/1F（含旧84项）：集成fixture缺原生回调必需的3个请求字段，尚未进入observer；补齐真实接口形状，不改生产或削弱断言。
- 再补5项原生负向接线/重入/输入变更/并发测试，共59新+84旧=143P/0.67s；后补5项不冒称经历初红。
- clean **b4cb98259**，14文件定向 **996P/2.75s**，collected=996，无失败/跳过。收据`20261001T145012Z-b4cb9825-43dbd561790f.json`经官方checker核验同SHA、环境/依赖、clean、无绕过、覆盖及对账，GitHub基座漂移0。不是新全仓成绩。
- 6个独立私有变异全部被杀死：去掉已知能力拦截、失败停机、放行未知回包、忽略正推理计数、授予release、截短ID“修复”。仓库源不变；预期失败变异不是原实现回归。
- clean同SHA离线读取R21/R24四份真实wire，使用原端点指纹，四份均在transport前被阻断；4份真实response审计均contradicted（55/29/697/255推理tokens），transport/网络/模型调用均0。
- R24两份原绑定另做只读解析核对：历史拒18保留；未来66字符ID仍拒。旧live、plan、授权与summary的hash均不变；R24仍refuted，R21仍partially_confirmed。

证据根`~/.finance-runtime/observation-control-gate-20261001/`：claim/plan、red/green/green-v2、mutations、committed/receipt-check、frozen-replay-result、acceptance、postcheck。私有原文/凭据不进Git。

## 收取上一文档提交CI（不能移作b4全仓）

2bdd487b11eb217f9cae762d88d52c2d35c1ae31对应workbench **36874956908**、registry **36874957019**五绿，Python **19182P/167S/2xfail/1478.23s**。实际checkout **d72629c11818dc34c7f1612dd0d0ab4f7c120845**与2bdd完整tree均 **4da90d73240445e3cdf0ade151e049e205a62b5a**；父包含2bdd。只是CI临时合并树等价，未实际合并。证明在R24根ci-docs-proof.json；新b4实现不能挪用这个成绩。

## 隔离与剩余门

GitHub main3a2718c6，生产healthy@2c394978/code_matches_repo=true；队列7385/hash、冻结DB大小/hash/0444与R24一致。模型新增0、系列27、所有额度关闭，未合并/部署。

已知GLM-5.3/off组合现在只能被拒，不能被软件守卫变成可用；low不是off。更换模型或明确允许其它模式仍需新的配置/预算授权和证据。回显ID可靠性、真实同次联合输出及角色质量尚未解决；不能靠补ID解除。R18保真、PR8内容、正式在线接口、四格先于240继续阻断。
