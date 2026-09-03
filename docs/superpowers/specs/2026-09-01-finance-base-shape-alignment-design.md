# 设计：金融 Agent 底座形状对齐（pi 四层 / dsh ctx 插件）

日期：2026-09-01
状态：已实施；包装门按预算上游重判为绿。逐项工具序不是包装验收（90/60/30 授权额的下游）。未新跑 LLM。
口径修订（2026-09-01 审稿）：对照臂改 `live_probe`；包装点改到 adapter；账本复用 benchmark 契约子集；判据拆成工具序列硬门 / 正文结构比对。见文内「2026-09-01 审稿」注。
口径修订（2026-09-01 账本）：硬门改为首轮 `task_frame_hash` + `input_tokens`±3 + `financial_data` ∈ 首轮 `tool_calls`。全序写入 `budget_downstream`。不要求首轮集合两两相等（对照臂会多 `kb_search`）。见收据「尝试 4 更正」。
实施收据：`docs/verification/2026-09-01-finance-base-shape-alignment.md`
本文件：只活在本路径，未合 main 前以工作区为准
父稿：

- `docs/layered-rebuild-roadmap.md`（2026-08-06：不换底座，固定现有 loop）
- `docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`（通用底座 vs 领域 Harness；dsh 是形状参照不是运行臂）
- `docs/agent-product-door.md`（产品门 / 引擎 A / 积木）

仓内已有资产（本单必须接上，禁止另起一份）：

- `intelligence/eval/live_probe.py`（sidecar + `POST /api/runs` + 读 run 目录）
- `intelligence/runtime/dsh_stub_runtime.py`（08-15 §8 / #61 的脚本化 dsh 适配器）
- `intelligence/eval/runtime_backend_benchmark.py` 的 `RuntimeArmResult`（多 runtime 产物契约）
- `intelligence/eval/metric_field_contract.py`（指标 ↔ 产物字段对表）

对照源（只读，不引入为运行时）：

- pi：`/Users/a77/pi`（`earendil-works/pi`，包 `pi-ai` / `pi-agent-core` / `pi-coding-agent` / `pi-tui`）
- dsh：`/Users/a77/deepseek-harness`（HEAD 当时 `99f6f02`）与仓内 sparse `tmp/dsh-source-index`

---

## 0. 一句话结论

做两份 **Python 外壳**，分别模仿 pi 的竖切四层和 dsh 的 `ctx` 插件组装。外壳底下仍走现有生产装配：`ContinuousTurnAdapter` → `GLMAgentRuntime` → `ContinuousAgentEpisode` → `ResearchToolRegistry`。**不换 TypeScript，不 boot 真 pi / 真 dsh，不改 8792。**

本轮验收是「拆开之后还是同一台机器」：同一 resolved 快照、同一道题，两份入口与对照臂的 **首轮 prompt 身份**（`task_frame_hash`、`input_tokens`±3）相同，且首轮都点了 `financial_data`；正文做结构比对（claim / 数字），不要求逐字相等。全序工具名会随 90/60/30 授权额分叉，不能当包装坏了的证据。

真接 `pi-agent-core` 或真 dsh 当司机，是后续单。那一刀会改答案（停轮、压缩、有无修复），本单故意不买。

---

## 1. 为什么先对齐格式

用户原想用真 pi / 真 dsh 跑同一道题，对比 8792 的答案。那要求跨语言桥（TS `AgentTool` ↔ Python `ToolObservation`），工期在桥和合同对账，不在「四层还是插件」。

同模型、同工具、同提示、同数据时，**司机不同答案仍可能差**：8792 有终局 JSON、判官、修复、合成预留；pi/dsh 默认没有。差的是停不停和门，不是目录形状。

因此：

| 阶段 | 做什么 | 答案该不该变 |
|---|---|---|
| **本单** | Python 形状对齐，装配仍走 adapter | **工具序列不该变**；正文允许模型方差，只比结构 |
| 后续（未立案） | 真接 pi-core / 真 dsh + 同一座工具桥 | 允许变，且必须把「同工具同提示」钉死，否则测的是少挂了领域 |

本单不回答「哪个底座答案更好」。

---

## 2. 目标与非目标

### 2.1 目标

1. 在 `/Users/a77/finance-base-ab/` 落下两份可启动入口：`pi-shape`、`dsh-shape`。
2. 目录和导出名让后来人能指着说：这层对应 pi 的哪一包 / dsh 的哪个 `ctx` 键。诚实标注：我们的 `agent_core` **不等于** pi 的 `pi-agent-core`（见 §5）。
3. 各入口能跑完同一道短事实题，打出符合 §7.3 的臂结果（benchmark 契约子集 + 从 events 派生的工具名序列）。
4. 与 **同一 resolved 快照 revision** 的对照臂对齐（见 §7）。对照臂是 `live_probe` sidecar，不是生产 8792 的 conversations。
5. 8792 进程、启动器、resolved 快照工作区零改动。

### 2.2 非目标（写死，别顺手做）

- ❌ 不 `npm install` / 不 `import` `@earendil-works/*`，不 `pnpm dsh`。
- ❌ 不把 Cordis 或 Node 引进实验树。
- ❌ 不改 `intelligence/runtime/agent_episode.py` 的生产控制流。
- ❌ 不改 `~/.local/bin/start-finance-workbench`，不切 8792。
- ❌ 不复制 DuckDB / wiki / 用户账本；不往生产用户态（`~/.local/share/finance-workbench/users/`）写对话。
- ❌ 不把 verifier / Evidence Ledger / 截止日抽成可换插件（那是领域真源，见 08-17 对照）。
- ❌ 不把 `ToolPipeline` 接到生产 Episode（接缝仍休眠，见 `intelligence/services/episode_scope.py` 文首，**在 services/ 不在 runtime/**）。
- ❌ 不宣称形状对齐等于底座可热插真 pi。
- ❌ 不写进 `RUNTIME_BACKEND_NAMES`，不注册第三条生产 backend（与 `dsh_stub` 同一条纪律，见 §6.1）。
- ❌ 不新开第二份跨 runtime 产物契约（见 §7.3）。
- ❌ 不另写一份 dsh 协议适配器来替代 `dsh_stub_runtime.py`（见 §6.1）。

---

## 3. 术语

| 词 | 本单含义 | 不是 |
|---|---|---|
| **形状 / 格式** | 包边界、导出名、组装方式 | 换 loop 实现 |
| **pi 四层** | `ai` → `agent_core` → `finance_agent`；无 TUI | 安装官方 npm 包；`agent_core` ≠ `pi-agent-core` |
| **dsh spine** | session、prompt 组装、工具流水线、`Agent` 合同、默认 loop 这组默认骨架 | 「最底层库」 |
| **ctx** | 本单的 Python 字典式注册表（`ctx["llm"]` 等），模仿 Cordis 共享上下文 | 真 Cordis `Context` |
| **外壳** | 新树里的薄包装，import 现有 `intelligence.*` | 复制一份 Episode；第二条装配路径 |
| **对照臂** | `live_probe` 拉起的一次性 sidecar + `POST /api/runs` + 读 run 目录 | 生产 8792 的 `POST /api/conversations` |
| **resolved 快照** | `readlink -f /Users/a77/finance-workspace-runtime`（内容寻址目录，如 `~/.finance-runtime/finance-workspace-<rev>`） | symlink 本身；`finance-workspace-private` 工作区 |

与 08-15 §2 对齐：通用底座 = 怎样跑；领域 Harness = 金融题怎样才算对。本单外壳暴露底座形状，领域仍焊在现有 Episode 调用里——**故意**，否则工具序列必漂。

---

## 4. 放置与隔离

### 4.1 树

```text
/Users/a77/finance-base-ab/          # 独立目录，不是 8792 快照，不是 private 仓内 worktree
  README.md
  question.txt                       # 第一道题，三边逐字相同
  compare.sh                         # 依次打 pi-shape / dsh-shape / live_probe，落账
  pi-shape/
    packages/ai/
    packages/agent_core/
    packages/finance_agent/
    run.py
  dsh-shape/
    ctx.py
    spine.py
    plugins/llm.py
    plugins/tools.py
    plugins/loop.py
    plugins/finance_domain.py        # 只登记；execute 仍进 registry
    run.py
  out/                               # gitignore；三份臂结果
```

设计稿留在本文件（private 仓）。实验代码不进 `intelligence/`，避免 `layer_audit` 和快照误吸。

**加载哪份代码：cwd 是硬约束，PYTHONPATH 不够。**

启动器同时做两件事：`PYTHONPATH=…/finance-workspace-runtime` 和 `cd "$RUNTIME_DIR"`。`python -m` 让 `sys.path[0]=cwd` 排在 `PYTHONPATH` 前面。数据仓根目录有一份 `intelligence/` 时，在数据仓 cwd 里起的进程会加载工作树（含未提交改动），`PYTHONPATH` 被无视——2026-07-31 已踩过，当时防坑检查全绿。

因此：

1. 钉的路径是 **resolved 快照**，不是 symlink：`SNAPSHOT=$(readlink -f /Users/a77/finance-workspace-runtime)`。health 的 `loaded_code_root` / `code_root` 也是解析后的内容寻址目录。
2. 两份 `run.py` 与 `compare.sh` 必须 `cd "$SNAPSHOT"` 再 exec；`PYTHONPATH` 只附加 `/Users/a77/finance-base-ab/<shape>`（外壳），**不得**把 `finance-workspace-private` 放进 `PYTHONPATH`。
3. 数据根仍用 `FINANCE_WS`（只读）。凭证跟 sidecar 同一条生产装配链（经 `GLMAgentRuntime`，见 §5），不另造 key，不裸调 `detect_providers()`。

### 4.2 端口与进程

对照臂复用 `intelligence/eval/live_probe.py`：

- `RESERVED_PORTS = {8792, 8793, 8795, 8799, 8801}`
- `PORT_SCAN = range(8796, 8821)`
- sidecar 用户默认 `live-probe`，产物默认 `~/.finance-runtime/live-probe-traceability`
- 文首原话：读 run 目录，never the public trace projection；Does not touch production 8792

pi-shape / dsh-shape 的入口是一次性 CLI，不常驻 HTTP。禁止 `WORKBENCH_REPO_ROOT` 指到 `finance-base-ab`。禁止占用 `RESERVED_PORTS`。

生产 8792 只用来读 health / revision，不接实验题、不写生产 conversation。

---

## 5. pi 形状（竖切）

依赖只许向下，禁止 `ai` import `finance_agent`。

**包装点选 adapter，不选 Episode。** `ContinuousAgentEpisode.run()` 要 `TaskFrame` + `ResearchRunContext` + `ResearchToolRegistry` + 构造期的 `AgentModelClient`（`agent_episode.py`）。从一行问题到这四样，生产走 `continuous_turn_adapter.py` → `glm_agent_runtime.py` → Episode。外壳自己拼 = 第二条装配路径，工具序列对不齐；只包 Episode = `agent_core` 变成没人穿过的空层，§9 的 import 检查会在空层上假绿。

| 包 | 名义对应 pi | 实际包装 | 本单允许的厚度 |
|---|---|---|---|
| `packages/ai` | `@earendil-works/pi-ai` | `GLMAgentRuntime` 的 provider 链 + 采样（`temperature=0.0` / `disable_thinking=True` / `tool_choice="auto"`，见 `glm_agent_runtime.py`） | 再导出 runtime 用的那条链。**禁止**裸包 `llm_refine.detect_providers()`——那会打到启动器里另一条 `LLM_MODEL`/`LLM_BASE_URL`，且 `chat_with_tools` 默认 `temperature=0.2`，对照臂却是 `glm-5.3` + 0.0。禁止新重试策略 |
| `packages/agent_core` | `@earendil-works/pi-agent-core`（**仅名义**） | `ContinuousTurnAdapter`（及其内部的 `GLMAgentRuntime`） | 暴露 `run(question)` = 调 adapter 的生产接缝。可空挂 `transform_context` / `before_tool_call` / `should_stop_after_turn` **默认 no-op**，不得改变 adapter/Episode 行为 |
| `packages/finance_agent` | `@earendil-works/pi-coding-agent` | 入口、题面、把 adapter 结果投影成 §7.3 | 不重写工具，不拼第二份 `ResearchRunContext` |

README 必须写明：

> pi 的 `agent-core` 在我们这儿对应 `ContinuousTurnAdapter` + `GLMAgentRuntime`，**不**对应 `ContinuousAgentEpisode`。Episode 是 adapter 后面的司机，不是本层包装点。

不建 `tui` 包。pi 的 TUI 对应 Workbench HTTP 门；本单对照走 `live_probe`，不复刻终端 UI。

`run.py`：`cd` 到 resolved 快照 → 读 `question.txt` → `finance_agent` → `agent_core.run`（adapter）→ 写 `out/pi-shape.json`。

---

## 6. dsh 形状（ctx 插件）

不引入 Cordis。最小 `ctx`：

```python
ctx: dict[str, object]  # 键：llm, tools, agent_loop, sessions
```

启动：`spine.boot()` 按固定顺序 `register` 四个插件（llm → tools → loop → finance_domain）。`finance_domain` 只把现有工具名登记到 `ctx["tools"]`；`execute` 转 `ResearchToolRegistry`，禁止第二份执行体。

| 插件 | 模仿的 ctx 键 | 本单做什么 |
|---|---|---|
| `plugins/llm.py` | `ctx.llm` | 转 `GLMAgentRuntime` 的 provider+采样，与 §5 `packages/ai` 同一条链 |
| `plugins/tools.py` | `ctx.tools` | `register` / `execute` 门面；流水线阶段可点名但不新开执行路径 |
| `plugins/loop.py` | `ctx.agentLoop` | 调 `ContinuousTurnAdapter`（与 §5 `agent_core` 同一接缝） |
| `plugins/finance_domain.py` | 领域插件 | 登记工具；不拥有 loop |

`sessions` 本单可以是内存记账（本次 run 的工具账），**不**替代 Evidence Ledger，不写 session JSONL 新格式。

卸插件 / 生命周期回滚不做。本单只借「往 ctx 上挂」这一个形状。

`run.py`：`cd` 到 resolved 快照 → boot → 同一 `question.txt` → 写 `out/dsh-shape.json`。

### 6.1 与 `dsh_stub_runtime.py` 的关系

`intelligence/runtime/dsh_stub_runtime.py`（约 550 行）已按父稿 §8.1–§8.3、§11 第 7 步合入（#61）。它是**脚本化协议适配器**：经 `HeadlessToolGateway` 的 JSON/HTTP 面跑通 task frame / episode scope / tool definitions / tool call / tool result / durable event / final outcome。它不是第二套工具执行器；不 import dsh SDK；**不**进 `RUNTIME_BACKEND_NAMES`（factory 认了这个名字却没有独立 readiness，会掉进 headless 回落）。

本单 `dsh-shape` **不是**它的第二份，也不是替代它。关系：

| | `dsh_stub_runtime` | 本单 `dsh-shape` |
|---|---|---|
| 目的 | 窄协议对照（以后真 dsh 打 Python 网关） | 目录/组装形状（ctx 上挂插件） |
| 司机 | 脚本化 stub | 现有 `ContinuousTurnAdapter` |
| 本单动作 | **只读、不改、不复制** | 外壳可在 README 里链到它；loop 插件不得 import stub |

禁止把 stub 抄进 `finance-base-ab/`。真接 dsh 的后续单应在 stub 的网关协议上接，不在本单的字典 ctx 上长协议。

---

## 7. 对照臂（live_probe，不是生产 conversations）

### 7.1 必须同一份 resolved 代码

8792 与 sidecar 都应加载 resolved 快照，不是 `finance-workspace-private` 工作区，也不是未解析的 symlink。

实施第一步：

```text
curl -s http://127.0.0.1:8792/api/health
readlink -f /Users/a77/finance-workspace-runtime
python -c "import intelligence.runtime.agent_episode as m; print(m.__file__)"
```

第三条必须在 **cwd=resolved 快照** 下跑。把 `source_revision`、resolved `code_root`、`agent_episode.__file__` 写入 `out/baseline-health.json`。对不上就停。

`compare.sh` **开始前和结束后** 各读一次 health 的 `source_revision` 与 `readlink -f`。实验期间若 8792 被切，symlink 会指向另一棵树——两次不一致则整次作废，不准拿旧 baseline 对新树比。

### 7.2 同一道题 + 对照怎么打

文件：`/Users/a77/finance-base-ab/question.txt`，一行，三边逐字相同。

选题规则（实施时选定并写进该文件，本 spec 不锁死公司名）：

- 短事实，现有只读工具能在一轮内打到；
- 不选「目前市场怎么看」这类会吃满预算、对照噪声大的题；
- 不选确定性引擎 B 题型（`DETERMINISTIC_OWNER_TYPES`），对照的是引擎 A / Episode。

对照臂：**只许**走 `intelligence/eval/live_probe.py`（`ask`：起 sidecar，除非 `--attach`；`POST /api/runs`；拷 run 产物）。

禁止：

- `POST /api/conversations/{id}/messages`（202 异步；公开投影 `_public_message_payload` 没有 `tool_calls`/`arguments`；会写入生产用户账）
- 读公开 trace 投影当工具账真源（`live_probe` 文首：public projection strips prompts）

工具账真源：run 目录的 `trace.jsonl`（`intelligence/services/run_store.py`）。`live_probe` 已拷 `RUN_ARTIFACTS`（含 `trace.jsonl` / `run.json` / `answer.md`）。

sidecar 端口遵守 `RESERVED_PORTS` / `PORT_SCAN`。默认用户 `live-probe`，不碰生产用户目录里的对话。

### 7.3 产物契约（benchmark 子集，不新开 schema）

禁止自造 `{arm, answer_text, tool_calls:[{arguments}]}` 第二份契约。臂级字段必须能对上 `RuntimeArmResult`（`intelligence/eval/runtime_backend_benchmark.py`），并过 `_LOCAL_PATH_RE` / `_SECRET_VALUE_RE` 脱敏（产物不得带 `/Users/...` 或 key）。

本单使用的子集（名字跟契约走，不是新词）：

| 本单要用的 | `RuntimeArmResult` 字段 | 来源 |
|---|---|---|
| 臂名 | `backend`（取值 `pi-shape` / `dsh-shape` / `live-probe`） | 外壳填写 |
| 题 | `case_id`（或 NOTES 里写 question.txt 的哈希） | `question.txt` |
| 模型 | `model` | 与 sidecar 同一条链 |
| 正文 | `answer`（= `published_answer`） | adapter / run `answer.md` |
| 停因 | `stop_reason` | outcome / run.json |
| 时延 | `latency_seconds` | 墙钟 |
| 工具次数 | `tool_calls`（**计数**，契约如此） | events 派生 |
| revision | 不在 `RuntimeArmResult` 顶层：写入 `diagnostics` 或旁路 `out/baseline-health.json` | health |

**工具名序列**不在 `RuntimeArmResult` 顶层（顶层 `tool_calls` 是 int）。按 `metric_field_contract.py` 纪律：从 `diagnostics.events` / `trace.jsonl` 的 `tool_request` 派生 `name` 序列。这是硬门禁用的结构，不是新契约文件——派生规则写进 `compare.sh`，字段名与 `normalize_harness_trace.py` 的 `tool_request` 对齐。

需要参数对账时：从同一条 `tool_request` 取 arguments，**不**把完整参数表提升为臂级新字段（避免和第二份 schema 同形）。`compare.sh` 比的是派生序列，不是另存一份。

对齐规则（两级，现在就写死）：

1. **硬门禁**：三份的 `question`（或 `case_id` 哈希）、resolved `source_revision`、`model` 相同；首轮 `model_turn.task_frame_hash` 相同；首轮 `input_tokens` 极差 ≤3；`financial_data` 出现在每一臂首轮 `tool_calls`。全序 `tool_request` name 序列记入 `budget_downstream`，不卡包装。
2. **结构比对（正文）**：同一组可抽取数字 / 同一 claim 集合（可用已有 `RuntimeClaim` 或 `answer.md` 的引用表）。**不**要求 `answer` 逐字相等。父稿 §11 第 8 步已因方差把样本量锁到 30×15；单次逐字比对当门禁会必然返工。
3. 三臂必须经 `GLMAgentRuntime` 采样（0.0 / disable_thinking），不得一臂裸 `detect_providers`。
4. 删除旧稿「逐字失败后再改判写 NOTES」条款——那是给不该立的门准备的逃生阀。

---

## 8. 和现有分层的关系

```text
用户题
  pi-shape:  finance_agent → agent_core(ContinuousTurnAdapter) → GLMAgentRuntime → Episode
  dsh-shape: ctx.agent_loop(同一 adapter) → GLMAgentRuntime → Episode
  对照臂:    live_probe sidecar → /api/runs → 同一 adapter → Episode
                ↓
         同一 ContinuousAgentEpisode
                ↓
         同一 Registry / 同一数据 / 同一 GLMAgentRuntime 采样
```

`agent.py`（CLI agent）仍不在服务器里，本单不碰。

08-15 的 `ToolPipeline` / `EpisodeScope` 本单只允许在 dsh-shape 的 `plugins/tools.py` **点名阶段**（注释或空方法），禁止接到生产 `ToolBatchExecutor`。

---

## 9. 验收（可执行）

本单完成 = 下面全部为真，缺一条不算。

1. `git -C "$(readlink -f /Users/a77/finance-workspace-runtime)" status --porcelain` 在 compare **前、后** 均为空。`start-finance-workbench` 未改。
2. `curl` 生产 8792 `/api/health` 仍为 200；`source_revision` 与 `out/baseline-health.json` 在 compare 前、后相同。若本条红：先排除自干扰（见 §9.1），再查是否被切流。
3. 加载自哪：在实验 `run.py` 进程（或 compare 为它准备的 cwd）下  
   `python -c "import intelligence.runtime.agent_episode as m; print(m.__file__)"`  
   打印路径位于 resolved 快照内，**不是** `/Users/a77/finance-workspace-private/intelligence/...`。已起 sidecar 则对其 pid 做 `lsof -a -p <pid> -d cwd`，cwd 必须是 resolved 快照。
4. `bash /Users/a77/finance-base-ab/compare.sh` 退出 0（§7.3 两级判据）。
5. `out/pi-shape.json`、`out/dsh-shape.json`、`out/live-probe.json` 字段是 `RuntimeArmResult` 子集 + events 派生的 name 序列；过脱敏（无 `/Users/` 正文、无 key）。
6. `pi-shape/packages/ai` 的传递 import 不出现 `finance_agent`。`dsh-shape` 的 loop 插件不直接 import 工具执行体（只经 `ctx["tools"]`），也不 import `dsh_stub_runtime`。
7. 全树 `rg "@earendil-works|from cordis|deepseek-harness" /Users/a77/finance-base-ab` 无运行时依赖命中（README 说明除外）。
8. `pi-shape` README 含 §5 那句诚实标注（`agent_core` ≠ Episode ≠ 官方 `pi-agent-core`）。

### 9.1 配额与自干扰（预先写明，避免假红）

- LLM 走 5 小时滚动配额；本单三臂各 1 次，合计约 3 次，预留失败重跑。实施记录剩余配额；不够就停，不准换模型凑绿。
- 8792 活着时起 sidecar 是负载。08-17 实测旁路测量能把 8792 `/api/readiness` 打成 `not_ready`（`probe_rag_cli` 抢同一份模型/CPU）。§9.2 若红：先看 sidecar 是否刚跑完、readiness 是否在数秒内恢复；**恢复后 health 200 + revision 未变则本条不算失败**。持续 `not_ready` 才红。
- 对照臂用 sidecar 端口，不把题打进 8792。8792 只做 revision 哨兵。

---

## 10. 实施顺序

1. `readlink -f` + 8792 health + `agent_episode.__file__` → `out/baseline-health.json`。cwd 不对就停。
2. 选定 `question.txt`。
3. 搭 `pi-shape` 三包 + `run.py`（adapter 接缝，`cd` 快照）。
4. 搭 `dsh-shape` ctx + 四插件 + `run.py`（同一 adapter；README 链到 `dsh_stub_runtime`，不复制）。
5. 对照臂：`live_probe ask`，产物进 `out/live-probe/`（或拷到 `out/live-probe.json`）。
6. `compare.sh`：§7.3 硬门 + 结构比对；红则修外壳，不修 Episode / 不改 stub / 不改 benchmark 契约。
7. 回写本文件状态：Draft → 已实施，并补 `docs/verification/2026-09-01-finance-base-shape-alignment.md` 收据（实施时另开）。

---

## 11. 后续（本单不施工）

只有 §9 绿了才允许立案：

- 真接 `pi-agent-core`：一座 Python 工具桥，TS `AgentTool` 打桥；同一 `question.txt`。预期答案开始和对照臂有差，差必须能归因到停轮/压缩/修复，不能归因到少挂工具或裸 `detect_providers`。
- 真接 dsh：在 `dsh_stub_runtime` 已跑通的网关协议上接，不在本单字典 ctx 上长协议。
- 把领域门（verifier / ledger / 截止日）从 Episode 控制流里抽到外壳钩子。那是解耦，不是 `mv`；全序工具名本单已不当包装门。
- 若要恢复逐项序门：先修 90/60/30（抬 tier、reserve 随剩余缩、或首轮 LLM 不记在工具钟上）。那是 Episode 单。

---

## 12. 红线

- 领域正确性仍归现有 Episode + Ledger + Verifier。外壳不得另判「这数对不对」。
- 不得用实验进程的失败去重启或切 8792。
- 不得把 `finance-base-ab` 做成 `intelligence/` 的软链别名。包装边界必须能指出来：`agent_core` = adapter+`GLMAgentRuntime`，不是 Episode。
- 不得在数据仓或 private 工作区 cwd 里起实验进程。
- 两刀仍有效（08-15 §14）：通用底座不管对错；「明天做成 dsh 插件挂哪条缝」——真 dsh 挂 `dsh_stub` 的网关，不挂本单 ctx。本单允许领域仍在 Episode 里被调用——外壳还没资格抽它。
