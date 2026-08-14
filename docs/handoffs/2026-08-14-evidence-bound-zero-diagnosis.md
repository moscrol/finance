# Evidence Bound 为 0 的诊断与复核清单

**日期**: 2026-08-14  
**诊断者**: Claude (Devin)  
**问题**: Runtime 拿到证据（24-60条），但 `evidence_bound` 恒为 0，输出"证据不足"

---

## 一、判断依据

### 1.1 数据证据

从 `intelligence/eval/runs/20260813T1810Z-qc28-full.json` 统计 28 个 turns：

```
题型分组               总数  evidence_bound=0  evidence_bound>0
─────────────────────────────────────────────────────────────
A 组（A1-A10）         10         1 (10%)         9 (90%)
B 组（B1-B8）           8         7 (88%)         1 (12%)
C 组（C1-C10）         10         9 (90%)         1 (10%)
─────────────────────────────────────────────────────────────
总计                   28        17 (61%)        11 (39%)
```

**关键观察**：
- 所有 runs 都标记 `backend=continuous_glm`（说明 continuous runtime 已启用）
- 所有 turns 都有 `trace_steps`（17-35 步不等，说明 episode 确实执行了）
- **`evidence_bound=0` 的 turns 同时有 `evidence_count=0`**（说明根本没取到证据，不是取到了但没绑定）

### 1.2 题型差异

**A 组示例**（evidence_bound > 0）：
- A1: "2026-07-23 今天市场怎么样" → evidence_bound=3
- A3: "立新能源怎么看" → evidence_bound=14
- A2: "2026-07-21 收盘了，明天怎么看" → evidence_bound=3

**C 组示例**（evidence_bound = 0）：
- C2: "2026-02-17 涨停家数多少" → evidence_bound=0
- C4: "2026-07-21 MLCC 板块成交额多少" → evidence_bound=0
- C10: "2026-07-23 哪些板块双红" → evidence_bound=0

**B 组示例**（evidence_bound = 0）：
- B1: "光刻胶" → evidence_bound=0
- B2: "液冷" → evidence_bound=0
- B4: "电网设备是怎么发酵到 2026-07-23 双红的" → evidence_bound=0

### 1.3 代码证据

#### 证据 1: DETERMINISTIC_OWNER_TYPES 拒绝 continuous

**文件**: `intelligence/runtime/continuous_turn_adapter.py`

```python
# Line 78-80
DETERMINISTIC_OWNER_TYPES = frozenset(
    {"external_market", "quick_fact", "dated_market_review"}
)

# Line 247-248
if frame.question_type in DETERMINISTIC_OWNER_TYPES:
    return _declined_result()  # 直接拒绝，不走 continuous episode
```

**含义**: `quick_fact` 类型的问题**被硬编码排除**在 continuous episode 之外。

#### 证据 2: 题型到 question_type 的映射

**文件**: `intelligence/services/task_frame.py`

```python
# Line 41
"quick_fact": "current_fact_evidence",

# Line 693
"quick_fact": ("fact_value", "as_of_date", "evidence_boundary"),
```

**文件**: `intelligence/services/route_table.py`

```python
# Line 36
def is_quick_fact_query(query: str) -> bool:
    # 词面识别："多少"/"什么时候"/"股价"/"市盈率" 等快速查询

# Line 261-265
RouteEntry(
    route_id="quick_fact",
    ...
    question_type="quick_fact",
)
```

#### 证据 3: evidence_bound 的计算逻辑

**文件**: `intelligence/eval/acceptance.py`

```python
# Line 198-200
trace.evidence_bound = sum(
    1 for e in evidence if isinstance(e, dict) and e.get("status") == "hit"
)
```

**含义**: `evidence_bound` 只统计 `status="hit"` 的证据数量。如果 `evidence` 列表为空，结果恒为 0。

#### 证据 4: 两条执行路径

**文件**: `intelligence/runtime/conversation_orchestrator.py`

```python
# Line 41（编排格局注释）
# 编排格局：**一个调度器 + 两个引擎**
# A = agent_episode continuous loop（模型自选工具，生产默认）
# B = ask.answer_query 写死流程（接 quick_fact/external_market/dated_market_review 三题型）
```

**文件**: `intelligence/services/ask.py`（B 引擎）
- 有完整的查询执行逻辑
- **但没有调用 episode verifier 或 evidence binding**
- 返回结果不包含 `evidence_bound` 字段

### 1.4 交接记录确认

**文件**: `.agent-memory/20_projects/finance-workspace-private.md` Line 161

```markdown
- **🔴 卡点未解**：continuous 路径 `evidence_bound` 恒为 0，工具正常取回 24–60 条证据却输出「证据不足」。
  变量已锁定 `ASK_CONTINUOUS_RUNTIME`（off→30/13，on→0/0），**与代码版本无关**，可二分、零配额起步。
```

**解读**: 
- "off→30/13, on→0/0" 说明：
  - `ASK_CONTINUOUS_RUNTIME=off` 时：30个有证据，13个无证据
  - `ASK_CONTINUOUS_RUNTIME=on` 时：0个有证据，0个无证据（**这个读数可能是误读**）
- 但我们的实测数据显示：`backend=continuous_glm` 时，A组题型有 `evidence_bound>0`

---

## 二、初步诊断结论

### 2.1 根因

**题型路由差异，不是开关问题。**

- **C 组**（快速事实查询）→ `question_type="quick_fact"` → 被 `DETERMINISTIC_OWNER_TYPES` **强制排除** → 走 ask.answer_query 路径 → **设计上就不填充 evidence_bound**
- **B 组**（题材研究）→ 可能走 specialized owner 或其他路径 → 未绑定证据
- **A 组**（复杂研究）→ 走完整 continuous episode → 有 evidence binding → `evidence_bound > 0` ✅

### 2.2 我之前的错误判断

**错误**: 认为是 `ASK_CONTINUOUS_RUNTIME=off` 导致 continuous episode 没跑。

**为什么错**:
1. 所有测试的 runs 都标记 `backend=continuous_glm`
2. 所有 turns 都有 trace_steps（说明 episode 执行了）
3. A 组题型有正常的 `evidence_bound>0`

**正确认识**: `ASK_CONTINUOUS_RUNTIME` 只控制是否启用 continuous runtime，但**题型路由**决定了某个具体问题是否真的会走 continuous 路径。

### 2.3 这是 Bug 还是设计？

**我的判断：这是设计，不是 bug。**

**理由**:
1. `DETERMINISTIC_OWNER_TYPES` 是**硬编码的排除列表**（不是配置错误）
2. 快速事实查询（"涨停家数多少"）**不需要** LLM judge 的语义验证（成本高、延迟大）
3. 这类查询直接从 DuckDB 取数返回即可
4. 架构文档明确说明："一个调度器 + **两个引擎**"

---

## 三、需要复核的点（请下一个 Agent 验证）

### 3.1 核心假设验证

**假设 1**: `quick_fact` 题型被设计为不走 continuous episode

**验证方法**:
```bash
cd /Users/a77/finance-workspace-private
# 检查 DETERMINISTIC_OWNER_TYPES 的使用
grep -n "DETERMINISTIC_OWNER_TYPES" intelligence/runtime/continuous_turn_adapter.py

# 检查 quick_fact 路由
grep -n "quick_fact" intelligence/services/route_table.py
grep -n "is_quick_fact_query" intelligence/services/turn_controller.py
```

**预期**: 应该看到 `quick_fact` 在 continuous_turn_adapter 被显式排除。

---

**假设 2**: ask.answer_query 路径不填充 evidence_bound

**验证方法**:
```bash
# 搜索 ask.py 中是否有 evidence_bound 赋值
grep -n "evidence_bound" intelligence/services/ask.py

# 检查返回结构
grep -A 20 "def answer_query" intelligence/services/ask.py | head -30
```

**预期**: ask.py 不应该有 `evidence_bound` 的赋值逻辑。

---

**假设 3**: C 组题型确实被路由为 quick_fact

**验证方法**:
```python
# 在 intelligence/services/route_table.py 中测试
from intelligence.services.route_table import is_quick_fact_query

test_queries = [
    "2026-07-23 哪些板块双红",           # C10
    "2026-02-17 涨停家数多少",          # C2
    "立新能源 2026-07-20 涨了多少",     # C5
    "2026-07-23 今天市场怎么样",        # A1 (对照)
]

for q in test_queries:
    result = is_quick_fact_query(q)
    print(f"{q[:30]:30s} -> quick_fact: {result}")
```

**预期**: C 组应该返回 `True`，A 组应该返回 `False`。

---

### 3.2 交接记录的数据复核

**需要确认**: `.agent-memory` Line 161 的 "off→30/13, on→0/0" 这个读数是否准确。

**验证方法**:
```bash
cd /Users/a77/finance-workspace-private

# 统计最近 runs 的 evidence_bound 分布
python3 << 'EOF'
import json, glob
files = sorted(glob.glob('intelligence/eval/runs/202608*.json'), reverse=True)[:20]
for f in files:
    with open(f) as fp:
        data = json.load(fp)
    preflight = data.get('preflight_detail', '')
    cases = data.get('cases', [])
    eb_values = [turn.get('evidence_bound', 0) 
                 for c in cases for turn in c.get('turns', [])]
    nonzero = sum(1 for x in eb_values if x > 0)
    zero = sum(1 for x in eb_values if x == 0)
    print(f"{f.split('/')[-1]:40s} {preflight:30s} eb>0:{nonzero:2d} eb=0:{zero:2d}")
EOF
```

**问题**: 如果 `backend=continuous_glm` 时有 `evidence_bound>0` 的案例，那么 "on→0/0" 的结论是错的。

---

### 3.3 B 组题材研究的路径确认

**B 组题型**（如 "光刻胶"、"液冷"）也是 `evidence_bound=0`，但它们**不是** quick_fact。

**需要确认**:
1. B 组走的是什么路径？（specialized owner？theme research？）
2. 为什么它们也没有 evidence_bound？
3. 是设计行为还是缺陷？

**验证方法**:
```bash
# 搜索题材研究相关路由
grep -n "theme" intelligence/services/route_table.py
grep -n "theme_track" intelligence/services/turn_controller.py

# 检查 B 组题型的 question_type
# 从 runs JSON 中提取 B1-B8 的 question_type（如果有记录）
```

---

## 四、可能的修复方向（取决于复核结果）

### 方案 A: 如果是设计行为（我倾向这个）

**结论**: 不需要修复，这是架构设计。

**文档化建议**:
1. 在 `CLAUDE.md` / `AGENTS.md` 中明确说明：
   - 快速事实查询（C组）不走 continuous episode
   - `evidence_bound` 只在 A 组复杂研究题型有值
   - 验收台统计时需要按题型分组，不能用全局 `evidence_bound` 判断质量

2. 在验收脚本中加入题型过滤：
   ```python
   # 只统计走 continuous 路径的题型的 evidence_bound
   research_turns = [t for t in turns 
                     if t.get('question_type') not in DETERMINISTIC_OWNER_TYPES]
   ```

---

### 方案 B: 如果确认是缺陷

**需要满足以下条件之一**:
1. 用户需求明确要求 C 组快速查询也要有 evidence_bound
2. 验收标准依赖 evidence_bound，但没有区分题型
3. B 组题材研究理应有证据绑定但实际缺失

**修复方向**:

#### B1: 为 ask.answer_query 路径添加 evidence binding

**改动点**: `intelligence/services/ask.py`

**难度**: 中等（需要理解 ask 路径的返回结构，并与 episode 的 evidence 结构对齐）

**风险**: 可能破坏 ask 路径的性能（加入 evidence binding 会增加延迟）

---

#### B2: 把某些 C 组题型改路由到 continuous 路径

**改动点**: 
- `intelligence/services/route_table.py` 的 `is_quick_fact_query()`
- `intelligence/runtime/continuous_turn_adapter.py` 的 `DETERMINISTIC_OWNER_TYPES`

**难度**: 低（只改路由规则）

**风险**: 
- 延迟显著增加（从 DuckDB 直接取数 vs 走完整 episode + judge）
- 成本增加（每个查询都要调用 LLM judge）

---

#### B3: 在验收台单独处理 DETERMINISTIC 题型

**改动点**: `intelligence/eval/acceptance.py`

**方案**: 
```python
# 不统计 DETERMINISTIC_OWNER_TYPES 的 evidence_bound
# 或为这些题型使用不同的验收标准
if question_type in DETERMINISTIC_OWNER_TYPES:
    # 用其他指标（如 status、elapsed_s）评估
    pass
else:
    # 正常统计 evidence_bound
    trace.evidence_bound = sum(...)
```

**难度**: 低

**风险**: 低（只改统计逻辑，不改执行路径）

---

### 方案 C: 混合方案

1. **C 组快速查询**: 保持现状，文档化说明
2. **B 组题材研究**: 排查为什么没有 evidence_bound，按需修复
3. **验收台**: 按题型分组统计，避免误判

---

## 五、复核 Checklist

请下一个 Agent 按以下顺序验证：

- [ ] **验证假设 1**: `quick_fact` 是否被 `DETERMINISTIC_OWNER_TYPES` 排除
- [ ] **验证假设 2**: `ask.answer_query` 是否不填充 `evidence_bound`
- [ ] **验证假设 3**: C 组题型是否被路由为 `quick_fact`
- [ ] **复核交接记录**: "on→0/0" 的读数是否与实测数据矛盾
- [ ] **排查 B 组路径**: 题材研究走什么路径，为何无 evidence_bound
- [ ] **读取用户需求**: 用户是否真的需要所有题型都有 evidence_bound
- [ ] **读取验收标准**: 当前验收是否错误地对所有题型使用统一标准

---

## 六、关键文件清单

| 文件 | 作用 | 复核时必读 |
|------|------|----------|
| `intelligence/runtime/continuous_turn_adapter.py` | 定义 DETERMINISTIC_OWNER_TYPES，决定哪些题型走 continuous | ✅ 是 |
| `intelligence/services/route_table.py` | 题型路由规则，`is_quick_fact_query()` | ✅ 是 |
| `intelligence/services/ask.py` | B 引擎（deterministic 路径）的实现 | ✅ 是 |
| `intelligence/eval/acceptance.py` | 验收台计算 evidence_bound 的逻辑 | ✅ 是 |
| `intelligence/services/turn_controller.py` | 题型判定与路由决策 | 建议读 |
| `intelligence/services/task_frame.py` | 题型到 required_outputs 的映射 | 建议读 |
| `.agent-memory/20_projects/finance-workspace-private.md` Line 161 | 原始问题记录 | ✅ 是 |
| `docs/handoffs/2026-08-12-tool-interface-and-rag-fixes.md` | 相关历史问题 | 可选 |

---

## 七、我的置信度

| 判断 | 置信度 | 依据 |
|------|--------|------|
| C 组走 quick_fact 路径 | 95% | 代码 + 题型特征明确 |
| quick_fact 被排除在 continuous 外 | 99% | 硬编码常量，清晰可见 |
| 这是设计而非 bug | 75% | 架构注释支持，但缺用户需求确认 |
| B 组也应该有 evidence_bound | 50% | 不确定，需要排查 B 组实际路径 |
| 之前的 "on→0/0" 读数有误 | 70% | 与我们的实测数据矛盾 |

---

## 八、给复核 Agent 的建议

1. **先跑验证假设 1-3**，确认代码层面的事实
2. **再读用户需求**，确认 evidence_bound 的业务含义
3. **最后决定**：这是设计（文档化） vs 缺陷（修复）
4. 如果是缺陷，优先考虑方案 B3（验收台单独处理），成本最低

---

**诊断完成时间**: 2026-08-14  
**下一步**: 等待复核 Agent 验证假设并给出最终结论
