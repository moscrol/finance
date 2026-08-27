# 工单：工具「授权 → 调用」差值遥测（2026-08-27）

- 状态：**待认领**。P0 零运行时改动可独立领；P1 依赖 P0 定下的口径，不要并行开。
- 来源：2026-08-27 harness 回程边审查建议 2。审查原稿有三处表述问题（worktree 数标错命令、
  Open 表只报 3/7 个状态、`grep` 有命中却写成「零命中」），已在本单修正——本单所有数字
  自带命令与分母。
- 基座：`gitea/main@fea0633e`，干净树 `/Users/a77/fwp-wt-tool-usage-differential`，
  分支 `feat/tool-usage-differential`。**未动主检出**（其上另一 session 的
  `docs/macro-map-and-code-map-refresh` 脏树在途）、未动 8792/8796/8802。
  ⚠ 本单写作时 `main`(本地) 已前进到 `e4276e00`（一行 ledger 表头改动，PR 未合入
  `gitea/main`）。若本单落地时 `e4276e00` 已合，`docs/prediction-ledger.md` 表头会有
  一行冲突，取主干版即可——本单只在 Open 表尾追加行，不动表头。
- 台账：**预注册 `R-20260827-08`，且台账行与本单同提交**。
  理由：`scripts/audit_ledger_spec_crosswalk.py` 正向门要求 spec 引用的号在台账
  有且仅有一行，缺行报 error。分两次提交就是自己破自己的门。

---

## 0. 一句话

工具面有两条边，我们只装了一条的传感器：**「要了没有」有 `tool_hunger`，「有了没要」零遥测。**

本单先用**已有产物离线把第二条边量出来**——不改运行时、不加门、不动执行路径。

---

## 1. 形状（为什么这条边重要）

`intelligence/services/tool_hunger.py` 的 docstring 逐字：

> Hunger means the model asked for a capability the closed registry could not serve.

三个事件 `unknown_tool` / `finance_query_rejected` / `capability_denied` 全部是「问了、被拒」。
引擎 A 的定义是模型自选工具，所以**「授权了、声明能填、但模型压根没问」是它的结构性风险面**，
而这一侧现在没有任何计数器——因为模型没问，不会触发任何 hunger 事件。

这不是推测。`docs/handoffs/2026-08-22-r3-capability-alignment-closeout.md` 自己记了：

> KB 只参与 5/9 题——**episode 层路由随机本身是个值得留意的形状，尚未立案**

本单就是给那句「尚未立案」立案，并且把 n 从 9 提到 700+。

---

## 2. 关键发现：两半数据**已经在同一个产物里**

这决定了 P0 不需要碰运行时。

`intelligence/runtime/continuous_turn_adapter.py:1084-1094` 组装的私有产物，经
`conversation_orchestrator.py:4073` 以 `run_store.add_artifact(run_id, "continuous-episode.json", ...)`
落盘。里面同时有：

| 半边 | 字段 | 含义 |
|---|---|---|
| 声明侧 | `satisfiability_precheck.checks[].contributing_tools` | 本次**授权工具集内**声明能产出该 output 的工具 |
| 实际侧 | `events[]` 中 `kind == "tool_request"` 的 `payload.name` | 本轮真正被调用的工具 |

`contributing_tools` 是在 `authorized_specs(contract.allowed_capabilities)` 上算的
（`research_tool_registry.py:1148` `check_satisfiability`），所以差值天然就是
**「本次授权 ∧ 声明能填 ∧ 从未被调」**，不需要另外再判授权。

`tool_request` 是对账权威——`agent_episode.py:694` 明写这三个事件「一字未动」。

---

## 3. 本轮实测基线（不是推断）

### 3.0 ⚠ 判据口径必须先钉死（否则 §8 第 1 条是个假判据）

**本单的基线数是用一次性内联脚本算的，那个脚本没有留存。**
如果只写「四组数逐个相等」而不写怎么算，实施方任何一处口径差都会让判据失败——
**而失败原因是 spec 欠定义，不是实现错**。所以口径在此逐字钉死：

```text
样本      = glob("$FORESIGHT_USERS_DIR/*/runs/*/continuous-episode.json")   # 不按 user 过滤
sp        = doc["satisfiability_precheck"]        # 缺该键 → 整份跳过
checks    = sp["checks"]                          # 空 list → 计入「有 checks」分母？否，见下
called    = { e["payload"]["name"]
              for e in doc["events"] if e["kind"] == "tool_request" } - {None}

「有 checks 的 run」 = checks 非空                                    → 735
declared(run)        = ⋃ c["contributing_tools"] for c in checks
「可算差值的 run」   = declared(run) 非空                             → 698
「有差值的 run」     = declared(run) - called ≠ ∅                     → 572
工具级分母           = 该工具 ∈ declared(run) 的 run 数
工具级分子           = 且该工具 ∉ called 的 run 数
output 实例级差值    = Σ over checks: c["contributing_tools"] 非空 且 与 called 交集为空  → 425
suspicious 实例      = Σ over checks: c["status"] == "suspicious"     → 1193
```

判据改为：**同一口径下重算相等**。口径不同则先对齐口径，不算判据失败。

⚠️ **离线脚本不带、也不应带归一步骤。** 归一钩子（`_normalize_output_id`）由 runtime
在**写入侧**注入（`continuous_turn_adapter.py:1551`），且 `check_satisfiability` 存进产物的是
**原始 `output_id`**、归一只用于匹配。基线表里 `direct_assessment`(123) 与 `direct_answer`(107)
分列两行就是证据。读取侧再加一套归一，两族会合并、§3.2 表变样、验收 1 必然过不了。

**可迁移**：**规范化做在写入侧，读取侧就不得再带一套**——否则两份归一表必漂，
且漂的时候读数依然自洽。这是「单一真本源」在数据管线上的投影。

样本：`$FORESIGHT_USERS_DIR/*/runs/*/continuous-episode.json`，**747 份，2026-08-08 → 2026-08-27**。

**样本成分必须写清，别当成生产用户体验**：387 份在 `linxiaoqi5111`/`a77`/`default` 名下，
360 份在显式探针/评测 id 名下（`longtail-ab-0816` 88、`probe-v6-0821` 51 等）；
且即便前者也混有评测批跑（同一冻结题重复 15-22 次）。
样本还**横跨多个 revision**，其间工具集、produces 表、契约逻辑都变过。
**这是「机制存在性」的基线，不是「产品质量」的读数。**

### 3.1 粗口径（run 级）

可算差值的 run **698**，其中至少有一个「声明能填但没被调」的 run **572 = 81.9%**。

| 工具 | 被声明为 contributor 的 run | 其中未被调 | 未调率 |
|---|---:|---:|---:|
| `kb_search` | 603 | 406 | **67.3%** |
| `web_search` | 89 | 83 | 93.3% |
| `news_search` | 120 | 89 | 74.2% |
| `evidence_lookup` | 84 | 55 | 65.5% |
| `l3_lookup` | 5 | 3 | 60.0% |
| `graph_lookup` | 199 | 99 | 49.7% |
| `market_data` | 459 | 171 | 37.3% |
| `mainline_context` | 59 | 14 | 23.7% |

`kb_search` 67.3% 与 08-22 那句「KB 只参与 5/9」（≈56% 未参与）**同形，且 n 大 67 倍**。

### 3.2 尖口径（output 实例级，推荐作为正式判据）

粗口径会高估：一个工具声明 `supporting_evidence`，不等于每轮都该调它。
更尖的口径是**按 output 实例**数「该 output 有声明 contributor，但一个都没被调」：

有 checks 的 run **735**，命中 **425 个 output 实例**：

| output_id | 实例数 |
|---|---:|
| `direct_assessment` | 123 |
| `direct_answer` | 107 |
| `chain_mapping` | 99 |
| `prime_news` | 39 |
| `prime_quote` | 30 |
| `supporting_evidence` | 21 |
| `company_mapping` | 5 |
| `relation_map` | 1 |

`chain_mapping` 99 尤其值得先看：产业链映射是硬需求，`graph_lookup` 声明了它，却整轮没被调。

---

## 4. 成立边界（**这一节是本单最容易被跳过、也最容易翻车的地方**）

### 4.1 循环依赖：这把尺子的量程 = produces 表的质量

差值遥测**只能看见「有工具声明过」的 output**。produces 留空的工具永远不当 contributor，
于是：

- **正向（该调没调）：抓不到。** 空 produces 的工具在任何一格都不是 contributor，
  它没被调也不会进差值。
- **反向（调了但没声明）：可见。** 这是唯一能发现声明表漏项的方向。

**同一份数据已经量出这个盲区有多大**：`suspicious`（有工具声明了 produces，但没人声明这个
output_id）实例 **1193**，是 425 的 **2.8 倍**。也就是说**这把尺子看不见的比看得见的多**。

所以 P0 的产出必须**同时报两个数**（425 与 1193），并且**禁止**把 425 单独拿去当
「路由缺口总量」——那会把声明表的洞读成模型的洞。

### 4.1b 第二个高估源：425 **没有**检查那格最后是否真的没填上

`contributing_tools` 里没有一个被调用 ≠ 那个 required_output 空着。它仍可能被
**声明表没覆盖的工具**填上（正是 §4.1 那个盲区的镜像），或被 harness 预取的证据填上。

所以 **425 是上界，不是「真实漏填数」**。要拿到下界，须再与本轮 outcome 的
`gaps` / 未填 required_output 求交——**本单没做这一步**，实施方若要下更强结论必须补。

结论：425 同时受两个方向污染——§4.1 让它**低估**（空 produces 的工具进不了分子），
本节让它**高估**（填上了也算差值）。**它是一个「值得看一眼」的信号，不是一个可下结论的度量。**

### 4.2 这个盲区不是假想：`memory_lookup` 刚发生过

能力图谱 `finance-agent-capability-graph.md:210` 至今写着 `memory_lookup` 的 `produces`
「**有意留空**」「永远不当 contributing_tool——属 fail-open 的漏抓」，
而 main 上实际是 `frozenset({"prime_memory"})`（`d36f43e2` 加，测试已改名
`test_memory_lookup_declares_prime_memory_only`）。`graph_audit.py` 仍 exit 0，
因为它校验 `path::symbol` **存在**，不算符号的**值**。

**本单逮到的这处漂移和本单提议的差值法是同一枚硬币的两面**：声明表漂了，尺子就跟着漂，
而且漂的时候读数依然自洽。所以 4.1 那两个数必须并排出现，不能只报一个。

---

## 5. P0 · 离线差值审计（零运行时改动）

**交付**：`scripts/audit_tool_usage_differential.py`

**输入**：`$FORESIGHT_USERS_DIR/*/runs/*/continuous-episode.json`（可 `--since` / `--user` 过滤）

**输出**（JSON + Markdown 双份，落 `intelligence/eval/measurements/`，与 `tool-hunger-*` 同目录同命名族）：

1. run 级：可算差值 run 数、至少一处差值的 run 数与占比
2. 工具级：声明为 contributor 的 run 数（分母）、其中未被调数、未调率
3. output 实例级：425 那张表
4. **`suspicious` 计数（1193 那个数），与 3 并排**，且输出里写明 §4.1 那句「尺子量程 = 声明表质量」
5. 自述：样本份数、日期跨度、**revision 跨度**、探针/评测 id 占比

**硬性要求**：

- **只读**。不写 run 目录、不改任何产物、不进请求路径。
- **口径自述**。输出头部必须打印「本读数对哪些 run、哪个日期窗、样本成分如何」——
  这条是本单来源审查踩过的坑（读数不带对账目标，事后无法裁决）。
- **分母显式**。每个比率必须同时打印分子分母，禁止只给百分比。

---

## 6. P1 · 前向遥测（依赖 P0 口径，**不要并行开**）

P0 跑通、口径稳定后，把同一差值写进 run 目录：

- 落点：`$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/tool_usage_differential.jsonl`
  ——与 `tool_hunger.jsonl` 同目录同族，读的人只学一个位置。
- 写入纪律**照抄 `tool_hunger`**：fail-open、contextvar 注入 sink、
  **sink/磁盘失败绝不 raise 进工具路径**、**绝不改变返回给模型的字节**。
- 台账登记：`docs/learning/ledger-map.md` 加一行（唯一写入者 = 运行时，提交=否，用户态）。

---

## 7. 明确**不做**什么

1. **不把 `check_satisfiability` 预检升级成拦截门。**
   `continuous_turn_adapter.py:535-543` 已经论证过为什么不该升：produces 是人手维护的，
   让一张不完整的声明表拥有拦截权，就是造一个新的静默失败源。§4.1 的 1193 : 425
   是这个论证的定量版——声明表现在**确实**不完整。谁要提这件事，先把这个比值降下来。
2. **不改工具选择逻辑、不加 prompt 提示、不调预算。** 本单只装传感器。
3. **不据 425 下「模型路由差」的结论。** 见 §4.1。
4. **不动 `tool_hunger` 现有 schema。** 它是另一条边，两边各自独立。

---

## 8. 验收判据

P0：

1. 脚本按 **§3.0 钉死的口径**对同一样本跑出的四组数与本单相等
   （425 / 1193 / 698 / 572 / 八行工具表）。
   ⚠ 不等时**先核对口径是否一致**再判失败——本单基线的原始脚本未留存，
   口径分歧是预期内的第一嫌疑，不是实现错。
2. 输出头部含样本份数、日期跨度、revision 跨度、探针占比四项，缺一不算过。
3. 每个比率打印分子分母。
4. `--since 2026-08-25` 能跑出子集且分母随之变小（证明过滤真的生效，不是恒等）。
5. 全量 pytest 不降（基线以领单当天 `check_test_receipt.py --expect-revision` 收据为准）。

---

## 9. 变异点（先红后绿，逐个精确击杀）

| # | 变异 | 预期 | 抓的是 |
|---|---|---|---|
| 1 | 让差值忽略 `tool_request` 事件（视作从未调用任何工具） | 未调率全部变 100%，专项钉**红** | 实际侧真的被读了，不是恒为空 |
| 2 | 把 `suspicious`（`contributing_tools` 为空）也计入差值 | 425 膨胀到 1618，专项钉**红** | 两个口径没被混为一谈（§4.1 的核心） |
| 3 | `called` 集合改从 `kind == "tool_result"` 构造 | 报错工具的调用被静默丢弃 → 未调率虚高，专项钉**红** | 实际侧读的是 `tool_request`（对账权威，`agent_episode.py:694`）；**请求了但报错**仍算「调了」 |
| 4 | 把分母从「声明为 contributor 的 run」换成「全部 run」 | 未调率整体下降，专项钉**红** | 分母是对的那个 |

⚠ **变异前先 commit**——`git checkout --` 还原的是已提交态，未提交的实现会被冲掉重写。
这条在本仓交接里写过两次仍被踩，当成变异流程第 0 步。

---

## 10. 台账预注册

`R-20260827-08`，行随本单同提交进 `docs/prediction-ledger.md` Open 表。

**判据**：P0 脚本落地后，对 §3 同一样本重算，四组数与本单逐个相等；
且输出自述样本成分与 revision 跨度。

**失败形状**：数对不上 → **先核对是否同 §3.0 口径**，再查分母定义；
数对上但没人看 → 本单退化成第 88 条 pending（这正是同批审查建议 1 治的病，别自己撞上去）。

**成立条件**：本行的读数只证明「机制能量出这条边」，
**不证明**「模型路由有问题」——后者受 §4.1 的声明表盲区限制，需 1193 降下来后另立。
