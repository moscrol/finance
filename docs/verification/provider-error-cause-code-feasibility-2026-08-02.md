# Provider cause code 穿透可行性结论（2026-08-02）

## 结论

1. **路线 A 技术上可行，也是唯一能提供权威归因的路线。** 但改动点不在金融
   Runtime，而在 Cockpit 打包的 `cockpit-cliproxy`。Cockpit Tools 源码公开，当前
   本机 `v1.3.15` 对应源码 tag 可复现，sidecar 内嵌 CLIProxyAPI `v7.1.22`。
2. **原设想的路线 B（runtime 按同一 `requestId` 关联 `auth_result` 日志）当前不可行。**
   Cockpit 生成的 request ID 没有返回给 Python 客户端；而且账号池已经不可用时，
   请求在选账号之前就失败，不会产生同 request ID 的 `auth_result`。
3. **当前 28 题验收不必等待 Cockpit 改造。** 首次真实上游失败仍会把原始故障体
   返回给客户端；配合 Task 1 已落地的私有 `error_detail`，runner 可在首个 Provider
   故障时立即熔断并标记整批污染。只有要做到“池已熔断后，每个新 Run 仍能得到精确
   原因”时，才需要实施路线 A。
4. Task 3 的数据模型建议选择：**保留稳定、粗粒度 `stop_reason`，新增结构化
   `provider_error` 子字段**。不要为每个供应商故障不断扩张 `sdk_*` 终态枚举。

## 对原问题的事实修正

“三种上游故障在 sidecar 当场被压成同一句”并不完全准确。真实链路分两阶段：

```text
首次上游失败
  -> auth_result 保留真实响应体和 HTTP status
  -> 客户端也收到真实响应体
  -> scheduler 将该账号/模型置为 unavailable

后续请求
  -> 在选择账号前失败
  -> 没有 auth_selected / auth_result
  -> 只返回 503 auth_unavailable: no auth available
```

本机脱敏后的同一请求证据：

```text
requestId=cd06f4e0
auth_result: httpStatus=403,
  errorMessage={"code":"INSUFFICIENT_BALANCE",...},
  authStateReason=payment_required
request_completed: status=403,
  errorMessage=Error #01: {"code":"INSUFFICIENT_BALANCE",...}
```

该请求之后，账号池内没有可选凭据的请求只出现：

```text
executor_failed: auth_unavailable: no auth available
request_completed: status=503
```

并且没有对应的 `auth_result`。所以真正的信息丢失点是 **scheduler 从已持久化的
`ModelState.LastError` 合成下一次 `auth_unavailable` 时丢掉 cause**，不是 Codex
executor 第一次收到上游错误时丢失。

## 源码证据

- Cockpit Tools `v1.3.15` 是公开源码，仓库中直接包含 sidecar 和内嵌 CLIProxyAPI：
  <https://github.com/jlcodes99/cockpit-tools/tree/v1.3.15/sidecars/cockpit-cliproxy>
- sidecar 的 `authHook.OnResult` 已把 HTTP status、error code、error message 和账号
  可用状态写进 `auth_result`：
  <https://github.com/jlcodes99/cockpit-tools/blob/v1.3.15/sidecars/cockpit-cliproxy/main.go#L2994-L3071>
- CLIProxyAPI 的 `ModelState` 已保存 `LastError`，但 scheduler 的
  `unavailableErrorLocked` / `mixedUnavailableErrorLocked` 最终只构造通用
  `auth_unavailable`：
  <https://github.com/jlcodes99/cockpit-tools/blob/v1.3.15/sidecars/cockpit-cliproxy/cdk/CLIProxyAPI/sdk/cliproxy/auth/scheduler.go#L430-L462>
  <https://github.com/jlcodes99/cockpit-tools/blob/v1.3.15/sidecars/cockpit-cliproxy/cdk/CLIProxyAPI/sdk/cliproxy/auth/scheduler.go#L843-L861>
- 错误响应构造器本来就会原样保留合法 JSON 上游错误体，因此首次错误可穿透：
  <https://github.com/jlcodes99/cockpit-tools/blob/v1.3.15/sidecars/cockpit-cliproxy/cdk/CLIProxyAPI/sdk/api/handlers/handlers.go#L103-L148>
- 截至核验时的 CLIProxyAPI `main`（`bc71c77f`，2026-08-01）仍使用通用
  `auth_unavailable`，上游尚未解决该信息丢失。

## 两条路线的客观比较

| 路线 | 权威性 | 当前可行性 | 代价 | 结论 |
|---|---:|---:|---:|---|
| A. Cockpit 响应携带结构化 cause | 高 | 可行 | 需要改/构建 sidecar，并处理升级维护 | 生产级首选 |
| B. 同 requestId 查 `auth_result` | 低 | 当前不可行 | 客户端拿不到 ID；generic 503 没有 auth_result | 不实施 |
| B'. 按时间/model 倒推最近日志 | 低 | 可做 | 并发时会错配，只能给 heuristic | 仅辅助排障，不能驱动验收结论 |
| C. 首错即熔断 | 高（针对首错） | 现在可做 | 无法解释池已坏后的每个新请求 | 当前验收首选 |

### 为什么 B 不能作为兜底真值

1. sidecar 的 8 位 request ID 在本地中间件生成，只进入日志，没有放进响应 header/body。
2. generic 503 在 credential selection 前返回，不会触发 `authHook.OnResult`，所以不存在
   可按 request ID 查找的 cause 事件。
3. 按时间窗口寻找“最近一次失败”在并发、多账号和多模型池下会产生错误归因。
4. 金融验收可以保存这种推测为 `source=log_inference`、`confidence=heuristic`，但不能据此
   把产品失败改判为基础设施失败。

## 若选择 A：最小改动面

改 Cockpit 的独立分支或向其上游提交 PR，不直接替换当前运行中的 app：

1. 在 CLIProxyAPI `auth.Error` 增加安全、结构化的 cause（只允许 code/status/retryable，
   不带账号、key、完整响应体）。
2. 在 scheduler 汇总不可用凭据的 `ModelState.LastError`：
   - 所有候选原因一致时，返回权威 `cause_code`；
   - 原因冲突时不猜单一原因，返回 `mixed_provider_failures` 或 cause code 集合；
   - 没有历史原因时仍保留 generic `auth_unavailable`。
3. 在 OpenAI-compatible error envelope 中保留外层稳定 code，并增加嵌套字段，例如：

   ```json
   {
     "error": {
       "code": "auth_unavailable",
       "type": "server_error",
       "message": "no auth available",
       "provider_error": {
         "cause_code": "INSUFFICIENT_BALANCE",
         "http_status": 403,
         "retryable": false
       }
     }
   }
   ```

4. 可同时返回 `X-Cockpit-Request-Id`，只用于诊断；它不能替代结构化 cause。
5. 覆盖单账号一致原因、多账号同因、多账号混合原因、无历史原因、密钥不落响应等测试。

预计改动集中在 sidecar/CLIProxyAPI 4–6 个 Go 文件及其测试；金融仓随后只需解析
`provider_error`，不需要读 Cockpit 日志。

## Runtime 数据模型建议

保持：

```text
stop_reason = sdk_auth_unavailable | sdk_rate_limited |
              sdk_upstream_unavailable | sdk_run_failed | ...
```

新增私有审计字段：

```json
{
  "provider_error": {
    "schema_version": 1,
    "provider": "cockpit_local",
    "outer_code": "auth_unavailable",
    "kind": "payment_required",
    "provider_code": "INSUFFICIENT_BALANCE",
    "http_status": 403,
    "retryable": false,
    "source": "provider_response",
    "confidence": "authoritative"
  }
}
```

理由：`stop_reason` 表达 Episode 为什么停止，`provider_error` 表达底层供应商为什么失败。
两者不是同一维度。分开后，runner 熔断、基础设施污染统计和后续新故障码都不需要破坏
已有终态协议。

## 当前建议与待决策

**为了完成 Continuous Harness 内部验收，建议暂不维护 Cockpit fork：先进入 Task 4，
利用首次精确错误 + runner 首错熔断。** 这能直接阻止 24 道题继续白跑。

如果目标提升为“生产环境任何时刻、任何 Run 都必须得到权威 provider cause”，则先实施
路线 A，再进入 Task 3。路线 B 不应实现为权威分类链路。

本 Task 仅调研和记录结论；未修改 Cockpit、未替换 sidecar、未实现 Task 3。
