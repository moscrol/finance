# semantic-consistency / 2026-10-01

## 范围
PR14 draft；不合main、不部署、不改默认off。R16～R24已claim。模型累计27，所有额度关闭，R24 STARTED_ONCE已存在，严禁重启。

## 最新R24：refuted
源码cf2b86e4723f2a45034ffd1f7a99f75d45091ff3，仅私有runner+docs；未改生产或探针代码。用户新批2次，历史→未来各1HTTP/响应，身份准入0，19.705/22.939s。
历史两处角色及来源/基数通过，原生拒18保留。未来返回JSON围栏，严格入口失败；离线去围栏后review_id回显66字符≠请求64，仍拒。不能替它改ID/补core洗绿。
两wire请求thinking disabled，但回包有非空推理字段及697/255推理tokens。源码llm_refine:1228已有GLM5.3强制推理提示，本轮预检漏查能力/回包，不是有效关闭。R21旧回包同样55/29，角色2/2不变但整体改partially_confirmed。13预检/10后验控制；原件、失败、错假设均保留。
协议docs/verification/2026-10-01-bound-native-role-live.md；证据bound-native-role-20261001。预算2/2关闭，不跑整稿修复，无第3次请求。

## R23接线已验
实现851da2ec26eeb1b80b687ef09bd7b2ccbf694dfa；clean12文件910P/2.80s、32新、5/5变异，官方收据20261001T134046Z-851da2ec-17f628f4ee16。
显式judge_fn观察，不是生产默认/新HTTP。真实删除两轮、材料隔离复判/超时、重编号、最终标注失效与baseline对照；初始fixture三次78P1F保留。冻结两案各1dispatch/替身transport，交付相同且仍待核。详见quantity-role-observer协议。
cf2 CI已五绿：36871079095/36871079128，19182P167S2xfail/1578.50s，实际86272e5f与cf2完整tree87879133等价，不是合并。

## 旧成绩分账
R22 clean993：52新/684P/4变异；9f CI五绿19150P167S2xfail，6db23637与9f完整tree ae1143c6等价。
R19@84d8：966=955适用通过+11精确批准不适用，旧error保留；Mac19190P75S2xfail、CI19098P167S2xfail。

## 红线/下一步
每原生调度最多一次transport；逻辑帽不等于物理授权。异请求/header/core无效整次失败；仅roles坏保留已验当前core。latest-only，交付变更无自动重映射。放行/身份标志恒false。
先补有效模型控制准入与严格绑定下输出可用性；不得把low当off，不得只靠宽松抓JSON。新配置/真实预算另批。R18保真、PR8内容、正式在线接口、四格先于240仍阻断。

## 后检
GitHub main3a2718c6，生产healthy@2c394978/match=true，队列7385/hash、DB hash/0444均不变。本地旧main47a不是GitHub ref，R23误比已单独留档纠正。
