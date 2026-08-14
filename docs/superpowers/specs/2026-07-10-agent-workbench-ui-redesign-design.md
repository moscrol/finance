# Agent Workbench UI 重构与产物渐进迁移设计

- 日期：2026-07-10
- 状态：已批准，待实施计划
- 分支：`codex/feat/workbench-ui-redesign`
- 关联设计：`docs/superpowers/specs/2026-07-08-agent-workbench-productization-design.md`

## 1. 背景与目标

当前金融 Agent 已经不是单一问答函数，而是一套完整研究系统：问题路由、研究编排、多源检索、证据分层、题材生命周期、每日复盘、预测回检、双盲质检、用户纠偏、经验卡和知识库回补都已有实现。现有 Workbench 仅展示历史任务、回答、运行步骤、产物和追问，绝大多数能力仍然藏在 CLI、JSON/JSONL、Markdown 和独立 HTML 页面里。

本设计的目标是：

1. 用一个统一研究入口承载自由问答、每日复盘、题材深挖和个股研究。
2. 让所有面向 human reading 的产物都能从 Workbench 被发现、阅读和追溯。
3. 保留现有 HTML 总舱及各类可视化页，通过注册和嵌入先接入，再按使用频率逐步原生化。
4. 把 Agent 的证据、记忆、反证、降级和回检能力变成持续可见的产品对象。
5. 不改变 canonical 数据源和唯一写入者，不为了 UI 重写已稳定的数据管线。

产品定位仍是研究工作台，不是交易下单工具，也不输出个性化买卖和仓位指令。

## 2. 核心设计原则

### 2.1 统一研究入口

自由研究问答是首屏主动作。每日复盘、题材深挖和个股研究是三种快捷工作流，共用同一套 Run、Trace、Artifact 和追问协议，不建立三套平行产品。

### 2.2 Human-readable Coverage Contract

任何由系统生成、预期供人阅读的 HTML、Markdown 或结构化报告，都必须满足：

```text
human-readable output
  -> Artifact Registry 注册
  -> Workbench 可搜索/可打开
  -> 可回到 canonical 来源和生成任务
```

Workbench 是统一阅读层，不是新的事实源。

### 2.3 Canonical 数据与视图分离

- JSON/JSONL、Markdown、DuckDB 和台账文件继续作为 canonical 数据或正文来源。
- HTML 是渲染物；React 页面也是渲染物。
- UI 不把用户操作静默写回非 canonical 文件。
- 台账写入仍服从 `docs/learning/ledger-map.md` 的唯一写入者约束。

这属于典型的“数据模型与视图分离”。同一个 canonical 数据可以有 HTML、Markdown、React 三种视图，而不会产生三份相互漂移的事实。

### 2.4 渐进迁移

先让旧产物在新壳层里可发现、可阅读，再迁移高频页面；只有在原生视图达到功能等价后，才允许停用旧 HTML 渲染器。

### 2.5 证据优先

右侧检查器默认展示数据时点、来源、证据层、检索命中、数据缺口和降级原因。记忆和回检也围绕“本次命中了什么、为什么使用、结果如何”呈现，不使用泛化成长等级替代研究解释。

## 3. MVP 范围

### 3.1 本轮实现

1. 三栏 Workbench 壳层。
2. 统一研究首页和三个工作流入口。
3. 现有研究 Run 的运行中、完成、失败和降级状态。
4. 回答正文、产物、追问和父子 Run 导航。
5. 右侧证据/运行检查器；记忆/回检先展示当前 Run 可获得的信息。
6. Artifact Registry 及产物库。
7. 现有 HTML 总舱、每日复盘、Agent 简报、题材候选、策略矩阵、双盲台账等的渐进接入。
8. 桌面、窄屏和移动端可读性验证。

### 3.2 本轮不做

- 登录、多用户权限和云端分享。
- 自动交易、下单或仓位控制。
- 实时行情推送。
- 重写全部旧 HTML。
- 重构知识库和复盘数据管线。
- 完整的记忆编辑后台、决策胜率产品和知识库运营后台。

## 4. 技术选型

### 4.1 推荐：React + Vite + FastAPI + SSE

- **React**：组件化前端框架。适合把侧栏、回答、运行步骤、产物查看器和检查器拆成可独立测试的组件。
- **Vite**：前端构建工具。开发启动快，构建后输出纯静态文件，适合由现有 FastAPI 托管。
- **FastAPI**：继续提供 Run、Artifact 和静态资源 API。
- **SSE（Server-Sent Events，服务端事件推送）**：继续把运行步骤从服务端单向推送给浏览器。Agent 运行是典型的服务端持续输出，SSE 比 WebSocket 更简单且足够。
- JavaScript 包管理使用 `pnpm`，遵循项目约定。

建议目录：

```text
intelligence/webapp/       React/Vite 源码
intelligence/api/          FastAPI 与 API
intelligence/api/static/   前端构建产物，由 FastAPI 托管
```

本地运行仍只需要启动 FastAPI；不要求用户长期运行额外 Node 服务。

### 4.2 替代方案比较

**继续扩展单文件 HTML/JavaScript**：改动最少，但状态、路由和组件数量增加后难以维护，也不利于组件测试。

**Next.js**：适合需要 SSR（服务端渲染）、线上路由和 Node 服务的产品。当前是本地单用户工具，FastAPI 已承担后端，Next.js 会增加第二套服务端运行时，因此不作为本轮首选。

**WebSocket**：适合双向协作、实时控制或高频交互。当前运行流主要是服务端向浏览器推送步骤，SSE 的复杂度更低。

## 5. 信息架构

### 5.1 左侧：任务与产物导航

- 新建研究。
- 工作流：今日复盘、题材深挖、个股研究。
- 最近任务与父子追问关系。
- 产物库入口。
- 需要 human action 的回检或数据缺口数量。

左侧不是完整功能菜单。低频诊断和知识库运营能力放入产物库或折叠入口。

### 5.2 中间：研究主区域

首页状态：

- 统一提问框。
- 三个工作流快捷入口。
- 最近需要继续研究或回检的任务。

运行状态：

- 人话化阶段名，例如“理解问题”“查询盘面”“检索证据”“生成回答”“质量复核”。
- 默认不暴露内部函数名；内部工具名放在展开详情中。
- 失败和降级必须立即可见。

完成状态：

- 一句话结论与数据截止时间。
- 回答正文。
- 证据、反证、验证信号和降级说明。
- Artifact 产物。
- 猜你想问与父子 Run 导航。

### 5.3 右侧：研究检查器

四个标签：

1. **证据**：来源、时间、L1-L4、命中原因、事实/推断、缺口。
2. **运行**：阶段、耗时、warnings、degrades、原始工具详情。
3. **记忆**：本次命中的 corrections、experience cards、用户原则及来源。
4. **回检**：关联 checkpoint、到期时间、验证字段和历史结果。

MVP 默认打开“证据”。窄屏下右侧栏变为抽屉，不挤压正文。

## 6. 组件边界

```text
AppShell
├── Sidebar
│   ├── WorkflowShortcuts
│   ├── RecentRuns
│   └── ArtifactLibraryLink
├── MainSurface
│   ├── ResearchHome
│   ├── RunView
│   │   ├── RunHeader
│   │   ├── RunProgress
│   │   ├── AnswerView
│   │   ├── ArtifactList
│   │   └── FollowupList
│   └── ArtifactViewer
├── ResearchInspector
│   ├── EvidencePanel
│   ├── TracePanel
│   ├── MemoryPanel
│   └── ReviewPanel
└── Composer
```

每个组件只依赖清晰的数据结构，不直接知道后端文件路径。文件路径到 UI 模型的转换由 API 和 Artifact Provider 完成。

## 7. Artifact Registry

### 7.1 ArtifactDescriptor

```json
{
  "artifact_id": "daily-agent:2026-07-09",
  "title": "每日 Agent 简报 - 2026-07-09",
  "category": "daily_agent",
  "format": "html",
  "date": "2026-07-09",
  "viewer": "legacy_html",
  "source_of_truth": "market_feature_store/exports/2026-07-09-daily-agent.json",
  "source_path": "复盘/daily/2026-07-09/2026-07-09-daily-agent.html",
  "related_run_id": null,
  "status": "warn",
  "schema_version": "1",
  "updated_at": "2026-07-09T23:00:00+08:00"
}
```

`viewer` 首期支持：

- `native_markdown`：Workbench 原生 Markdown 阅读器。
- `native_json`：有明确适配器的结构化视图。
- `legacy_html`：注册后的旧 HTML，通过内嵌查看器或新窗口打开。
- `download`：暂不支持预览但允许打开/下载的文件。

### 7.2 Provider

MVP 不做无边界的全仓文件扫描，而是使用明确 Provider：

- `RunArtifactProvider`：现有 `RunStore` 产物。
- `DailyArtifactProvider`：每日复盘、题材候选、Agent 简报。
- `CockpitArtifactProvider`：驾驶舱总入口与复盘组合工作台。
- `LedgerArtifactProvider`：预测复盘、双盲和胜率台账。
- `MatrixArtifactProvider`：策略矩阵。
- `BriefingArtifactProvider`：晨汇和卖方材料的已有阅读入口。

新管线后续应直接输出 ArtifactDescriptor 或 manifest，逐步减少文件名推断。

### 7.3 API

新增或扩展：

```text
GET /api/artifacts?category=&date=&status=&q=
GET /api/artifacts/{artifact_id}
GET /api/artifacts/{artifact_id}/content
GET /api/workbench/bootstrap
```

`bootstrap` 返回工作流入口、最近 Run、待回检数量、最新日常产物和数据截止时间，避免首屏发起大量零散请求。

客户端不得传入任意文件路径。服务端只返回和读取 Registry 已注册、位于允许目录内的文件，防止路径穿越。

## 8. 三条关键数据流

### 8.1 自由研究

```text
Composer
  -> POST /api/runs
  -> SSE /events 展示阶段
  -> Run 完成
  -> 拉取 run / trace / answer / followups / artifacts
  -> 右侧检查器展示 evidence / memory / review
```

### 8.2 工作流快捷入口

- 今日复盘：默认打开最新 daily artifact；用户可继续发问并建立关联 Run。
- 题材深挖：设置 `task_type=theme` 并预填问题结构，仍走统一 Run API。
- 个股研究：设置 `task_type=stock_research` 并预填问题结构，仍走统一 Run API。

快捷入口是预设，不是新的聊天系统。

### 8.3 旧 HTML 渐进接入

```text
Artifact Provider 发现旧 HTML
  -> Registry 生成 descriptor
  -> 产物库展示
  -> ArtifactViewer 内嵌或新窗口打开
  -> 右侧展示来源、日期和 canonical 数据
```

React 不解析旧 HTML 来重新构造事实。原生化时改为读取其 canonical JSON/JSONL/Markdown。

## 9. 能力到 UI 的映射

| Agent 能力 | UI 位置 | MVP 接法 |
|---|---|---|
| ask/chat/orchestrate、scenario tree、red-team、自动评分、追问 | 研究会话 | 原生 |
| daily review、daily-agent、题材候选、research queue | 今日视图 | 先接 HTML，再原生 JSON |
| 知识图谱、L1-L4、L3 补查、retrieval audit、evidence gap | 证据检查器 | 原生 |
| forecast ledger、checkpoint、verdict、双盲、effectiveness | 回检中心 | 先接台账，再原生 |
| corrections、experience cards、perspective、subconscious | 记忆检查器 | 当前 Run 命中先原生 |
| 总舱、复盘组合、策略矩阵、胜率、资金流、晨汇 | 产物库 | 零重写注册 |
| kb ingest queue、receipt、dream、adapter health | 诊断区 | 只冒出需人工处理项 |

## 10. 错误、空状态与降级

### 10.1 Run

- SSE 断线：显示“连接中断，正在恢复”，重新连接后依靠服务端步骤重放恢复。
- Run 失败：保留已完成步骤和现有产物，不清空页面。
- 数据源降级：在结论上方展示影响范围；详细原因进入运行检查器。
- 无回答产物：显示失败原因和可重试动作，不留下永久“加载中”。

### 10.2 Artifact

- 文件不存在：Registry 返回 `missing`，UI 提供来源路径和重新生成提示。
- 格式暂不支持：允许新窗口打开或下载。
- HTML 内嵌失败：提供新窗口打开，不阻塞其他页面。
- canonical 来源缺失：明确标为“仅有渲染物”，进入诊断项。

### 10.3 首页

- 没有历史 Run：工作流入口和示例问题仍然可用。
- 没有当日日常产物：显示最近可用日期，不伪造“今日已生成”。
- 没有待回检项：使用安静的空状态，不用大面积空白或营销文案填充。

## 11. 安全与可信边界

- Markdown 必须经过安全解析和 HTML 清洗。
- Artifact 内容接口只允许 Registry 白名单路径。
- 旧 HTML 仅允许项目内已知生成目录；内嵌查看器使用受限 iframe，并保留新窗口打开。
- 不在前端暴露本机绝对路径、密钥和环境变量。
- 不把 warnings、degrades 或数据截止时间隐藏在调试区域。
- 继续显示“不构成投资建议”，但不能让免责声明替代具体证据和风险提示。

## 12. 视觉与交互规范

- 这是高频研究工具，不做营销式 hero。
- 基础色使用白、浅灰和中性墨色；研究主色使用克制的森林绿，警告用琥珀，失败用红色，链接与信息状态可用蓝色。
- 不沿用总舱的大面积米色编辑风作为操作壳层，但旧 HTML 在 ArtifactViewer 内保留自己的视觉身份。
- 卡片圆角不超过 8px；普通列表优先使用行分隔，不把每个区块都做成卡片。
- 使用 Lucide 图标，不手绘 SVG；不使用 Emoji 充当功能图标。
- 正文字号 14-16px，长文限制舒适行宽。
- 输入框不能遮挡回答正文，页面底部保留足够滚动空间。
- 桌面三栏；小于 1180px 时右栏变抽屉；小于 900px 时左栏变图标导航；移动端为单列阅读。
- 工具步骤默认显示人话名称，内部函数名仅在详情中出现。

## 13. 测试与验收

### 13.1 后端

- Provider 能稳定发现已知产物并生成唯一 `artifact_id`。
- Registry 过滤、排序、latest 和 missing 状态正确。
- 内容接口拒绝未注册路径和 `../` 路径穿越。
- 现有 Run、SSE、followups 和 artifact API 回归测试继续通过。

### 13.2 前端

- 使用 Vitest + Testing Library 测试组件状态和交互。
- 使用 Playwright 验证首页、运行中、完成、失败、降级、旧 HTML 查看和追问流程。
- 验证 1440px、1024px、390px 三类视口无内容重叠、遮挡和横向溢出。
- 验证键盘可达、焦点可见、菜单有标签、状态变化不只依赖颜色。

### 13.3 MVP 验收标准

1. 用户打开一个本地 URL，可以自由提问或进入三个快捷工作流。
2. 运行过程以研究阶段展示，失败和降级清楚可见。
3. 回答、产物、追问、证据和父子 Run 在同一工作台闭环。
4. 现有总舱和主要 human-readable HTML 能从产物库找到并打开。
5. 每个产物能追溯到 canonical 来源或明确标注来源缺失。
6. 不改变现有台账唯一写入者，不破坏 CLI、每日复盘和知识库流程。
7. 窄屏和移动端可读，无输入框遮挡正文。

## 14. 渐进迁移顺序

### 阶段 1：统一壳层与注册

- React/Vite 壳层。
- 首页、Run 状态和检查器。
- Artifact Registry。
- 现有 HTML 零重写接入。

### 阶段 2：高频产物原生化

1. 研究回答和运行轨迹。
2. 每日 Agent 简报。
3. 证据检查器。
4. 当前 Run 的记忆和回检。

### 阶段 3：闭环视图原生化

- 预测台账、checkpoint、verdict、双盲和 effectiveness。
- 题材候选与 research queue。
- 数据缺口和知识库回补诊断。

### 阶段 4：收敛旧渲染器

只有当原生视图功能等价、链接稳定并通过视觉与数据核对后，才逐项停用重复 HTML 渲染器。驾驶舱总入口在迁移期继续保留。

## 15. 实施边界

- 本次只修改 Workbench 前端、Artifact Registry/API 和相关测试。
- 不修改用户现有复盘结果、预测答卷、策略矩阵数据和私有学习层。
- 不把未跟踪的用户数据加入提交。
- 合并回 `main` 必须等待用户明确确认。
