# Handoff — 8792 复活 + 领域/harness 分层拆分（2026-08-06d）

> 给 agent A。两个任务，**互相独立**。任务 A 是止血（已完成），任务 B 是架构落地第一步。
>
> 背景：用户评估过是否换 agent 底座（`earendil-works/pi` / OpenAI Agents SDK），
> **决定暂不换**，先固定现有底座，再像搭积木一样往上搭、搭一个测一个。
>
> 🔴 **任务 B 已于 2026-08-06 晚整体重写，方向与初版相反。** 初版的搬迁顺序、基线数字、
> 落点、以及一条"要断的边"共四处有误，全部修正并记在文末「修订记录」。
> **如果你读过初版，请以本版为准，不要按记忆继续。**

## 0. 一句话

- **A**（✅ 已完成）：`.finance-runtime` 快照被删、软链悬空，8792 的 UI 返 503，launchd 一重启就彻底起不来。已修复并复核，但引入了新的删除面，见 A.5。
- **B**：新建 `intelligence/runtime/` 装 **15 个 loop 模块**，其余 200 个模块**原地不动**；
  门禁一条目录级规则；当前只有 **1 条**接缝要断。

---

# 任务 A — 救活 8792

## A.1 现状（实测 2026-08-06 22:25）

```
curl http://127.0.0.1:8792/    →  503  {"detail":"Workbench 前端尚未构建"}
```

根因链：

```
启动器 /Users/a77/.local/bin/start-finance-workbench:51
    cd /Users/a77/finance-workspace-runtime
         ↓ 软链
    /Users/a77/.finance-runtime/finance-workspace-8ccca8ca
         ↓
    【该目录已被删除】.finance-runtime/ 下一个 finance-workspace-* 都不剩
```

- 当前进程 pid 57100（8/5 23:15 启动）还活着，只因内核持有已删除目录的 inode。
- `STATIC_DIR/index.html` 在那个已删目录下 → `app.py:1806` 的 `frontend_built` 判 false → 根路径 503。
- **launchd 一旦重启它就彻底起不来**：启动器是 `set -euo pipefail`，`cd` 到不存在的路径直接退出。
  `launchctl list` 里 `com.a77.finance-workbench` 最后退出码已是 `-15`。

## A.2 要做

1. **先查清是谁删的。** 如果是清理脚本或某个 launchd job 干的，重建后会再删一次。
   找到就先停掉；查不到就接受"重建后观察一天"（用户已认可这个选项）。

2. **从 `main@88b28ab4` 重建快照**到 `.finance-runtime/finance-workspace-88b28ab4`。

   ⚠️ **必须用 git 方式建**（`git archive` / `clone`；`git worktree add --detach` 也可以，
   但见下方 A.5 的耦合警告）。
   `intelligence/api/static/` 的 3 个文件（`index.html` + `assets/index-B3Vxcopm.js` +
   `assets/index-BDIbli-N.css`）**是 git 跟踪的**，走 git 会自带前端，不需要额外构建步骤。
   用 rsync 之类可能漏文件。

3. **重指软链** `/Users/a77/finance-workspace-runtime` → 新快照。

4. **启动器加前置断言**（现在是静默失败）：

   ```sh
   TARGET="$(readlink /Users/a77/finance-workspace-runtime || true)"
   [ -d "$TARGET" ] || { echo "runtime snapshot missing: $TARGET" >&2; exit 1; }
   ```

5. `launchctl kickstart -k gui/$(id -u)/com.a77.finance-workbench`

## A.3 验收（逐条跑，全过才算完）

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8792/       # 期望 200，不是 503
lsof -a -p $(lsof -ti :8792) -d cwd                                    # 期望指向新快照
test -d "$(readlink /Users/a77/finance-workspace-runtime)" && echo OK  # 软链不悬空
```

## A.4 红线

- ⛔ **不要用 `/api/health` 验收。** 实测它现在报 `code_root=/Users/a77/finance-workspace-private`、
  `source_revision=3bf2dad0`，**和实际加载的树不是同一个**（真实 cwd 是那个已删快照，主树在
  `88b28ab4`）。**判断加载哪份代码只认 `lsof -a -p <pid> -d cwd`。**
- ⛔ **不要手工 `kill` + `nohup`。** 属主是 launchd，切指针必须走 `launchctl kickstart -k`。
- ℹ️ health 里 `source_dirty: true` 是主树那个 `?? docs/span-io-trace-prd.md` 导致的，
  **不是故障**。agent B 的 `fix/source-dirty-parity` 正在修这个口径。

## A.5 ⚠️ 事后补记：worktree 方式引入了新的删除面

任务 A 已完成（实测复核：根路径 200、pid 37634、cwd 指向 `finance-workspace-88b28ab4`、
软链不悬空）。但快照是用 `git worktree add --detach` 建的，它**不是独立副本**：

```
$ cat /Users/a77/.finance-runtime/finance-workspace-88b28ab4/.git
gitdir: /Users/a77/finance-workspace-private/.git/worktrees/finance-workspace-88b28ab4
```

**生产快照现在和开发仓共享 `.git`，并出现在 `git worktree list` 里。** 后果：

- 在主仓跑 `git worktree prune` / `git worktree remove` **会删掉生产快照**——
  正是本次故障的同一形状，换了个门重新进来。
- 主仓被移动或重命名，快照的 gitdir 指针失效。
- 任何"清理 worktree"的自动化都会扫到它。

**建议**（未做，留给下一位判断）：要么改成自包含副本（`git archive` 到目标目录，
或 `clone --depth 1` 后删 `.git`），要么在 `.finance-runtime/` 放一个显式的
`DO-NOT-PRUNE.md` 并在 worktree 清理类脚本里加排除。**本文档原句"必须用 git 方式建"
把三种方式并列了，没说清 worktree 的耦合代价——这是原 handoff 的缺陷。**

---
# 任务 B — 固定底座：把 loop 层搬进 `intelligence/runtime/`

> ⚠️ **本节已于 2026-08-06 晚整体重写，方向与初版相反。**
> 初版说「把 8 个领域模块搬出 harness」，实测后改为「把 15 个 loop 模块搬进 `runtime/`，
> 领域模块原地不动」。四处修正见文末「修订记录」。**如果你读过初版，以本节为准。**

## B.0 结论先行

```
新建 intelligence/runtime/ ，装 15 个 loop 模块
services/ 及其余 200 个模块原地不动，一个 import 都不用改
门禁一条：intelligence/services/**  不得 import  intelligence.runtime.*
当前违反者：1 条
```

## B.1 为什么是这个方向（实测对比）

AST 实测 `intelligence/` 219 模块 / 122K 行：harness 24 个模块共 22,900 行，其中
**只有约 5,200 行是真 loop 骨架**，另有 **7,511 行是领域逻辑穿了 `episode_` 外衣**
（最大一块 `episode_semantic_verifier.py` **2,894 行**的金融语义 grounding 判据）。
干净积木 **184 模块 / 88,781 行**。

初版方案是"把那 8 个领域模块搬出去"。实测两个方向的代价：

| | 搬 8 个领域模块（初版） | **搬 15 个 loop 模块（本版）** |
|---|---|---|
| import 改动（非测试） | 40 条 / 22 文件 | **30 条 / 13 文件** |
| import 改动（含测试） | 94 条 / 55 文件 | **81 条 / 42 文件** |
| 要断的接缝 | 8 步拓扑序，中途涨到 3 | **1 条，一次搬完** |
| `research_tool_registry` 12 处 import | 全改 | **0 处** |
| `agent_runtime` 14 处 import | 全改 | **0 处** |
| 门禁形态 | 手维护常量白名单 | **目录级规则，无名单可漂** |
| 新增模块 | 要有人记得登记 | **默认落 `services/`，自动受保护** |

**搬更多文件反而改更少 import**，因为那 8 个领域模块是**枢纽**（定义契约和注册表，谁都要用），
15 个 loop 模块是**顶层编排者**（没人往上依赖）。**搬枢纽最贵，搬顶层最便宜。**

方向上也更对：**被圈起来的应该是底座，不是积木。** 底座 15 个、稳定、不该增长；
积木 200 个、会长。门禁圈住小而稳的那个，才不需要持续维护。

## B.2 `intelligence/runtime/` 装哪 15 个

```
agent_episode              continuous_turn_adapter    conversation_orchestrator
glm_agent_runtime          openai_agents_runtime      codex_headless_runtime
agent_runtime_factory      episode_finalizer          episode_tool_batch
sub_research               continuous_sub_research    headless_tool_gateway
agent                      turn_control_core          episode_progress
```

**留在 `services/` 的关键几个，别搬错**：

| 模块 | 为什么留下 |
|---|---|
| `agent_runtime.py` | docstring 就是 "Provider-neutral **contracts**"，定义 Protocol 不是实现 |
| `episode_session.py` | 91 行纯 `Protocol` + 一个测试适配器，"Provider-neutral continuation **seam**" |
| `research_tool_registry.py` | 工具白名单 + `produces` 声明，是契约 |
| `episode_protocol.py` | 系统提示词 + `validate_episode_finish` 证据绑定校验，是业务规则 |
| `episode_tools.py` | 金融工具的实际实现 |
| `episode_semantic_verifier.py` | 2,894 行金融语义判据 |
| `episode_verifier.py` | 确定性 output-to-evidence 校验 |
| `episode_factory.py` | 从 TaskFrame 投影 capability |
| `turn_controller.py` | 路由表 + 检索硬触发 |

**判别口径**（后续遇到同类模块照此判，别看名字前缀）：

- 做 IO / 调模型 / 起子进程 / 管预算 → `runtime/`
- 只声明"长什么样"、只做纯变换、只有 Protocol 与数据类 → `services/`

`turn_control_core` 与 `episode_progress` 两个偏纯投影，**实测放哪边接缝数都是 1**，
本版归 `runtime/`（它们描述的是 runtime 的控制流与事件投影）。这两个若你有不同判断，
改了不会破坏门禁。

## B.3 门禁

**一条规则，目录级，不需要维护任何名单：**

```
intelligence/services/**  不得 import  intelligence.runtime.*
（反向允许：runtime 编排 domain 是正常方向）
```

### TYPE_CHECKING 怎么算

**算违规，但分两级**：

```
runtime import 违规       → ERROR，拦截提交
TYPE_CHECKING 块内违规    → WARN，记录不拦截，但必须在门禁输出里逐条列出
```

**为什么算**：门禁保护的是"harness 可替换"。领域模块的公开签名里出现 harness 类型，
换掉 harness 就得回来改领域模块——正是门禁要防的事。运行时不耦合不代表契约不耦合。

**为什么只 WARN 不拦截**：一刀切拦截会逼人改用 `Any` 或裸字符串注解规避，
那是**丢掉类型检查而没解除耦合**，比违规本身更糟。

**修法是依赖倒置，不是删注解**：让 runtime 依赖 services 定义的 `Protocol`，
而不是 services 引用 runtime 的具体类。

### 门禁脚本要求

原型见 `docs/handoffs/2026-08-06d-layer-scan.py`（已验可跑）。落成 `scripts/layer_audit.py` 时：

- 用**目录**判层（`intelligence/runtime/` vs 其余），不要再用模块名常量表
- 区分 runtime import 与 TYPE_CHECKING import，分别计数、分别退出码
- **输出必须自述审的是哪个 revision**——否则 `exit 0` 会被读成"main 上就是这样"
- 以**当前 1 条接缝**为基线，只减不增

## B.4 执行步骤

1. **先立门禁**（在搬之前），跑一次记录基线。此刻应报：`ERROR 1 条 / WARN 0 条`。
2. **建 `intelligence/runtime/`，一次性搬入 15 个模块**，改 30 条非测试 import + 51 条测试 import。
   这是一个 commit。它们内部高内聚，不需要分步。
3. **断唯一那条接缝**：

   ```
   services.episode_semantic_verifier → runtime.episode_finalizer   （runtime import，ERROR 级）
   ```

   修法用依赖倒置：在 `services/` 侧定义 finalizer 需要的 Protocol，让 `runtime/` 实现它。
   **不要**简单改成 TYPE_CHECKING —— 那只是把 ERROR 降成 WARN，耦合还在。
4. 门禁应报 `0 / 0`。

## B.5 验收

```bash
.venv-workbench/bin/python -m pytest intelligence/tests -q     # 见下方口径
.venv-workbench/bin/python scripts/layer_audit.py              # ERROR 0 条
```

### ⚠️ 基线口径：用总数，不要用 failed 数

**本分支测试总数 3819**（本文写时实测 `14 failed, 3805 passed, 2 skipped`；
另一时刻实测 `13 failed, 3806 passed` —— 两个都是真的）。

**"13 failed" 不是常数**，它取决于工作区状态：

- 工作区含 **tracked 修改** → 13 failed
- 工作区只有**未跟踪文件** → 14 failed，多出的正是
  `test_run_agent_runtime_benchmark.py::test_dry_run_records_exact_source_provenance`
  —— 即 agent B 正在 `fix/source-dirty-parity` 上修的那个 source_dirty 口径 bug

所以：**对账用 `passed + failed == 3819`，外加那 13 条宿主固有失败的具名清单**
（`test_userspace` 3 + `test_subconscious` 8 + `test_acceptance_board` 2）。
`fix/source-dirty-parity` 分支上总数是 3820（B 多加了一条回归测试）。

解释器必须 `.venv-workbench/bin/python`。`python3` 是宿主 3.14，缺依赖，
用它得出的"符号不存在""缺包"全是假的。

## B.6 坑

- **搬文件和改名分两个 commit。** 本版不要求改名（`episode_*` 前缀留着），
  但如果你顺手改，单独一个 commit——改名会砸掉 git blame 和现有 handoff 的行号引用。
- **顺手处理 `LEGACY_DETERMINISTIC_OWNER_TYPES`（`continuous_turn_adapter.py:67`）的名字。**
  实测全仓无任何文档说明它是"待清理的遗留"还是"有意保留的确定性快路径"——
  行为是后者（`external_market` / `quick_fact` / `dated_market_review` 三题型走确定性
  owner、不进 agent loop，这是对的设计）。名字里的 `LEGACY` 会让下一个人去删它。
- **本仓有 5 个 worktree**（主树 `refactor/extract-domain-from-harness`、`fwp-wt-srcdirty`、
  `fwp-wt-evaluator`、`fwp-wt-logic-match`，外加**生产快照** `.finance-runtime/finance-workspace-88b28ab4`
  也是一个 detached worktree）。⚠️ **别在主仓跑 `git worktree prune`——会删掉生产快照**（见 A.5）。
  动手前 `git status --short && git branch --show-current`。

## B.7 明确不在范围内

- ❌ 合并或删除引擎 B（`ask.answer_query`）——设计决定不是债，要等边界清了再谈
- ❌ 接通 `memory_lookup`（实测：全仓非测试代码零授权，结构性不可达）
- ❌ 改 `episode_protocol` 的系统提示词结构（实测：1,601 字符 / 4 个换行 / 最长无换行段 1,501 字符 / 24 条约束平铺）
- ❌ 补上下文压缩（实测：全树零实现，`messages` 只 append 不裁，已见 124K token 单次上下文）
- ❌ codex / A-B 对照线——用户已决定暂停；`codex_headless` 默认关闭（`AGENT_RUNTIME_BENCHMARK_ENABLE` 未设），不挡主线

以上五条都在**任务 B 完成之后**再排。

---

## 修订记录（2026-08-06 晚）

初版有四处错误，均已在本版修正。若你读过初版，请以本版为准：

| # | 初版 | 实际 | 根因 |
|---|---|---|---|
| 1 | 「前 6 个零依赖 loop 层，可直接搬」+ 一份 1→8 顺序 | **顺序错**。按初版顺序搬，接缝数轨迹是 `1→2→1→0→1→1→2→3→0`，非单调 | 排序脚本算"依赖 loop 层"时，集合里**不含这 8 个模块自己**，组内依赖（如 `episode_tools → research_tool_registry`）完全不可见。表里那列还标着"被引用"（入度），旁边却写"可直接搬"（另一套口径），两个数并排诱导误读 |
| 2 | 「全量基线 13 failed / 3807 passed」 | **两个数都不稳**。3807 是在 `fix/source-dirty-parity` 上测的（那条分支多一个测试）；本分支是 3819 总数，failed 数随工作区状态在 13/14 之间浮动 | 见 B.5 |
| 3 | 没写物理落点 | 已定：`intelligence/runtime/` 装 15 个 loop 模块，方向与初版相反 | 初版只说"搬出 harness"，而 harness 没有物理边界，"搬出"无处可去 |
| 4 | 把 `agent_runtime → episode_session` 列为"要断的边" | **不该断**。`episode_session.py` 是 91 行纯 Protocol（"Provider-neutral continuation seam"），与 `agent_runtime` 是同一契约单元的两半，TYPE_CHECKING 块存在正是为打断这对循环——教科书用法 | 初版把 `episode_session` 误分进 loop 层。修正后接缝从 2 条降到 **1 条** |

**给下一位的方法论**：第 1 条的形状值得记——**断言的对象和被检查的对象必须是同一个集合**。
这和 agent B 那次"回归测试永远绿"（断言读生产侧、变异改测试侧）是同一族错误。
排序/分层这类算法，验收方式应该是**模拟执行一遍看指标是否单调**，而不是读一眼表格觉得合理。

---

## 附：本轮已确认的架构事实（别再重新发现一遍）

1. **服务器里只有一条线。** `api/app.py` 是唯一部署；前端唯一下单口是
   `POST /api/conversations/{id}/messages` → `conversation_orchestrator`。
2. **一个调度器，两个引擎。** 引擎 A = `continuous_turn_adapter` → `agent_episode`；
   引擎 B = `ask.answer_query`（兜底 + 三个确定性题型）。**引擎 B 也调 LLM**，
   两者差别是"流程由代码定死"vs"流程由模型自己决定"，不是"用不用 LLM"。
3. **`agent.py` 不在服务器里。** `api/app.py` 从不 import 它；它只服务 `cli.py:304`
   和 `eval/runner.py:91`。是命令行工具，不是产品链路。
4. **`POST /api/runs` 前端不调**（构建产物里 `/api/runs` 只以 `/api/runs/${id}/...`
   形式出现），但它是崩溃后恢复孤儿 run 的兜底路径（`app.py:1698` lifespan），**别删**。
5. **契约层 6 个模块 3,758 行、自身全部干净**：`research_contract`(1246)、`task_frame`(686)、
   `agent_research`(1054)、`evidence_ledger`(265)、`evidence_capabilities`(254)、
   `research_plan`(253)。这是整套系统的语汇底座。
