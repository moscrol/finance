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

### 3.4 契约可满足性预检（本设计的增量）

> ⚠️ **成本更正（2026-08-05 复核后改写）。** 初稿写的是「同一份 registry 知识事前
> 也能用，白捡」——**这是错的**。`_claim_candidates`（`task_fulfillment.py:238`）
> 拿 `output_id` 去子串匹配**运行时已产出的 claim**（`claim.claim_id` / `claim.text`）。
> 事后判得出来，是因为那时 claim 已经存在；**事前没有这份知识可查。**
> 全仓不存在「能力 → 可产出 output」的静态声明。这一条是**新建能力，不是复用**。

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

本机有 **108 条去重真实 query 的 run 产物**。可以统计：
每个 `(question_type, required_output)` 组合历史上被 fulfilled 过没有。
从未被满足过的组合 → 可疑。

比路 A 便宜得多且无需维护声明，但它是**经验规律不是保证**：
新能力上线、旧样本不足都会误报。适合当**第 3 步的探针版**，
先用它量出「不可满足的 required_output 有多常见」，
再决定值不值得为路 A 付维护成本。

**建议先做路 B。** 它能回答「这个护栏值不值得建」这个问题本身，
成本是一个离线脚本。

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
| **第 1 步** | 止血：逐个修词面泄漏正则（`comparison` 已完成，`scenario_tree` 次之） | 进行中 |
| **第 2 步** | 3.2 + 3.3：候选/置信/低置信触发。**先不接 LLM**，低置信时仍走规则首选，只记录「本次本应裁定」 | 待评审 |
| **第 3 步** | 3.4 可满足性预检。可独立于 LLM 上线，纯确定性 | 待评审 |
| **第 4 步** | 3.5 + 3.6：接 LLM 裁定 + 校验 + 评测固化 | 待评审 |

**第 2、3 步都不引入非确定性**，可以先上并观察「本应裁定」的比例，
用真实数据决定第 4 步值不值得做。这样避免了「先改架构再发现没必要」。

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

1. **第 3 步走路 A 还是路 B？** 已查实：registry **不支持**事前查询（见 §3.4 更正），
   所以这不再是「白捡」。我的建议是先做路 B（离线统计 108 条真实 run），
   用它量出不可满足 output 的真实频率，再决定路 A 的维护成本值不值得付
2. 置信度阈值定在哪、由谁定？建议初版**不设浮点阈值**，只用
   「结构自洽 / 结构不完整」这个二值判断，避免调参
3. 评测固化用 question hash 缓存，还是评测模式强制规则首选？后者更简单但覆盖不到
   「裁定本身是否改善了答案」这个问题
4. 第 2 步的「只记录不生效」阶段要观察多久、看什么数？建议看两个数：
   低置信触发率、以及触发样本里人工判读的真实误判占比。前者高但后者低，
   说明触发条件太松，要回头改条件而不是往下推第 4 步
