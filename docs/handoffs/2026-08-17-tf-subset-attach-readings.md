# T-F 摘接小窗读数：EpisodeScope + 工具阶段

- 日期：2026-08-17
- spec：`docs/superpowers/specs/2026-08-17-tf-subset-attach-design.md`（#139 `ef5cb9e4`）
- 计划：`docs/superpowers/plans/2026-08-17-tf-subset-attach.md`（#141）
- 底座 / 臂 0：`/Users/a77/fwp-wt-tf-arm-a-83e83b42` @ `83e83b429965a7c084443dbfc775532e92960366`
- 摘接来源：仅 `2a2523f7d26c666ee398d2da730d13cdee778c85`（不是当前 main）
- 臂 1：`/Users/a77/fwp-wt-tf-arm-1-subset` 分支 `tf/subset-attach-arm1`，HEAD 仍是底座；11 路 staged 未提交
- 收据：`~/.finance-runtime/tf-subset-20260817/graft-scan.txt`、`pytest-gate.txt`

## 0. 一句话

**这一对摘不干净。** 工程门在旧 `test_agent_episode` 红了；按 spec §6.2 / §8 停，未开烟测，未开 5×5，不开 900，不退整包 A′。

「吸收兑现」不在本窗结论集里。

## 1. 工程门

| 项 | 结果 |
|---|---|
| `git diff --name-only 83e83b42` | 恰好 §4 白名单 11 路 |
| §5 路径 | `forbidden_hits []` |
| 禁止名单 import（白名单文件） | `import_hits []` |
| 四个新测试 | 37 passed |
| `test_agent_episode.py` | **1 failed / 89 passed** |
| `test_continuous_turn_adapter.py` | 70 passed |
| `scripts/layer_audit.py` | ERROR 0 |
| dry + live 烟测 | **未跑**（§6.2 已红） |
| 5×5 | **未跑** |
| 8792 `model_load_count` / `source_revision` | **未碰** |
| 臂 1 提交 | 未提交。pre-commit `unread-fields` 要给 `episode_scope` 找读者，读者在禁止取的 `glm_agent_runtime.py`；未 `--no-verify`，未取 §5 |

失败测试：`test_progress_sink_observes_append_only_events_before_and_during_model_work`。

sink 观察到的 kind：

`task, model_turn, plan, mode_decision, model_turn, tool/pre_execute, tool/result, tool_request, tool_result, model_turn, finish`

durable `outcome.events`：

`task, model_turn, plan, mode_decision, model_turn, tool_request, tool_result, model_turn, finish`

多出来的两条只在 live 车道：`tool/pre_execute`、`tool/result`。durable 的 `tool_request` / `tool_result` 仍在。这与摘进来的 `agent_episode.py` D3 注释一致：`tool/*` 走实时出口，不进 ledger。

分类：

- 不是缺 `EpisodeScope` / `TOOL_*` / `LiveEventSink`（符号能解析，四个新测试绿）。
- 不是整包测试咬合（adapter 70 全绿；失败信息不含 `runtime_handle` / `research_profile` / `dsh_stub` / `episode_projection`）。
- 是旧断言 `sink kinds == ledger kinds` 与「这一对」的 live 车道设计打架。

整包 A′ 把同一测试改成了「sink 是两条车道的共同出口，durable 是子集」。那份 `test_agent_episode.py` 相对底座 +251 行，并且 `from intelligence.services.episode_projection import project_durable_events`，还大量构造 `GLMAgentRuntime`。整取该测试文件会拖进 §5 符号；只改底座上那一行断言则违反「不准为过门改断言」。过不了门，也不准靠禁止名单过门。

## 2. 主表（§7 三行；本窗未采集）

| 行 | 口径 | 本窗 |
|---|---|---|
| 还能跑 | 每臂 `runner_exception` 数；`trace_count_ok` 为 True 的条数 / 有事件条数（空事件单独报） | 未采集。工程门未过，10 次 live 未跑 |
| 墙钟 | 每臂 `latency_seconds` min / 中位 / max；`median(臂1)/median(臂0)` | 未采集。n=1 烟测也未跑，没有墙钟可写 |
| 修复 | 进入 `repair_goal` 的次数；其中末条 finish ∈ {`repair_model_finish`,`repair_model_stop`,`model_finish`} | 未采集。不加跑 |

repair 仍禁止用臂级 `stop_reason`（诚实闸会改写成 `numeric_lineage_gap`）。

> **更正（2026-08-17 晚，写于 #144 复核）**：括号里那个理由**即将失效**。
> #144 的 `2ed2fbb9` 删掉了 `_run_research_arm` 里那段把臂级 `stop_reason` 改写成
> `numeric_lineage_gap` 的代码（缺口仍记在 `issues`）。**#144 合入 main 之后**，
> 这一个污染源就没了。
>
> 但别据此直接把 repair 行改回读 `stop_reason`：本页写这条禁令时只点名了这一个
> 污染源，**没有穷举过别的**。要恢复，先自己搜一遍还有谁在改写臂级 `stop_reason`，
> 并说明结论对哪个 revision 成立。在 #144 合入前，本页正文的写法仍然成立。Trace 对账仍要求**有事件**；空事件是 `None`，不是通过对账。本页没有 10 个 json，不调用 resolver，也不编数字。

## 3. 判定

spec §8 三选一：**这一对摘不干净。**

依据：§6 工程门第 2 条失败（改了 `agent_episode.py` 之后对应旧测试红）。编译和四个新测试、层级门、§5 扫描都过，但完成标准是全过才开 5×5。

不是「接得上但慢了」：没有墙钟样本。不是「接得上、数量级没炸」：工程门没过。

## 4. 下一块怎么选

下一块不要再做「另一个不太能动延迟/repair 的可行性窗」。二选一：

1. **选可能动可判指标的接缝**：RuntimeHandle（取消 / 排空 / close）。这要先做 §9.2 失败注入，否则 cancel/resume 样本永远是 0。另开 spec，不并进 900。
2. **承认吸收收益不在可判指标上**：改判形状价值（T-E 静态对照 / Scope.dump 可达性收据），不再用墙钟证明吸收兑现。

不要接着摘 ResearchProfile 或 dsh stub 再开一个 5×5——那还是可行性探针，结论集不会出现「收益」。

本窗连「能跑、没变慢」都没走到：EpisodeScope 是授权门、工具阶段是纯观测，本来就不太会改善延迟/repair；先卡在旧测试与 live 车道的焊点上。用户看过读数再开下一块 spec。
