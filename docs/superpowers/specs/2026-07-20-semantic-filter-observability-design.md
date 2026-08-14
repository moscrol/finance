# 语义过滤可观测性分级设计

## 问题

`evidence_judge` 成功识别并丢弃无关 RAG 命中后，
`evidence_providers._apply_semantic_judge()` 把“丢弃 N 条无关召回”写入
`ClosedLoopRetrievalResult.warnings`。Workbench 编排器把任何 skill warning
都记为 run degrade，于是一次正常的防幻觉过滤被展示为“研究降级”。

这既误导用户，也把控制面诊断泄漏到了展示面。真正应该降级的是：

- 过滤后没有足够证据；
- 检索超时、失败或预算耗尽；
- 必要证据阶段未完成。

“过滤器成功移除噪声”本身不是故障。

## 方案

### A. 为闭环检索增加 diagnostics 通道（采用）

`ClosedLoopRetrievalResult` 新增 `diagnostics`：

- 语义闸门的丢弃数量、标题和理由写入 diagnostics；
- `inspector_dict()` 暴露 diagnostics，保留 trace 可观测性；
- `warnings` 只保留超时、空召回、协议/索引异常等会影响答案质量的问题；
- `AskResult.warnings` 不再接收成功过滤信息。

优点：状态语义清楚、trace 不丢、对编排器改动最小。

### B. 编排器按字符串过滤 warning

改动小，但把 evidence-provider 的语义知识泄漏到通用 orchestrator，容易随文案
变化失效。

### C. 保持 degrade，仅修改文案

无法解决状态错误，成熟度看板和告警仍会被假阳性污染。

## 验收

- 语义 judge 丢弃无关命中后，命中进入 `discarded`。
- `warnings` 为空，`diagnostics` 记录过滤详情。
- inspector/trace 可看到 diagnostics。
- 个股生产 E2E 不因成功过滤噪声而降级；若存在真实证据 gap，仍如实降级。
