# 原生日常报告设计与实施清单

- 日期：2026-07-10
- 目标分支：`codex/feat/workbench-ui-redesign`
- 关联 PR：#177
- 状态：待实施

## 一、设计清单

### 1. 目标

- [ ] 将 Daily Agent 和 Daily Review 建设为首批 Workbench 原生、适合公开阅读的报告。
- [ ] 把信息和用户任务迁移到统一的产品语言，而不是把旧 HTML 页面直接搬进主体验。

### 2. 产品原则

- [ ] 普通读者无需了解内部字段名、工作流命令或仓库路径，也能理解页面。
- [ ] 首屏回答三个问题：发生了什么、为什么重要、下一步需要关注什么。
- [ ] 专业细节通过渐进披露保留，不主导默认视图。
- [ ] 每条结论保留日期、证据边界、缺失证据和 canonical 来源。
- [ ] 旧 HTML 作为标注为 `原始报告（Original report）` 的次级对照面，不作为 Daily Agent 或 Daily Review 的默认视图。
- [ ] 现有 canonical 写入者和台账所有权保持不变。

### 3. 范围

#### 3.1 本轮范围

- [ ] 从 canonical JSON 生成原生 Daily Agent 投影。
- [ ] 从 canonical Markdown 生成原生 Daily Review 投影。
- [ ] 为缺少 Markdown 的历史 Daily Review 产物提供兼容投影：
  - [ ] 仅从已注册 HTML 中提取已知章节。
  - [ ] 将来源模式标记为 `legacy_html_projection`。
- [ ] 提供共享的 React 报告界面和统一的 Workbench 视觉语言。
- [ ] 安全访问已注册旧报告的同目录配套资源，用于次级原始报告查看器。
- [ ] 修复 PR 审查中发现的可靠性问题：
  - [ ] 导航竞态。
  - [ ] 滚动位置恢复。
  - [ ] SSE 重放去重。
  - [ ] 移动端无障碍名称。
  - [ ] CI 可复现性。

#### 3.2 本轮不做

- [ ] 不原生迁移策略矩阵、预测台账、驾驶舱或所有 Artifact Registry 分类。
- [ ] 不修改 Daily Review、台账或知识库的 canonical 写入者，只保留工作流已经声明的 Markdown 输出。
- [ ] 不新增交易建议或个性化买卖指令。

### 4. 架构

```text
Daily Agent JSON -----------+
                            |
Daily Review Markdown ------+--> DailyReportProjection --> React DailyReportView
                            |
历史已注册 HTML -------------+    仅用于兼容投影

已注册 HTML + 同目录资源 --> 沙箱化的“原始报告”
```

- [ ] 后端负责标准化，因为源数据 schema 和来源追溯属于领域契约。
- [ ] 前端只接收稳定投影并负责展示。
- [ ] 投影层作为防腐层，避免旧输出格式变化泄漏到产品 UI。

#### 4.1 投影契约

`DailyReportProjection` 包含：

- [ ] `report_type`、`title`、`date`、`source_mode`。
- [ ] `plain_summary`：最多三条由确定性源字段生成的简短结论。
- [ ] `metrics`：少量带标签的指标，可附上下文和语气状态。
- [ ] `sections`：按顺序排列的可行动条目分组。
- [ ] `glossary`：不可避免的研究术语简释。
- [ ] `provenance`：
  - [ ] canonical 路径。
  - [ ] 渲染产物路径。
  - [ ] warnings。
  - [ ] 是否存在原始报告。

章节条目统一使用以下字段：

- [ ] `title`
- [ ] `summary`
- [ ] `badges`
- [ ] `meta`
- [ ] `next_action`
- [ ] 可选的结构化详情

约束：

- [ ] 不把未知字段直接倾倒到主界面。

### 5. Daily Agent 展示

适配器将 canonical JSON 映射为：

1. [ ] **三件需要知道的事**
   - [ ] 确定性统计数量。
   - [ ] 优先级最高的已验证或待确认信号。
2. [ ] **研究工作量**
   - [ ] IMA 数量。
   - [ ] 官方证据数量。
   - [ ] 市场验证数量。
   - [ ] 降级/观察数量。
3. [ ] **值得关注**
   - [ ] 展示优先候选。
   - [ ] 展示生命周期。
   - [ ] 展示证据状态。
   - [ ] 展示代表股票。
   - [ ] 说明为何值得关注。
4. [ ] **今天要做什么**
   - [ ] 按现有优先级展示可行动队列。
5. [ ] **证据边界**
   - [ ] 缺失的 L2/L3 证据层。
   - [ ] warnings。
   - [ ] 来源模式。
   - [ ] 生成时间。

语言转换：

- [ ] 将 `old_logic_wakeup` 等内部键翻译为面向读者的中文标签。
- [ ] 保留 L1-L4，但通过术语表解释每一级含义。

### 6. Daily Review 展示

- [ ] 优先使用 canonical Markdown。
- [ ] 使用有边界的解析器解析标题和 Markdown 表格。
- [ ] 投影以下内容：

1. [ ] **三件需要知道的事**
   - [ ] 市场性质/阶段。
   - [ ] 主导方向。
   - [ ] 风险或验证边界。
2. [ ] **市场温度**
   - [ ] 指数。
   - [ ] 成交额。
   - [ ] 涨跌广度。
   - [ ] 涨停/跌停。
   - [ ] 集中度。
   - [ ] 强度。
3. [ ] **主要方向**
   - [ ] 双红题材。
   - [ ] 新高方向。
   - [ ] 涨停题材。
4. [ ] **风险与验证**
   - [ ] 市场判断。
   - [ ] 覆盖告警。
   - [ ] 下一交易时段验证重点。
5. [ ] **专业数据**
   - [ ] 精选源章节。
   - [ ] canonical Markdown 链接。

历史 HTML 兼容规则：

- [ ] 仅在 Markdown 缺失时启用。
- [ ] 只读取 `核心看板（Core dashboard）` 和 `市场环境判断（Market environment assessment）`。
- [ ] 不复用旧 CSS、脚本、导航或布局。
- [ ] UI 显示来源追溯警告，避免兼容投影被误认为完整 canonical 投影。

### 7. 前端体验

- [ ] `ArtifactViewer` 对支持的日常报告分类请求 projection。
- [ ] 使用 `DailyReportView` 渲染 projection。
- [ ] 共享报告沿用现有 Workbench：
  - [ ] 色板。
  - [ ] 间距。
  - [ ] 字体层级。
  - [ ] 状态徽标。
  - [ ] 响应式断点。
- [ ] 密集数据使用无外框章节、紧凑指标条、行列表和折叠详情。
- [ ] 不新增营销式 hero 或嵌套卡片堆叠。
- [ ] `原始报告` 作为次级操作和原生报告下方的折叠区。
- [ ] 导航时立即清除旧数据。
- [ ] 忽略迟到响应。
- [ ] 对重放的 trace step 去重。
- [ ] 切换 surface 时重置页面滚动位置。
- [ ] 移动端纯图标控件始终保留明确的无障碍名称。

### 8. 旧报告资源兼容

只有满足以下条件时，API 才允许读取相对配套资源：

- [ ] 父 artifact 已注册。
- [ ] 解析后的资源仍位于已注册 artifact 的目录内。
- [ ] 目标是普通文件。
- [ ] 请求不能通过 `..` 或符号链接逃逸。

其他约束：

- [ ] 原始 HTML 继续在 sandbox 中运行。
- [ ] 配套资源支持只用于准确的历史归档对照，不作为原生渲染机制。

### 9. 错误与降级

- [ ] projection 来源缺失或无效：
  - [ ] 显示原生错误状态。
  - [ ] 原始报告可用时保留原始报告入口。
- [ ] canonical Markdown 缺失但历史 HTML 有效：
  - [ ] 使用兼容投影。
  - [ ] 显示兼容模式 warning。
- [ ] Daily Agent JSON 无效：
  - [ ] 不将原始 JSON 作为公开报告兜底。
  - [ ] 展示已注册来源和恢复提示。
- [ ] 导航响应迟到：
  - [ ] 丢弃迟到响应。
  - [ ] 不改变当前 surface。
- [ ] SSE 重连/重放：
  - [ ] 使用相同 `step_id` 替换已有步骤，而不是追加重复步骤。

### 10. 测试与发布门禁

- [ ] 后端测试覆盖：
  - [ ] Daily Agent projection。
  - [ ] Daily Review Markdown projection。
  - [ ] 旧 HTML 兼容 projection。
  - [ ] 异常输入。
  - [ ] 配套资源路径穿越。
- [ ] 组件测试覆盖：
  - [ ] 面向读者的标签。
  - [ ] 术语表。
  - [ ] 降级状态。
  - [ ] 原始报告折叠区。
  - [ ] 移动端无障碍名称。
- [ ] E2E 覆盖：
  - [ ] 桌面、平板、移动端的原生 Daily Agent。
  - [ ] 桌面、平板、移动端的原生 Daily Review。
  - [ ] 滚动重置。
  - [ ] 失败导航隔离。
- [ ] CI 执行：
  - [ ] 817 个 intelligence 测试。
  - [ ] lint。
  - [ ] TypeScript。
  - [ ] 组件测试。
  - [ ] 生产构建。
  - [ ] Playwright。
  - [ ] 使用可发现的 Python 可执行文件。
- [ ] 使用真实本地产物验证，而不是只依赖 mock HTML。

### 11. 验收标准

- [ ] Daily Agent 和 Daily Review 默认以 Workbench 原生报告打开。
- [ ] 首屏无需内部 schema 知识即可理解结论和下一步行动。
- [ ] 两类报告共享一套视觉和交互系统。
- [ ] 原始 HTML 明确处于次级位置，且其已注册相对图片能够正常加载。
- [ ] 切换 Run 或 artifact 时，不会在新选择下残留旧内容。
- [ ] 所有自动检查可在干净 checkout 中通过，无需手工创建 `.venv` 符号链接。

## 二、实施清单

> Agent 执行要求：实施时使用 `superpowers:subagent-driven-development`（推荐）或
> `superpowers:executing-plans`，逐任务完成并即时勾选。

**目标：** 让 Daily Agent 和 Daily Review 默认打开为一致、适合公开阅读的 Workbench 原生报告，同时只把旧 HTML 保留为安全的次级参考。

**架构：** 新增后端 projection adapter，将 canonical Daily Agent JSON 和 Daily Review Markdown 归一为一个 `DailyReportProjection`。历史 HTML 仅由有边界的兼容适配器解析。React 使用共享报告组件渲染 projection；Artifact Registry 继续作为来源追溯和内容访问边界。

**技术栈：** Python 3.12、FastAPI、dataclasses、标准库 HTML 解析、React 19、TypeScript、Vitest、Playwright、GitHub Actions。

### Task 1：日常报告投影适配器

**文件：**

- 新建：`intelligence/api/daily_reports.py`
- 新建：`intelligence/tests/test_daily_report_projection.py`

- [ ] **Step 1：先写 Daily Agent JSON projection 失败测试**

创建 fixture，断言：

- [ ] 面向读者的摘要。
- [ ] 队列数量。
- [ ] 已翻译的生命周期/证据标签。
- [ ] 术语表条目。
- [ ] canonical 来源追溯。
- [ ] projection 不暴露内部 JSON 键。

```python
projection = project_daily_agent(payload, source_path="exports/2026-07-01-daily-agent.json")
assert projection["report_type"] == "daily_agent"
assert projection["metrics"][0]["label"] == "旧逻辑重新活跃"
assert "old_logic_wakeup" not in json.dumps(projection, ensure_ascii=False)
```

- [ ] **Step 2：先写 Markdown 和历史 HTML projection 失败测试**

断言：

- [ ] 提取核心看板。
- [ ] 提取市场判断。
- [ ] 正确标记 `source_mode`。
- [ ] 包含兼容模式 warning。
- [ ] 未知标题和脚本不进入 projection。

- [ ] **Step 3：运行 projection 测试并确认失败**

运行：

```bash
python -m pytest -q intelligence/tests/test_daily_report_projection.py
```

预期：由于 `intelligence.api.daily_reports` 尚不存在，测试收集失败。

- [ ] **Step 4：实现 projection 契约和有边界适配器**

实现以下聚焦函数：

```python
def project_daily_agent(payload: dict[str, object], *, source_path: str) -> dict[str, object]: ...
def project_daily_review_markdown(source: str, *, source_path: str, date: str | None) -> dict[str, object]: ...
def project_daily_review_html(source: str, *, source_path: str, date: str | None) -> dict[str, object]: ...
```

约束：

- [ ] 使用确定性字段映射。
- [ ] 使用标准库 `HTMLParser` 子类。
- [ ] 摘要最多三条。
- [ ] 候选和行动列表数量有明确上限。

- [ ] **Step 5：运行 projection 测试**

预期：所有 projection 测试通过。

### Task 2：Registry projection 与配套资源 API

**文件：**

- 修改：`intelligence/api/artifacts.py`
- 修改：`intelligence/api/app.py`
- 修改：`intelligence/tests/test_artifact_registry.py`
- 修改：`intelligence/tests/test_workbench_api.py`

- [ ] **Step 1：新增失败 API 测试**

覆盖：

```python
projection = client.get(f"/api/artifacts/{artifact_id}/projection")
assert projection.json()["report_type"] == "daily_agent"

asset = client.get(f"/api/artifacts/{review_id}/chart.png")
assert asset.status_code == 200
assert client.get(f"/api/artifacts/{review_id}/..%2Fsecret.txt").status_code in (403, 404)
```

- [ ] **Step 2：新增安全 canonical 与同目录资源解析**

新增 Registry 方法：

- [ ] 只解析 descriptor 已注册的 canonical 路径。
- [ ] 只解析 descriptor 所在的同目录资源。
- [ ] 解析符号链接后拒绝根目录之外的路径。

- [ ] **Step 3：新增 projection 与配套资源路由**

- [ ] `GET /api/artifacts/{artifact_id}/projection`：选择对应 daily adapter。
- [ ] `GET /api/artifacts/{artifact_id}/{asset_path:path}`：只为已注册旧内容提供安全的同目录文件。

- [ ] **Step 4：运行后端 API 测试**

运行：

```bash
python -m pytest -q \
  intelligence/tests/test_daily_report_projection.py \
  intelligence/tests/test_artifact_registry.py \
  intelligence/tests/test_workbench_api.py
```

预期：所有测试通过。

### Task 3：原生 Daily 报告 UI

**文件：**

- 新建：`intelligence/webapp/src/components/DailyReportView.tsx`
- 新建：`intelligence/webapp/src/components/DailyReportView.test.tsx`
- 修改：`intelligence/webapp/src/types.ts`
- 修改：`intelligence/webapp/src/api.ts`
- 修改：`intelligence/webapp/src/App.tsx`
- 修改：`intelligence/webapp/src/components/ArtifactViewer.tsx`
- 修改：`intelligence/webapp/src/styles.css`

- [ ] **Step 1：先写失败组件测试**

断言：

- [ ] 五层报告结构。
- [ ] 面向读者的中文标签。
- [ ] 术语表折叠区。
- [ ] 兼容模式 warning。
- [ ] 次级原始报告折叠区。

- [ ] **Step 2：新增 TypeScript projection 类型和 API client**

定义：

- [ ] `DailyReportProjection`
- [ ] `ReportMetric`
- [ ] `ReportSection`
- [ ] `ReportItem`

新增：

- [ ] `getArtifactProjection()`

- [ ] **Step 3：实现 `DailyReportView`**

渲染：

- [ ] 无外框报告布局。
- [ ] 紧凑摘要带。
- [ ] 稳定指标网格。
- [ ] 有序行动行。
- [ ] 证据标签。
- [ ] 术语表折叠区。

约束：

- [ ] 不渲染未知的原始 JSON 字段。

- [ ] **Step 4：将原生 projection 设为日常报告默认视图**

- [ ] `daily_agent` 和 `daily_review` 由 `App` 请求 projection。
- [ ] `ArtifactViewer` 渲染 projection。
- [ ] sandbox iframe 移入 `原始报告` 折叠区。

- [ ] **Step 5：新增响应式 Workbench 样式**

- [ ] 沿用现有 design tokens 和断点。
- [ ] 验证固定网格约束。
- [ ] 验证文本换行。
- [ ] 验证页面无横向溢出。

- [ ] **Step 6：运行组件检查**

在 `intelligence/webapp` 下运行：

```bash
pnpm lint
pnpm typecheck
pnpm test
```

预期：全部通过。

### Task 4：导航与无障碍可靠性

**文件：**

- 修改：`intelligence/webapp/src/App.tsx`
- 修改：`intelligence/webapp/src/components/Sidebar.tsx`
- 修改：`intelligence/webapp/src/components/components.test.tsx`
- 修改：`intelligence/webapp/e2e/workbench.spec.ts`

- [ ] **Step 1：新增迟到响应隔离和 trace 去重测试**

- [ ] 使用 deferred request 证明迟到的 Run 响应不能替换当前选择。
- [ ] 使用 deferred request 证明迟到的 artifact 响应不能替换当前选择。
- [ ] 重放同一 `step_id`，断言只显示一条 trace。

- [ ] **Step 2：实现请求代际保护**

- [ ] 使用 ref 跟踪 Run 请求代际。
- [ ] 使用 ref 跟踪 artifact 请求代际。
- [ ] 加载前清除旧状态。
- [ ] 仅在响应代际仍为当前值时应用结果。

- [ ] **Step 3：切换 surface identity 时重置滚动**

调用：

```typescript
window.scrollTo({ top: 0, behavior: "auto" });
```

- [ ] **Step 4：保留移动端无障碍名称**

为以下按钮添加显式 `aria-label`，不依赖可见文字或徽标：

- [ ] 新建研究。
- [ ] 首页。
- [ ] 产物库。

- [ ] **Step 5：对 SSE step 去重**

- [ ] 在 App state 中按 `step_id` upsert。
- [ ] 初始 trace 拉取、SSE 重放和重连都不能产生重复 inspector 行。

### Task 5：可复现 E2E 与 CI

**文件：**

- 修改：`intelligence/webapp/playwright.config.ts`
- 修改：`intelligence/webapp/e2e/workbench.spec.ts`
- 新建：`.github/workflows/workbench-check.yml`

- [ ] **Step 1：在 Playwright 配置中发现 Python 可执行文件**

按以下顺序选择：

1. [ ] `WORKBENCH_PYTHON`
2. [ ] 仓库 `.venv-workbench`
3. [ ] 仓库 `.venv`
4. [ ] `python3`

- [ ] 构造一个正确引号包裹的 uvicorn 命令。

- [ ] **Step 2：扩展 E2E mock 与断言**

- [ ] mock projection 响应。
- [ ] 测试原生 Daily Agent。
- [ ] 测试原生 Daily Review。
- [ ] 测试原始报告折叠区。
- [ ] 测试滚动重置。
- [ ] 在 1440、1024、390 三种宽度验证无横向溢出。

- [ ] **Step 3：新增 GitHub Actions 发布门禁**

安装：

- [ ] Python 3.12。
- [ ] API requirements。
- [ ] pytest。
- [ ] PyYAML。
- [ ] Node 22。
- [ ] pnpm 10.12.1。
- [ ] Playwright Chromium。

执行：

- [ ] intelligence 测试套件。
- [ ] lint。
- [ ] TypeScript。
- [ ] 组件测试。
- [ ] production build。
- [ ] Playwright。

- [ ] **Step 4：运行完整本地门禁**

运行：

```bash
env -u FORESIGHT_USER \
  -u FORESIGHT_USERS_DIR \
  -u SUBCONSCIOUS_VAULT \
  python -m pytest -q intelligence/tests

pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

预期：

- [ ] 817+ 个 Python 测试通过。
- [ ] 所有前端检查通过。
- [ ] 无需手工创建 `.venv` 符号链接。

### Task 6：真实产物与视觉验证

**文件：**

- 通过 `pnpm build` 更新 `intelligence/api/static/` 下的生成构建产物。

- [ ] **Step 1：从隔离的 PR worktree 启动 FastAPI**

- [ ] 使用已发现的 Python 可执行文件。
- [ ] 使用空闲 localhost 端口。

- [ ] **Step 2：检查真实 Daily Agent 和 Daily Review 产物**

- [ ] 验证面向读者的首屏。
- [ ] 验证 `source_mode`。
- [ ] 验证原始报告折叠区。
- [ ] 验证历史图表的 `naturalWidth` 和 `naturalHeight` 均大于 0。

- [ ] **Step 3：验证桌面、平板和移动端布局**

视口：

- [ ] 1440×900。
- [ ] 1024×768。
- [ ] 390×844。

检查：

- [ ] 无横向溢出。
- [ ] 无元素重叠。
- [ ] 无标签裁切。
- [ ] 无未命名控件。

- [ ] **Step 4：提交并更新 PR #177**

- [ ] 对照仓库红线审查暂存文件。
- [ ] 提交实现。
- [ ] 将结果 fast-forward 推送到 `codex/feat/workbench-ui-redesign`。
