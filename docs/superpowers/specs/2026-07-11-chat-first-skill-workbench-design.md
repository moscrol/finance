# Chat-first Skill Workbench 设计

- 日期：2026-07-11
- 状态：已批准
- 前置基线：PR #178 原生日报；PR #181 结构化模块流式输出
- 产品目标：以持续对话为主入口，把现有总舱能力迁移为可组合 Skill，而不是直接移植 HTML

## 1. 已确认的产品定义

Workbench 的主产品不是“产物浏览器”，而是一个可持续对话的金融研究 Agent：

1. 用户在同一会话里连续提问，历史消息、研究上下文和 Run 均可恢复。
2. 系统根据问题自动选择 Skill，用户也能在输入框手动指定 Skill。
3. 每轮明确显示实际调用的 Skill、数据截止日、证据来源和降级状态。
4. 总舱里的高频能力逐个迁移成 Skill；Skill 在当前消息内流式产出文字、指标、表格、证据和后续动作。
5. 旧 HTML 仅作为原始报告和过渡兼容，不作为最终大众产品界面。
6. UI 使用统一的通俗表达和视觉协议，专业术语可展开解释。

## 2. 技术方案比较

### 方案 A：Prompt 模板即 Skill

只为每种能力编写提示词，让 LLM 自己输出 Markdown。开发最快，但数字、表格结构和引用容易漂移，也难以单测。它适合原型，不作为金融产品主架构。

### 方案 B：继续挂载 HTML

每个功能仍生成独立 HTML，聊天页只展示链接或 iframe。它最大化复用旧页面，但对话被打断、移动端和视觉风格割裂，也无法进行模块级流式输出。旧 HTML 仅保留为迁移期“原始报告”。

### 方案 C：结构化 Skill + LLM 综合表达（采用）

Skill executor 先从 DuckDB、RAG、知识图谱、台账或 canonical 文件取得结构化事实，再由 LLM 在事实边界内组织自然语言。前端依据统一协议渲染文字、表格、指标、证据和动作。

优势是数字可校验、结构可测试、UI 一致、Skill 可组合，且保留 LLM 的对话能力。代价是需要先定义 Skill 契约、流协议和适配器。

## 3. 总体架构

```text
React Workbench
  -> Conversation API
  -> Turn Orchestrator
       -> Hybrid Skill Router
            -> 用户手动指定 Skill（强制执行）
            -> 规则候选召回（稳定兜底）
            -> LLM 结构化选择（自动补充）
       -> Skill Executors（确定性数据与证据）
       -> Ask/RAG Pipeline（每轮重新检索）
       -> LLM Synthesis（只在证据边界内表达）
  -> RunStore + ConversationStore
  -> SSE Stream Envelope
  -> React 原生消息块
```

核心边界：

- Conversation 管长期交互；Run 管一轮可观测执行；Message 管用户可见内容。
- 一个 Conversation 有多条 Message；每条用户消息触发一个 Run；Run 产出一条 assistant Message。
- 现有 `Run.session_id` 在兼容期保存 `conversation_id`，避免同时维护两套会话标识。
- 每轮重新运行检索。金融数据和问题主题都可能变化，首轮证据只能作为历史上下文，不能替代本轮检索。

## 4. Conversation 数据契约

用户态 canonical 路径：

```text
intelligence/users/<user>/conversations/<conversation_id>/
  conversation.json
  messages.jsonl
```

`conversation.json` 保存：

- `conversation_id`、`user_id`、`title`
- `status: active | archived`
- `created_at`、`updated_at`
- `summary`：较早消息的压缩摘要
- `last_run_id`

`messages.jsonl` 采用 append-only 写入：

- `message_id`、`conversation_id`、`role`
- `content`、`created_at`、`status`
- `run_id`
- `selected_skill_ids`、`invoked_skill_ids`
- `citations`、`degrades`

删除会话首版采用归档，不物理删除研究记录。标题先由首问确定性截断生成，LLM 标题仅作为后续增强。

## 5. Skill 契约与路由

每个产品 Skill 必须声明：

- `skill_id`、`name`、`description`、`version`
- `triggers` 和输入 JSON Schema
- `permissions`：只读、联网、写台账等能力边界
- `timeout_seconds` 和成本级别
- executor：真实查询或工作流入口
- 输出 `modules`、`citations`、`warnings`、`as_of`、`raw_result_ref`
- 无数据、超时、LLM 未启用时的降级行为
- 单元测试和至少一个真实产物集成测试

路由采用混合模式：

1. 用户手动选择的 Skill 是强制集合。
2. 规则路由根据 `task_type`、实体、日期和关键词召回候选。
3. LLM 只能从 allowlist 候选中做结构化选择，不能发明 Skill 名。
4. 自动路由可在手动集合之外补充 Skill，但每轮默认总数不超过 3 个。
5. 路由失败时退回普通 `ask`，并在 UI 明示“未调用专项 Skill”。

现有 `intelligence/services/skill_tools.py` 是 Agent 内部只读工具桥，不直接承担产品 Skill 注册表。新的产品契约可以包装它，但不能破坏它的安全 allowlist。

## 6. 统一流式协议

PR #181 已有 `report_start/report_module/report_complete`，本阶段在其上演进，不新建第二套平行报告协议。

统一 SSE envelope：

```json
{
  "schema_version": 1,
  "event_id": "evt_run_20260711_001_0007",
  "event_type": "skill.result",
  "run_id": "run_20260711_001",
  "conversation_id": "conv_20260711_001",
  "message_id": "msg_20260711_002",
  "seq": 7,
  "created_at": "2026-07-11T10:00:00+08:00",
  "payload": {}
}
```

首期事件：

- `message.start`
- `trace.step`
- `skill.start`
- `skill.result`
- `report.start`
- `report.module`
- `text.delta`
- `citation.ready`
- `message.complete`
- `message.error`

`seq` 在单个 Run 内严格递增，浏览器按 `event_id` 去重。断线重连通过 `Last-Event-ID` 或 query cursor 只补发缺失事件。PR #181 的旧事件名保留一轮兼容适配。

## 7. 原生消息块

首期支持：

- `narrative`：LLM 流式文字
- `summary`：一句话结论和摘要列表
- `metrics`：稳定尺寸指标组
- `table`：确定性列和行
- `evidence`：引用、证据层、事实/推断标记
- `warning`：数据缺口、过期、降级
- `actions`：后续验证和可点击追问
- `artifact`：原始报告或可下载产物

表格中的数字和事实字段由 Skill executor 锁定，LLM 只能生成解释文本，不能改写原始值。原始结果另存 artifact，供检查器和测试核对。

## 8. 首批 Skill

### Daily Review

- canonical 输入：最新 `*-daily-review.md`
- 复用：`project_daily_review_markdown()` 和 PR #181 的 `daily_projection_modules()`
- 输出：核心摘要、指标、市场阶段、题材与验证动作

### Daily Agent

- canonical 输入：最新 `*-daily-agent.json`
- 复用：`project_daily_agent()`
- 输出：候选题材、证据状态、研究队列和下一步动作

这两个 Skill 已有原生 projection，最适合作为契约样板。题材深挖、个股研究、资金流后续按同一契约接入。

## 9. UI 信息架构

- 左侧：会话列表、搜索、新建、归档。
- 中间：连续消息流；Run 步骤是消息内可折叠状态，不再让“一轮 Run”占满整个页面。
- 输入区：自然语言输入、Skill 选择器、已选 Skill chip、停止与重新生成。
- 回答内：显示本轮“自动选择/手动指定”的 Skill。
- 右侧检查器：来源、数据时点、Skill 原始结果、记忆、回检和运行详情。
- 移动端：会话侧栏和检查器使用抽屉，主消息流保持单列。

## 10. 失败与降级

- 无 LLM key：Skill 结构化模块照常输出，叙事区显示“模板表达”，不得伪装成 LLM 回答。
- Skill 超时：其他 Skill 和普通检索继续；超时 Skill 显示独立 warning。
- 路由无结果：退回普通 ask。
- SSE 断线：重连并按 cursor 补发，不重复消息块。
- 用户停止：Run 进入 `cancelled`，保留已完成模块与 trace。
- canonical 输入缺失：模块标记 `degraded`，不使用旧 HTML 推断事实。

## 11. 安全与站点边界

本阶段仍是本地/私有单用户站点。公开部署不在本计划内，因为当前 API 接受客户端 `user`，不能构成真实身份边界。

后续公开站点必须先增加：服务端认证身份、用户目录隔离、限流与成本配额、任务队列、取消/超时、日志脱敏和服务端密钥管理。

## 12. 完成定义

1. 刷新页面后可恢复会话和消息。
2. 同一会话连续三轮提问，每轮均重新检索并保留父子 Run 可追溯性。
3. 用户可手动选择 Daily Review；系统也可根据“今天市场怎么样”自动选择它。
4. Daily Review 与 Daily Agent 在聊天消息中原生流式展示，不依赖 HTML。
5. UI 明示本轮实际 Skill、LLM provider/model、数据日期和降级。
6. 无 key、Skill 超时、SSE 重连和取消均有自动化测试。
7. 旧 Run API 和 PR #181 流式报告在兼容期不回归。
