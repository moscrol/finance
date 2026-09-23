# 独立审查：阻塞记录，不是通过结论

候选 `d3abd6703368c668405e74a7e50beacd49b7581b`，独占 detached 检出，现有 Plus 的 `mirasim-kimi/kimi-k3` 通道。只读候选源码，生产数据/凭证/作者交接与验收报告拒读；命令写入仅限审查工作目录，命令网络拒绝。没有切换模型或绕过额度。

| 阶段 | 实测结果 | 可得结论 |
|---|---|---|
| 第一次网关预检 | HTTP 200，1 次请求 | 当时最小载荷可用，不认证后续长载荷 |
| explore | 360.91 秒；退出 143；stop_reason=deadline；7 次请求预占 | 源码阅读已发生，无探针、无正式报告，不能签 Spec/Quality |
| 收紧范围后的重试前预检 | 46.795 秒；TimeoutError；1 次请求 | 重试被前置门阻止，未启动第二个审查会话 |
| execute / report | 未运行 | 审查者自造探针 0；阳性对照未执行；无独立裁决 |

控制器状态：`BLOCKED_REVIEW_DEADLINE`，随后 `BLOCKED_PROVIDER_TIMEOUT`。这两个标签由执行证据归类，不是审查者出具的结论。作者测试另见上级完整门禁目录，不填入独立探针计数。

合计 9 次请求预占：7 次审查 + 2 次最小通道探针。预占不等于请求完成，也不是费用账单。重跑旧预检目录曾被 `EEXIST` 守卫拒绝，发生于凭证访问及请求之前，0 次模型请求；之后采用全新预检目录，旧证据未覆盖。

## 可复核证据

- `explore-execution.json`：候选和作者树首尾身份、输入/输出哈希、请求数、超时、退出码。候选未变；输入未变。作者树首尾均为干净的 `bb8e207e6`。
- `request-admissions.jsonl`：7 次审查请求在发出前预占。
- `gateway-before-explore.json` / `gateway-before-retry.json`：预检原件，无凭证和响应正文。
- `events.compact.jsonl`：去掉流式增量与模型 thinking 内容，保留工具执行与普通消息。没有把未完成的推理当报告。
- `harness/`：实际首轮 runner 与工具边界快照。`run.source.json` 将原始脚本保存为 JSON 字符串，保留行末空格等原始字节；`jq -j '.source' harness/run.source.json | shasum -a 256` 必须匹配 execution 中 `inputs_sha256["run.py"]`。不是后续调整预算的版本。
- 原始完整流与私有运行目录：`/Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/independent-d3abd670/`。原始流哈希见 execution；不得用空 stderr 或无 model_errors 推导成功。

原计划三个会话分别设计、执行和报告；首轮未交付，后续预检又失败，因此停止追加调用。实际仅运行一个审查会话，不把预备的后续 prompt 说成已执行。审查进程及其 runner 已退出。
