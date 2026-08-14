# Agent Workbench 产品化改造设计

- 日期：2026-07-08
- 状态：设计稿，待用户审阅
- 目标版本：P0 本地可用工作台，P1 统一任务编排，P2 多用户/分享化

## 1. 背景

用户提供了一段 Knevo 风格录屏，希望判断自己的金融 Agent 要做到类似体验还差在哪里，并把“需要做的”整理成可执行文档。

录屏里的产品不是单纯聊天机器人，而是一个 Agent 工作台：

- 用户用自然语言提问。
- 系统先给结构化结论、风险和后续追问。
- 系统自动生成 Markdown 文件，例如 `earnings-review.md`。
- 页面展示子 Agent 与工具调用过程，例如 `finance-researcher`、`finance_entity_resolve`、`finance_statement`、`finance_graph_context`。
- 产物可以预览、下载、分享。

当前金融 Agent 的底层研究能力已经比较强：DuckDB 盘面数据、Theme Radar、知识图谱、证据分层、双盲答卷、checkpoint/verdict、回答质量 rubric 都已存在。真正缺口不在“模型会不会分析”，而在“能不能把这些能力包装成一个连续、透明、可复用的产品体验”。

一句话目标：

> 把现有金融研究能力从“脚本 + CLI + 静态 HTML + 台账”升级成一个本地优先的 Agent Workbench：一问触发任务，一屏看见过程，一键得到报告，所有结论可追溯、可回检、可复用。

## 2. 产品定位

中文名暂定：

- 金融 Agent 工作台
- 题材研究工作台
- Market Intelligence Workbench

定位：

> 面向 A 股主题研究的个人 Agent 工作台，把盘面数据、知识图谱、研报/公告证据、个人复盘框架和双盲验证串成一个可对话、可生成文件、可回看任务过程的研究界面。

它不是交易下单工具，也不是荐股机器人。它的终态仍然是研究员/分析顾问：帮助用户整理线索、拆证据、出反证、生成报告、登记验证，不替用户做买卖决策。

## 3. 核心差距

### 3.1 统一入口缺口

当前能力分散在多个入口：

- `python3 -m intelligence.cli ask`
- `python3 -m intelligence.cli foresight`
- `python3 -m intelligence.cli daily`
- `skills/theme-radar/scripts/radar.py`
- `复盘/index.html`
- `docs/learning/forecast-review-ledger/`
- 各类 render 脚本和台账

用户需要知道该用哪个命令、哪个文件、哪个报告。录屏产品的优势是把这些能力收束到同一个聊天入口里。

需要做：

- 建一个 Workbench 首页，默认就是任务/聊天入口。
- 把 `ask`、`theme`、`daily`、`foresight` 包装成可选任务类型。
- 对用户隐藏底层命令，只展示“正在查盘面 / 正在查证据 / 正在生成报告 / 已完成”。

### 3.2 Artifact 产物系统缺口

录屏里每次任务会生成一个文件卡片，可以预览、下载、分享。当前项目虽然生成很多 Markdown、JSON、HTML，但它们不是“本次对话产物”的一部分，用户需要自己去目录里找。

需要做：

- 建立 `Run` 概念：一次用户请求 = 一个 run。
- 每个 run 下面挂产物：
  - `answer.md`
  - `summary.json`
  - `trace.json`
  - 可选 HTML 报告
  - 可选图片/图表
- UI 中展示 Artifact 卡片：文件名、类型、生成时间、来源任务、预览、下载。
- 所有产物都要能追溯到输入、数据截止日、知识库 commit、工具版本。

### 3.3 工具链透明度缺口

录屏清楚展示子 Agent 和工具列表，用户知道系统不是在“黑箱胡说”，而是在按步骤查资料。

当前项目底层有很多真实工具，但用户看不到执行路径：

- DuckDB 查询
- 知识库 Hybrid 检索
- Theme Radar 六模式
- evidence index
- checkpoint/verdict
- answer rubric

需要做：

- 为每次任务生成 `trace.json`。
- trace 至少记录：
  - step id
  - step name
  - status
  - started_at / finished_at
  - input summary
  - output summary
  - warnings
  - linked artifact
- UI 中用时间线展示工具调用过程。

可复用知识点：

> 这就是 Agent observability（Agent 可观测性）。面试里可以讲：复杂 Agent 不能只看最终答案，还要记录中间工具调用、检索命中、失败降级和产物版本，否则无法调试和建立信任。

### 3.4 主动追问产品化缺口

录屏会自动生成“猜你想问”。当前项目已有 `foresight` / 潜意识模式，但它还不是聊天页面的一等交互。

需要做：

- 每次回答后生成 3-5 个追问卡片。
- 追问卡片分类型：
  - 证据加深
  - 反证验证
  - 替代标的
  - 盘面回检
  - 题材迁移
- 点击追问卡片可以直接启动新的 run。

### 3.5 报告模板缺口

当前 `ask` 已有六段式输出，`finance-answer-rubric` 也有评分体系，但不同任务的报告模板还不够产品化。

需要做：

- 为高频问题建立固定报告模板：
  - 个股上涨空间分析
  - 题材深拆
  - 晚间卖方研报深度分析
  - 每日复盘机会判断
  - 盘后验证回检
  - 反方审稿
- 每个模板都定义：
  - 输入字段
  - 必跑工具
  - 输出章节
  - 引用要求
  - 反证要求
  - 风险提示
  - 可验证指标

### 3.6 分享与协作缺口

当前项目偏个人本地使用。录屏里已经具备分享入口。

P0 不急着做在线分享，但要先把产物结构设计成可分享：

- 每个 run 有稳定 id。
- 每个 artifact 有相对路径和元数据。
- HTML 报告可以从本地工作台打开。
- 后续可以接入静态站点或内网分享。

## 4. 推荐技术方案

### 4.1 推荐方案：Next.js + FastAPI + SSE

架构：

```text
浏览器 Workbench UI
  -> Next.js / React 前端
  -> FastAPI 后端
  -> intelligence CLI / Python service layer
  -> DuckDB + Knowledge Wiki + Theme Radar + Ledger
  -> Run Store + Artifact Store + Trace Store
```

技术解释：

- Next.js：React 应用框架，适合做聊天界面、文件卡片、时间线、报告预览。React 是组件化 UI 框架，适合把“消息、工具步骤、产物卡片”拆成可复用组件。
- FastAPI：Python Web API 框架，适合把现有 Python CLI 包成 HTTP 接口。优点是类型清晰、写法轻、和现有 Python 代码栈贴合。
- SSE：Server-Sent Events，服务端向浏览器单向推送事件。适合展示“任务进行中”的 step 日志，比轮询更顺滑，比 WebSocket 简单。
- DuckDB：本地列式分析数据库，继续作为市场 feature store。
- RAG：Retrieval-Augmented Generation，中文叫检索增强生成。先从知识库/证据库检索，再让模型基于检索结果回答，减少幻觉。
- Hybrid 检索：向量检索 + BM25 关键词检索混合。BM25 是传统关键词相关性算法，擅长精确词命中；向量检索擅长语义相似；两者结合更稳。
- rerank：重排序。先召回一批候选材料，再用更强的排序器或规则重新排序，提高最终给模型的上下文质量。

为什么推荐：

- 能最大化复用现有 Python 资产。
- UI 产品感足够接近录屏。
- SSE 能自然呈现工具调用过程。
- 不要求一开始上云，符合本地优先和隐私边界。

### 4.2 替代方案 A：Streamlit / Gradio 快速壳

做法：

用 Streamlit 或 Gradio 直接包现有 CLI，快速做一个输入框 + 输出报告 + 文件下载。

优点：

- 最快，1-3 天可做出可用 demo。
- Python 单栈，几乎不需要前端工程。
- 适合先验证工作流。

缺点：

- 产品感弱，交互像实验面板。
- 复杂任务时间线、文件卡片、报告预览会比较粗糙。
- 后续要转真正产品时可能需要重写。

适用场景：

- 如果目标是“先自己用、快速验证”，可以作为 P-1 原型。
- 如果目标是“做成录屏那样的产品”，不建议作为主线。

### 4.3 替代方案 B：只增强 CLI + 静态 HTML

做法：

继续加强 `intelligence.cli`，每次任务生成 Markdown/HTML，然后用现有 `复盘/index.html` 串起来。

优点：

- 改动最小。
- 与当前系统最兼容。
- 稳定、低风险、可离线。

缺点：

- 仍然不像一个对话式 Agent 产品。
- 用户无法在一个界面里看到“提问 -> 执行 -> 产物 -> 追问”。
- 对外演示弱。

适用场景：

- 作为 P0 的后端产物层继续保留。
- 不作为最终产品入口。

## 5. P0 范围

P0 目标是做出“像录屏那样能用”的本地版本，不追求多用户、权限、云部署。

### 5.1 P0 必做

1. 本地 Workbench UI
   - 左侧任务/会话列表。
   - 中间聊天与报告流。
   - 下方输入框。
   - 右侧可选运行详情或文件列表。

2. Run Store
   - 保存每次任务的 id、时间、用户问题、任务类型、状态、数据截止日。
   - 第一版可以用本地 JSONL 或 SQLite。

3. Artifact Store
   - 每次任务保存 Markdown、JSON、HTML 链接。
   - UI 展示文件卡片。

4. Trace Store
   - 记录每个工具步骤。
   - UI 展示执行时间线。

5. 任务类型
   - `ask`：普通研究问答。
   - `theme`：题材深拆。
   - `daily`：每日复盘入口。
   - `foresight`：猜你想问。

6. 报告模板
   - 先做两个模板：
     - 题材深拆报告。
     - 个股/公司研究报告。

7. 安全边界
   - 明确“不构成投资建议”。
   - 不接交易下单。
   - 不写明文密钥。
   - 所有结论保留证据引用和反证条件。

### 5.2 P0 不做

- 不做登录系统。
- 不做团队权限。
- 不做云端部署。
- 不做实时行情推送。
- 不做自动下单。
- 不重构整个知识库。
- 不把所有老 HTML 都重写成 React。

## 6. P1 范围

P1 目标是把工作台从“能看”升级到“能持续跑研究流程”。

需要做：

1. 统一任务编排
   - 把 `ask/theme/daily/foresight/verdict` 都接入统一 run 协议。
   - 每个任务有标准输入、标准输出、标准 trace。

2. 子 Agent 概念
   - `finance-researcher`：研究问答。
   - `theme-radar-agent`：题材雷达。
   - `verdict-agent`：盘后回检。
   - `foresight-agent`：主动追问。
   - `red-team-agent`：反方审稿。

3. 追问卡片闭环
   - 每个回答后自动生成追问。
   - 点击追问启动新 run。
   - 追问与原 run 建立 parent-child 关系。

4. 评分与复盘
   - 接入 `finance-answer-rubric`。
   - 回答生成后可自动打分。
   - 低分项进入改进队列。

5. 双盲与 verdict 可视化
   - 工作台能查看 Codex/Claude 双盲答卷。
   - 展示 hit/miss/partial/unverifiable。
   - 按 source 分账：duckdb、briefing、sellside。

## 7. P2 范围

P2 目标是接近可推广产品。

需要做：

1. 分享链接
   - 本地静态分享。
   - 可选发布到内部站点。

2. 多用户上下文
   - 用户画像。
   - 自选股/关注题材。
   - 私有纠偏和偏好。

3. 更完整的检索层
   - Hybrid 检索统一服务。
   - rerank 接入。
   - 检索可观测 dashboard。

4. 评测闭环
   - 问答质量样本集。
   - 双盲结果统计。
   - 用户纠偏回灌。

5. 产品化部署
   - 本地桌面版或内网版。
   - 任务队列。
   - 日志与错误恢复。

## 8. 数据模型草案

### 8.1 Run

```json
{
  "run_id": "run_20260708_001",
  "created_at": "2026-07-08T22:45:00+08:00",
  "question": "帮我分析浪潮信息这次 Q2 业绩预告的含金量",
  "task_type": "stock_research",
  "status": "completed",
  "source_date": "2026-07-08",
  "duckdb_cutoff": "2026-07-08",
  "kb_commit": "abc123",
  "artifacts": ["answer.md", "summary.json", "trace.json"]
}
```

### 8.2 Trace Step

```json
{
  "step_id": "s03",
  "name": "finance_graph_context",
  "status": "completed",
  "started_at": "2026-07-08T22:45:12+08:00",
  "finished_at": "2026-07-08T22:45:15+08:00",
  "input_summary": "浪潮信息 + 国产算力 + 服务器产业链",
  "output_summary": "命中 4 个相关概念、8 条公司暴露、5 条证据",
  "warnings": []
}
```

### 8.3 Artifact

```json
{
  "artifact_id": "artifact_answer_md",
  "run_id": "run_20260708_001",
  "type": "markdown",
  "path": "runs/run_20260708_001/answer.md",
  "title": "浪潮信息 Q2 业绩预告深度分析",
  "previewable": true,
  "downloadable": true
}
```

## 9. UI 草案

第一屏结构：

```text
┌─────────────────────────────────────────────┐
│ Market Intelligence Workbench               │
├───────────────┬─────────────────────────────┤
│ 会话 / 任务列表 │  回答流                    │
│               │                             │
│ 今日复盘       │  结构化结论                 │
│ 浪潮信息研究   │  证据链                     │
│ 液冷题材深拆   │  风险/反证                  │
│               │  猜你想问                   │
│               │  Artifact 文件卡片          │
├───────────────┴─────────────────────────────┤
│ 输入问题...     技能选择  数据源选择  发送     │
└─────────────────────────────────────────────┘
```

交互原则：

- 默认让用户“问一句就能开始”。
- 高级设置折叠，不挡住主流程。
- 工具过程默认折叠，但失败和警告必须明显。
- 文件卡片靠近对应回答，不让用户去目录里找。
- 每条结论保留来源和可验证指标。

## 10. 实施顺序

### 第 0 步：先做 Run/Artifact/Trace 协议

先定义本地数据契约，不急着做漂亮 UI。

产出：

- `docs/superpowers/plans/...` 实施计划。
- `intelligence/runs/` 或 `intelligence/services/run_store.py` 设计。
- 一个最小样例 run。

原因：

> 产品化 Agent 的核心不是页面，而是“每次任务的输入、过程、输出能被保存和复现”。这在 RAG、自动化工作流、企业 Agent 平台都通用。

### 第 1 步：包一条 ask 流

先把 `python3 -m intelligence.cli ask` 包成后端 API。

验收：

- 前端输入问题。
- 后端执行 ask。
- UI 展示回答。
- 生成 `answer.md` 和 `trace.json`。
- 有 Artifact 卡片。

### 第 2 步：接入 foresight 追问

验收：

- 回答后出现 3-5 个追问卡片。
- 点击追问启动新 run。
- 新 run 能关联 parent_run_id。

### 第 3 步：接入 theme-radar

验收：

- 题材问题自动走 theme 任务。
- 输出题材深拆报告。
- trace 能看到 `brief/front-map/deep-dive/replay` 等模块。

### 第 4 步：接入 daily / verdict

验收：

- 工作台能打开每日复盘产物。
- 能看到双盲答卷状态。
- 能看到 verdict 命中率。
- 按 source 分账，不混淆盘面、晨汇、卖方。

### 第 5 步：做视觉打磨

验收：

- 类似录屏的文件卡片、步骤卡片、追问卡片。
- 移动端至少可读。
- 本地演示顺畅。

## 11. 验收标准

P0 通过标准：

1. 用户打开一个本地 URL，就能完成一次金融研究问答。
2. 问答结果不是纯文本，而是有 Markdown 产物卡片。
3. 用户能看到工具执行过程。
4. 回答后有追问卡片。
5. 产物能从 UI 预览和下载。
6. 结论带证据引用和风险提示。
7. 不破坏现有 CLI、复盘 HTML、台账流程。

## 12. 风险与约束

### 12.1 最大风险：先做 UI，后补数据契约

如果先做漂亮页面，没有 run/artifact/trace 协议，后面会变成“页面能看但不可复现”。所以先定协议，再做 UI。

### 12.2 最大工程风险：直接重构现有 CLI

现有 CLI 和脚本承载很多已验证流程，不应为了工作台大改。P0 应以 wrapper 方式接入，等协议稳定后再逐步服务化。

### 12.3 最大产品风险：变成荐股 App

工作台必须守住研究员定位。所有输出都要有反证、验证指标和“不构成投资建议”边界。

### 12.4 最大体验风险：暴露太多内部细节

工具 trace 要让用户建立信任，但不能把所有日志原样堆出来。UI 只展示摘要、状态和关键警告，详细日志留给开发模式。

## 13. 面试可讲点

这条产品化路线可以包装成一个很强的 Agent 系统设计案例：

- 多源 RAG：市场结构化数据 + 知识图谱 + 原始证据。
- Hybrid retrieval：向量语义召回 + BM25 精确召回 + rerank。
- Agent observability：trace、工具调用、warnings、artifact。
- Reproducibility：manifest、数据截止日、kb commit、verdict。
- Evaluation loop：rubric 打分、双盲答卷、hit/miss 回检。
- Human-in-the-loop：用户纠偏、人工裁决保护、批量任务门控。

人话版：

> 这不是“套个聊天框”，而是把一个复杂研究系统做成可观察、可复现、可评价、可迭代的 Agent 产品。

