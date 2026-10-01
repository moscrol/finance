# semantic-consistency / 2026-10-01

## 范围
PR14 draft，不合main、不部署、不改默认off。R16～R26已claim。模型累计29，所有额度关闭；R24/R26 STARTED_ONCE已存在，严禁重启。

## 最新R26：仅两案联合接口confirmed
用户新批bound_tool_output_budget=approve_enabled_two，允许GLM5.3启用thinking；请求low，缺回显必须记未验证。受验fe648215608a7d4d8a8cffed489a7dc2fb1ce542，私有runner+docs，未改仓库服务/探针。
历史→未来各1HTTP/响应，身份0，各1个submit_bound_grounding_report，ID64字符与本次请求/唯一枚举逐字相同。历史两处E10E11/两日期/基数2过，未来持续角色不借历史；原生core保留passed=false及拒16/18/20、18/20。34.035/14.988s。
low两案unverified，回包推理tokens1506/556；不以token量推档位。26预检/18后验控制，原件不变。2/2关闭，没有整篇修复/交付。不是单变量A/B/稳定性/泛化，未来句15仍自解释；不改变旧失败。
协议docs/verification/2026-10-01-bound-tool-output-live.md；证据bound-tool-output-20261001。

## R25控制门与CI
实现b4cb98259411100f001caf82f9d2831e03fc7477；59新，clean14文件996P/2.75s，官方收据20261001T145012Z-b4cb9825-43dbd561790f，6/6变异。
必须显式装配；已知GLM5.3/off出站前拒，未知能力不推定。声明引用不是验真。共享guard首个控制失败停后案/并发/重入；逻辑帽不等于物理授权。回包缺证停，齐备自报仅reported_consistent；effective_disabled_verified/identity/release恒false。R26新enabled授权不是伪造off能力或把low当off。
fe CI36880087581/36880087639五绿，19241P167S2xfail/1251.10s；实际a3bc35ff与fe完整tree9e9fba39等价，非合并。后续文档CI另查，不冒称重跑。

## 旧结果分账
R24仍refuted：2HTTP、历史绑定过/拒18；未来围栏+回显ID66≠64失败。关闭thinking预检漏查，回包697/255推理tokens；R21旧回包55/29，角色2/2不变、整体partially_confirmed。旧响应/summary不覆盖。
R23@851：32新/clean910P/5变异；cf2 CI19182P167S2xfail五绿。R22@993：52新/684P/4变异；9f CI19150P167S2xfail五绿。R19@84d8：966=955适用成功+11精确批准不适用，原error保留，不泛化豁免。

## 剩余/后检
现在只确认已知两例同次接口可用，角色仍无放行权。生产默认provider接线、R18正确句保真、PR8内容、修复/交付和四格先于240仍阻断。新真实模型必须另批，不把接口成功当内容完成。
GitHub main3a2718c6，生产healthy@2c394978/match=true，队列7385/hash、DB hash/0444均未变。
