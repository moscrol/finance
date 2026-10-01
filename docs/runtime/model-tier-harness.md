# 模型档位与 harness 分层（地板 / 天花板）

2026-10-02。状态：**档位框架已接线，默认行为不变（HOLD，2×2 实验结束后与 11/13–17/19 一起合入）**；
评测闸门 `scripts/harness_tier_gate.py` 可立即使用。

## 1. 目标

同一套 harness，**实惠模型用了能达标，强模型用了能更强**，而不是只给弱模型立规矩。
经济上的落点是：大部分题交给实惠模型，难题和没把握的题升到强模型（§5 分流）。

由此推出一条硬约束：**任何 harness 改动都不得让强模型变差**（§4 闸门）。只帮弱模型、
却压住强模型的改动，要么不合，要么只对 economy 档生效。

## 2. 三层

| 层 | 内容 | economy | frontier |
|---|---|---|---|
| 地板 | 硬路由、固定步数、低置信度先澄清、正则车道判定 | 严格执行 | 降为建议，模型可自行处理 |
| 天花板 | 工具质量、证据干净程度、研究步数、证据长度 | 预算保守 | 预算放开 |
| 核查 | 数字闸、证据边界、检索硬触发下限、单位换算代码化 | **全开** | **全开** |

核查层永远不随档位放松：强模型同样会编数字、同样会漏单位，核查对它只有好处没有限制。

按这个分法回看 2026-10-01 的 19 个补丁：

* 两边都受益（天花板 / 核查）：工具说明瘦身（−32%）、单位类与字段单位（12、15）、
  不检索车道审计（19：该查的题不再零检索）、内容正确性题集（10）。
* 偏地板（对强模型可能多余）：一部分正则路由（16、17 的定义/分析判定）。这些在 frontier
  档下的影响要用 §4 的闸门实测，不能凭感觉。

## 3. 当前接线（`intelligence/services/model_profile.py`）

选档：环境变量 `FWP_MODEL_PROFILE=standard|economy|frontier`。未设置或取值不认识 → `standard`。

| 旋钮 | 接入点 | standard（= 引入前） | economy | frontier |
|---|---|---|---|---|
| 研究循环步数 | `agent_research.max_steps()` | 4 | 4 | 8 |
| 证据字符预算倍率 | `kb_rag.evidence_budget_for_query()` | 1.0（封顶 8000） | 1.0 | 1.5（封顶 12000） |
| 路由权威 | `turn_controller._apply_policy()` | binding | binding | advisory |

* **优先级**：单项环境变量（如 `ASK_AGENT_MAX_STEPS`）> 档位 > 代码默认值；上限
  `MAX_CONFIGURED_STEPS=24` 不变。产品级硬顶 `PRODUCT_MAX_TOOL_CALLS=60` / 600s 不受档位影响。
* **advisory 的确切含义**：controller LLM 置信度 < 0.6 时，binding 一律转 clarify；advisory 下
  - 题面自带落点 + 车道是 chat/meta/clarify → 升到**带检索**的 knowledge 车道，由模型自行消歧；
  - 题面自带落点 + 车道是 research/workflow/knowledge → 按原车道走后续规则（不再被截成 clarify）；
  - 题面含指示词却无题内先行词、或带「上次/刚才/你说的」等跨轮标记（「那这个呢」「它还能涨吗」）
    → **照旧 clarify**：信息确实缺失，强模型也猜不出。
  - 确定性规则产出的 clarify（不经 `_apply_policy`）不受影响；检索硬触发下限对所有档位生效。
* **economy 目前数值与 standard 相同**：它是 §5 分流预留的身份（`escalation_eligible=True`），
  具体数值等 2×2 实验数据校准，不拍脑袋。
* 等价性由 `intelligence/tests/test_model_profile.py` 锁死：standard 的证据预算与引入前的
  实现逐项比对；高置信度判断在 standard 与 frontier 下 `to_dict()` 完全一致。

## 4. 评测闸门（每个 harness 改动都要过）

```
# 四次运行：{实惠模型, 强模型} × {改动前, 改动后}，同一题面
python3 scripts/content_correctness_eval.py export --out /tmp/cc_prompts.jsonl
# …各自产出 answers.jsonl 后：
python3 scripts/content_correctness_eval.py score --answers wb.jsonl --json > wb.json   # 其余三份同理
python3 scripts/harness_tier_gate.py check \
    --weak-base wb.json --weak-new wn.json --strong-base sb.json --strong-new sn.json
```

* **逐题判定**，不只看通过率——「修好 2 题、弄坏 2 题」通过率不变，但强模型弄坏的那题就是
  改动在限制强模型的证据。
* FAIL：强模型有任何一题从过变不过，或弱模型净退步；WARN：强模型无退步、弱模型无净增益；
  PASS：强模型无退步、弱模型净增益 > 0。退出码 FAIL=1，其余 0，输入错误 2。
* 同时报「强弱差距」（同版 harness 下强模型领先多少题）：差距缩小 = 在补地板；强模型自己也涨 =
  在抬天花板。两者都要，分开看。
* 任何逐题判分的评测都能接入：转成 `{"cases": {"<id>": true|false}}` 即可（路由探针、2×2 实验
  的 judge 结果都适用）。
* 档位本身也要过这道闸：强模型 `FWP_MODEL_PROFILE=frontier` vs `standard` 跑一遍，确认放开
  天花板确实没有让强模型变差，再考虑把 frontier 设为强模型的默认。

## 5. 路线图（按依赖排序，均需 2×2 实验数据）

1. **用实验数据校准档位**：先用闸门比 frontier vs standard（强模型），再定 economy 是否要比
   standard 更紧（更少步数换成本）。
2. **路由从命令改成提示**（frontier）：把规则的判断与理由放进提示，模型可提出不同意见；当前
   advisory 只覆盖「低置信度不强制澄清」这一处，是最小可验证的一步。
3. **按难度分流**：economy 先答；核查不过（数字闸 / 证据边界 / judge 低分）或模型自报没把握
   → 升到强模型重答。成本收益最大的一项，前提是核查信号足够准——这要先看实验里核查闸的
   误报率。
4. 更多旋钮按「闸门实测有收益」再加，不预先铺开（工具调用预算、synthesis 预算、子研究分支数）。

## 6. 本次顺带发现（未修）

* 「上次说的那个怎么样」被确定性规则判成 `comparison_analog` 研究车道（与档位无关，
  standard 下同样如此）：「上次说的」触发了类比路由。应走跨轮回指 / 澄清。记入后续路由审计。
