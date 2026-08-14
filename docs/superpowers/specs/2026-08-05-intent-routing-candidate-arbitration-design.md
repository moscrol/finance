# 设计：意图路由改为「规则提候选 → LLM 裁定 → Harness 校验」

日期：2026-08-05 · 作者：claude · 状态：**待评审，未实施**
关联：`fix/continuous-runtime-provider-neutral` 上的 `_COMPARISON_RE` 止血修复（第 1 步）

---

## 0. 一句话

`_research_operators()` 的九个正则是**无条件布尔断言**，没有「我不确定」这个状态。
误判会无损传导到契约门并被如实拒答，且**全链没有任何一层有纠正权**。
本设计给它加一个候选/裁定/校验环节，让 LLM 拿到**否决权但拿不到扩权**。

---

## 1. 问题：一个正则分支能让整道题拒答

2026-08-05 实测。题目：

```
以 2026-08-04 收盘数据为准，分析当前行情，你认为哪个方向、哪只个股比较有机会？
```

`_COMPARISON_RE` 的第一支是裸词 `(比较|对比|相比|赔率排序)`，把程度副词
「比较有机会」读成了动词「比较 A 和 B」。之后：

```
operators += "comparison"
  → _required_outputs() 追加 "comparison"
  → question_type = "comparison"
  → task_frame.py:627 追加 comparison_dimensions / key_differences / evidence_boundary
  → 工具目录里没有任何 claim 能填这四项
  → task_fulfillment.py:468 判缺 → 契约门如实拒答
```

产出是一段「仍缺少：TaskFrame 要求的输出…」模板。用户看到的表面症状是
**「证据不足」**，于是会去查检索层——而检索层是好的。

**链上每一层都在正确履职，包括最后那道门。坏的只有第一个正则分支。**
这是这个缺陷难被发现的根本原因。

### 1.1 不是孤例

九个 operator 的假阳性审计（手造负样本 66 条，命中 63）：

| operator | 形态 | 伤口类型 |
|---|---|---|
| `scenario_tree` | **纯子串** `any(term in text …)`，词表含 `能否`/`能不能` | 词面泄漏 |
| `relation` | 裸词 `(上游\|下游\|供应\|客户\|合作\|…)` | 词面泄漏 |
| `history_analog` | 纯子串 ×12：`上次`/`类似`/`过往`… | 词面泄漏 |
| `money_flow` | 裸词 `(资金流\|主买\|净流入\|大单)`，无词边界 | 词面泄漏 |
| `comparison` | 裸词 + 2 条有结构分支 | 词面泄漏（**第 1 步已修**） |
| `counterevidence` | 裸词 `(反证\|证伪\|…)` | 时态/语气泄漏 |
| `company_mapping` | 短语级裸词 | 语义分层泄漏 |
| `market_change` | 短语级裸词 | 时态/语气泄漏 |
| `cause_attribution` | 有结构 | 语义分层泄漏 |

`能否/能不能` 是汉语最高频的礼貌请求前缀，「能否帮我把复盘导出成 PDF」
会点着 `scenario_tree`——**比 `比较` 更严重**。

三类伤口需要三种修法，**继续堆正则只能修第一类**：

- **词面泄漏**：加上下文约束可缓解，但受限于枚举，长尾修不完
- **时态/语气泄漏**：「已被证伪」（既成事实陈述）vs「帮我做反证」（祈使请求），
  差别在语气不在词面，正则难表达
- **语义分层泄漏**：「白酒行情下跌的原因」误入 `cause_attribution`，
  是因为它没区分全市场/题材/外盘。这是**口径缺失**，改正则只会换一个错口径

---

## 2. 现状机制（实测，非推断）

```
用户输入
  ↓
① _research_operators()            query_understanding.py:779
   九个独立布尔检测，命中即 append，无置信、无冲突检测、无「不确定」态
  ↓
② _required_outputs()              query_understanding.py:781
   operator → required_output 一一映射
  ↓
③ build_task_frame()               task_frame.py:177
   docstring: "Compile rules first, then optionally merge one constrained LLM draft"
   ⚠️ llm_complete 五个生产调用点一个都没传 → LLM 草案是死代码
   ⚠️ 即使传了，align_task_frame() 只合并 user_goal / assumptions / ambiguities
      —— question_type 与 required_outputs 明确 code-owned，LLM 改不了
  ↓
④ _deterministic_decision()        turn_controller.py:1064
   命中即 return，LLM 一次都不调
  ↓
⑤ LLM controller                   turn_controller.py:1068
   只做技能/车道选择，吃的是 ② 已定好的 task_frame
  ↓
⑥ 检索 / 工具调用
  ↓
⑦ task_fulfillment                 task_fulfillment.py:468
   事后判缺，能区分四种失败原因（registry 无 claim / 正文没写 / 证据没绑 / 缺 marker）
```

### 2.1 现有约束是对的，只是过宽

`align_task_frame` 的 docstring：

> Required outputs are also code/owner-contract owned: an alignment model may
> improve the goal or surface assumptions, but **cannot enlarge the task gate**.

意图站得住——不让 LLM 自己改门槛，否则它可以把门改小让自己通过（LLM-as-judge
的自证陷阱）。但实现把两件事混在了一起：

| 行为 | 该不该禁 |
|---|---|
| LLM **扩大/缩小**任务门 | ✅ 该禁 |
| LLM **纠正**上游题型误判 | ❌ 不该禁，现在一起禁了 |

---

## 3. 设计

### 3.1 原则

> **Harness 不负责穷尽用户意图，Harness 负责让 LLM 的意图理解运行在安全、可验证的范围里。**

分工：

| 判断 | 归属 |
|---|---|
| `600519` 是不是六位代码 | Harness 规则 |
| 「昨天」对应哪一天 | Harness 按系统时间解析，**原词保留** |
| 当前用户有没有写库权限 | Harness |
| 这句话在问事实/解释/预测/行动建议 | **LLM，在规则给的候选内** |
| 该不该真的写入跟踪池 | Harness |
| 工具返回是否日期错位/越权 | Harness |

### 3.2 改动：operator 从「断言」变「候选 + 置信」

```python
# 现状：query_understanding.py:779
def _research_operators(query) -> tuple[ResearchOperator, ...]:
    if _COMPARISON_RE.search(query):
        operators.append("comparison")      # 无条件断言
    ...

# 目标
@dataclass(frozen=True)
class OperatorCandidate:
    operator: ResearchOperator
    confidence: float          # 由命中的是哪一支决定
    evidence: str              # 命中的片段，供 LLM 裁定与事后审计
    structural_gaps: tuple[str, ...]   # 例：comparison 命中但找不到第二个可比对象
```

置信度**由命中分支的结构强度决定**，不是拍脑袋：

| 命中方式 | 置信 |
|---|---|
| 有结构分支（`A 和 B…差异`、`比较一下 X 和 Y`） | 高 |
| 裸词分支，且结构自洽（如 comparison 命中且句中确有两个实体） | 中 |
| 裸词分支，且结构不完整（comparison 命中但 `subject=null`、无第二对象） | **低 → 送裁定** |

### 3.3 三条低置信触发（对应你的退出机制）

```
规则单一命中、结构自洽        → 直接定型，不调 LLM（保留现有快路径）
多个互斥题型同时命中          → 低置信 → 裁定
命中但结构不完整              → 低置信 → 裁定
```

第三条是这道题的救命稻草：`comparison` 命中了，但 `subject=null`、
全句找不到两个可比对象——**规则自己就能识别出「我这次不确定」**。
这比让规则去穷尽「比较」的所有副词用法稳得多，也不需要枚举长尾。

### 3.3b required_outputs 的三个来源（2026-08-09 补：本设计原先只盯住其中之一）

本设计通篇把 `_research_operators()` 当成 `required_outputs` 的**唯一**来源。
读 `task_frame.py:601-607` 后发现不是——真实算法有三段，且**九个 operator 是优先级最低的一段**：

```python
explicit_outputs = _explicit_required_outputs(question)   # ① 正则，命中即 return
if explicit_outputs:
    return explicit_outputs                              # ← 直接返回，②③ 全不执行
return _clean_outputs(
    _default_required_outputs(question_type, question),   # ② 按 question_type 查表
    extra,                                                # ③ ← 九个 operator 只在这
)
```

| # | 来源 | 位置 | 依据 | 实测贡献 |
|---|---|---|---|---|
| ① | `_explicit_required_outputs` | `task_frame.py:610` | **另 4 条正则** | 命中即**独占**，覆盖 ②③ |
| ② | `_default_required_outputs` | `task_frame.py` 同文件 | `question_type` 枚举查表 | **89% 的题全靠它** |
| ③ | `_research_operators` → `extra` | `query_understanding.py:779` | 九条正则 | **仅 11% 的题有贡献** |

**两个此前没被记录的事实：**

1. **正则不止九个。** `task_frame.py` 里还有 `_COMPARATIVE_DECISION_RE` /
   `_COUNTERFACTUAL_ASSESSMENT_RE` / `_DECISION_METHOD_RE` / `_INVALIDATION_FOLLOWUP_RE`
   四条，命中就 `return`，**把题型表和九个 operator 的产物一起丢掉**。
   即「关键词决定验收标准」这件事发生在**两个文件**里，本设计只盯了一个。
2. **承重结构是题型表，不是正则。** 89% 的题目契约完全来自 `question_type` 查表，
   而 `question_type` 有 LLM 参与、有兜底、有置信度。**真正的地板是那张表。**

#### 由此修正本设计的一处判断偏差

> 原文 §1 说「一个正则分支能让整道题拒答」——**成立**，但它把杠杆估大了。
> 九个 operator 只在 11% 的题上有贡献；而 ① 那四条正则是**独占**的，
> 一条命中就换掉整套验收标准。**按误判代价排序，① 比 ③ 更该先治，
> 而本设计对 ① 一字未提。**

#### 为什么这层必须留在 harness（有事故实证，不是偏好）

`task_frame.py:538-558` 记着 run_20260731_175959_316535：

```
turn controller 的 LLM 调用失败 → question_type 停在默认 general_finance_qa
  → 「要不要检索」落到关键词分支 → 关键词表里没有「A股」（只有「大盘」）
  → 「你觉得a股明天会怎么走」判 False → 检索地板不生效
  → 兜底成 chat 车道 → 用户拿到「我没办法预测」，整条研究链一次都没跑
```

**契约必须能在 LLM 挂掉时算出来**，否则失败形态是「静默降级成闲聊」。
但注意那次的修法**不是补关键词**，而是改用 `required_outputs` 判——同一段注释里写着：

> 只补关键词是「打地鼠」：关键词表永远追不上用户的说法，
> 而 `required_outputs` 是结构化的，不会因为换个措辞就漏。

**系统自己已经写下了「别靠自由文本正则」这条结论**，本设计应当承接它而不是绕过它。

#### 结论：要治的不是「用不用正则」，是「正则的产物往哪一侧走」

| 方案 | 做法 | 优 | 劣 |
|---|---|---|---|
| A. 契约交给 LLM 生成 | 全语义 | 长尾好 | LLM 挂了无地板；LLM 能改自己的及格线（自证陷阱），07-31 事故即此形状 |
| B. 现状（正则 + 题型表） | 确定性 | 有地板 | 正则误判 = 拒答；长尾修不完 |
| C. 砍掉正则，只留题型表 | 最稳 | 无自由文本输入 | 丢掉**可组合意图**——题型是单选枚举，表达不了「个股深挖 + 要对比 + 要反证」的叠加 |
| **D. 正则保留，改接检索侧** | 命中 → 加检索义务，**不加验收项** | 误判代价从「拒答」降为「白查一次」；不引入 LLM、不引入非确定性 | 真·对比题可能少一项验收保障（**质量上限降，换掉拒答**）|

**建议 D**，理由是它同时满足三条：保留 harness 确定性（LLM 挂了照样算）、
把误判代价降到可接受、且**不需要建 §3.5/§3.6 那套仲裁机制**
（实测 11% 命中率、0 条互斥冲突，见 §3.4 路 C）。

不建议 C：正则捕捉的是**可组合意图**，这是它存在的真实理由。

#### 可迁移原则（本轮最值钱的一条）

> **规则给下限，模型给上限。规则的产物若是「义务」（去查/去看/去试），宽松无害，
> 多花一次成本；若是「判据」（必须交付/必须达标），宽松就是误杀。**

两者放进同一个数据结构传递，就会出现本设计描述的事故。
同形坑见于权限系统、限流、告警规则：**推荐规则可以宽，拦截规则必须准。**

### 3.4 契约可满足性预检（本设计的增量）

> ⚠️ **成本更正（2026-08-05 复核后改写）。** 初稿写的是「同一份 registry 知识事前
> 也能用，白捡」——**这是错的**。`_claim_candidates`（`task_fulfillment.py:238`）
> 拿 `output_id` 去子串匹配**运行时已产出的 claim**（`claim.claim_id` / `claim.text`）。
> 事后判得出来，是因为那时 claim 已经存在；**事前没有这份知识可查。**
>
> 🔴 **二次更正（2026-08-09 实测）：上面这段的最后一句「全仓不存在能力→可产出
> output 的静态声明，这是新建能力不是复用」——同样是错的，而且错得更彻底。
> 这套东西已经建好了。**
>
> | 已存在 | 位置 | 状态 |
> |---|---|---|
> | `ToolSpec.produces` 字段 | `research_tool_registry.py:317` | 已实现 |
> | 12 个工具的 produces 声明 | `_DEFAULT_TOOL_METADATA` | **11/12 已填**，并集 19 个 output_id |
> | `check_satisfiability()` 事前预检 | `research_tool_registry.py:660` | 已实现，fail-open 三态 |
> | 防漂移对账测试 | `test_tool_produces_satisfiability.py::TestProducesMatchesHistory` | 已有，冻结 45 个 episode 采集 |
>
> 也就是说，下面「路 A」描述的**全部**内容——静态声明、fail-open 语义、
> 与历史 fulfilled 交叉核对的门禁——都不用建。**唯一缺的是一根线：
> `check_satisfiability` 没有任何生产调用者**（全仓三处引用：两处注释、一处
> 自身 `def`，其余全在测试）。真实成本是**加一个调用点**，不是新建能力。
>
> **为什么会连错两次**：沿用了本文档的断言而没独立验证。而它恰好带了一条
> 「⚠️ 成本更正」——**一份自己纠过错的文档读起来比没纠过的更可信**，于是没再查。
> 搜索也搜偏了：查的是 `_claim_candidates` / `output_id`，没查 `produces` /
> `satisfiab`——**搜的是自己猜的实现方式，不是这个能力的所有可能命名**。
> 这正是 `CLAUDE.md`「负面断言规矩」要防的事（说「我们没有 X」前必须全树 grep 同义词）。

想法仍然成立，但要认清代价。两条路：

**路 A：补静态声明（干净，但要动的地方多）**

每个 capability / research owner 声明它能产出哪些 `output_id`：

```
required_outputs 定稿前：
  在当前 contract.allowed_capabilities 下，
  每个 required_output 是否存在任一声明能产出它的能力？
    全部可满足      → 放行
    存在不可满足项  → 「规则判错了」的强信号 → 送裁定
```

价值在于**它是通用护栏，不是逐正则打地鼠**：P0/P1/P2 三类伤口都会被同一个
机制拦住。一个 operator 无论因为什么原因误命中，只要它带来的 required_output
在当前授权下无人能填，就会被标为可疑。

代价是这份声明必须**和实现保持同步**，否则它会变成第二个事实源——
声明说能产出、实际产不出，就成了新的静默失败。需要配一条门禁：
声明与 `task_fulfillment` 的事后判缺结果做交叉核对，长期偏离即报警。

**路 B：用历史产出反推（便宜，但只是经验规律）**

> 🔴 **已实测，此路不通（2026-08-09）。语料前提不成立，不是成本问题。**
>
> 原设想是统计「每个 `(question_type, required_output)` 组合历史上被 fulfilled 过没有」。
> 盘完全部 run 产物后的事实：**这两个字段一个都没落盘。**
>
> | 产物 | 有什么 | 缺什么 |
> |---|---|---|
> | `users/*/runs/*/` | `run.json`(question/task_type)、`trace.jsonl`(step 级摘要)、`stream.jsonl`(report 事件) | 无 `required_outputs`、无判缺明细 |
> | `eval/runs/*.json` | 121 turns / **30 条去重 query**、`gaps` 自由文本 | 同上 |
> | `eval/measurements/**` | 带 `task_frame.required_outputs` + `acceptance_contract_gaps` ✅ | **只有 5 条去重 query，且 0 条有 gap** |
>
> 关键一击：`eval/runs` 里 **11 个** turn 的 gaps 含「最终回答未完成任务契约，已按部分完成标记」，
> 但**没有一个**记下是哪一格 required_output 缺了——`gaps` 是给人看的自由文本（全库共 33 种措辞），
> 不是结构化判缺结果。**事后判缺的诊断粒度很好，但没有被持久化。**
>
> 另：「108 条去重真实 query」这个数字对不上。把五个来源全并起来（`eval/runs` +
> `measurements` + `users/*/runs` + `conversations` + `eval/cases`）实得 **62 条**去重，
> 其中**真实用户流量仅 23 条**（`user_runs` / `conversations`），另 39 条来自评测用例与 measurements。原文这个数是推断，不是实测。

原始设想：统计每个 `(question_type, required_output)` 组合历史上被 fulfilled 过没有，
从未被满足过的组合即可疑。比路 A 便宜且无需维护声明，但它是经验规律不是保证。
**按上方实测，这条路缺的不是成本而是数据本身，已放弃。**

**路 C：直接探针现役函数（2026-08-09 实际采用）**

`_research_operators()` 是**纯函数**——不必等 run 产物落盘，直接把真实 query 喂进去
当场量命中率。这比路 A/路 B 都便宜，且回答的是同一个问题。

实测（62 条去重 query，走 `QueryResolver` 生产同构路径以正确解析 anchor）：

| 指标 | 读数 |
|---|---|
| 至少命中一个 operator | **7 / 62（11%）** |
| 命中 >=2 个 operator（互斥冲突态） | **0** |
| 命中样本内 `subject` 未解析 | 4 / 7（57%） |
| 修复前 `scenario_tree` 假阳性 | 「能否帮我把复盘导出成 PDF」等祈使句**全部命中** |
| 修复后（真实用户子集 23 条） | `scenario_tree` 命中 2 条，**均为合法推演语义** |

⚠️ **方法论坑（记下来别再踩）**：初版探针直接调 `understand_query(q)` 未传 `anchor`，
量出 `subject` 未解析率 82%，据此差点得出「结构不完整极其普遍、必须上仲裁」。但生产链路走
`QueryResolver.resolve()`——它**先** `resolve_entity_anchor()` 再把 anchor 传进去。
补上后该数降到 53%（命中样本内 57%）。**探针必须复刻生产调用形态，否则量出来的是探针自己的缺陷。**
这条对任何「离线复现线上行为」的测量都成立（评测、回放、A/B 同理）。

### 3.5 LLM 裁定的边界

```json
输入 {
  "raw_user_message": "<原文，完整保留>",
  "candidates": [
    {"operator": "comparison", "confidence": 0.4,
     "evidence": "比较有机会", "gaps": ["无第二可比对象", "subject 未解析"]}
  ],
  "extracted_facts": {"resolved_date": "2026-08-04", "tickers": []},
  "unsatisfiable_outputs": ["comparison_dimensions", "key_differences"]
}

输出 {
  "selected_operators": ["<必须是 candidates 的子集>"],
  "rejected": [{"operator": "comparison", "reason": "程度副词，非比较请求"}]
}
```

**硬约束**：

1. `selected_operators` ⊆ `candidates` —— **只能否决，不能自创**
2. LLM 看到**原始用户文本**，因此可以推翻规则的解析（保真增强）
3. 输出不符合 schema → Harness 拒绝，回落规则首选，并留痕
4. LLM 不可用 / 超时 → 回落规则首选（现状行为，不劣化）

### 3.6 Harness 校验

```
LLM 返回
  → schema 校验（字段齐、类型对）
  → 子集校验（没自创 operator）
  → 可满足性复检（选完之后 required_outputs 全部可满足）
  → 任一不过：拒绝 + 回落规则首选 + 记 trace 事件
```

---

## 4. 代价：确定性会被侵蚀，必须配套

`10_knowledge/eval-harness-variance-governance.md` 立的规矩是
**「确定性手段优先，LLM 判官只吃残差」「方差要用干净对照测」**。

`question_type` 一旦可被 LLM 影响，**同一道题在不同 run 可能路由到不同题型**，
壳的 A/B 里会混进路由方差——那正是这一轮一直在防的事。

配套（**不做就不要上**）：

1. **评测模式固化**：按 question hash 缓存首次裁定结果，或评测时强制走规则首选，
   让对照组回到完全确定性
2. **裁定必须留痕**：`selected/rejected/reason` 全部进 `trace.jsonl`，
   使「这次为什么路由不同」可事后归因
3. **裁定率是一级指标**：正常应当是少数派。若 >30% 的 query 走裁定，
   说明规则层退化成了摆设，要回头修规则而不是加大 LLM 依赖

---

## 5. 分期

| 期 | 内容 | 状态 |
|---|---|---|
| **第 1 步** | 止血：逐个修词面泄漏正则 | ✅ **已完成（2026-08-09）**：`comparison` + `scenario_tree` 两处词面泄漏均已修 |
| **第 2 步** | 3.2 + 3.3：候选/置信/低置信触发。**先不接 LLM**，低置信时仍走规则首选，只记录「本次本应裁定」 | 🟡 **暂缓**——实测触发面太小，见下方判据 |
| **第 3 步** | 3.4 可满足性预检 | 🔴 **路 A 挂起 / 路 B 已否 / 路 C 已用**，见 §3.4 |
| **第 4 步** | 3.5 + 3.6：接 LLM 裁定 + 校验 + 评测固化 | 🔴 **不做**，见下方判据 |

### 5.1 2026-08-09 实测后的分期结论

用路 C 量完 62 条真实 query，得到三个数，它们**共同否掉了继续往下推的理由**：

| 判据 | 设计文档原假设 | 实测 | 含义 |
|---|---|---|---|
| operator 命中率 | 未量 | **11%（7/62）** | 89% 的 query 根本不进 operator 逻辑，改这里的杠杆很小 |
| 互斥题型同时命中 | §3.3 第二条触发 | **0 条** | 该触发条件在真实流量里**从未发生**，为它建仲裁是为零样本建机制 |
| 结构不完整命中 | §3.3 第三条触发 | 4/7 | 有样本，但基数是 7 |

**关键澄清**：设计文档 §1.1 的「手造负样本 66 条，命中 63」是**对抗性构造下的命中率**，
不是真实发生率。真实发生率是 11%，且修完两处词面泄漏后，真实用户子集里的
`scenario_tree` 假阳性**已归零**。用 63/66 去推架构投入，会把量级估高一个数量级。

**因此**：
- 第 2 步（候选/置信）**暂缓**。它的三条触发里，第二条零样本、第三条基数 7。
  真正该先做的是**让判缺结果结构化落盘**（见下），否则第 2 步上线后同样量不出效果。
- 第 4 步（LLM 裁定）**不做**。§4 列的三条配套（评测固化、留痕、裁定率一级指标）
  成本高于它在 11% 命中面上能拿到的收益，且会给 A/B 引入路由方差。

### 5.2 实测暴露的真实缺口：判缺结果没有结构化落盘（✅ 已修）

这是本轮**最有价值的副产物**，也是路 B 走不通的根因。

**根因链（2026-08-09 查明，与初版判断不同）**：

```
task_fulfillment 能区分四种成因（no_candidate_claim / text_absent
                                / evidence_unbound / marker_absent）
  ↓  FulfillmentVerdict.to_dict() 早就带 reason_code + candidate_count
  ↓  orchestrator 也已写进内部 trace step（conversation_orchestrator.py:2848 / :2880）
  ↓
但公开 trace API 只对 `answer_synthesis` 一步投影 `diagnostic`
  ↓  → task_fulfillment 步的结构化载荷**一次都没出过内网**
  ↓
落盘产物里只剩那句自由文本「最终回答未完成任务契约，已按部分完成标记。」
11 个 turn 命中它，没有一个能回答「缺的是哪一格 output」
```

⚠️ **初版本节写「在现有 gap 写入点旁加结构化字段」——判断错了。**
结构化字段**早就存在且早就在算**；缺的是**出口投影**，不是生产端。
落盘产物里确实出现过 `reason_code`，但那是 `ask_synthesis` 的另一套词表
（`validated` / `grounded_required_fallback` / `deadline_exhausted_local`），
判缺四码**从未出现在任何落盘产物里**——两套同名字段混在一起，让「已经有了」
的错觉更难被发现。

**已实施**：

| 改动 | 位置 |
|---|---|
| stage/message 映射加 `task_fulfillment` | `api/app.py` 的 `_PUBLIC_TRACE_STAGE_BY_PRIVATE_NAME` / `..._MESSAGE_...` |
| 新增 `_public_fulfillment_diagnostic()` 投影 | `api/app.py`，白名单 `output_id` / `status` / `reason_code` / `candidate_count` |
| `TurnTrace.fulfillment` 字段 + `_capture_fulfillment()` | `eval/acceptance.py`，倒序取终态（修复轮优先） |

**刻意不外放** `items[].gap`（给人读的中文长句、可能带内部措辞）与
`answer_spans`（正文片段）：定位缺哪一格靠 `output_id` + `reason_code`，
那才是结构化判据。形状不完整时**整体不投影**——半截结构比没有更难排查。

### 5.3 另两条实测纠正（2026-08-09）

**① 四条独占正则：从「最该先治」降级为「不做」。**

会话中我曾判断 `_explicit_required_outputs`（§3.3b）的四条正则「爆炸半径最大、
应排第 2 优先」，理由是它**独占**——一条命中就丢掉题型表算出的整套契约。
实测推翻：

| 判据 | 实测 |
|---|---|
| 四条正则在 62 条真实 query 的命中 | **1/62（2%）** |
| 命中的是哪条 | `_DECISION_METHOD_RE`，且该题**历史 0 次 run** |

而且「改独占为合并」这个改法本身有害：合并会让契约项变多（4 → 4+3），
**在「填不满就拒答」的机制下，契约变长只会让拒答更容易**。
教训与 §3.4 那次同源——**从代码形状推严重性，不如直接量**。

**② 预检漏了 output_id 归一，噪音虚高三倍多。**

接线后立刻实测，发现 `check_satisfiability` 的比对是字面的，而契约侧与
produces 侧不是同一套字面 id（`evidence_boundary` 判缺时归一到 `counterpoint`、
`direct_answer` 归一到 `direct_assessment`）：

| | 不归一 | 归一后 |
|---|---|---|
| covered | 85（47%） | **150（84%）** |
| suspicious | 94（53%） | **29（16%）** |

62 条真实 query 产生 179 个 output 实例，其中 **65 个纯属字面差异**——
`evidence_boundary` 33 次、`direct_assessment` 32 次，两项都是几乎每题都有的基础项。

**这个数字同时证明了 fail-open 设计的必要性**：若当初让预检直接拦人，
53% 的 output、11% 的整题会被拦——**一个观测器会变成系统最大的拒答来源**。
作者 docstring 里那句「让一张不完整的声明表拥有拦截权，比不做更糟」，
现在有了具体量级：**比不做糟 53%**。

修法是**依赖注入**而非复制：归一表 `_LEGACY_OUTPUT_ALIASES` 是 runtime 层的
唯一事实源，而 `check_satisfiability` 在 services 层，`scripts/layer_audit.py`
门禁禁止 `services/** → runtime.*`。故给它加 `normalize` 回调（默认恒等），
由 adapter 侧注入。抄第二份表就等于把那边的修改和这里的比对解耦。

**③ 接线时踩了鸭子类型坑（第二次踩同一个）。**

第一版直接调 `registry.authorized_specs(...)`，**37 条既有测试立刻转红**——
`registry_factory` 的多个测试替身返回的是字符串 `"registry"`。
与 `38c06356` 那次在 `ResearchDeadline` 上加方法是同一个坑：
**在鸭子类型注入点上新增依赖，必须对缺失接口 fail-open**。
最终实现对缺失接口与任何异常都返回空结果——观测手段不得有能力杀掉整轮回答。

---

## 6. 明确不做

- **不放松契约门。** 它挡的是「没有证据支撑的结论」，正是要保留的
- **不让 LLM 扩大/缩小任务门。** 只给否决权
- **不让 LLM 自创题型。** 题型是封闭枚举，下游按它派活
- **不继续为 P1/P2 两类伤口堆正则。** 时态/语气与语义分层用正则表达不了，
  应由裁定与口径拆分解决
- **不动 `task_fulfillment` 的事后判缺。** 它工作正常，且诊断粒度已经很好

---

## 7. 评审要回答的问题

1. ~~**第 3 步走路 A 还是路 B？**~~ **已由 2026-08-09 实测答掉，无需评审：**
   两条路都不用走。路 A 描述的静态声明**早就建好了**（`ToolSpec.produces`
   11/12 已填 + `check_satisfiability` fail-open 三态 + 防漂移对账测试），
   只是**没接线**；路 B 的语料前提不成立（判缺结果从未结构化落盘）。
   实际做法是**路 C**：直接探针纯函数。详见 §3.4 的二次更正与 §5.3。
   > ⚠️ 本条原文两处依据均已被推翻，保留在此仅为留痕：
   > 「registry **不支持**事前查询」——错，它支持，见 §3.4 二次更正；
   > 「离线统计 **108 条**真实 run」——数字不实，全并五个来源实得 62 条去重
   > （真实用户流量仅 23 条）。
2. 置信度阈值定在哪、由谁定？建议初版**不设浮点阈值**，只用
   「结构自洽 / 结构不完整」这个二值判断，避免调参
3. 评测固化用 question hash 缓存，还是评测模式强制规则首选？后者更简单但覆盖不到
   「裁定本身是否改善了答案」这个问题
4. 第 2 步的「只记录不生效」阶段要观察多久、看什么数？建议看两个数：
   低置信触发率、以及触发样本里人工判读的真实误判占比。前者高但后者低，
   说明触发条件太松，要回头改条件而不是往下推第 4 步
