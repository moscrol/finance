# Continuous Harness 验收可信度与 Cockpit 直连设计

## 背景

现有 28 题验收不能证明 Continuous Harness 已被真实执行：生产 8792 的
`ASK_CONTINUOUS_RUNTIME` 为 `off`，历史结果全部来自 legacy Workbench；现有
`preflight()` 只检查服务健康、revision 是否存在和 backend 是否 ready，没有核对
mode、dirty、实际 import root 或每个 Run 的执行身份。C10 的三轮问题还分别创建了
三个 conversation，因此不能作为多轮一致性证据。

本机 Cockpit sidecar 已提供 OpenAI-compatible API：
`http://127.0.0.1:57244/v1`。2026-08-02 已对 `/models` 和 `/responses` 做最小实测，
`gpt-5.6-sol` 返回成功。现有 `sdk_gpt` runtime 已使用 OpenAI Responses adapter，
因此首批优化复用该 seam，不新增另一套模型协议。

## 目标

第一批只解决“验收对象是否真实、可归因”这一个问题：

1. 让验收在运行前精确确认正在测试的进程、代码、模式、backend 和模型。
2. 让每次 Run 按 attempt 留下不可变的执行 provenance。
3. 让验收按产品语义核对预期执行路径，而不是要求所有题伪装成同一路径。
4. 修复 C10，使其真实复用同一个 conversation，并绑定精确的 Run 和消息。
5. 使用 Cockpit 直连 `gpt-5.6-sol` 跑独立新基线，不消耗 GLM 额度，也不与旧 GLM
   基线做单变量对比。

## 非目标

本批不实现：

- 工具权限状态机；
- 完整工具生命周期重构；
- HTTP、子进程和 sub-research 取消故障注入；
- transactional outbox 与终态原子性修复；
- Episode checkpoint resume；
- 10–15 轮上下文压缩与长期记忆策略；
- 持久研究 Fork；
- 修改 C8 的产品路由。

这些项目在本批验收身份可信后分批处理，避免同时改动执行层、持久层和验收层。

## 方案选择

### 采用：现有 `sdk_gpt` + Cockpit Responses API

隔离实例选择 `AGENT_RUNTIME_BACKEND=sdk_gpt`，由现有
`OpenAIAgentsRuntime` 通过 Cockpit 的 `/responses` 接口调用
`gpt-5.6-sol`。这条路径已有 runtime seam、工具 schema 兼容层和单元测试，新增工作
集中在身份记录、严格门禁和验收脚本。

### 不采用：新增 `continuous_openai_compat`

该方案可让手写 Continuous Episode 继续使用 Chat Completions，只替换模型 provider；
但需要新增 backend、readiness 和 composition 分支，并会继续承载当前 GLM 路径的事后
`tool_request` 语义。它适合以后做 runtime 对照实验，不属于当前最小可信验收范围。

### 禁止：用 Cockpit 环境变量伪装 `continuous_glm`

虽然 `GLMModelClient` 底层能够调用 OpenAI-compatible provider，但继续把实际 Cockpit
执行记录为 `continuous_glm/glm-5.2` 会制造错误归因，违背本批核心目标。

## 分支与部署隔离

实施分支为 `fix/continuous-harness-acceptance-trust`，叠加在尚未进入 `main` 的
`fix/exposure-ranking-truncation` Runtime 基线上。不得合并或强推 `main`。

生产 8792 保持不动。验收使用单独端口、独立进程和明确环境：

```text
ASK_CONTINUOUS_RUNTIME=on
AGENT_RUNTIME_BACKEND=sdk_gpt
OPENAI_BASE_URL=http://127.0.0.1:57244/v1
OPENAI_AGENT_MODEL=gpt-5.6-sol
LLM_MODEL=gpt-5.6-sol
AGENT_RUNTIME_PROVIDER_LABEL=cockpit_local
```

启动器在运行时从
`~/.antigravity_cockpit/codex_local_access_sidecar/config.json` 读取 key，只注入子进程
环境，不打印、不复制到仓库、不写入验收产物。启动器必须清除可能继承的 GLM 和其它
provider key，保证 runtime provider chain 只有 Cockpit 一项。

## 运行身份模型

### 进程级身份

应用启动时生成一个 `runtime_instance_id`，并在 `/api/health` 的 runtime 投影中提供：

```json
{
  "runtime_instance_id": "runtime_<opaque-id>",
  "source_revision": "<40-char git sha>",
  "source_dirty": false,
  "code_root": "<configured repo root>",
  "import_root": "<root resolved from intelligence.__file__>",
  "python_executable": "<resolved executable>",
  "continuous_agent": {"mode": "on"},
  "agent_runtime": {
    "backend": "sdk_gpt",
    "model": "gpt-5.6-sol",
    "provider_label": "cockpit_local",
    "provider_protocol": "openai_responses",
    "endpoint_fingerprint": "<sha256 of normalized base URL>",
    "ready": true
  }
}
```

`import_root` 必须来自实际导入模块的位置，不能复用配置中的 `code_root`。endpoint 只
记录固定标签和 hash，不记录 key，也不把可能含凭据的任意 URL 原文写入产物。

### Run attempt 级身份

每次 worker 执行或重启重放都创建新的 attempt；同一个 `run_id` 可以拥有多个
attempt，但 attempt 记录不能原地覆盖。canonical 记录采用 Run 目录内 append-only
`attempts.jsonl`，每条写入后 flush + fsync。记录分三类：

1. `attempt.started`：attempt ID/index、runtime instance、选定 backend/model、revision、
   dirty、import root、启动时间。
2. `execution.bound`：实际 execution path、terminal owner、contributors、effective
   backend/model、TaskFrame hash、cutoff。
3. `attempt.finished`：终态、结束时间、与本 attempt 绑定的 artifact receipt。

公开 API 只投影非敏感字段；密钥、Authorization、完整 prompt、provider continuation
不得进入 provenance。

`attempt_id` 在一次执行中不可变，恢复或整轮重放必须创建新的 `attempt_id` 并递增
`attempt_index`。这样可以区分“同一 Run 恢复”与“同一段代码真的只执行一次”。

## 执行路径契约

验收新增独立的 execution-contract overlay，不修改冻结问题正文。允许值为：

```text
continuous_episode
continuous_fast_path
continuous_clarification
legacy_direct
```

当前 28 题的契约为：

- 26 题：`continuous_episode`；
- B6：`continuous_clarification`，缺少所指卖方材料时由 Continuous 控制层澄清，不调用
  模型工具 Episode；
- C8：`legacy_direct`，保留现有普通聊天/不存在表的拒答路由；
- C10 的两个 follow-up 与首轮一样均为 `continuous_episode`。

因此 28 个 case 实际包含 30 个 turn：28 个 `continuous_episode` turn、1 个
`continuous_clarification` turn、1 个 `legacy_direct` turn。验收通过要求“观察路径等于
契约路径”，不是把 30 个 turn 都强行标成 Continuous Episode。

`terminal_owner` 使用稳定枚举区分 Episode、clarification 和 legacy direct owner；
`contributors` 只记录参与的稳定组件/Skill ID，不记录自由文本。

## `continuous-episode.json` 绑定

只有 `continuous_episode` 路径要求该内部 artifact。artifact 内容或伴随 receipt 必须
绑定：

```text
run_id
attempt_id
runtime_instance_id
task_frame_hash
cutoff
artifact_sha256
```

验收从 Run API 取得 artifact metadata，再核对 attempt 的 receipt。仅凭文件名存在不能
计为 Continuous 执行证据；来自旧 attempt、旧 TaskFrame 或旧 cutoff 的文件均失败。

`continuous_clarification` 和 `legacy_direct` 不要求伪造该 artifact，但必须拥有完整
attempt provenance 和正确 execution path。

## 严格 preflight

验收 CLI 接收显式期望值，并返回结构化 `PreflightReport`。至少核对：

- health status；
- `continuous_agent.mode == on`；
- `source_dirty == false`；
- expected revision 与完整 source revision 相等；
- expected code root 与 `code_root` 相等；
- `import_root == code_root`；
- backend、model、provider label、provider protocol 精确匹配；
- runtime ready；
- 依赖和 Cockpit 最小 readiness 正常。

`--force` 可以保留诊断用途，但任何 preflight 失败的输出必须标记
`acceptance_eligible=false`，不能进入正式看板计数。验收文件保存完整的非敏感 health
快照、期望值、preflight receipt hash 和失败字段，不再只保存一句描述文本。

## C10 真多轮

验收客户端拆为两个动作：

1. 每个 case 创建一次 conversation；
2. 在该 conversation 内顺序提交首问和 follow-up。

每次 POST 的响应必须立即保存：

```text
conversation_id
user_message_id
assistant_message_id
run_id
```

轮询时按精确 `assistant_message_id` 和 `run_id` 查找，不再读取“最后一条 assistant”。
C10 的结构性通过条件为：

- 三轮 `conversation_id` 完全相同；
- 三个 `run_id` 和 `assistant_message_id` 两两不同；
- 后两轮 `parent_run_id` 形成同一 conversation 的顺序链；
- 三轮 observed execution path 均为 `continuous_episode`；
- TaskFrame/cutoff 保留 2026-07-23 的 PIT 约束；
- 现有答案一致性规则继续单独评分。

三轮不足以验证长上下文压缩；10–15 轮 Context Retention 测试另立批次，不能把 C10
通过宣传为“压缩已正确”。

## 验收数据流

```text
严格 preflight
  -> 创建 case conversation
  -> POST turn，保存精确 ID
  -> 等待该 message/run 终态
  -> 读取 Run provenance + artifact receipt
  -> 对比 execution-contract overlay
  -> 保存 TurnTrace
  -> 执行既有答案质量判定
```

执行可信度与答案质量分成两层：

- Layer 1：30/30 turn 的进程身份、执行路径和 artifact 绑定是否可信；
- Layer 2：28 个 case 的业务答案是否通过既有规则。

Layer 1 失败时，Layer 2 可以留作诊断，但不得被称为 Continuous Harness 正式验收。

## 测试与放量顺序

1. 单元测试：runtime identity、dirty/import-root 门禁、attempt append/read、execution
   contract、artifact receipt、C10 精确 ID 轮询。
2. Cockpit 协议 smoke：`/models` 与 `/responses`，只发送最小提示。
3. 隔离 Workbench health smoke：确认 mode/backend/model/provider/revision 全部精确。
4. 四题 canary：一题普通 research、B6、C8、C10；C10 含三轮。
5. canary 的所有 turn 通过 Layer 1 后，才允许跑完整 28 题。

正式执行可信度通过标准：

```text
preflight.acceptance_eligible == true
30 / 30 turn observed path == expected path
28 / 28 continuous_episode turn receipt 绑定正确
0 个错误 legacy/continuous 归因
C10 三轮同一 conversation，精确 Run/message ID 均不同
0 个 dirty、revision、import root、backend、model 或 runtime instance 漂移
```

完整 28 题是 Cockpit/`gpt-5.6-sol` 的新基线。旧 GLM 基线只能保留历史参考，不能把
两者差异归因于 Harness 单一变量。

## 错误处理与安全边界

- Cockpit 不可达、模型列表不符或 `/responses` smoke 失败：停止，不跑题。
- 发现其它 provider key 或 provider chain 不唯一：停止，避免静默 fallback。
- 任一 turn 的 runtime instance/revision 与 preflight 不同：整次 run 不具备正式验收资格。
- observed execution path 缺失：按失败处理，禁止从 artifact 名称或 answer 文本猜测。
- artifact receipt 不匹配：按旧产物/错 attempt 处理，即使答案存在也不计 Continuous。
- 所有日志与产物继续通过现有 secret redaction；新测试增加 Cockpit key 不落盘断言。

## 后续批次

本批通过后，下一批按以下顺序推进：

1. 工具生命周期：`requested -> authorized|denied -> started ->
   completed|failed|timed_out|cancelled`；
2. 慢 HTTP、子进程、sub-research 的真实取消与硬崩溃注入；
3. transactional outbox 与终态原子性；
4. 结构化 ContextFrame 和 10–15 轮上下文保留测试；
5. 写工具上线前的权限控制；
6. 持久研究 Fork 与决策后验闭环。
