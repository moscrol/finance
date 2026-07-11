# Chat-first Skill Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 Workbench 从“一次 Run 一个报告页”升级为可恢复的多轮聊天，并以“自动调用 + 手动指定”的方式把 Daily Review、Daily Agent 接成首批结构化 Skill。

**Architecture:** Conversation 负责长期消息，Run 负责每轮可观测执行；混合路由器选择 allowlist Skill，Skill 先产出确定性结构化模块，LLM 再在证据边界内流式综合表达。沿用 PR #181 的 StructuredReport 和 SSE 存储并向通用 envelope 演进，不再建立 HTML 主输出路径。

**Tech Stack:** Python 3、FastAPI、JSON/JSONL 用户态存储、现有 Ask/RAG 管线、OpenAI-compatible LLM provider、SSE、React、TypeScript、Vite、Vitest、Playwright、pytest。

---

## 执行前提

PR #181（`feat/structured-streaming-workbench`）是前置依赖，已实现结构化模块、模块级 SSE 和 React 原生报告。执行 Agent 必须先判断它是否已经合并：

```bash
git status --short
git branch --show-current
git fetch origin main feat/structured-streaming-workbench
gh pr view 181 --json state,mergeStateStatus,headRefOid,baseRefOid,url
```

- 若 #181 已合并：从最新 `origin/main` 新建 `feat/chat-first-skill-workbench`。
- 若 #181 未合并：从 `origin/feat/structured-streaming-workbench` 新建同名分支，并在新 PR 中声明依赖 #181。
- 使用独立 worktree，禁止在当前脏工作区直接开发。
- 禁止提交 `intelligence/users/`、`.env*`、数据库、日报私有产物、虚拟环境和构建缓存。
- 不合并 `main`，不强推。

## 执行总表

| 顺序 | 优先级 | 任务 | 依赖 | 主要交付 | 完成门槛 |
|---|---|---|---|---|---|
| 0 | P0 | 基线与兼容测试 | PR #181 | clean branch、基线报告 | Python/前端基线全绿 |
| 1 | P0 | ConversationStore | 0 | 会话与消息 canonical 存储 | 刷新/重启可恢复，归档不丢数据 |
| 2 | P0 | Conversation API | 1 | 会话 CRUD、消息触发 Run | API 与路径安全测试通过 |
| 3 | P0 | 通用 SSE envelope | 1 | 有序、可重放的消息/Skill/报告事件 | 重连不重复、不漏块 |
| 4 | P0 | 产品 Skill 契约与混合路由 | 2、3 | registry、router、权限与降级 | 手动必选，自动只选 allowlist |
| 5 | P0 | Daily Review / Daily Agent Skill | 4 | 两个原生 Skill executor | 不依赖 HTML，数字与 canonical 一致 |
| 6 | P0 | 每轮重检索的对话编排 | 2、4、5 | TurnOrchestrator、摘要上下文 | 连续三轮均重检索且可追溯 |
| 7 | P0 | Chat-first React UI | 2、3、6 | 会话栏、消息流、Skill 选择器 | 桌面/平板/手机完整可用 |
| 8 | P0 | 真实集成与回归测试 | 1-7 | unmocked API 测试、真实产物 E2E | key/no-key、超时、重连、取消全覆盖 |
| 9 | P1 | 私有站点运行说明 | 8 | 启动说明与公开部署安全差距 | 不误称为公开多用户站点 |

## Task 0: 固定基线和兼容边界

**Files:**
- Read: `docs/superpowers/specs/2026-07-11-chat-first-skill-workbench-design.md`
- Read: `intelligence/api/structured_reports.py`
- Read: `intelligence/services/run_store.py`
- Read: `intelligence/webapp/src/types.ts`
- Test: `intelligence/tests/test_structured_reports.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: 创建 clean worktree**

#181 已合并时：

```bash
git worktree add -b feat/chat-first-skill-workbench ../finance-workspace-chat-first origin/main
```

#181 未合并时：

```bash
git worktree add -b feat/chat-first-skill-workbench ../finance-workspace-chat-first origin/feat/structured-streaming-workbench
```

Expected: 新 worktree 的 `git status --short` 为空。

- [ ] **Step 2: 跑后端基线测试**

```bash
python3 -m pytest intelligence/tests/test_structured_reports.py intelligence/tests/test_workbench_api.py -q
```

Expected: 全部通过；不得通过删除断言掩盖已有失败。

- [ ] **Step 3: 跑前端基线测试**

```bash
cd intelligence/webapp
pnpm install --frozen-lockfile
pnpm lint
pnpm exec tsc -b
pnpm test -- --run
pnpm build
```

Expected: lint、typecheck、Vitest 和 build 全部成功。

## Task 1: ConversationStore

**Files:**
- Create: `intelligence/services/conversation_store.py`
- Create: `intelligence/tests/test_conversation_store.py`
- Modify: `.gitignore`
- Modify: `docs/learning/ledger-map.md`

- [ ] **Step 1: 先写失败测试**

先固定 store 的最小公共接口，并用真实写盘断言覆盖核心行为：

```python
import pytest

from intelligence.services.conversation_store import ConversationStore


def test_create_append_reload_and_archive_conversation(tmp_path):
    store = ConversationStore(user_id="demo", root=tmp_path / "conversations")
    conversation = store.create_conversation(title="今日复盘")
    message = store.append_message(
        conversation.conversation_id,
        role="user",
        content="今天市场怎么样？",
        status="completed",
    )

    assert store.load_conversation(conversation.conversation_id).title == "今日复盘"
    assert [item.message_id for item in store.load_messages(conversation.conversation_id)] == [
        message.message_id
    ]

    archived = store.archive_conversation(conversation.conversation_id)
    assert archived.status == "archived"
    assert len(store.load_messages(conversation.conversation_id)) == 1


def test_conversation_id_rejects_path_traversal(tmp_path):
    store = ConversationStore(user_id="demo", root=tmp_path / "conversations")
    with pytest.raises(ValueError, match="conversation_id"):
        store.load_conversation("../other-user")
```

同文件再覆盖消息 append-only 顺序、可见字段写前脱敏，以及归档后消息仍可读取。

Run: `python3 -m pytest intelligence/tests/test_conversation_store.py -q`

Expected: FAIL，因为模块尚不存在。

- [ ] **Step 2: 实现数据类型和唯一写入者**

```python
@dataclass
class Conversation:
    conversation_id: str
    user_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    summary: str = ""
    last_run_id: str | None = None

@dataclass
class Message:
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    status: str
    run_id: str | None = None
    selected_skill_ids: list[str] = field(default_factory=list)
    invoked_skill_ids: list[str] = field(default_factory=list)
    citations: list[dict[str, object]] = field(default_factory=list)
    degrades: list[str] = field(default_factory=list)
```

`ConversationStore` 提供 `create_conversation()`、`list_conversations()`、`load_conversation()`、`append_message()`、`load_messages()`、`rename_conversation()`、`archive_conversation()`、`update_summary()`。元数据使用临时文件 + 原子替换，消息 JSONL 只追加；所有可见字符串复用 `run_store.redact()`。

- [ ] **Step 3: 登记 canonical 路径**

在 `.gitignore` 忽略 `intelligence/users/*/conversations/`；在 `docs/learning/ledger-map.md` 登记唯一写入者为 `ConversationStore`。

- [ ] **Step 4: 测试并提交**

```bash
python3 -m pytest intelligence/tests/test_conversation_store.py -q
git add intelligence/services/conversation_store.py intelligence/tests/test_conversation_store.py .gitignore docs/learning/ledger-map.md
git commit -m "feat(workbench): persist conversations and messages"
```

## Task 2: Conversation API

**Files:**
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `intelligence/webapp/src/types.ts`
- Modify: `intelligence/webapp/src/api.ts`

- [ ] **Step 1: 为 API 写失败测试**

覆盖创建、列表、重命名、归档、加载消息、向会话发送消息；所有 ID 拒绝路径穿越。

```text
POST  /api/conversations
GET   /api/conversations
GET   /api/conversations/{conversation_id}
PATCH /api/conversations/{conversation_id}
POST  /api/conversations/{conversation_id}/archive
GET   /api/conversations/{conversation_id}/messages
POST  /api/conversations/{conversation_id}/messages
GET   /api/skills
POST  /api/runs/{run_id}/cancel
```

发送消息 body：

```json
{
  "content": "今天市场怎么样？",
  "skill_mode": "hybrid",
  "selected_skill_ids": ["daily-review"]
}
```

返回 `202`，包含 `conversation_id`、`user_message_id`、`assistant_message_id`、`run_id`。

`GET /api/skills` 只返回 registry 中对产品可见的 Skill 描述；cancel 接口设置协作式取消信号，重复取消必须幂等。

- [ ] **Step 2: 实现 API 并兼容旧 Run**

新消息创建 Run 时设置 `session_id=conversation_id`。保留 `POST /api/runs`；PR #181 的既有 API 测试必须继续通过。

- [ ] **Step 3: 添加 TypeScript 类型和 client**

定义 `Conversation`、`ChatMessage`、`CreateMessageRequest`、`CreateMessageResponse`，API URL 只能由 `api.ts` 生成。

- [ ] **Step 4: 测试并提交**

```bash
python3 -m pytest intelligence/tests/test_workbench_api.py -q
cd intelligence/webapp && pnpm exec tsc -b
git add intelligence/api/app.py intelligence/tests/test_workbench_api.py intelligence/webapp/src/types.ts intelligence/webapp/src/api.ts
git commit -m "feat(workbench): expose conversation APIs"
```

## Task 3: 通用、有序、可恢复的 SSE 协议

**Files:**
- Create: `intelligence/api/stream_events.py`
- Modify: `intelligence/services/run_store.py`
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_run_store.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Create: `intelligence/webapp/src/streamEvents.ts`

- [ ] **Step 1: 写顺序、去重和 cursor 失败测试**

验证每个 Run 的 `seq` 从 1 单调递增、`event_id` 唯一、传入 cursor 后只重放更大的 `seq`，终态后仍可完整重放。

- [ ] **Step 2: 实现 StreamEnvelope**

```python
@dataclass(frozen=True)
class StreamEnvelope:
    schema_version: int
    event_id: str
    event_type: str
    run_id: str
    conversation_id: str | None
    message_id: str | None
    seq: int
    created_at: str
    payload: dict[str, Any]
```

由 `RunStore.append_stream_event()` 分配 `seq`。API 支持 `?after=<seq>`，前端按 `event_id` 去重。

- [ ] **Step 3: 保留 PR #181 兼容映射**

新事件使用 `report.start/report.module/report.complete` 等点号命名。SSE 输出层在兼容期映射旧的 `report_start/report_module/report_complete/report_error`，并以测试证明旧监听器仍可收到报告。

- [ ] **Step 4: 测试并提交**

```bash
python3 -m pytest intelligence/tests/test_run_store.py intelligence/tests/test_workbench_api.py -q
cd intelligence/webapp && pnpm test -- --run && pnpm exec tsc -b
git add intelligence/api/stream_events.py intelligence/services/run_store.py intelligence/api/app.py intelligence/tests/test_run_store.py intelligence/tests/test_workbench_api.py intelligence/webapp/src/types.ts intelligence/webapp/src/streamEvents.ts
git commit -m "feat(workbench): add replayable message stream protocol"
```

## Task 4: 产品 Skill 契约与混合路由

**Files:**
- Create: `intelligence/workbench_skills/__init__.py`
- Create: `intelligence/workbench_skills/contracts.py`
- Create: `intelligence/workbench_skills/registry.py`
- Create: `intelligence/workbench_skills/router.py`
- Create: `intelligence/tests/test_workbench_skill_router.py`

- [ ] **Step 1: 写契约和路由失败测试**

覆盖：未知 Skill 被拒绝、手动 Skill 必须保留、自动结果只能来自 allowlist、重复去重、总数最多 3 个、LLM 无 key 时规则路由可用、选择理由可展示。

- [ ] **Step 2: 实现 Skill 类型**

```python
@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    version: str
    triggers: tuple[str, ...]
    input_schema: dict[str, Any]
    permissions: tuple[str, ...]
    timeout_seconds: int

@dataclass
class SkillOutput:
    skill_id: str
    modules: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    warnings: list[str]
    as_of: str | None
    raw_result_ref: str | None
```

executor 使用 `Protocol`，统一 `execute(context) -> SkillOutput`。首批 Skill 权限仅为 `local_read`。

- [ ] **Step 3: 实现混合路由**

顺序固定为：校验手动集合 -> 规则候选 -> 可选 LLM 结构化选择 -> 合并去重 -> 上限裁剪。LLM 返回必须 JSON parse 并再次经过 registry 校验。结果包含 `selection_source: manual | rule | llm` 和人话理由。

- [ ] **Step 4: 测试并提交**

```bash
python3 -m pytest intelligence/tests/test_workbench_skill_router.py -q
git add intelligence/workbench_skills intelligence/tests/test_workbench_skill_router.py
git commit -m "feat(workbench): define product skill registry and hybrid router"
```

## Task 5: Daily Review 与 Daily Agent Skill

**Files:**
- Create: `intelligence/workbench_skills/daily_review.py`
- Create: `intelligence/workbench_skills/daily_agent.py`
- Modify: `intelligence/workbench_skills/registry.py`
- Modify: `intelligence/api/structured_reports.py`
- Create: `intelligence/tests/test_workbench_daily_skills.py`

- [ ] **Step 1: 使用真实最小 fixture 写失败测试**

逐字段比较 canonical 日期、指标值、候选题材、证据状态、warning 和 provenance，不能只判断页面“能渲染”。

- [ ] **Step 2: 实现 Daily Review executor**

复用 `daily_projection_modules()` / `project_daily_review_markdown()`，不复制 Markdown 解析规则。将脱敏原始结果保存为 run artifact 并设置 `raw_result_ref`。

- [ ] **Step 3: 实现 Daily Agent executor**

读取 registry 允许的最新 `*-daily-agent.json`，复用 `project_daily_agent()` 转成 `summary/metrics/list/actions/evidence` 模块。缺 JSON 时返回 degraded warning，不从 HTML 反推事实。

- [ ] **Step 4: 测试并提交**

```bash
python3 -m pytest intelligence/tests/test_workbench_daily_skills.py intelligence/tests/test_structured_reports.py -q
git add intelligence/workbench_skills intelligence/api/structured_reports.py intelligence/tests/test_workbench_daily_skills.py
git commit -m "feat(workbench): add native daily report skills"
```

## Task 6: 每轮重检索的 TurnOrchestrator

**Files:**
- Create: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/llm_refine.py`
- Modify: `intelligence/api/app.py`
- Create: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 写三轮对话失败测试**

用 spy 证明 `answer_query()` 每轮调用一次，而不是复用首轮 `AskConversation.messages`；第二、三轮 prompt 包含会话摘要和最近消息；每轮 Run 的 `session_id` 相同、`parent_run_id` 指向上一轮。

- [ ] **Step 2: 实现上下文窗口**

采用最近 6 条消息原文 + 更早消息摘要。摘要为空时先用确定性截断，LLM 摘要仅是可选增强。摘要不能替代当前轮检索证据。

- [ ] **Step 3: 实现编排顺序**

```text
append user message
-> create Run / assistant placeholder
-> route skills
-> execute selected skills（独立 Skill 可并行）
-> run current-turn Ask/RAG retrieval
-> synthesize from current evidence + skill outputs + conversation context
-> append assistant message
-> complete Run and stream
```

Skill 失败按模块降级，不得让整轮丢失。普通 ask 成功但 LLM 无 key 时，仍保存结构化模板回答。

取消采用协作式信号：orchestrator 在路由后、每个 Skill 前后、检索后和每个 LLM delta 之间检查取消状态；命中后停止后续工作，把 Run 置为 `cancelled`，并保留已经落盘的模块和 trace。不要依赖 `Future.cancel()` 中止已经运行的线程。

- [ ] **Step 4: 增加真实文本增量接口**

在 `llm_refine.py` 增加 OpenAI-compatible streaming reader，将 provider delta 转成 `text.delta`。不支持流式的 provider 退回单个完整 delta；不要把完整文本人工切碎冒充真实流式。

- [ ] **Step 5: 测试并提交**

```bash
python3 -m pytest intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py -q
git add intelligence/services/conversation_orchestrator.py intelligence/services/ask.py intelligence/services/llm_refine.py intelligence/api/app.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py
git commit -m "feat(workbench): orchestrate fresh retrieval for every chat turn"
```

## Task 7: Chat-first React UI

**Files:**
- Create: `intelligence/webapp/src/components/ConversationList.tsx`
- Create: `intelligence/webapp/src/components/MessageThread.tsx`
- Create: `intelligence/webapp/src/components/MessageBubble.tsx`
- Create: `intelligence/webapp/src/components/SkillPicker.tsx`
- Create: `intelligence/webapp/src/components/SkillInvocation.tsx`
- Modify: `intelligence/webapp/src/components/Composer.tsx`
- Modify: `intelligence/webapp/src/components/RunView.tsx`
- Modify: `intelligence/webapp/src/App.tsx`
- Modify: `intelligence/webapp/src/styles.css`
- Modify: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1: 写组件失败测试**

覆盖会话恢复、切换、手动选择/取消 Skill、自动调用标签、增量更新、重连去重、停止、重新生成、无 key 标识和移动端抽屉。重新生成创建新 Run，并以原 Run 为 `parent_run_id`，不覆盖旧回答。

- [ ] **Step 2: 把 RunView 降为消息内详情**

主区域改为连续 `MessageThread`。Run 的运行轨迹、产物和检查器数据保留为 assistant message 内的折叠详情；追问不得跳到一张新的单 Run 页面。

- [ ] **Step 3: 实现 SkillPicker**

输入框默认 `hybrid`；用户可从菜单选择 Skill，已选项显示为可删除 chip。提交后分别标记“手动指定”和“自动调用”，不展示内部 Python 函数名。

- [ ] **Step 4: 适配通用流事件**

`text.delta` 追加当前 narrative 模块；`report.module` 按 `module_id` upsert；`skill.start/result` 更新调用状态；`message.complete/error` 结束 loading。每次更新同时校验 `conversation_id + message_id + run_id`，防止旧请求覆盖新会话。

- [ ] **Step 5: 响应式与可访问性**

桌面三栏；1024px 检查器抽屉；390px 会话栏和检查器均为抽屉。按钮使用 Lucide 图标和 tooltip，控件有 accessible name，键盘可选择 Skill 和发送消息，正文与输入框不重叠。

- [ ] **Step 6: 测试并提交**

```bash
cd intelligence/webapp
pnpm lint
pnpm exec tsc -b
pnpm test -- --run
pnpm build
git add src ../api/static
git commit -m "feat(workbench): make conversations the primary interface"
```

## Task 8: 真实集成、E2E 与回归门

**Files:**
- Create: `intelligence/tests/test_workbench_conversation_integration.py`
- Modify: `intelligence/webapp/e2e/workbench.spec.ts`
- Modify: `.github/workflows/workbench-check.yml`
- Modify: `docs/superpowers/plans/2026-07-11-chat-first-skill-workbench.md`

- [x] **Step 1: 添加 unmocked 后端/前端集成测试**

至少一个测试启动真实 FastAPI，使用临时用户目录和最小 canonical 日报 fixture，经浏览器创建会话、发送消息、接收 SSE、刷新并恢复消息。仅 LLM 网络调用可 mock，ConversationStore、RunStore、router 和 Daily Skill 不得 mock。

- [x] **Step 2: 覆盖关键失败路径**

```text
1. hybrid 自动选择 Daily Review
2. 手动指定 Daily Agent
3. 同一会话连续三轮
4. 无 LLM key 的诚实降级
5. 一个 Skill 超时、其他模块继续
6. SSE 中断后从 cursor 恢复
7. 用户停止后状态为 cancelled
8. 刷新后恢复会话、消息、Skill 与 Run
```

- [x] **Step 3: 三视口视觉验证**

Playwright 使用 `1440x900`、`1024x768`、`390x844`。断言无横向溢出、输入框不遮挡消息、表格在移动端可读、两个抽屉均可关闭。

- [x] **Step 4: 全量质量门**

```bash
python3 -m pytest intelligence/tests -q
cd intelligence/webapp
pnpm lint
pnpm exec tsc -b
pnpm test -- --run
pnpm build
pnpm exec playwright test
git status --short
```

Expected: 全部通过；状态中不含用户会话、密钥、数据库、日报私有产物、`node_modules` 或虚拟环境。

- [x] **Step 5: 提交测试和真实验收数字**

```bash
git add intelligence/tests/test_workbench_conversation_integration.py intelligence/webapp/e2e/workbench.spec.ts .github/workflows/workbench-check.yml docs/superpowers/plans/2026-07-11-chat-first-skill-workbench.md
git commit -m "test(workbench): cover persistent skill conversations"
```

在本文件“执行结果”追加真实 commit、测试数字和已知限制。

## Task 9: 本地私有站点运行说明

**Files:**
- Modify: `README.md`
- Create: `docs/workbench/local-site.md`

- [ ] **Step 1: 写本地启动说明**

记录 Python 环境、前端构建、LLM 环境变量名、FastAPI 启动命令、数据目录和健康检查。只写变量名，不写 key 值。

- [ ] **Step 2: 明确公开部署前的安全门**

列出认证身份、服务端 user 推导、用户隔离、限流/费用、队列/取消/超时、服务端密钥、审计和脱敏。完成这些项目之前，页面只能描述为本地/私有站点。

- [ ] **Step 3: 文档检查并提交**

```bash
rg -n "API_KEY=|TOKEN=|SECRET=" README.md docs/workbench/local-site.md
git add README.md docs/workbench/local-site.md
git commit -m "docs(workbench): document private chat site operation"
```

Expected: 搜索结果不含真实凭据赋值。

## 最终验收清单

- [ ] 对话是首屏和主要导航对象，不是 Run 卡片列表。
- [ ] 刷新和服务重启后仍能恢复会话与消息。
- [ ] 每轮重新检索，历史摘要只提供语境，不替代最新证据。
- [ ] 自动调用和手动指定 Skill 同时可用，实际调用列表对用户透明。
- [ ] Daily Review / Daily Agent 原生输出文字、指标、表格、证据和动作。
- [ ] 表格数值与 canonical fixture 逐字段一致，LLM 不修改事实字段。
- [ ] LLM provider/model 和是否真实启用在 UI 可见。
- [ ] 无 key、超时、断线、取消均诚实降级并保留已有内容。
- [ ] 旧 Run API、Artifact Library、原生日报和 PR #181 报告协议保持兼容。
- [ ] Python、lint、typecheck、Vitest、build、三视口 Playwright 全绿。
- [ ] PR 不包含用户数据、密钥、数据库、日报私有产物或缓存。
- [ ] 不合并 `main`，由用户确认后再合并。

## 执行 Agent 首条指令（可直接转交）

```text
请执行 docs/superpowers/plans/2026-07-11-chat-first-skill-workbench.md。
先读对应 design 文档和 AGENTS.md，检查 PR #181 是否已合并，再从正确基线创建独立 worktree/feature branch。
严格按 Task 0 -> Task 9 顺序推进，使用 TDD，小步提交；不要直接迁移 HTML，不要复用首轮证据冒充多轮检索，不要提交用户数据或密钥，不要合并 main。
每完成一个 Task，回报：改动文件、测试命令/结果、commit、残余风险；遇到设计冲突先停下说明，不自行扩大范围。
```

## 执行结果

此节由执行 Agent 在实施过程中逐项追加真实结果。

### Task 8

- Commit：`test(workbench): cover persistent skill conversations`（本任务提交）
- Python：`950 passed`；另有 1 条既有 Starlette/httpx 弃用警告。
- Frontend：ESLint、TypeScript、production build 通过；Vitest `25 passed`。
- Playwright：desktop `1440x900`、tablet `1024x768`、mobile `390x844` 共
  `6 passed`。真实 FastAPI 使用 synthetic canonical fixture 与临时用户目录，
  ConversationStore、RunStore、router、Daily Skill 均未 mock。
- 覆盖：三轮 fresh turn、自动/手动 Skill、无 key 降级、Skill 超时隔离、SSE
  cursor 恢复、取消、刷新恢复、重新生成 parent link、表格与响应式抽屉。
- 已知限制：真实 provider 网络流需配置合法服务端 LLM key 后单独验收；当前
  E2E 刻意固定在无 key 的确定性模板路径，且不使用任何用户日报或会话数据。
