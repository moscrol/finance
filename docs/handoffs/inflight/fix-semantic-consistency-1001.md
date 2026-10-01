# semantic-consistency / 2026-10-01

## 范围
只推进既有验收门，PR14 draft；不合main、不部署、不改默认off。模型系列25，所有额度关闭。R16～R23已claim，勿重复领取。

## 当前
R23显式可选judge_fn观察适配器实现851da2ec26eeb1b80b687ef09bd7b2ccbf694dfa。生产服务/prompt/schema/机械门未改、无新HTTP实现。详见docs/verification/2026-10-01-quantity-role-observer.md。

## 已验
- R23 clean851：12文件910P/2.80s，32新测试，官方收据20261001T134046Z-851da2ec-17f628f4ee16；5/5私有变异。
- 默认拒句保留策略、真实删除两轮、材料隔离复判/重编号/次轮超时、最终待核标注失效均与baseline对照。初始删句fixture错误预期及三次78P1F日志保留，未改生产来洗绿；最终84单元项通过。
- 冻结历史2/未来1区间：各1dispatch/1替身transport；公开文本/状态/issues与baseline相同、仍待核；最终绑定stale。原R21响应2/2仍拒，网络/模型0、原件不变。
- R22实现99318ab00：52新/clean684P/4变异；后补9f的CI五绿，19150P167S2xfail/1740.88s，实际6db23637与9f完整tree ae1143c6等价。不是R23的全仓成绩。
- R19受验84d8：966=955适用成功+11精确批准不适用，原error保留；Mac19190P75S2xfail、CI19098P167S2xfail另账，不挪用。

## 红线
一次原生调度最多一次transport，显式逻辑帽不等于HTTP/模型授权。header/context/core无效整次失败；仅roles坏保留已验当前core。latest-only；文本/上下文变更不自动重映射。release_authorized/model_identity_verified恒false。结构一致不证明角色词义，不去待核。

## 剩余
R23新head CI须另收，不能预记全绿。正式在线接口、真实完整原生上下文角色质量、R18正确句保真、PR8内容、四格先于240仍阻断。R21只有独立影子2例，未来句自解释；不能补造core/nonce升级身份。

下一步必须先明确新实验的prompt/schema差异与独立有限授权；旧25次额度不可复用。不扩大题目/修复清单，不把观察标签变成生产豁免。

## 后检
GitHub main/origin/main3a2718c6，生产healthy@2c394978/match=true；队列7385/hash与DB hash/0444未变。本地旧main47a与GitHub不是同ref，首轮后检引用误比已留档纠正，未改ref。
