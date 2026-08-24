# Workbench Research Journey 原生进度与研究收据设计

- 日期：2026-08-24
- 状态：用户已确认，可进入实施
- 实施分支：`codex/feat-workbench-research-journey`
- 基线：`gitea/main@62e273376740dc763b574fe70959f65792a07f33`
- 范围：`intelligence/webapp/` 前端与相关测试

## 1. 目标

Workbench 已有成熟的三栏研究壳、暖灰/石墨/陶土橙视觉语言、SSE 消息流与可追溯 Trace。当前运行中主区只把最新一条 Trace 摘要放在三个跳动圆点后，用户看不到研究现在处于理解、检索、核验还是成文阶段；完成后运行细节又立即折叠，主区缺少一条简明研究收据。

本设计将 Vidio 已验证的「单一焦点 → 因果桥接 → 停稳 → 结论留读」方法迁移到 Workbench，但不复制视频 HTML/CSS/GSAP 片段，不改造全局品牌。

成功标志：

1. 用户在一秒内能判断研究当前阶段及最新动作。
2. 完成后能看到证据数、数据截止日、产物数和限制/缺口数，不需先展开诊断详情。
3. 所有状态由已有公开 SSE/Trace/RunContext 事实驱动，不猜测后端步骤，不猜测回答语义。
4. 不新增后端字段、第三方前端依赖或跨仓运行时耦合。

## 2. 决策与备选方案

### 2.1 选定：Workbench 原生组件纵向切片

用 React + TypeScript + CSS 实现 `ResearchJourney` 和 `ResearchReceipt`，先改研究运行过程，再根据真实使用结果决定是否扩展到今日首页和结构化回答。

该方案复用 Vidio 的设计方法和时序原则，但以 Workbench 自己的数据契约、响应式布局、Lucide 图标和语义色为实现边界。

### 2.2 备选 A：直接复制 Vidio 片段

Vidio `library/` 现有模块是 HTML/CSS/GSAP 视频时间轴片段，不是 React 组件。直接复制虽能快速出视觉效果，但会引入不必要的 GSAP 依赖、固定画幅假设、双仓样式漂移和可访问性成本，不选。

### 2.3 备选 B：先重构全部 CSS

`styles.css` 已经约 5300 行，长期确实需要收敛。但把全量 token/样式拆分作为前置会放大范围，并延迟用户可见收益。本批只建立新组件需要的局部深模块，不顺手重构无关样式。

## 3. 范围

### 3.1 本批实现

- 研究进行中的四阶段 `ResearchJourney`。
- 研究结束后的 `ResearchReceipt`。
- Trace 步骤到用户阶段的纯函数归并器。
- 运行、完成、失败、跳过、取消、重连和未知步骤状态。
- 桌面、平板和手机的不同信息密度。
- 组件、归并器和真实消息流的测试。

### 3.2 明确不做

- 不改侧边栏、导航、今日首页或 Composer 品牌。
- 不引入 GSAP、Framer Motion 或新 UI 组件库。
- 不把 Vidio 仓设为 submodule/package/runtime 依赖。
- 不复制 `picture` 仓图片到 Workbench；它只是回归证据和视觉参考。
- 不解析 Markdown 正文猜测「核心判断」、证据层或重要性。
- 不把 warning、degrade 或 evidence gap 合并成一个含义不清的总分。
- 不删除或简化现有原始 Trace 详情。

## 4. 视觉命题与阅读顺序

视觉命题：一个谨慎的金融研究用户先看见当前研究在做什么，再看见该动作属于哪个阶段，最后在回答稳定后读到一条可核对收据；整体是克制的编辑型工具，不是宣传片。

进行中阅读顺序：

```text
Foresight · 正在研究

✓ 理解与计划 ── ● 查找证据 ── ○ 交叉核验 ── ○ 形成结论
                     正在核对公告、盘面与知识库……
```

完成后阅读顺序：

```text
Foresight · 已完成
22 条可验证引用 · 数据截至 2026-08-21 · 3 个产物 · 1 项限制

[回答正文]

研究详情 >
```

视觉上只保留一个高显著度动态焦点：当前阶段。已完成阶段降低对比，未开始阶段只留结构，不与当前步骤争抢。

## 5. 组件与模块边界

```text
researchJourney.ts
├── buildResearchJourney(progress, answerPhase, terminalStatus)
├── buildResearchReceipt(bundle)
└── 阶段映射、状态优先级、文案归一化

ResearchJourney.tsx
├── 桌面/平板四阶段轨道
├── 手机当前阶段 + 四段进度条
└── 实时人话摘要与重连提示

ResearchReceipt.tsx
├── 可验证引用数
├── 数据截止日
├── 产物数
└── 限制/缺口数（分类展示）

MessageBubble.tsx
└── 只决定何时显示 Journey / Receipt / 旧兜底

RunView.tsx / ResearchInspector.tsx
└── 继续保留原始 Trace 、warning、degrade 和高级详情
```

`researchJourney.ts` 是唯一语义归并点。React 组件不自己猜步骤含义，`MessageBubble` 不再临时拼阶段文案。后续若今日首页需要同类收据，只消费归并结果，不复制规则。

## 6. 数据流

```text
SSE trace.step / answer.snapshot / message.complete
  → applyChatStreamEvent()
  → LiveMessageState.progress / answerPhase / status / connection
  → buildResearchJourney()
  → ResearchJourney

Run 结束后重载
  → RunBundle(run + trace + context + artifacts)
  → buildResearchReceipt()
  → ResearchReceipt
```

不新增 API，不修改 SSE schema，不把 UI 状态写回 RunStore。

## 7. 四阶段语义映射

| 用户阶段 | 已知 Trace `name` | 含义 |
| --- | --- | --- |
| 理解与计划 | `understanding`, `planning`, `route_skills` | 识别问题、确定路由与研究计划 |
| 查找证据 | `research`, `ask_current_turn`, `ask_retrieve_compose` | 读盘面、公告、知识库与其他获准来源 |
| 交叉核验 | `repair`, `verification` | 补缺口、检查引用和判断边界 |
| 形成结论 | `finalizing`, `render_artifacts`, `foresight_followups` | 形成公开回答、产物和后续验证问题 |

`answerPhase` 参与最后一阶段：

- `verified_draft`：「形成结论」仍为进行中，文案为「可核验草稿已形成，正在精修」。
- `validated_synthesis`, `verified_fallback`, `decision_brief_fallback`, `evidence_gap_fallback`：为「形成结论」提供一条合成 `completed` 证据，并保留各自现有人话状态。如果同阶段仍有显式 running/failed Trace（例如追问或产物收尾），显式 Trace 优先，不得提前把整阶段标绿。

未知 Trace 不被强行归入某个阶段，也不会导致阶段虚假完成。它的真实 `output_summary` 仍作为当前动作显示；无摘要时才使用「执行研究步骤」。

## 8. 状态归并契约

1. 先按 `step_id` 保留最新事件，并按该 `step_id` 最后一次 replay 输入位置排列，与现有 `upsertTraceStep` 的 replay 语义一致。
2. 归并时每个不同 `step_id` 的终态事件只关闭同一生命周期组中一个更早、尚未关闭的 running：已知阶段按阶段分组，未知步骤按原始 `name` 分组。若终态 `step_id` 自己在 replay 历史中已有 running，它只闭合自身，不能再消费并行 running；不得由摘要文本猜关联，也不得一项终态关闭并行分支。
3. 每阶段状态为 `waiting | running | completed | skipped | attention`。
4. 同一阶段内优先级：`failed → attention`，其次 `running`，再次 `completed`，最后 `skipped`。
5. 只有真实完成事件才能把阶段标为 `completed`。不得因后一阶段已开始，就伪造前一阶段完成。
6. 终态到来时，从未出现过的阶段保持 `skipped`，不补绿。
7. `connection=reconnecting` 是连接状态，不是研究失败；已有进度保留，只显示「连接恢复中」。
8. 终态失败/取消保留已完成阶段；当前阶段显示 `attention`，不清空轨迹。
9. 历史恢复和 SSE replay 只恢复状态，不重播「新步骤入场」动画。
10. 页面只显示一个「当前动作」：先选最新失败步骤，再选 `started_at` 最晚的 running 步骤，最后选 `finished_at` 最晚的 completed/skipped 步骤。时间字段不可解析时保持输入顺序，不猜时序。

## 9. Research Receipt 口径

| 字段 | 来源 | 展示规则 |
| --- | --- | --- |
| 可验证引用数 | `context.evidence` 中 `classification=bound_evidence` | 只计可绑定证据，不把检索候选当引用 |
| 数据截止日 | `run.source_date ?? run.duckdb_cutoff ?? context.metadata.source_date ?? context.metadata.duckdb_cutoff` | 无数据显示「未记录」，不回显当天伪装新鲜 |
| 产物数 | `run.artifacts.length` | 真实 Run 产物数，不把尚未注册的文件算入 |
| 限制/缺口 | `context.gaps` 经 `userFacingIssue`、trim、去空白和去重后数量 | `context.gaps` 是该 Run 的原始、合并问题事实源；不与已脱敏的 `run.degrades` 分别计数 |

收据是研究交付的索引，不是质量总分。它不宣称「可发布」、「高置信」或「高质量」。

## 10. 展示规则

### 10.1 进行中

- `live.status` 为 `pending` / `streaming` 且尚未有终态回答时显示 `ResearchJourney`。
- 有部分草稿时轨道仍显示，但收紧为一行，不与正文争抢。
- 无 Trace 事件时显示「正在启动研究」的静态兜底，不伪造四阶段进度。

### 10.2 结束后

- 已加载 `RunBundle` 时显示 `ResearchReceipt`。
- 未加载 bundle 时保留现有回答状态，不显示全 0 伪收据。
- 原始运行详情继续位于 `RunView` 折叠区；收据不替代详情。

### 10.3 响应式

- 桌面/平板：显示四阶段水平轨道和当前动作摘要。
- 小于 720px：显示「阶段 n/4 + 当前阶段名」、四段进度条和动作摘要；不在 390px 横向硬塞四个完整标签。
- 收据可换行，但不允许横向滚动。

## 11. 动效与可访问性

- 只有当前阶段可使用一个低幅度呼吸提示；其他元素不循环动画。
- 新状态采用约 160ms 的 opacity/transform 过渡，不使用弹跳、飞入、摄影机或大范围模糊。
- 过渡使用 CSS，不引入动效依赖。
- 继续服从全局 `prefers-reduced-motion: reduce`；在减少动画模式下过渡近似即时。
- 图标、文字和形状共同表达状态，不依赖颜色一项。
- 最新动作摘要使用 `role="status"` / `aria-live="polite"`；四个状态点本身不反复广播，避免读屏器被 SSE 事件淹没。
- 轨道使用有序列表语义，每阶段有可读状态文本。

## 12. 错误与降级

| 场景 | 行为 |
| --- | --- |
| SSE 重连 | 保留所有阶段，单独显示「连接恢复中」 |
| Run 失败 | 当前阶段进入 `attention`，已完成阶段不倒退 |
| Run 取消 | 保留进度与已生成正文，状态文案为「已停止」 |
| Trace 无摘要 | 使用 `userFacingStage(name)`；未知名称显示「执行研究步骤」 |
| Context 未加载 | 不显示全 0 收据，保留终态标签 |
| 无可验证引用 | 明确显示 0 且保留现有公司证据警告，不隐藏 |
| 无截止日 | 显示「数据日期未记录」，不推断当天 |

## 13. 预计文件边界

| 文件 | 作用 |
| --- | --- |
| `intelligence/webapp/src/researchJourney.ts` | 纯函数语义归并与收据构建 |
| `intelligence/webapp/src/researchJourney.test.ts` | 归并不变量、口径与重放测试 |
| `intelligence/webapp/src/components/ResearchJourney.tsx` | 进行中轨道 |
| `intelligence/webapp/src/components/ResearchReceipt.tsx` | 完成收据 |
| `intelligence/webapp/src/components/researchJourney.css` | 组件内聚样式与响应式 |
| `intelligence/webapp/src/components/MessageBubble.tsx` | Journey/Receipt/兜底安装点 |
| `intelligence/webapp/src/components/components.test.tsx` | 用户可见状态与 ARIA 测试 |
| `intelligence/webapp/e2e/workbench.spec.ts` | 真消息流、三视口与详情对账 |

不改 `types.ts` 公开协议形状，除非实施时发现归并器输出类型必须对外复用；默认保持模块内部类型。

## 14. 测试设计

### 14.1 纯函数

- 每个已知 Trace 名称归入正确阶段。
- 同 `step_id` 的 running → completed 更新不产生重复步骤。
- failed 不会被同阶段早期 completed 覆盖。
- 后阶段开始不会伪造前阶段完成。
- terminal 时未出现阶段为 skipped。
- 未知阶段保留摘要但不改动四阶段。
- verified draft 与四种终态 answer phase 映射正确。
- 收据只计 `bound_evidence`；限制/缺口仅从 `context.gaps` 经 `userFacingIssue`、trim、去空白和去重生成。
- 截止日优先级与空值文案正确。

### 14.2 组件

- pending 无 trace 显示启动兜底。
- running 显示唯一当前阶段和最新真实摘要。
- reconnecting 不清空轨道。
- completed + bundle 显示收据，原始 RunView 仍可展开。
- failed/cancelled 保留进度和终态人话。
- 状态有文字/图标，`aria-live` 只包含当前摘要。

### 14.3 端到端与视觉检查

- 复用现有真聊天 E2E，断言运行中轨道出现，完成后收据出现，运行详情仍可展开。
- desktop / tablet / mobile 均通过无横向溢出与 Composer 不遮挡检查。
- 本地浏览器人检运行中、完成、失败、重连和减少动画状态。
- 不在首批引入跨环境像素金图；它的字体和渲染差异噪声大于本次收益。

## 15. 验收门

1. `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm build` 全绿。
2. 相关 Playwright 三视口用例全绿。
3. 无新生产依赖，`package.json` 的 dependencies 不增加。
4. 无后端/API/SSE schema 改动。
5. 未知步骤、跳过步骤、重连和失败都不被伪装成 completed。
6. 可验证引用、截止日、产物、gap 和 degrade 口径与 RunBundle 真值一致。
7. 390px 不横向硬塞四个完整标签，不遮挡回答或 Composer。
8. 减少动画模式下不存在可见循环动画。
9. 原始 Run Trace、warning、degrade、Artifact 和追问入口全部保留。
10. `git diff --check` 通过，提交不含本仓红线文件。

## 16. 渐进扩展顺序

首批验收后才考虑：

1. 把同一 `ResearchReceipt` 视图模型用到今日首页的当日交付收据。
2. 基于 `StructuredReport` 明确模块构建 `InsightCallout`，不从 Markdown 猜核心结论。
3. 视真实使用情况收敛 `styles.css` 中重复的状态样式和 token；不在本批预支重构成本。

## 17. 权利、来源与仓库边界

- Vidio 作为方法来源，固定检查点为 `feat/design-language-contract@3f7a7c9b864a66bd0c87cbad44dbea8d72eabfc1`。
- 不复制 Vidio 视频工程、渲染产物、第三方字体或上游品牌资产。
- `picture@809fd521d7b02a10da89c7b99c49a3fae6614d6c` 仍是 FinHot 截图/录屏证据仓，不作组件依赖。
- Workbench 对迁移后的 React/TypeScript/CSS 实现拥有独立所有权与测试责任。

## 18. 交付边界

- 实施、验收、push 和 PR 在当前独立 worktree 中进行，不触碰主检出中的他人改动。
- 所有提交使用明确 pathspec，禁止 `git add -A` / `git add .` / 裸 `git commit`。
- 未经用户明确确认，不合并 `main`、不切换 8792 生产运行时。
