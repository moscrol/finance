# T-E 重跑：dsh 静态形状对照（47f9438 → 99f6f02）

- 日期：2026-08-22 ｜ 执行：专用 worktree `fwp-wt-dsh-audit-0822` ｜ 分支 `docs/dsh-shape-audit-0822`
- 依据：吸收稿 `2026-08-15-agent-base-dsh-absorption-design.md` §9.5（只执行，不改规则）
  ＋ 学习合同 `2026-08-22-harness-seams-to-learn-design.md` §5 L4
- **成立于**：本仓 revision `5d4a3684`（`gitea/main`）；dsh 本机完整 clone
  `/Users/a77/deepseek-harness` HEAD `99f6f02fec`（merge of `release/dsh-0.1.0-rc.7`）。
  stub 仍钉 `PINNED_DSH_COMMIT = 47f943859bef60e4160492346772ded9b24f765a`，本收据**不改**该 pin。
- 前一份：`docs/verification/2026-08-17-dsh-static-shape-audit.md`（文首已盖 superseded）。
- 未跑 live、未改 factory / `RUNTIME_BACKEND_NAMES` / 吸收稿、未把 dsh 源文件拷进本仓、未烧 LLM 配额。

## 0. 四分类口径（与 08-17 同一把尺子）

反推口令仍是：明天若必须做成 dsh 插件，它挂哪条**已经画在架构图上的**接缝？

| 判定 | 含义 | 记什么 |
|---|---|---|
| 挂得上、不用改 loop 图 | 形状能在 dsh 上跑 | 记接缝名；无动作 |
| 只能塞进某个 tool 的 `execute` | dsh 只宿主流水线 | 记为可接受；对错仍由 Evidence / Verifier 判 |
| 焊死了 | 找不到接缝、或必须改 agent-loop | 待拆的债 |
| 领域真源 | 挂不上才对 | 正常，不立整改项 |

L4 追加：新包若只是本仓已有接缝的**同族实现**，记「学形状、先不焊」并指认本仓符号。
**「能挂上」≠ 生产改去跑 dsh。** 本收据不把任何 dsh 目录抄进 `intelligence/`。

---

## 1. 窗口事实（只读对照，未改 dsh 仓）

| 项 | 值 |
|---|---|
| 旧尺子（stub pin） | `47f943859bef60e4160492346772ded9b24f765a` |
| 新尺子（本机 HEAD） | `99f6f02fecdb7dff40c3fbc9470f5907c29f74ca` |
| 窗口提交数 | 111（`git log --oneline 47f9438..99f6f02`） |
| 窗口 diff | 539 files, +8183 / −1625 |
| 包族（`packages/*`） | 49 → 49 |
| 叶子 `package.json` | 新增 0，删除 0 |
| 叶子包仅 version 抖动 | 189 |
| 叶子包有非 `package.json` 改动 | 30 |
| 本窗口**新增**的 `packages/*/src` 文件 | 4 个（见下） |

**结论先写：这个窗口没有新包族、没有新叶子包。**
`guard/` `hooks/` `jobs/` `spill/` `compaction/` 在 pin `47f9438` 已经存在，
本窗口只改了各自 `package.json` 的版本号（`0.1.0-rc.7`），源码零 diff。

本窗口新建的源文件（不是新包）：

| 新文件 | 属于 |
|---|---|
| `packages/acp/acp/src/content.ts` | ACP 图文块编解码 |
| `packages/client/ui-conversation/src/client/skeleton/safari.ts` | Safari textarea 折行 |
| `packages/client/ui-primitives/src/useDismissOnOutsidePointer.ts` | 点击外侧关闭 |
| `packages/client/ui-settings-plugins/src/client/tab-store.ts` | 插件自有设置面 |

module-graph 只多了两条边：`pkg_acp → pkg_attachment` / `pkg_acp → pkg_llm`，
以及 `pkg_mcp_client → pkg_attachment`。没有新接缝名。

---

## 2. 合同点名、本窗口未新增：同族实现，学形状、先不焊

这四族在 08-17 的 sparse cone（`core` / `bundle/base` / `llm` / `cli` / `host`）里
本来就不在尺子上。本次用完整 clone 看见它们，但它们**不是** 47f9438→99f6f02 的新包。
按 L4 仍给出对照，避免下一次再把它们当缺口。

| dsh 包族 | 形状 | 本仓对应符号 | 判定 |
|---|---|---|---|
| `guard/`（`repeat-tool-reminder`） | 相同工具调用循环时给提醒 | `query_ledger.executed`（per-key single-flight；同 key 不跑第二遍） | 挂得上。**学形状、先不焊** |
| `hooks/`（`hook-protocol` / `hooks-claude-code` / `hooks-codex`） | hook 协议 + 会话事件 | SessionStart 事实投递（`scripts/session_facts.sh` → Claude/Devin `additionalContext`） | 挂得上。**学形状、先不焊** |
| `spill/`（`spill` / `spill-local` / `spill-policy`） | 过大 tool 文本落盘，上下文留 locator | `tool_result_budget.budget_tool_observation`（压缩第 1 层：全文已进 Durable，模型侧留预览） | 挂得上。**学形状、先不焊** |
| `jobs/`（`jobs` / `jobs-local` / `tool-jobs`） | `ctx.jobs` 后台登记 / 取消 / 完成通知 | `_BranchBudgetView`（不铸新预算，消耗记父账本）。学习合同 §3：无真后台隔离需求，不为 `jobs/` 去抄 | 挂得上。**学形状、先不焊** |
| `compaction/compaction-tool-result-pruner` | 无模型 head/middle/tail 剪 tool-result | 学习合同 L3 的下一层；禁搬目录进 `intelligence/` | 挂得上。**学形状、先不焊**（L3 另开窗，不在本收据施工） |

---

## 3. 本窗口有源码变动的 30 个叶子包

口径：只分类「接缝/能力是否变了」。文案、CSS、测试夹具、version 对齐不算新接缝。

### 3.1 真结构变化（能力或公开面变了）

| 包 | 窗口里变了什么 | 分类 | 本仓符号 / 先不焊 |
|---|---|---|---|
| `packages/acp/acp` | 新增 `content.ts`；session/prompt 桥接有序图文；依赖挂上 `attachment` + `llm`。README 自陈：这是 transport adapter，**不是** capability seam | 挂得上（`ctx.agents` + `ctx.attachments`） | **学形状、先不焊**。本仓窄协议是 `HeadlessToolGateway` JSON/HTTP，不是 ACP |
| `packages/attachment/attachment` | 有序图像批量准入；`AttachmentErrorCode` 拆出可纠正的 admission 子集 | 挂得上（`ctx.attachments`） | **学形状、先不焊**。本仓 Episode 不收模型可见图像；Evidence Ledger 管证据身份，不管字节 |
| `packages/mcp/mcp-client` | tool 结果里的图像走 durable attachment；graph 新边 `→ attachment` | 只能进 `execute`（MCP 工具挂 `ctx.tools`） | **学形状、先不焊**。本仓 12 个研究工具已在 `ResearchToolRegistry`，不接通用 MCP |
| `packages/core/tools` | code mode 转发嵌套图像结果 | 挂得上（tools 定义面） | **学形状、先不焊**。Code Mode 是吸收稿 §7.7 P2，指标触发前不搬 |
| `packages/fs/tool-fs` | 删本地 `read-image` 路径（图像改走 attachment） | 只能进 `execute` | 可接受。本仓无 fs 读图工具 |
| `packages/llm/llm` | assembler 与 replay 状态对齐；不可用 state 降级 | 挂得上（`ctx.llm`） | **学形状、先不焊**。本仓 provider 适配在 runtime，不抄 assembler |
| `packages/llm/llm-deepseek` | 支持 low reasoning effort | 挂得上（adapter 插件） | **学形状、先不焊** |
| `packages/llm/llm-pi-ai` | replay / convert / loader-composition 与 assembled content 对齐 | 挂得上（adapter 插件） | **学形状、先不焊** |
| `packages/subagent/subagent-claude-code` | 产品子代理一发后台 + provider 显式 opt-in | 挂得上（`ctx.subagents` / `ctx.jobs`） | **学形状、先不焊**。本仓 `SubResearchCoordinator` + `_BranchBudgetView` |
| `packages/subagent/subagent-codex` | 同上（Codex 后端） | 挂得上 | **学形状、先不焊**。同上 |
| `packages/subagent/tool-subagent` | `backgroundMode=one-shot` 默认前台；显式后台只回 `jobId` | 只能进 `execute`（模型面委托工具） | **学形状、先不焊**。不为独立时钟抄 `jobs/` |
| `packages/client/ui-settings-plugins` | 插件自有设置面：每个已注册 namespace 出卡片；新增 `tab-store.ts` | 挂得上（settings / client 插件） | **学形状、先不焊**。本仓配置面是 `ResearchProfile` + `dump_effective_config()` |
| `packages/host/apiproxy` | 从 proxy 里拆掉一块配置/模型面（净删） | 挂得上（host 插件） | **学形状、先不焊**。本仓无 apiproxy |
| `packages/shell/tool-bash-persistent` | 持久 bash 保持 controlled prompt，加快 settle | 只能进 `execute` | 可接受。本仓 agent 只读 + 无 shell 工具 |
| `packages/terminal/terminal-bash` | 同上，终端侧 | 只能进 `execute` | 可接受。本仓无终端宿主 |

### 3.2 产品壳 / 测试 / 文案（有 diff，无新接缝）

| 包 | 窗口里变了什么 | 分类 |
|---|---|---|
| `packages/bundle/base` | README / i18n | 挂得上。文档抖动，不改 08-17 对 Base Bundle 的判断 |
| `packages/client/ui-agent-preset` | code preset 改名为 PTC Mode | 挂得上（产品壳）。本仓 Workbench 自己画预设 |
| `packages/client/ui-conversation` | Safari textarea 软折行 | 挂得上（产品壳） |
| `packages/client/ui-jobs` | Job 文案 | 挂得上（产品壳） |
| `packages/client/ui-primitives` | 点击外侧关闭 hook | 挂得上（产品壳） |
| `packages/client/ui-settings-general` | CSS | 挂得上（产品壳） |
| `packages/client/ui-settings-models` | 测试镜像 | 挂得上（产品壳） |
| `packages/client/ui-user-questions` | ask-user 问题卡可折叠 | 挂得上（产品壳）。本仓追问走 `compose_followups` / `session_projection.view`，不抄这张卡 |
| `packages/context/agent-instructions` | 测试 2 行 | 挂得上。无新接缝 |
| `packages/core/agent-loop` | contract-regression / loop 测试 | 挂得上。loop 图没改；本仓仍是 `ContinuousAgentEpisode` |
| `packages/extensions/cordis-client-runner` | slot-catalog | 挂得上。Cordis 全量引入仍禁止（吸收稿 §12） |
| `packages/extensions/tool-cordis` | api-catalog | 同上 |
| `packages/extensions/ui-cordis` | Cordis 面板样式 | 产品壳 |
| `packages/session-query/session-query` | corpus 4 行 | 挂得上。Session query **不能**替代 Evidence Ledger（领域真源，08-17 §4 仍成立） |
| `packages/test-support/acp-snapshot` | ACP 快照夹具 | 测试支持，不进生产分类 |

---

## 4. 必须焊进本仓？

**没有。** 本窗口没有「找不到接缝、或必须改本仓 agent-loop」的新包。

理由（成立条件：尺子是 47f9438→99f6f02 的包增量，不是重审本仓 08-17 那条公开答案旁路）：

1. 新增包数 = 0；没有新的 capability seam 名出现在 module-graph。
2. 有源码变化的能力（图文桥、插件设置面、产品子代理后台、LLM replay、持久 bash）
   要么是已有接缝的同族实现，要么是产品壳 / execute 里的工具，要么是本仓明确不接的 ACP / MCP / Code Mode / Cordis。
3. 学习合同 L4 禁搬名单（`guard/` `hooks/` `jobs/` `spill/`）在本窗口源码未动；
   对照结果仍是「学形状、先不焊」，与合同三例一致。

08-17 记下的唯一焊点（公开答案投影出口不唯一）是**本仓代码**在当时 revision 的观测，
不是本窗口 dsh 增量制造的。本收据不覆写、不重开那条；旧稿正文保持原样，只在文首指向本文。

---

## 5. 与 08-17 收据的差异小结

| | 2026-08-17 | 2026-08-22（本文） |
|---|---|---|
| 问题 | 本仓组件相对 dsh **像不像插件** | dsh pin→HEAD **多了什么接缝**，要不要焊 |
| 尺子 | `DSH_SOURCE_INDEX` sparse cone，钉 `47f9438`，未连真实 dsh | 本机完整 clone HEAD `99f6f02`，只读 `log` / `diff --stat` / 目录 |
| 本仓 revision | `31ee58ce6c45` | `5d4a3684` |
| 产出 | 7 项协议 + 12 工具 + foresight/skills/投影 的四分类；1 条焊死 | 0 个新包；30 个有 diff 的叶子包分类；合同点名四族补对照 |
| 焊死 | 1 条（`public_answer` 3 个旁路，归 T-B） | **本窗口 0 条**。旧焊点不搬进本文当新发现 |
| 领域真源 | 5 类（Verifier / Evidence Ledger / cutoff / D3） | 不因 dsh 升级而改档；`session-query` 仍不能替代 Ledger |
| 待判 | 0（§7 已补完） | 0 |

08-17 的 ①②③-b 分类**不因这次 dsh 升级失效**——失效的是「继续拿 47f9438 sparse cone 当当前尺子」。
所以旧稿 superseded，而不是改写旧正文。

本 stub 的 `PINNED_DSH_COMMIT` 仍是 `47f9438`。L4 的验收是「新开收据 + 旧稿盖章」，
**不是**把 pin 前移。pin 前移是另一扇门，需要单独论证。

---

## 6. 明确没做

- 不改 `intelligence/runtime/dsh_stub_runtime.py` / factory
- 不改 `PINNED_DSH_COMMIT`
- 不把 `dsh_stub` 或 dsh 登记进 `RUNTIME_BACKEND_NAMES`
- 不改吸收稿 §9.5
- 不把 `/Users/a77/deepseek-harness` 的任何源文件拷进本仓
- 不写代码、不跑 live、不 push、不开 PR
