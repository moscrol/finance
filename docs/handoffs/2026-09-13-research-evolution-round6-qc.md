# 研究进化 · 第五轮修复后的独立复核（第六轮 QC）

## 结论

**原第五轮 4 个固定缺陷钉已转绿，但候选集合仍不通过：新增确证 PV10/P1、J11/P2、J12/P2。**

只审查，不改候选代码、不 push、不合 main、不切生产。四个固定 SHA 分别检出在独立干净树；本报告不是 06 跨轨集成验收。

| 轨 | 本次固定 SHA | 上一轮固定候选 | 本次变更 |
|---|---|---|---|
| 01 | `d39b011e`（实现 `8127283d`） | `b886b796` | J8/J9/J10 |
| 02 | `e27b3352` | 同左 | 无 |
| 04 | `fcc7838c` | 同左 | 无 |
| 05 | `dd3e8ad0`（实现 `340d3b26`） | `15da570f` | PV9 |

01/05 的最终 tip 相对实现提交仅改交接/进度文档，未夹带其它实现变化。

## 1. PV10 / P1：有 run 时仍以任意组件费用核销整次尝试

定位（05 `dd3e8ad0`）：
- `intelligence/services/product_value/summarize.py:163–164`：`attempts` 非空直接返回无需补组件。
- `intelligence/services/product_value/measure.py:556–563`：`costed_runs/costed_attempts` 不区分组件；只要该 run/attempt 出现在任一费用条目中，就跳过 `no_usage_evidence_for_attempt`。
- summarize 的类别覆盖是全试点级，而不是逐任务/逐 run；别的任务已有 writer/review 后，本任务缺这两笔不会再被类别缺口挡住。

### 最小复现与合法对照

复用两份完整配对的构造器。第一份完整成本 CNY 0.46；第二份**保留真实解析成功的 run 事件**，仅移除其费用事件，再逐项补回账。冻结协议只适用 writer/review/tool。所有测量均经公开 `measure_pair → summarize` 入口，非手造收据。

| 第二份费用输入 | 实际完整成本状态 | 实际已知小计 | 应有状态 |
|---|---|---|---|
| 无费用 | unknown | CNY 0.46 | unknown（合法负控） |
| tool 0.01 | **known** | CNY 0.47 | unknown：writer/review 缺失 |
| writer 0.36 + tool 0.01 | **known** | CNY 0.83 | unknown：review 缺失 |
| writer 0.36 + review 0.10 + tool 0.01 | known | CNY 0.93 | known（合法正控） |

各例 `invalid_reasons=[]`、事件 `rejected=[]`，第二任务 attempt 的 `evidence_status=ok/run_status=completed`。这不是坏事件被接受、run 解析失败或无 run 路径的问题。

**归因：PV9 相邻遗漏，不是本轮新引入。** `15da570f` 修前对照读数相同。第五轮只覆盖 attempts 为空，helper 注释声称下游逐 attempt 已覆盖，但下游仍是按“有任意账”核销。

修复要求：费用覆盖必须按身份与组件联合核验；有 run 不得绕开模型组件缺口。保留失败重试、unknown/estimated 与覆盖层级去重语义；不能用其它任务的费用补本任务、不能用工具费补模型费，合法完整账仍 known。

## 2. J11 / P2：绑定创建日修了使用端，解析端仍按字符串前缀校验

定位（01 `d39b011e`）：`intelligence/services/judgment_maintenance/contracts.py:499–501`。

`created_day` 已换 `market_day_of`，但 `parse_binding` 仍执行 `baseline_cutoff > created_at[:10]`。将 baseline_cutoff 设为 `2026-09-12`：

| created_at | 上海日期 | 实际解析 |
|---|---|---|
| `2026-09-11T16:30:00Z` | 09-12 | **拒绝 baseline_cutoff_after_created_at** |
| `2026-09-12T00:30:00+08:00` | 09-12，同上时刻 | 接受（合法正控） |
| `2026-09-12T00:30:00+14:00` | 09-11 | **接受未来基线** |
| `2026-09-11T18:30:00+08:00` | 09-11，同上时刻 | 拒绝（合法负控） |

所以既会误拒合法 UTC 补录，又会因偏移写法放过晚于市场创建日的基线。第五轮 J9 测试把 baseline_cutoff 固定为 09-10，没走到这一条校验差异。

**归因：J9/J6 相邻遗漏，修前已有。** 应把解析端和使用端统一到同一市场日期函数，不能只改 property。不要求 UTC/上海写法的完整 ID 相同，只要求准入与业务日期语义一致。

## 3. J12 / P2：同 id 优先留 open 导致 supersedes 历史链成环

定位（01 `d39b011e`）：`intelligence/services/judgment_maintenance/assess.py:635–643`；上游 `build(... supersedes=previous_id)` 保留旧边。

直接复用第五轮“歧义消解”数据，无须增加事件：
1. 09-10 观察 h1→h2，生成 A。
2. 09-11 纯日期 h0 竞争，生成 B，`B.supersedes=A`。
3. 09-12 h0 过期，回到 h2；末态复用 A 的 id，`A.supersedes=B`。
4. 去重以最后的 open A 替换最初 A，留下 **A→B→A**。

实际输出：
- `jmi-56ced59c10c6e386`：09-11、superseded、回指 `jmi-7eb7f88d7161a205`。
- `jmi-7eb7f88d7161a205`：09-12、open、回指 `jmi-56ced59c10c6e386`。
- `items_open=1`、歧义 gap 在；但初态 A 已不在历史中，B 反而指向未来 A。遍历任何一项都会回到自己。

**归因：第五轮 J10 新回归。** 修前 `b886b796` 此输入无环，但因旧去重而丢 open；修复只解决了末态数量，没有保住替代链。

修复要求：明确“内容状态相同”与“同一次维护项出现”是否同一身份。可为再次出现的状态建立稳定 occurrence 身份，或另存转折历史并重新投影无环关系；不能随机加扫描时间打破幂等，也不能只截断一条边却宣称历史完整。需新增无环、先后顺序、重复扫描稳定性断言，保留原 open 与 gap 断言。

### 额外边界：旧管理动作复活（不另计确证缺陷）

构造同一 selected h2 的“无歧义→有歧义→无歧义”，在首态上登记合法 snooze，再对消解后报告执行公开 `reduce_actions`：首末态 `id/item_version` 相同，旧 snooze 被 `applied`，`items_open=1→0`。这不是旧 key 迁移问题，完全发生在第五轮新实现内部。

是否允许“内容回到已处理状态就继承旧管理动作”需要明确产品语义，故本轮不另列 P1。但不能仅凭 assess 的 open=1 宣布端到端待办保留；06 应覆盖已有 close/snooze、歧义出现与消解的管理事件回放。J12 的环本身不依赖此语义判断，已可独立判错。

## 4. 独立验证与收据边界

解释器均为主树 `.venv-workbench/bin/python`。候选工作树始末均 dirty=0。

| 层 | 本次结果 |
|---|---|
| 第五轮原安全断言 | **5 passed** |
| 第四轮原 test_adjacent | **4 passed** |
| 本轮新安全断言 | **5 failed / 1 passed**（3 根因：J11 两方向、J12 无环、PV10 两缺口；合法费用正负控通过） |
| 01 模块 | **108 passed** @d39b011e |
| 02 模块 | **65 passed** @e27b3352 |
| 04 模块 | **74 passed** @fcc7838c |
| 05 模块 | **114 passed** @dd3e8ad0 |
| 四轨全仓 ruff | 全 exit=0 |
| 归档复跑 | standards_01、standards_02_timezone、standards_04、standards_04_boundary、probe_05_extra 均 exit=0；不声称复跑了第一至四轮全部脚本 |
| 全仓 pytest | **本轮未重跑**；只核对下述固定收据，不把已有全量绿当新反例已过 |

全量收据核对属实：
- `20260913T141838Z-8127283d.json`：9648 passed / 77 skipped，dirty=false、failed_ids=[]、exit=0。
- `20260913T143105Z-340d3b26.json`：9654 passed / 77 skipped，dirty=false、failed_ids=[]、exit=0。
- 第四轮 `20260913T125455Z-197133f2.json`：失败确为 `intelligence/tests/test_workbench_conversation_integration.py::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`，不是 test_pipeline_p0。原汇报更正成立；本次没有重跑其隔离 3/3，也不据此单独证明 flaky 根因。

一次归档调度误用了不存在的 `standards_02_probe.py`，FileNotFoundError、exit=1；实际应为 `standards_02_timezone_probe.py`，纠正后 exit=0。原错误日志仍保留，不混成产品失败或隐去首跑。

## 5. 复现与归档

提交的探针：
- `docs/verification/research-evolution-round6/probe_round6.py`
- `docs/verification/research-evolution-round6/test_round6.py`

在本次四个固定检出树复现：

```bash
RESEARCH_EVOLUTION_QC_ROOT=/tmp/research-evolution-r6-qc-fgmhNt \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  docs/verification/research-evolution-round6/test_round6.py -rf
# 当前预期：5 failed / 1 passed。修复后应全绿。
```

单轨探针还支持显式第二参数 `/path/to/pinned/tree`，便于修前/修后对比。全部为本地仿真，imported 仅为夹具测试汇总分区，不写真人台账、不外呼模型、不读生产私有事实。

耐久证据目录：`~/.finance-runtime/reviews/research-evolution-round6-qc-20260913/`。含 manifest（四轨完整 SHA/干净状态/文件 SHA256）、adjacent/before 输出、fixed 第五轮输出、模块/ruff/归档/密封探针日志、核对过的全量收据。临时工作树 `/tmp/research-evolution-r6-qc-fgmhNt/{01,02,04,05}`。

## 6. 下一步与决定

1. 01 修 J11/J12；05 修 PV10。02/04 本轮不增加阻断项，仍保留候选，不等于集成通过。
2. 修复后同时跑原第五轮与本轮反例；J12 必须覆盖管理事件归约，而不只断言 open 数。
3. 06 再用最终 SHA 验证旧 key/旧动作衔接及跨轨输入；运行完整合入门禁后才谈合并，仍需用户确认。
4. 本次选择独立纯函数探针而非启动 UI 或全仓重跑：缺陷在纯领域合同内即可确定性复现，成本更低且不触碰共享生产。两份有效全量收据保留其原条件；不以新边界失败否认原固定反例已修。
5. 没有扩展公共工具或门禁：这是只审查授权，保存针对性自动反例交修复者，不越权改候选。可迁移教训是按作用域核验覆盖、验证器与消费者同用时钟函数，以及内容去重键不能无条件兼作历史节点身份。
