# Pi 工具桥：公开结果与私有审计边界

## 发现

方法细化候选 `e23f80081` 的新题 R1（2026-09-25）主要表为空，新闻工具返回 `future_of_cutoff`。
正式 `evidence=[]`，但桥接代码 `safe(obs)` 把整个 ToolObservation 发给模型，包含
`telemetry.temporal_withheld.evidence/observation` 中的6条未来新闻原文。
最终答案虽然说不采用后见资料，仍复述了被扣留的标题。因此不能把这条样本读成严格时间边界通过。

原件：`~/.finance-runtime/knevo-pi-method-1010/r1-0925/pi-tools.jsonl`，
SHA-256 `5bcbcc8b7f224b4e3c8528ef9e79ba7862e23d2bc7477abe4f6c1440fc1edb40`。
模型实际输入在同目录 `pi-model-requests.jsonl`；原件不覆盖。

## 根因与修复

生产 `ResearchHarness.project_tool_result` 明确将 telemetry 只放审计，不放模型；证据行走 `public_agent_evidence`。
Pi 桥把通用 dataclass 序列化误当成模型投影，重新暴露了领域层已经扣留的材料。

本分支增加小型 `integrations/pi/model_view.py`：

- 复用 `public_agent_evidence`，只交付已准入证据。
- 复用 `ToolObservation.result_status_fields()`，保留 empty/stale/partial/future_of_cutoff 与错误的区别。
- 显式保留 query_basis/source_context/gaps 和有效观察，把范围放在事实列表前。
- 私有 telemetry 与原始 trace 不进模型；完整原件仍在本地台账。
- `pi-tools.jsonl` 新增实际发送的 `model_observation`，可与后续模型请求逐项对账。

未直接搬整份 ResearchHarness 投影，因为它还加入了 Pi 当前不存在的 finish/owned-result 合同与引用指令。
没有新增金融判官或正文拒收门，没有修改生产模块。

## 验证

- 原 R1 的11份观察全部可投影；6条应扣留标题全部排除，公开查询范围与 gaps 保留，原文件哈希未变。
- 专项测试覆盖部分准入证据、未来材料、原始 trace、未知私有字段、公开状态与不修改审计。
- 真实 Pi + 真实 bridge 的 loopback 模型检查实际收到的结果没有 telemetry/trace，且有领域状态。
- 五个变异均被捕获：重新序列化整个审计、带回 telemetry、带回 trace、删查询范围、删已准入证据。
- 相关测试在修复后100P，收据 `20261009T174927Z-e23f8008-00d8e5c366bf.json` 为开发树读数，不冒充净树或真实模型质量通过。

## 真实验证边界

R1 因数据缺口及审计泄漏不签内容通过；R2（2026-09-24）虽区分了三种口径与未来假设，仍有总体/唯一断言越界，保持 NOT_PASSED。
修复后的 R3 使用新的9月23日题，启动前只核该日期存在，不读价格/行业值挑题。
预注册 `~/.finance-runtime/knevo-pi-method-1010/r3-preregistration.md`；真实结果单列，不能覆写前两题。
