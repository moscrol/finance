# R-20261001-22：数量角色的离线绑定接口

## 本单做了什么

用户要求继续推进，已有25次模型请求的额度均关闭。本单不调用模型、不改生产判官、提示词、默认off或机械门；把下一阶段必须遵守的接口边界做成可执行探针，而不是又补一个“两日”白名单。

实现提交 **99318ab008b14155c945957752c54d1f2d732c58**，只新增：

- `scripts/review_probes/quantity_role_contract.py`：离线prepare/check CLI及Python接口。
- `tests/test_quantity_role_contract.py`：52项边界/兼容测试。

## 从现有源码确认的断点

1. 原生`_parse_report`和tool schema严格限制字段；R21独立影子JSON不是原生`GroundingJudgeReport`，直接交进去会被拒绝，不能手造一个passed=true冒充补齐。
2. `_mark_numeric_condition_doubts`依据最终verified draft重新计算机械标注；原生报告并没有携带这些角色。仅给解析器多加键既不能完成修复，也不能保证交付阶段使用的是同一版文本。
3. 后续投影/删句会改变文本或编号，`_recheck_research_delivery`也会重新分句。不能凭旧句号继续套用此前角色。

代码图查询的structure为空，未据此断言架构不存在；以上来自实际schema、parser、report和交付源码及执行测试。

## 接口如何约束

旁路附加记录独立于正式判官结论，不授予放行权限：

- prepare接收完整原生投递请求和每处数量的Unicode字符区间，冻结问题、日期上下文、证据、绑定、句子等全部内容。
- 每次prepare生成新的随机发送标识nonce，再生成完整内容指纹review_id。相同文字的另一次发送不能借用旧结果。同一句重复两次数量必须分别覆盖；重叠/重复区间拒绝。
- check还必须提供当前原生请求，不能只检查自己保存的旧快照。改句、删句重排、加待核文字、改日期、换问题/证据/绑定都拒绝复用。
- 合并响应必须同时有独立的`grounding_report`与`quantity_roles`。原生报告仍走原严格parser，原拒句/问题保留；角色不能抹去它们。
- 历史角色必须引用当前registry内的唯一ID，明确唯一source_date集合及集合基数；无效/重复日期、未知ID、bool冒充整数、缺项/重复角色都阻断。
- 未来/unknown/other角色不能携带历史集合基数来授权自身。
- 输出始终是`diagnostic_only=true`、`release_authorized=false`、`model_identity_verified=false`。真实传输身份仍须由既有模型准入另验，文件和指纹不是作者签名或可信模型证明。

### 必须公开的反例

测试故意把未来条件贴成“历史集合”，再配上一组真实历史日期：结构绑定可能一致，但不能证明角色正确。把“四日”配成三条source_date也不能靠绑定检查证明数字理解正确。**两种结果都仍无放行权。** source_date也不必然等于交易日/指标期间。本接口不是自然语言语义验证器，不能据它去掉待核。

## 实际验证

- 先为新接口写47项测试，占位API抛NotImplementedError时47失败；这不是旧生产已有47项回归。实现后47通过；再补5项交付/CLI边界，共52项。
- 首次功能绿后ruff仍发现测试排版问题，格式化修正后ruff和diff检查通过，提交hooks全部通过。
- clean **99318ab00** 上7文件定向回归 **684 passed / 2.52s**，0失败/跳过，收集684。收据`20261001T125830Z-99318ab0-d258dff1ba4e.json`；官方checker通过SHA、解释器、依赖、clean、无绕过及收执对账，基座漂移0。**这是定向范围，不是全仓。**
- 4个私有独立变异：去掉当前请求一致性、发送绑定、来源日期约束、把不放行改为放行。4/4被对应测试杀死；仓库源未变。不能把这些预期失败的变异收据当原实现回归失败。
- 两份真实冻结上下文CLI prepare均成功，历史目标绑定2处“两日”、未来1处；两份真实R21旧影子JSON均exit2，未生成通过文件。没有篡改旧响应去补新协议。
- 两案各走一次现有真实投递/交付代码+明确全通过替身，首请求与旧冻结上下文一致；两案目标仍带待核。socket及模型transport双阻断，网络尝试/模型请求0，原episode与R20/R21产物hash不变。不是新真实模型验收。

私有证据根`~/.finance-runtime/quantity-role-contract-20261001/`：plan、red/green/定向/同提交日志与收据、变异、real-replay-result、acceptance、postcheck。不覆盖旧baseline或模型报告。

## 使用方式（仅离线）

```bash
python scripts/review_probes/quantity_role_contract.py prepare \
  --native-request native.json --spans spans.json --out review.new.json
python scripts/review_probes/quantity_role_contract.py check \
  --bundle review.new.json --response combined-response.json \
  --current-request current-native.json --out diagnostic.new.json
```

必须使用工作台解释器。所有输出exclusive-create，不覆盖；格式/绑定无效exit2。**exit0只表示诊断接口结构成立，不是答案通过，更不是部署许可。** Python API同样要求current_request；完整响应样式和非固定日期/数量例子见测试。

## 留下的门

本单confirmed仅指离线绑定接口，不是原生在线角色接线或内容修复。尚未改变生产schema/parser或交付；尚未取得原生提示词下的真实角色响应，不能复用R21模型实绩。

下一阶段需要共同评审原生schema、报告携带、修复轮与交付生命周期，并以独立语义验收确认角色正确。不能直接把这个诊断结果接成豁免。新真实模型实验须另行授权；系列仍25、预算关闭。R18正确句保真、PR8内容门、四格先于240继续保留。

本次未重跑全仓，不挪用84d8全仓/CI为993背书；推送后的新CI单独查看，本文不预记全绿。main3a2718c6、生产healthy@2c394978/code_matches_repo=true、队列7385/hash、冻结DB hash/0444均未变，未合并/部署。
