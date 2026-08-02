# B/C 组验收基线 + Knevo 信息量对比（2026-08-02）

承接 `docs/handoffs/`（2026-08-01e checkpoint）。**未重跑 A/B/C**，全部消费 08-01
冻结的存量 artifact；本段新增的只有信息量对比评审。

---

## 0. 与计划的偏差（先说清楚）

计划里第 4 步写的是「用独立 **Codex** evaluator 评」，且决策包里另有一条
「Codex 快照：重登 ChatGPT app sidecar 后冻结 28 份」。

实际执行用的是 **cockpit 本地代理**（`http://127.0.0.1:57244/v1`）的 `gpt-5.6-sol`：

- **独立性成立**：产品跑在 `continuous_glm / glm-5.2`，评审模型与产品无关，
  `evaluator.independent=true` 通过校验。
- **不是原计划那条路**：不是 `codex exec`，也没有动 ChatGPT app sidecar。
- **也没有让本轮做分析的 agent 自评**——那同样不满足 independent。

两份结果都通过 `validate-comparison`，artifact 自哈希与 queue 的
`source` / `rubric_sha256` / `entries` 全部绑定，可复核。

---

## 1. 运行基线（存量，未变）

| 组 | 正常 / 降级 | 真值 通过/失败/不可判 | 送达 通过/部分 |
|---|---:|---:|---:|
| A | 7 / 3 | 0 / 6 / 4 | 7 / 3 |
| B | 1 / 7 | 0 / 2 / 6 | 1 / 7 |
| C | 2 / 8 | 0 / 7 / 3 | 2 / 8 |
| **合计** | **10 / 18** | **0 / 15 / 13** | **10 / 18** |

正典题库 `acceptance_cases.json` sha256 = `a25c6825…a1c6`（未变）。
三份 live artifact 哈希均与 checkpoint 一致。

---

## 2. 信息量对比：11 / 18 已评

| 结果 | 条数 |
|---|---:|
| `knevo_wins` | **9** |
| `workbench_wins` | **2** |
| `tie` | 0 |
| `not_evaluated` | 0 |
| 未评 · missing（无参照快照） | 4 |
| 未评 · ineligible（题目本身不适合跨 agent 比） | 3 |

逐题：

| 题 | 结果 |
|---|---|
| B1-theme-photoresist | knevo_wins |
| B2-theme-liquid-cooling | knevo_wins |
| B3-theme-solid-state-battery | knevo_wins |
| B4-fermentation-trace | knevo_wins |
| **B5-cross-table-intersection** | **workbench_wins** |
| B7-volume-sentiment-evolution | knevo_wins |
| B8-valuation-band | knevo_wins |
| C1-future-date-no-data | knevo_wins |
| C2-non-trading-day | knevo_wins |
| C9-citation-integrity | knevo_wins |
| **C10-multi-turn-consistency** | **workbench_wins** |

> ⚠️ **口径**：这是**信息量**轴，不是真值轴。评审规则明确写着
> 「Factual correctness remains on the independent credibility axis and must not be
> silently re-scored here」。9:2 不等于「产品答错了 9 道」。

### 2.1 两场胜仗的共同点

`B5-cross-table-intersection`（前四题材里哪个双红）和
`C10-multi-turn-consistency`（07-23 哪些板块双红）——**都是需要本地精确数据、
有唯一正确答案、可逐项排除的题**。评审给的理由分别是「逐项排除→唯一双红→后续
验证点」和「直接给出唯一方向，且区分了双红与单项满足」。

### 2.2 九场败仗的共同点

题材研究（B1/B2/B3）、发酵回溯（B4）、量能演化（B7）、估值带（B8）、
休市/无数据处置（C1/C2）、引用完整性（C9）——**都是需要广度、因果链、标的分层、
催化剂顺序、跟踪信号的题**。评审反复给出同一类理由：参照方「更直接地给出
催化传导、标的分层、优先顺序、风险条件和后续验证信号」。

多条评审同时指出参照方**有显著的无出处细节风险**（B1「虽有显著来源与数据可信度
风险」、B3「虽有较高的无出处细节风险」），但按 rubric，可用决策信息仍然更多。

### 2.3 这个结果怎么用

**产品的强项是可审计的确定性回答，弱项是把证据组织成可决策的结构。**

这与既有的 degrades 归因互相印证：18 条降级里 13 条 `reason_code=validated`
（合成成功、校验通过），问题出在**出口的组织与交付**，不在检索或合成。

---

## 3. 未评的 7 题：保持显式，不补分

| 题 | 状态 | 含义 |
|---|---|---|
| B6-sellside-distillation | missing | 无 knevo 参照快照 |
| C3-empty-table / C4-unit-anomaly / C8-nonexistent-table | missing | 同上 |
| C5-data-contradiction / C6-strict-definition / C7-temporal-leakage | ineligible | 题目本身不适合跨 agent 信息量比 |

**不得把未评当 0 分**，也不得为了凑满而伪造参照快照（见决策包）。

---

## 4. 复核方式

```bash
W=<work clone>; PY=<venv python>; cd "$W"
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki "$PY" -m intelligence.eval.acceptance \
  validate-comparison docs/verification/2026-08-02-acceptance-b-knevo-result.json \
  --queue docs/verification/2026-08-02-acceptance-b-knevo-queue.json
# C 组同理换 b→c
```

预期：`✅ information comparison 有效：7 cases，evaluator=cockpit-cliproxy/gpt-5.6-sol`
（C 组 4 cases）。

产物：

| 文件 | 内容 |
|---|---|
| `2026-08-02-acceptance-{b,c}-knevo-queue.json` | 冻结对比包（含双方答案与各自 sha256） |
| `2026-08-02-acceptance-{b,c}-knevo-result.json` | 评审结果（自哈希，绑定 queue） |

rubric sha256 = `e86a7c4d…268fe`，与 queue 声明一致。
