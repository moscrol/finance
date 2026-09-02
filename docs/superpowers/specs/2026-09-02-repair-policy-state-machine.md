# 设计：`repair_policy` 状态机——修复轮的预算边与领域边

> 承接 `2026-09-02-research-harness-loop-decouple-design.md` §9 最后一条未做项：
> 「`repair_policy` / `fallback_after_empty_batch`。持状态、改控制流，**先画状态机**。」
>
> 本单只画状态机、只判归属，**不动一行运行时代码**。抽方法是下一刀。
>
> **所有 file:line 对 `gitea/main = 29c88639` 成立**（读的是该 revision 的工作树
> `fwp-wt-repair-policy`）。行号会漂，符号名不会——核对时以符号名为准。
>
> **实施进度**（分支 `refactor/harness-repair-policy-split`，叠在本 spec 之上）：
> - **M1–M4 已实施**（`e4657a11`）：`should_reenter` 拆为 `repair_is_warranted`（领域）
>   ∧ `can_afford_repair`（预算）；`work_units` 拆为 `repair_work_units`（格数）×
>   `calls_for_work_units`（换算）；`grant_for_progress` 变三行编排；`_mint_grant`
>   成唯一记账点。金标 + 网格等价 + 两次变异见 `intelligence/tests/test_repair_policy_split.py`。
> - **M6 已实施**（`8cc02f1f`）：三个 candidate 判据 + 两个 stop_reason 集合从 adapter 搬进
>   `services/repair_coordinator.classify_repair_failure` → `RepairFailureShape`；adapter 只叠
>   `allow_delivery_repair`（cycle 状态，底座的账）。1008 格逐格等价 + AST 棘轮。
> - **M5 已实施**（本提交）：五种 `grant_for_*`、两个 `admit_*`、`can_afford_repair` /
>   `calls_for_work_units` / `size_repair_window` / `_mint_grant` / `_resolve_seconds_cap` /
>   `_REPAIR_SECONDS_CAP` / `BACKFILL_BUDGET_FRACTION` 整体搬到 **`intelligence/runtime/repair_budget.py`**。
>   `services/repair_coordinator.py` 只剩值对象 + 领域判据（393 行），不再持有 `RootBudgetLedger`。
>   修复线的 `root_budget.grant()` 只在 `repair_budget._mint_grant` 一处被调。
>   **顺手发现（不属本单）**：`services/mode_governor.py:273` 的升档授予也在 services 侧
>   直接 `root.grant()`——与 M5 同一种错层（领域层碰账本），归 `govern_mode` 线另立案。
> - M7（`reopen_tools` 具名授权）/ §4 四方法签名 / `HarnessReferenceLoop.resume`：未做。

---

## 0. 一句话

修复轮现在有**四条入口、五种授予、两个执行体**，它们把「还允许不允许再来一轮」（预算）
和「该修什么、怎么说、算不算修好了」（领域）**逐个函数地缠在一起**；本单把这台状态机
画出来，逐条判定归属，并指出七处必须在抽 `repair_policy` 之前先拆的错层。

---

## 1. 为什么是先画状态机，而不是直接抽方法

前六刀（`assemble_prompt` / `admit_finish` / `interpret_plan` / `steering_message` /
`project_tool_result` / `govern_mode` / `project_sub_research`）能一刀一个方法地抽，
是因为它们都满足同一个前提：**纯函数式判定**——输入 context/evidence/registry，输出值，
不持有 loop 状态，抽出来不用改控制流（原 spec §4 对 P0 的选择理由）。

`repair_policy` 不满足。它：

1. **持状态**：`cycle` 跨回合累加（`continuous_turn_adapter.py:476 repair_cycles = 0`，
   :748 / :847 两处 `+= 1`），`transient_retries_left` 跨两跳共用
   （`agent_episode.py:1627`，repair 与 repair_finalize 同一个计数器）。
2. **改控制流**：`resume()` 内部有两次模型调用、一次工具批、六个提前返回出口。
3. **横跨三个文件两层**：判据在 `runtime/continuous_turn_adapter.py`，授予在
   `services/repair_coordinator.py`，执行在 `runtime/agent_episode.py`。

对这种形状，**先抽方法会把错层固化进签名**。举个具体的：如果照现状把
`grant_for_progress` 整个搬进 harness，就等于承认「预算算术属于领域」；如果整个留在
loop，又等于承认「进度判据属于底座」。它一个函数里两样都干——签名怎么写都是错的，
**必须先拆函数，再谈归属**。

> **可迁移**：这是重构里「先分离关注点、再移动代码」的标准顺序。反过来做（先移动、
> 再分离）会让第二步跨模块，代价高一个量级。同样的判断在 DB schema 迁移、
> 微服务拆分里复用：**先在原地把边界画清并用测试钉住，再搬家。**

---

## 2. 状态机全图

### 2.1 四条入口

| # | 入口 | 触发方 | 代码位置 | 授予函数 |
|---|---|---|---|---|
| A | 进度修复 | 结构/语义验证发现缺口 | `continuous_turn_adapter._resume_for_repair` :1226 | `grant_for_progress` |
| B | 交付修复 | 有证据但没写出稿/绑定 | 同上（`delivery_candidate`） | `grant_for_delivery_repair` |
| C | 冷启动修复 | 零证据饿死 | 同上（`cold_restart_candidate`） | `grant_for_cold_restart` |
| D | 补证修复 | IssueCode 指定缺 capability | `_resume_for_backfill` :1315 | `grant_for_backfill` |

A/B/C 三条共用 `admit_repair`（`repair_coordinator.py:500`），**按固定优先级择一**：
A 不成→试 B→再不成→试 C。D 走独立的 `admit_backfill_repair` :638。

第五种授予 `grant_for_transient_model_retry` :455 不是入口，是**执行体内部**的补救：
修复轮的模型调用遇瞬态错误时就地铸新窗（`agent_episode.py:1448`）。

### 2.2 状态转移

```
                    ┌──────────────────────────────────────────┐
                    │  RESEARCH_DONE（主轮出 outcome + 结构验证）│
                    └───────────────────┬──────────────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │ ADMITTING                     │  ← 无副作用，可拒
                         │  算 tools_open / remaining_*  │
                         │  判 delivery / cold / rewrite │
                         │  A→B→C 择一 grant             │
                         └──────┬────────────────┬───────┘
                      grant=None│                │grant≠None
                                │                │  （root_budget.grant() 已扣账）
                    ┌───────────▼──────┐  ┌──────▼─────────────────────────┐
                    │ TERMINAL_NO_REPAIR│  │ REPAIRING（agent_episode.resume）│
                    └───────────────────┘  └──────┬─────────────────────────┘
                                                  │
              ┌───────────────────────────────────┼────────────────────────────┐
              │                                   │                            │
   timeout≤0.001                         正常发 REPAIR_GOAL              unreachable≠()
              │                                   │                       （只降级，不跳过）
    ┌─────────▼──────────┐              ┌─────────▼──────────┐                 │
    │repair_deadline_    │              │ MODEL_TURN(repair) │◄────────────────┘
    │exhausted           │              └─────────┬──────────┘
    └────────────────────┘                        │
                              ┌───────────────────┼──────────────────┐
                    瞬态错误 & retries>0      有 tool_calls        直接给正文
                              │                   │                  │
                    ┌─────────▼────────┐  ┌───────▼────────┐         │
                    │ TRANSIENT_RETRY  │  │ TOOL_BATCH     │         │
                    │ 余量重试 或      │  └───────┬────────┘         │
                    │ 铸 transient 新窗│          │                  │
                    └─────────┬────────┘  ┌───────▼──────────────┐   │
                              │           │MODEL_TURN(repair_    │   │
                              └──────────►│      finalize)       │   │
                                          └───────┬──────────────┘   │
                                                  │                  │
                                          ┌───────▼──────────────────▼───┐
                                          │ admit_finish（harness，已抽） │
                                          └───────┬──────────────────────┘
                                    accepted=False│         │accepted=True
                                    ┌─────────────▼───┐  ┌──▼────────────────────┐
                                    │invalid_repair_  │  │ 判 repair_progressed  │
                                    │finish           │  │ finish / stop 二选一  │
                                    └─────────────────┘  └───────────────────────┘
```

**另一台独立状态机**（不属于 repair cycle，但同在 §9 入口清单里）：

```
   合成失败 ──► _can_recover_finalization ──► EpisodeFinalizer.recover ──► 四道 deadline 检查
                （有证据 ∧ synthesis_timeout                              （:2379 / :2409 /
                  ≥ MIN_FINALIZATION_RECOVERY_SECONDS）                    :2421 / :2436）
```

它与 A–D 的关键区别：**恰好一次，不计入 cycle，不经 `root_budget.grant()`**，
只用 `_consume_root_seconds` 事后扣账。这个不对称是现状事实，本单不改，但要在
状态机里标出来——它是「修复」这个词底下的第二种东西。

### 2.3 出口

| stop_reason | 来源 | 语义 |
|---|---|---|
| `repair_deadline_exhausted` | :1601 / :1673 / :1744 / :1787（四处） | 时钟用尽，结转旧稿或刚写的稿 |
| `repair_model_unavailable` | :1690 | provider 死 |
| `invalid_repair_finish` | :1818 / :1851 | 交回来的东西不合格（工具/错误/`admit_finish` 拒） |
| `repair_model_finish` | :1908 | 修了且**有进展** |
| `repair_model_stop` | :1908 | 修了但**没进展**（关键读数：P2'-live 里 Episode 臂就是这个） |

---

## 3. 逐条归层

判据用原 spec §3 的定义：**底座 = 拥有循环、算超时、记账；领域 = 回答「金融题怎样才算对」**。
再叠 §9 那句话：「什么时候允许再来一轮」是预算，「修什么、怎么写修复提示、修完算不算
进步」是领域。

### 3.1 明确属预算（底座）

| 项 | 位置 | 理由 |
|---|---|---|
| `remaining_calls` / `remaining_seconds` 的计算 | adapter :1190-1201 | hard cap − allocated，纯账本算术 |
| `tools_open` | adapter :1186 / :1299 | deadline 是否烧穿 |
| `root_budget.grant()` 扣账与幂等 | coordinator 各 grant 末行 | 账本写入 |
| `seconds = min(remaining, cap)` | :342 / :401 / :442 / :621 | 秒数算术 |
| `_TRANSIENT_RETRY_LIMIT` 熔断 | episode :110 / :1627 | 重试次数上限 |
| 两条瞬态补救路径 | episode :1427-1482 | 时钟层面的重问价 |
| `settle_seconds` fail-closed 结平 | episode :1445 | 记账修正 |
| `MIN_FINALIZATION_RECOVERY_SECONDS` 四道检查 | episode :2326 / :2421 | 时钟够不够 |
| `repair_deadline` / `repair_tool_deadline` 构造 | episode :1513-1522 | 窗口换算 |
| `BACKFILL_BUDGET_FRACTION`（25%） | coordinator :33 / :620 | 预算配比 |

### 3.2 明确属领域

| 项 | 位置 | 理由 |
|---|---|---|
| `build_repair_goal` 的四个缺口字段 | coordinator :221 | 修什么 |
| `unreachable_repair_goal` | coordinator :252 | 「这轮结构性不可能补上」是证据口径判断 |
| `apply_unreachable_downgrade` | `mandatory_satisfiability` | 降级哪张契约 |
| `REPAIR_GOAL` 消息文案 | episode :1572-1592 | 怎么写修复提示（**最后一段仍焊在 loop 里的领域话术**） |
| 工具开/关两套 instruction 分支 | episode :1581-1585 | 同上 |
| `progress.coverage_delta.progressed` | coordinator :301 | 算不算进步 |
| `repair_progressed` 三元判定 | episode :1866-1883 | 修完算不算数 |
| `current_gaps` 兜底文案 | episode :1882 | 领域话术 |
| `delivery_candidate` 判据 | adapter :1211-1217 | 「有证据没写出稿」是领域失败分类 |
| `cold_restart_candidate` 判据 | adapter :1222-1225 | 「饿死」是领域失败分类 |
| `contract_rewrite_candidate` | adapter :1206 | 表达重写 vs 取证 |
| `_carry_repair_finish` 取舍顺序 | episode :2647 | 「新稿 > 旧稿」是答案质量策略 |
| 草稿不倒退保护 | adapter :1267-1272 | 同上 |

### 3.3 混合——必须先拆（本单的核心结论）

以下七处，**一个函数同时干两层的活**。这是抽 `repair_policy` 的真正障碍。

**M1. `should_reenter`（coordinator :290）四条闸混装**

```python
if cycle < 1 or cycle > max_cycles:              return False   # 领域策略（tier→cycles）
if not progress.coverage_delta.progressed:       return False   # 领域（算不算进步）
if tools_open and remaining_calls <= 0:          return False   # 预算
if remaining_seconds < 1.0:                      return False   # 预算
```

拆法：`domain.repair_is_warranted(progress, cycle) -> bool` 与
`budget.can_afford(calls, seconds, tools_open) -> bool`，调用方求与。

**M2. `grant_for_progress`（:319）里嵌着 M1，再接预算算术**
先调 `should_reenter`（混合判据），再算 `work_units`（领域量：缺几个格），
再折成 `calls`（预算换算），最后 `root_budget.grant()`（记账）。
**一个函数四种职责**。

**M3. `work_units` 公式（:337 / :396）**
`min(4, max(1, len(missing_answer_elements) + len(missing_evidence_modes)))`——
「缺几个格」是领域，「一个格值几次工具调用」是预算换算，硬编在一个表达式里。
拆法：领域出 `work_units`（要做几件事），底座出 `calls_per_unit` 换算。

**M4. `max_repair_cycles_for_tier`（:310）住在 coordinator，形式是计数闸**
`deep=3 / quick=standard=1`。它**是领域策略**（研究强度决定容忍几轮），
但被 `grant_for_progress` / `grant_for_delivery_repair` 当预算闸内联调用。

**M5. 五个 `grant_for_*` 全在 `services/`（领域层），但主体是预算算术**
`services/` 按 §3 定义是领域层，却在这里持有 `RootBudgetLedger` 并铸额度。
`grant_for_transient_model_retry` 尤其纯粹——它一点领域判断都没有，纯粹是
「从 root 未分配余量再铸一笔」，**放在领域层是纯错层**。

**M6. 三个 candidate 判据在 `runtime/adapter`（底座层），内容却是领域失败分类**
`delivery_candidate` / `cold_restart_candidate` / `contract_rewrite_candidate`
读 `stop_reason` 集合判「这次失败属于哪一类」——这是领域对失败的解释，
却住在底座，且两个 `frozenset` 常量（:93 / :100）也在底座文件里。
**M5 与 M6 方向相反**：预算逻辑跑到了领域层，领域判据跑到了底座层。

**M7. `resume()` 里 `reopen_tools` 的预算后果由领域 flag 触发**
`goal.reopen_tools`（领域：冷启动准入置位）直接决定
`repair_tool_deadline = repair_deadline`（预算：重开一个烧穿的窗，episode :1516-1521）。
这条耦合本身是**对的**（领域申请、底座授予），但现在没有显式接缝——
领域把一个 bool 塞进 goal，底座读它改窗口。抽 `repair_policy` 时这应当成为
一个具名的授权，而不是一个搭便车的字段。

---

## 4. `repair_policy` 接缝的建议签名

按上面的拆分，harness 侧只留**三个纯判定 + 一段话术**，其余全归底座：

```python
class ResearchHarness(Protocol):
    def classify_repair_need(
        self, *, outcome, structural, semantic_gap_outputs, evidence_count
    ) -> RepairNeed | None:
        """这次失败该修什么、属于哪一类。合并现 M6 三个 candidate + build_repair_goal
        的缺口字段。返回 None = 领域认为不值得修。不看预算。"""

    def repair_is_warranted(self, *, progress, cycle, research_tier) -> bool:
        """算不算进步、这个 tier 容忍第几轮。合并 M1 前两条 + M4。不看预算。"""

    def repair_goal_message(self, goal, *, tools_open) -> str:
        """REPAIR_GOAL 文案 + 两套 instruction 分支（episode :1572-1592）。"""

    def admit_repair_result(self, *, performed_tool_action, admission, previous) -> RepairVerdict:
        """修完算不算进步（现 episode :1866-1883），以及新稿旧稿取舍（现 _carry_repair_finish）。"""
```

底座侧（`runtime/`）收走：`should_reenter` 的后两条、全部 `grant_for_*`、
`work_units→calls` 换算、`root_budget` 记账、瞬态重试、deadline 构造、
`MIN_FINALIZATION_RECOVERY_SECONDS`。

**授予协议**：领域返回 `RepairNeed{work_units, needs_tools, reason}`，
底座据此铸 `BudgetGrant` 或拒绝。M7 的 `reopen_tools` 变成
`RepairNeed.needs_tools=True` + 底座的 `grant_for_cold_restart` 决定给不给——
**领域申请、底座授予、领域不碰账本**。

> **替代方案对比**（为什么不选另外两种）：
> - **A：整个 `repair_coordinator` 搬进 harness。** 最省事，但等于宣布预算属于领域，
>   与 §4 #9「预算可见性属底座，不抽」自相矛盾，且 `HarnessReferenceLoop` 将被迫
>   连 root budget 一起实现，"一行领域逻辑不写"的棘轮会破。
> - **B：整个留在 loop，harness 只出文案。** 那 `repair_policy` 就是没牙的接缝
>   （§3「有牙」定义：换一个 harness 实现能改变 outcome）——换 harness 改不了
>   「修不修、修什么」，只改措辞，退化成 `steering_message` 的重复。
> - **C（本单选）：按判据性质拆，领域出判定、底座出额度。** 代价是签名多、
>   要先拆七处混合；收益是两侧都可独立测试，且 `HarnessReferenceLoop` 只需实现
>   四个纯函数就能跑修复轮。

---

## 5. 验收（下一刀实施时用，缺一条不算）

1. **等价**：拆分前后，A/B/C/D 四条入口 + 瞬态重试的 grant 序列逐字段相同
   （`grant_id` / `calls_granted` / `seconds_granted` / `cycle`）。
2. **有牙**：换一个 `repair_is_warranted` 恒 False 的 harness，`repair_cycles` 归零；
   换一个 `classify_repair_need` 只报 delivery 的 harness，冷启动路径不再触发。
   两条都要看 outcome 变化，不是看日志。
3. **无牙即失败**：`repair_goal_message` 换成自定义文案，必须真的出现在模型消息里
   （复刻 P1b `steering_message` 的钉法）。
4. **棘轮**：`agent_episode.py` 不再 import `repair_coordinator` 的任何领域判据
   （`should_reenter` / `max_repair_cycles_for_tier` / `unreachable_repair_goal`）；
   `continuous_turn_adapter.py` 不再持有 `_DELIVERY_REPAIR_STOP_REASONS` /
   `_COLD_RESTART_STOP_REASONS`。
5. **第二条 loop**：`HarnessReferenceLoop.resume` 从现在的「明确抛无修复轮」
   改成真的能跑一轮（P2'-live 里它是 `model_finish`、Episode 是 `repair_model_stop`，
   这条差就消掉了）。这是本刀完成的**可判定读数**。

---

## 6. 非目标 / 红线

- **不动 `_recover_finalization` 的「恰好一次、不进 cycle、不经 grant」这个不对称。**
  它是独立状态机，合并进 repair cycle 是另一个决定，需要单独立案。
- **不放宽任何现有闸门**：`unreachable_repair_goal` 的 docstring 写明它「不放宽任何
  限制、不加任何预算」，拆分后必须保持。
- 不为让测试绿而改 `episode_protocol.py` 判定。
- 不得 `git add -A`；提交一律 pathspec。合 main 等用户确认。
- 生产快照、8792、启动器零改动。

---

## 7. 本单交付

只有这份文档。**零运行时改动**——`git diff --stat` 应只含本文件。
下一刀（实施）建议顺序：先拆 M1/M2/M3（纯函数拆分，可用现有测试钉等价），
再搬 M5/M6（跨层移动），最后接 M7 与签名。M4 随 M1 走。
