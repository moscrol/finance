# Agent Workbench UI 重构与产物渐进迁移实施计划

日期：2026-07-10
状态：已完成
分支：`codex/feat/workbench-ui-redesign`
设计：`docs/superpowers/specs/2026-07-10-agent-workbench-ui-redesign-design.md`

## 目标与边界

本轮交付一个由 FastAPI 托管的 React/Vite 本地工作台，统一承载研究入口、Run 状态、
回答、追问、检查器和产物库，并通过明确 Provider 注册既有 human-readable 产物。

保持以下边界不变：

- Run、预测台账、每日复盘、DuckDB、Markdown/JSON/JSONL 继续是 canonical 来源。
- Artifact Registry 只建立只读索引，不成为新的事实写入者。
- 不修改复盘结果、预测答卷、策略矩阵数据、私有用户数据或知识库管线。
- 不停用既有 HTML 渲染器；原生视图达到功能等价前保留旧页面。

## 技术落点

```text
intelligence/api/
  app.py                 FastAPI、Run/SSE、Artifact 与 bootstrap API
  artifacts.py           Descriptor、Registry、显式 Provider、安全路径解析
  static/                Vite 生产构建，由 FastAPI 直接托管

intelligence/webapp/
  src/                   React/TypeScript 组件与 API client
  package.json           pnpm、Vite、Vitest、Testing Library、Playwright
```

前端使用 React SPA 而不是 Next.js：当前不需要 SSR 或第二套 Node 服务端。SSE 保留，
因为运行过程是服务端单向推送；WebSocket 的双向协议复杂度在本地单用户 MVP 中没有收益。

## 实施顺序

### Task 1：Artifact Registry 与显式 Provider

**Files**

- Create: `intelligence/api/artifacts.py`
- Test: `intelligence/tests/test_artifact_registry.py`

- [x] 定义 `ArtifactDescriptor`，对外只暴露仓库相对路径，不暴露本机绝对路径。
- [x] 实现 `RunArtifactProvider`、`DailyArtifactProvider`、`CockpitArtifactProvider`、
      `LedgerArtifactProvider`、`MatrixArtifactProvider`、`BriefingArtifactProvider`。
- [x] Registry 支持 category/date/status/q 过滤、稳定排序、唯一 artifact_id 与 missing 状态。
- [x] 内容读取只接受 Registry 已注册 descriptor，不接受客户端文件路径。
- [x] Provider 只扫描明确目录和文件模式，不做无边界全仓扫描。

### Task 2：扩展 FastAPI

**Files**

- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_workbench_api.py`

- [x] 新增 `/api/artifacts`、`/api/artifacts/{id}`、`/content`。
- [x] 新增 `/api/workbench/bootstrap`，一次返回工作流、最近 Run、最新日常产物、
      待处理数量和数据截止时间。
- [x] 新增 `/api/runs/{id}/context`，把当前 Run 已有 evidence/memory/review 信息投影给检查器。
- [x] 保留现有 Run、SSE、followups 和 artifact API；失败与降级继续可恢复、可重放。
- [x] FastAPI 挂载 Vite `assets/`，根路径继续只需启动一个 Python 服务。

### Task 3：React/Vite 工程与应用壳层

**Files**

- Create: `intelligence/webapp/package.json`
- Create: `intelligence/webapp/pnpm-lock.yaml`
- Create: `intelligence/webapp/vite.config.ts`
- Create: `intelligence/webapp/tsconfig*.json`
- Create: `intelligence/webapp/eslint.config.js`
- Create: `intelligence/webapp/index.html`
- Create: `intelligence/webapp/src/*`

- [x] 三栏 `AppShell`：左侧任务/工作流，中间研究面，右侧研究检查器。
- [x] 首页统一 Composer；今日复盘、题材深挖、个股研究作为预设或产物入口。
- [x] 使用 Lucide 图标、森林绿主色、琥珀警告、红色失败；不使用 Emoji 功能图标。
- [x] 1180px 以下检查器变抽屉，900px 以下左栏变图标导航，移动端单列。
- [x] Composer 不遮挡正文，所有交互有可见焦点和 accessible label。

### Task 4：Run、SSE 与研究闭环

- [x] 创建 Run 后订阅 SSE，展示“理解问题/查询盘面/检索证据/生成回答/质量复核”等人话阶段。
- [x] SSE 断线显示恢复状态；终态后重新拉取 run/trace/answer/followups/context。
- [x] 完成态展示数据截止、降级、回答、产物、追问、父子 Run。
- [x] 失败态保留已完成步骤和已有产物，不留下永久加载状态。
- [x] 右侧四标签展示当前 Run 可获得的证据、运行、记忆和回检投影。

### Task 5：产物库与安全 Viewer

- [x] 产物库支持搜索、分类、日期和状态过滤。
- [x] Markdown 使用解析器 + DOM 清洗后渲染；JSON 使用结构化只读视图。
- [x] legacy HTML 使用受限 iframe，同时提供新窗口打开。
- [x] 缺文件、缺 canonical、格式不支持均显示明确状态和恢复动作。
- [x] 每个产物展示 canonical 来源、生成任务、日期和更新时间。

### Task 6：测试与构建

**Files**

- Create: `intelligence/webapp/src/**/*.test.tsx`
- Create: `intelligence/webapp/e2e/workbench.spec.ts`
- Modify/Create: `intelligence/api/static/*`（由 Vite 生成）

- [x] 后端覆盖 Provider、过滤、missing、未注册路径和 traversal 拒绝。
- [x] Vitest + Testing Library 覆盖首页、状态、检查器、产物查看和追问交互。
- [x] Playwright 覆盖首页、完成、失败、降级、旧 HTML 和追问主路径。
- [x] 校验 1440px、1024px、390px 无遮挡、横向溢出或不可达交互。
- [x] 运行 Python tests、ESLint、TypeScript、Vitest、Vite build 和 Playwright。

### Task 7：提交与验收

- [x] 只提交 Workbench/API/Registry/测试/实施计划和 Vite 构建产物。
- [x] 不提交用户 runs、未跟踪复盘数据、虚拟环境、node_modules 或本地密钥。
- [x] 推送到 `codex/feat/workbench-ui-redesign` 并创建 PR；不合并 `main`。
- [x] 检查 CI、预览链接和 review comments，修复范围内问题。

## MVP 完成定义

1. 只启动 FastAPI 即可打开 Workbench。
2. 自由提问、三个快捷工作流、运行阶段、回答、追问和父子 Run 在同一界面闭环。
3. 主要旧 HTML 与 Markdown/JSON 报告可从产物库搜索、打开并追溯 canonical 来源。
4. Registry 不允许任意路径读取，前端不暴露绝对路径，Markdown/HTML viewer 有安全边界。
5. 现有 CLI、RunStore、SSE、每日复盘和台账唯一写入者不受破坏。
6. 桌面、窄屏和移动端均可读，失败与降级不会被隐藏。

## 验收结果

- Python：817 tests passed。
- Frontend：ESLint、TypeScript、5 个 Vitest 组件测试通过。
- Playwright：桌面、窄屏、移动端共 15 个场景通过，覆盖首页、运行中、完成、
  失败、降级、追问与旧 HTML 查看。
- Vite production build 已生成到 `intelligence/api/static/`。
