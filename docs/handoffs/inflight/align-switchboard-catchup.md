# align/switchboard-catchup

> 已让位。P0 对齐 + 8796 切流看 `align-switchboard-p0.md`。本文是并 `#345` 时的取证派工，不要当当前切流。

## 目标

两件**不同性质**的事，不要混成一个实验：

1. **Workbench ↔ 组件臂：正交层归因。** 相交那层（同一份 DuckDB、`decide_turn`、D10、
   `FinanceQuery`、`perspective_lab`、`reading_baseline`、`TurnControlCore`）P0 之后这道题
   已经对齐，**不是质量差的来源**。差距只能出在正交层，即 Workbench 独有的三处：
   **谁点下一刀 / 谁执笔 / 端上桌怎么剪**。
2. **main ↔ 解耦版：等价性检查。** 目的不是质量，是「解耦版更干净、更好搭、组件能单独测」。
   所以要验的是**行为没变**，不是**谁答得好**。

⛔ **任务 A / B / D 与「对齐组件臂质量」无关，不得串读。** A 是棘轮基线卫生；B + D 是
第 2 件事（main 和解耦版行为等不等价）。只有**任务 C** 服务于第 1 件事。把它们读成
「对齐组件臂」的连续步骤，会把结论重新引回相交层。

⛔ **本单只取证，不修。** 没有任何一条任务是「修发布门 / 修 complete 灯 / 让模型写出
组件臂那样的答案」。取完证再决定修什么，顺序不能倒。

### 相交 / 正交划分（本题成立，别再回头怪 D10 或题型信封）

| | 内容 |
|---|---|
| **相交** | 数据事实（DuckDB `fact_*`）；积木（`decide_turn` / D10 / `FinanceQuery` / `perspective_lab` / `reading_baseline`）；薄适配器 `TurnControlCore`（只收成 `TaskFrame`，不跑工具不写答案） |
| **正交 · Workbench 独有** | 入口（浏览器→FastAPI→会话）；底座 loop（`conversation_orchestrator` 管回合预算 / `agent_episode` 让模型自选工具 / `glm_agent_runtime` 执笔）；发布门（gate / 投影 / `business_status`）；技能层产品壳（`skill_mode` / 技能列表——组件臂根本没传这套旗标） |
| **正交 · 组件臂独有** | 人手写死 10 次 `FinanceQuery`；`answer.md` 是编码时写死的 f-string 模板（零模型调用）。**这是评测脚本，不是产品层** |

管道层、策略回测、仓内三十来个 skill 在这道题上两边都不是主路径，**不算相交也不算正交打分项**。

## 已完成（本分支，`75de5ed3`）

把 `gitea/main@3ac070a2` 并进解耦版，**消掉 9 个提交的滞后**。

为什么先做这个：对齐前解耦版领先 main 21 / 落后 9。落后那 9 个里含今天合的 P0（#345）。
不消掉就去比，差集里会混进「只是没跟上」这种平凡原因，说不出对齐还差多少。

- 唯一冲突在 `intelligence/services/asof_prefetch.py` 的 import 块，两侧都是新增、无语义冲突，两块都留。
- 合并后核对：P0 三处改动都在；ruff 绿；定向 133 passed；全量 **1 failed / 6187 passed / 13 skipped**。

### 那 1 条红是存量红，不是合并引入

```
test_capability_switchboard.py::test_noop_prompt_added_no_branch_to_the_loop
```

同一条在合并前的 `1c52e19f` 上**同样失败**（已在独立检出复核）。根因是**门禁基线过期**：

| | 值 |
|---|---|
| `SPEC_BASELINE_REV` | `4e0c6bf5`（2026-08-22） |
| 被判违规的改动 | `1c52e19f` 对 `intelligence/runtime/agent_episode.py` 的 +58/-1 |
| 那个改动是什么 | 即 #344「写作轮借到 20s 地板」，已独立评审并合进 main（`1bd734d9`，2026-08-23） |
| 基线是否含它 | **不含** → 棘轮没上调，门禁把已接受的改动当成新增拦下 |

**不是设计违规。** 门禁本身在正常工作（守着「零件应挂已有的缝，不得改 loop」），只是基线落后于一次已接受的改动。

---

## 待办任务

### 任务 A：上调门禁基线（小，做完这条全量就绿）

`intelligence/tests/test_capability_switchboard.py:36` 的 `SPEC_BASELINE_REV = "4e0c6bf5"`
推到含 #344 的修订（建议 `3ac070a2`，即本次并进来的 main tip）。

**只改基线常量，不许改断言、不许把 `agent_episode.py` 从 guarded 列表里删掉。**
删掉守护项等于永久放弃这道门禁；上调基线是棘轮的正常动作（存量免检、新增仍拦）。

改完跑：
```
.venv-workbench/bin/python -m pytest intelligence/tests/test_capability_switchboard.py -q
```
预期：48 passed。若还有别的 guarded 文件被判违规，**停下来报告**，那才可能是真违规。

### 任务 B：立一条 main 臂（不动生产）

现状实测：
```
/Users/a77/finance-workspace-runtime → ~/.finance-runtime/finance-workspace-1c52e19f9957
8792（生产默认）→ 同上   FORESIGHT_USERS_DIR=~/.local/share/finance-workbench/users
8796（隔离写根）→ 同上   FORESIGHT_USERS_DIR=~/.local/share/finance-workbench-capability-sidecar/users
```

**两个端口跑的都是解耦版。** 所以「main vs 解耦版」现在做不了——会变成解耦版 vs 解耦版
（早上那次三臂零差量就是这个原因）。

要做的是**另起一个端口跑 main**，8792/8796 一律不动：
- 新建一份 main 的运行快照（参考 `scripts/deploy_workbench_runtime.sh` 的做法；
  该脚本头部记着 2026-08-08 那次事故：合并了 ≠ 生产跑上了，而 health 的
  `source_revision` 会**前进**得像已经生效，取证只认快照里的文件）
- 给它独立的 `FORESIGHT_USERS_DIR`，不要复用上面两个
- 端口自选，记进 manifest

⛔ 不重启 8792/8796，不改它们的环境变量，不动 `finance-workspace-runtime` 这个 symlink。

### 任务 C：正交层 trace diff（Workbench ↔ 组件臂）

#### 取证臂钉死（这条不写死，结论会被带回相交层）

**Workbench 侧只准用这一次 run：**

```
run_id   run_20260823_114116_434045
revision 3ac070a2   source_dirty=False   code_matches_repo=True   port 8798
落盘     ~/.local/share/finance-workbench-prefetch-replay/users/
           prefetch-replay-p0-20260823/runs/run_20260823_114116_434045/
             answer.md 4.4KB / continuous-episode.json 190KB / trace.jsonl 13KB
             stream.jsonl 53KB / report.json / run.json / followups.json
```

**第一步是把这个 run 目录捞进 `~/.finance-runtime/prefetch-replay-20260823/`。**
重放那次只把信封和开场预取写进了产物目录，运行时落盘是完整的——
`continuous-episode.json` 顶层含 `events` / `traces` / `phase_trace` /
`structural_verifier` / `semantic_verifier` / `repair_attempts` / `repair_cycles`，
且 `draft` ×11、`projection` ×4、`business_status` ×2、`tool_call` ×16。
**投影前的稿和端上桌的稿都在，第 3 点能直接逐字 diff。不需要重跑。**

⛔ **禁止**用 `trace-diff-spt-fengyuan-history-20260823/` 的 `workbench-8792` /
`workbench-8796` 两臂做本任务。那两臂在 `1c52e19f`，**P0 之前**，空 manual 还在盖信封，
相交层当时是坏的。拿它比第 3 点会重新看见「没 D10」，把结论又怪回题型信封。
那个实验目录里**只有 `codex-component/` 可用**（它不受空 manual 影响）。

**组件臂侧用已冻结产物，不重跑、不固化进仓：**

```
~/.finance-runtime/trace-diff-spt-fengyuan-history-20260823/codex-component/
    answer.md  trace.jsonl  turn-control.json  evidence.json  run.json
```

⛔ **不比相交层。** `question_type` / `operators` / D10 有没有——P0 之后已对齐，
live 重放也验过。再去比是浪费，而且会把结论又引回 D10 和题型信封。

#### 三个点，只有一个是修法目标

| # | 决策点 | 怎么读 |
|---|---|---|
| 1 | **谁点下一刀** | **只记形状，不设对齐目标。** 模型自选工具 vs 人写死 10 次 `FinanceQuery`，本来就会不同，那是产品形状不是缺陷。**要找的是 loss**：某次 `tool_call` 有结果，但结果没进最终证据 |
| 2 | **谁执笔** | **只记形状，不设对齐目标。** 组件臂那份是离线打磨的模板（见「已知边界」），不是同一种执笔方式。**要找的是 loss**：拿到 N 条证据，最后一盘菜被剥成两句 |
| 3 | **端上桌怎么剪** | **唯一的修法目标。** `draft` → `projection` → 终稿逐字 diff，看被剪掉什么；`business_status` 是在什么条件下判成 complete 的 |

第 3 点是**首要嫌疑**：8796 那次的现象是「**菜还在、盘子被剥空**」——证据取到了，
是发布层把它剪没了。先看这一刀，再看前两刀。

**该修的正交失败只有 loss 这一类**：点到了却端不上桌、一盘菜被剥成两句。
「点得不一样、写得不一样」不是病。任何写成「让模型追齐组件臂」的结论，退回重写。

### 任务 D：main ↔ 解耦版等价性检查（不是质量对比）

目的是「解耦版更干净、更好搭、组件能单独测」，所以要验的是**行为没变**。

同一道冻结题打两条服务臂，**只比结构字段**：
`question_type` / `operators` / `retrieval_stages` / `evidence_plan.profile` /
证据条数 / 有没有 `[D10]` 块或 gap 标记。**差集应为空。**

⛔ **不比答案文本、不打质量分。** 已实测：8792 与 8796 在**同一目录、同一份字节、
请求 SHA 相同**的条件下 `answer_sha256` 仍不同（`4042d5e8…` vs `a1d87472…`）。
噪声地板非零，文本差异说明不了任何事。

「更干净、组件能单独测」这两条**不用跑题验**，用现成的结构手段即可：
`scripts/run_capability_switchboard.py --all-arms`（每颗开关关一次，看正控/负控是否成立）
加上每次 commit 都在跑的层级门禁。跑不动的那颗，就是还没解耦干净的那颗。

输出按既有 `trace-diff-manifest-1` 格式，并**新增 `arm_deltas` 字段**：明写每两臂之间的
已知差量（revision / 依赖指纹 / 配置 / 端口 / users_dir）。**差量 > 1 的配对不做因果归因。**

题面用冻结题（照抄，禁止改写）：
```
用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。
```

---

## 红线

- 不 push、不合 main，等用户确认。
- 不动 8792/8796/生产 symlink。
- 解释器一律 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 任务 A 只改基线常量。任何「把断言改松就绿了」的做法，停下来报告。

## 已知边界

- 本分支合并后**未跑 live**，只有离线测试。
- 今天的 P0 只保证 **Engine A 预取路径**的 D10 无穿越；Engine B（`ask.py`）与
  `stock_analogs` 仍未按 as_of 截断。
- 组件臂走**相交层**的领域积木（`TurnControlCore` / 判读基线 / 视角 / 信息截止日 / D10），
  但整条正交栈都不走。实测 `run_component_arm.py`（492 行）对
  `verifier` / `gate` / `business_status` / `allowed_capabilities` / `budget` /
  `episode_tools` / `research_tool_registry` / `orchestrator` 的调用**全部为 0**。
- **组件臂的 `answer.md` 是 f-string 模板，不是运行时生成的。** 脚本第 396 行
  `answer = f"""..."""`，全脚本**零模型调用**（openai / anthropic / glm / client / chat / llm
  全为 0）。数据是现算插值的（D10 窗口、成交额、涨停数），**叙述是 Codex 编码时写死的**——
  看过一次数据、想过、改过，才写进脚本；重跑数字会变、句子不变。
  所以它是**「拿同样的料离线打磨出来的样品菜」**：
  - ✅ 它证明**料够**——同一批证据能写成那样，问题在生成与发布环节（这是存在性证明）
  - ⛔ 它**不走 harness 发布契约**，未经质检、未经投影。**不能当质量天花板，更不能当契约。**
    拿它当基准等于拿一篇改过的稿子去比现场即兴，不公平也不可执行。
- 「遵不遵守契约」是**调用路径**的属性，不是 agent 的属性。脚本 import 到哪儿，约束就到哪儿；
  绕过的部分不会报错。这也是插件化的前提：**契约要下沉进零件**（如 D10 的 `as_of` 截断做在
  取数层，下游谁调都绕不过），靠上层编排调用的约束，每条新装配路径都能静默绕开。
