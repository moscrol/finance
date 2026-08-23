# align/switchboard-catchup

## 目标

让 `main` 和解耦版（`docs/capability-switchboard`）**逐步对齐**，并用三/四臂 trace diff 量两件事：

1. **服务层损耗**：组件臂（进程内直调）vs 服务臂（HTTP），代码相同，变量只有服务层。
2. **分支差异**：main 服务臂 vs 解耦版服务臂，服务层相同，变量只有分支。

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

### 任务 C：把组件臂脚本固化进仓

组件臂现在是一次性脚本，躺在产物目录里：
```
~/.finance-runtime/trace-diff-spt-fengyuan-history-20260823/codex-component/run_component_arm.py
```

它直调 `TurnControlCore` + `perspective_lab` / `reading_baseline` / `finance_query` /
`market_regime_analogs` / `research_contract`，**不经 HTTP、不经会话编排**。

问题：**每次重写就没法跨次比较**。对齐是持续过程，读数必须可比。
按仓里「可复用组件必须归位，不留在一次性脚本里」的规矩，把它搬进 `scripts/`，
参数化题面 / 用户 / 快照路径 / 输出目录，其余装配顺序**逐字不动**
（改了装配顺序，它就不再是同一个地面真值）。

### 任务 D：跑 2×2，先只看结构字段

```
              组件臂(进程内)    服务臂(HTTP)
main             A1               A2
解耦版           B1               B2
```

- `A1↔A2` = 服务层损耗 @main　　`B1↔B2` = 服务层损耗 @解耦版
- `A2↔B2` = 分支差异（服务层）　`A1↔B1` = 分支差异（领域层）

**这一轮只比结构字段**，它们是确定性的，单次就能比：
`question_type` / `operators` / `retrieval_stages` / `evidence_plan.profile` /
证据条数 / 是否有 `[D10]` 块或 gap 标记。

⛔ **这一轮不要比答案文本、不要打质量分。** 已实测：8792 与 8796 在**同一目录、
同一份字节、请求 SHA 相同**的条件下，`answer_sha256` 仍然不同
（`4042d5e8…` vs `a1d87472…`）。噪声地板非零，单次跑出来的「质量差」
分不清是分支差异还是模型抖动。质量对比等结构对齐之后另立一单，那时才值得花 n 次跑。

输出按既有 `trace-diff-manifest-1` 格式（参考
`~/.finance-runtime/trace-diff-spt-fengyuan-history-20260823/manifest.json`），
并**新增一个 `arm_deltas` 字段**：明写本次每两臂之间的已知差量（revision / 依赖指纹 /
配置 / 端口 / users_dir）。**差量 > 1 的配对不做因果归因，只记录现象。**

题面用冻结题（照抄，禁止改写）：
```
用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。
```

### 任务 E：差集台账（对齐的收口物）

对齐不要靠肉眼读报告。每次跑记下**哪些结构字段两臂不一致**，把这个集合往空里推。
形状照抄 `scripts/replay_operator_routing.py`——它已经在做「两次运行的命中集合做差集，
让『这次改动动了哪些 query』变成机械可查的事实」。

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
- 组件臂按设计**不走服务 harness，但走领域 harness**（它 import 的就是
  `intelligence/services/*`）。所以它不是「无约束基准」，是「去掉服务层的同一套领域逻辑」。
