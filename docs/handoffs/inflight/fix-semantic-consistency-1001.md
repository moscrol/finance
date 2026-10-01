# semantic-consistency / 2026-10-01

## 范围
PR14 draft，不合main、不部署、不改默认off。R16～R25已claim。模型累计27，所有额度关闭；R24 STARTED_ONCE已存在，严禁重启。

## 最新R25：仅离线可选门confirmed
实现b4cb98259411100f001caf82f9d2831e03fc7477，新增observation_admission及59测试，observer加文本解析；生产服务/prompt/schema未改，无HTTP实现。
clean14文件996P/2.75s，官方收据20261001T145012Z-b4cb9825-43dbd561790f；6/6变异。54初红→137P1F（fixture缺原生字段）→143单元项绿，原失败保留。
真实R21/R24四wire按原端点指纹0transport拦截，四回包均contradicted。R24历史原快照拒18保留；未来去围栏后66字符ID仍拒，未修ID/补core/回写旧结果。
协议docs/verification/2026-10-01-observation-control-gate.md；证据observation-control-gate-20261001。

## 门的边界
必须显式装配，不声称所有出口自动受保护。GLM5.3/flash的off已知不兼容不能被声明覆盖；未知模型需精确model/endpoint能力声明，声明引用不是验真。最终wire必须disabled，low/遗漏/旁路控制不当off。
同一序列共享guard：首个控制/传输失败永久停实例，含并发/重入；不可按案重建冒充停序列。逻辑帽不等于物理预算；transport仍负责原始bytes、账本、身份、deadline及无隐藏重试。
回包缺证停，不由空字段推断off；齐备自报仅reported_consistent。effective_disabled_verified/model_identity_verified/release_authorized恒false。单JSON围栏只改容器，不改绑定或角色权利。

## R24仍refuted
新批2HTTP/2响应/身份0，历史角色绑定过且拒18；未来围栏+回显ID66≠64失败。wire请求disabled但回包697/255推理tokens；预检漏查既有强制思考备注及回包，不能算有效off。R21旧回包55/29，角色2/2不变、整体partially_confirmed。旧预算2/2关闭，不跑整稿修复。

## 分账成绩
R23@851：32新/clean910P/5变异；cf2 CI19182P167S2xfail五绿。
R24文档2bdd CI36874956908/36874957019五绿，19182P167S2xfail/1478.23s；实际d72629c1与2bdd完整tree4da90d73等价。不是新b4全仓，新head CI另查。
R22@993：52新/684P/4变异；9f CI19150P167S2xfail五绿。
R19@84d8：966=955适用通过+11精确批准不适用；原error保留，不泛化豁免。

## 剩余/后检
仍缺真实有效控制/同次绑定可用性与角色质量；软件不能使GLM5.3/off变可用，也不得低推理冒充关闭。新配置与模型预算另批。R18保真、PR8内容、正式在线接口、四格先于240继续阻断。
GitHub main3a2718c6，生产healthy@2c394978/match=true，队列7385/hash、DB hash/0444均未变。
