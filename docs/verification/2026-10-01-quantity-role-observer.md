# R-20261001-23：数量角色的可选观察性接线

## 范围与结论

实现 **851da2ec26eeb1b80b687ef09bd7b2ccbf694dfa**；用户要求继续推进既有验收，旧模型预算均关闭。此次只在现有`SemanticEpisodeVerifier(judge_fn=...)`注入缝安装一个**显式可选**适配器；角色附加记录由调用方单独保存，返回生产解析器的仍是当前原生判官报告。没有修改生产服务、提示词、schema、默认开关或数字门，没有新的HTTP实现。

`confirmed`仅指离线接线边界与受测生命周期，不指模型角色判断正确、历史误标修复、默认在线接入或交付内容通过。

- `scripts/review_probes/quantity_role_observer.py`：可选回调适配器。
- `quantity_role_contract.py`：提取`check_native_report`，先核验完整绑定和core；原`check_review`仍完整校验core+角色，原52项测试全部通过。
- `tests/test_quantity_role_observer.py`：32项新测试。

## 调用与失败规则

```python
observer = QuantityRoleObserver(transport, target_selector, max_dispatches=2)
verifier = SemanticEpisodeVerifier(judge_fn=observer)
# verify(...) 后独立读取 observer.records；不把角色写进正式报告。
# 交付查询必须传当前完整请求及明确 review_id：
view = observer.delivery_view(current_request, review_id=review_id)
```

1. 调用方必须显式提供transport、精确数量区间选择器和正整数调度上限。每个准入的原生调度至多调用transport一次，原timeout原样传递；无内部重试、复位或补额度。逻辑调度帽**不是物理HTTP预算，更不是模型调用授权**。真实transport还须独立负责物理账本、期限和身份准入。
2. 有目标时使用R22完整请求+新nonce+数量区间协议；无目标时发送原native request，不强加角色结构。适配器不推断“两日”等词的自然语言含义。
3. 跨发送、上下文、nonce、整体结构或core无效，整次失败，不能挽救异请求的core。仅角色内容无效时保留**已核验的当前core**，包括拒句，附加记录标`invalid_roles`。
4. 返回的是原始、已验证的core，而非已经协调过材料声明的标准化副本，避免材料parser重复协调。core仍由现有原生parser及后续机械门处理。
5. 最新失败、无目标、新调度或超帽都不能复用旧成功角色。材料隔离复判、更改上下文、删除重编号及最终加待核文字后，旧绑定不得直接套用；不实现自动重映射或找旧成功兜底。
6. 保存与返回均隔离可变对象；运输中改动输入会失败；诊断仅记异常类型，不抄任意异常消息。`diagnostic_only=true`、`release_authorized=false`、`model_identity_verified=false`恒成立。内容指纹不认证模型作者，也不证明角色/数量词义正确。

## 实测与失败记录

- 新API占位时27项全部失败（27F/0.66s）；首次实现78P/1F（含旧52项）。两次fixture探索仍78P/1F，三个失败日志均保留。
- 唯一失败源于测试误把“无理由码拒句”当成删句授权：默认策略实际保留并记问题，baseline与adapter相同。后续局部关闭降级且加长首句，又触发原有短稿回退。没有改生产逻辑来满足错误预期。最终保留独立的原默认策略等价测试；删除用例改为现有`fact_beyond_evidence`分支、保留足够长的两句正文，实测真实两轮删除。最终测试不关闭生产语义降级开关。
- 后补5项覆盖，共32新+52旧=84项通过；不宣称后补5项也经历最初红测。
- clean **851da2ec2** 上12文件定向回归 **910 passed / 2.80s**，collected=910、无失败/跳过。官方收据`20261001T134046Z-851da2ec-17f628f4ee16.json`通过同SHA、解释器、依赖、clean、无绕过、覆盖及对账检查，GitHub基座漂移0。**不是全仓成绩。**
- 5个私有独立变异（调度帽、原生拒绝、latest-only、当前上下文、不放行）均被对应测试杀死；仓库源未改。预期失败变异不冒充原实现回归失败。
- 真实Verifier执行覆盖：默认策略保留/待核不变；事实错误删除两轮；删除前后目标重编号；材料→隔离非事实两阶段重编号与去除邻接材料；第二阶段角色坏而core拒绝不丢；第二阶段超时不得继承首阶段通过；最终公开数字标注使旧绑定失效。均为明确替身，不是模型质量测试。

## 真实冻结输入回放（仍是替身）

R18/R21两份原历史/未来上下文，各跑原生全通过baseline与观察适配器；后者使用明确的合成`unknown`角色，不套用旧模型结果。

| 原样本 | 数量区间 | 原生调度/transport | 公开文本、状态、issues对照 | 最终角色绑定 |
|---|---:|---:|---|---|
| 历史集合条件 | 2 | 1/1 | 与baseline全等，目标仍待核 | 最终文本已加标注，stale |
| 未来持续阈值 | 1 | 1/1 | 与baseline全等，目标仍待核 | 最终文本已加标注，stale |

首原生请求与冻结文件逐项相同；R21旧响应直接经新适配器仍2/2拒绝，没有补造core/nonce升级身份。socket与模型transport双阻断，网络尝试/模型请求0，旧产物hash不变。这证明接线未改受测交付，**不证明历史误标修好**。

证据根：`~/.finance-runtime/quantity-role-observer-20261001/`（plan、red、green各版、mutations、committed/receipt-check、real-replay-result、acceptance、postcheck）。不提交私有全文或大文件。

## R22 CI补收（不挪用于R23）

R22文档head **9f3281b7c706c81aadfdf7c4668f41c007e13bee** 的workbench run **36865993383**与registry run **36865993435**均success，五检查全过。Python **19150P/167S/2xfail/1740.88s**。

CI实际checkout **6db2363704e716e516501e59c01dd62517253709**，与9f的完整tree均为 **ae1143c69c5237c43aefe274cbcc4b82a34ab0b7**；9f相对993实现只有3份docs变化。这是CI临时合并树的等价证明，不是实际合并。日志与树证明已落R22私有证据根。**不把这个成绩算作851/R23新CI**；R23推送后另查，不预记全绿。

## 隔离与仍阻断项

GitHub main与origin/main均仍3a2718c6，生产healthy@2c394978/code_matches_repo=true；队列7385及hash、冻结DB大小/hash/0444均与R22后检一致。首次后检误比较本地旧`main`引用47a05e36与GitHub基线，断言失败已单独留档；改为查询GitHub权威ref并与origin/main交叉核对，没有改任何ref或把引用差异当生产变更。

模型新增0，系列25，预算全部关闭；未合并、未部署。正式provider/HTTP线上角色接口、原生完整上下文下真实角色质量、R18正确句保真、PR8内容门、四格先于240仍待验。下一次真实模型实验须独立授权，并明确提示词/schema变化；不可把旧影子成功或本次替身接线当成端到端修复。
