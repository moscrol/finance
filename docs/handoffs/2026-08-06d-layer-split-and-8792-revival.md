# Handoff — 8792 复活 + 领域/harness 分层拆分（2026-08-06d）

> 给 agent A。两个任务，**互相独立，可并行**。任务 A 是止血（生产 UI 现在打不开），
> 任务 B 是这轮架构讨论的落地第一步。
>
> 背景：用户评估过是否换 agent 底座（`earendil-works/pi` / OpenAI Agents SDK），
> **决定暂不换**，先把现有底座固定、把领域逻辑从 harness 里拆出来往上搭。
> 任务 B 就是"拆"的第一块，且**不管将来换不换底座都不白做**。

## 0. 一句话

- **A**：`.finance-runtime` 快照被删，软链悬空，8792 的 UI 返 503，且 launchd 一重启就彻底起不来。
- **B**：24 个 harness 模块里有 **7,511 行其实是领域逻辑**（金融语义判据、工具实现、路由表、证据校验），只是名字带 `episode_`。把它们搬出去。

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

# 任务 B — 把 7,511 行领域逻辑搬出 harness

## B.0 为什么

AST 实测（`intelligence/` 219 模块 / 122K 行）：

| 层 | 模块 | 行数 |
|---|---|---|
| harness | 24 | 22,900 |
| 入口层（`api.app` / `api.structured_reports` / `cli` / `eval.runner`） | 4 | 6,485 |
| **干净积木**（传递闭包不碰 harness） | **184** | **88,781** |
| **污染积木**（间接依赖 harness） | **7** | **3,851** |

边界比预想干净——**只有 7 个领域模块被污染，且其中只有 `services.lane_generation`
一个是直接 import harness**，其余 6 个（`workbench_skills.*` 5 个 + `services.kb_rag_selftest`）
都是间接沾上的。

但那 22,900 行 harness 里，**只有约 5,200 行是真·loop 骨架**（循环、provider 适配、
批次执行器、重试恢复——这批是可以不再自己写的）。另有 **7,511 行是领域逻辑穿了
harness 外衣**，必须留下并搬家。最典型的是 `episode_semantic_verifier.py`（**2,894 行**，
金融答案的语义 grounding 判据，全仓单个最大的领域文件之一）。

**本任务只做搬家，不做任何行为变更。**

## B.1 先立门禁（必须最先做，它是记分牌）

在仓里固化一条断言：**领域层模块不得 import harness 层模块**。

扫描脚本原型见本 handoff 附件 **`docs/handoffs/2026-08-06d-layer-scan.py`**
（仓根跑 `.venv-workbench/bin/python docs/handoffs/2026-08-06d-layer-scan.py`，已验可跑，
输出本文引用的全部数字）。把它改造后落成 `scripts/layer_audit.py`。要求：

- harness 白名单写成**显式常量**，不要靠文件名前缀猜（`episode_semantic_verifier`
  名字带 `episode` 但属领域，正是这个反例）。
- **输出必须自述审的是哪个 revision**——否则 `exit 0` 会被读成"main 上就是这样"。
  （这条来自 `2026-08-05` 交接记录的可迁移原则。）
- **以当前 7 条接缝为基线允许通过，只减不增**。每搬完一个模块基线减一。

## B.2 搬迁顺序（按实测依赖算的，前 6 个零依赖 loop 层）

| # | 模块 | 行 | 被引用 | 状态 |
|---|---|---|---|---|
| 1 | `episode_tools` | 1171 | 2 | ✅ 可直接搬 |
| 2 | `turn_controller` | 1211 | 3 | ✅ 可直接搬 |
| 3 | `research_tool_registry` | 729 | 12 | ✅ 可直接搬（引用最多，改 import 面最大） |
| 4 | `episode_protocol` | 439 | 3 | ✅ 可直接搬 |
| 5 | `episode_factory` | 341 | 1 | ✅ 可直接搬 |
| 6 | `episode_verifier` | 290 | 2 | ✅ 可直接搬 |
| 7 | `episode_semantic_verifier` | **2894** | 2 | ⚠️ 先断 → `episode_finalizer` 这一条边 |
| 8 | `agent_runtime` | 436 | 14 | ⚠️ 先断 → `episode_session` 这一条边 |

第 7、8 各只有**一条**指向 loop 层的边，断完即可搬。

## B.3 每搬一个的验收

```bash
.venv-workbench/bin/python -m pytest intelligence/tests -q    # 必须仍是 13 failed，其余全绿
.venv-workbench/bin/python scripts/layer_audit.py             # 接缝基线 -1
```

**全量基线：`13 failed, 3807 passed, 2 skipped`**
（`test_userspace` 3 + `test_subconscious` 8 + `test_acceptance_board` 2，宿主环境固有，
本轮已在 `fix/source-dirty-parity` 上实测复核过）。**多出任何一条都是新引入的。**

解释器必须 `.venv-workbench/bin/python`——`python3` 是宿主 3.14，缺依赖，跑出来的
"符号不存在""缺包"全是假的。

## B.4 坑

- **先搬位置、后改名，两步分开 commit。** `episode_*` 这批名字确实误导，但改名会砸掉
  git blame 和现有 handoff 里的行号引用。混在一个 diff 里没法 review。
- **一次一个模块、一个 commit。** 不要攒批。
- **顺手处理 `LEGACY_DETERMINISTIC_OWNER_TYPES`（`continuous_turn_adapter.py:67`）的名字。**
  实测全仓没有任何一处文档说明它是"待清理的遗留"还是"有意保留的确定性快路径"——
  它的行为是后者（`external_market` / `quick_fact` / `dated_market_review` 三个题型走
  确定性 owner，不进 agent loop，这是对的设计）。名字里的 `LEGACY` 会让下一个人去删它。
- **本仓有 4 个 worktree 各在不同分支**（主树 `main`、`fwp-wt-srcdirty`、`fwp-wt-evaluator`、
  `fwp-wt-logic-match`）。动手前先 `git status --short && git branch --show-current`。

## B.5 明确不在范围内

写下来免得顺手做了：

- ❌ 合并或删除引擎 B（`ask.answer_query`）——那是设计决定不是债，且要等边界清了再谈
- ❌ 接通 `memory_lookup`（实测：全仓非测试代码零授权，结构性不可达）
- ❌ 改 `episode_protocol` 的系统提示词结构（实测：1601 字符 / 4 个换行 / 最长无换行段 1501 字符 / 24 条约束平铺）
- ❌ 补上下文压缩（实测：全树零实现，`messages` 只 append 不裁，已见 124K token 单次上下文）
- ❌ codex / A-B 对照线全线——用户已决定暂停，且 `codex_headless` 默认关闭（`AGENT_RUNTIME_BENCHMARK_ENABLE` 未设），不挡主线

以上五条都在**任务 B 完成之后**再排。

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
   `research_plan`(253)。这是整套系统的语汇底座，任何底座迁移都要先在新环境说这套话。
