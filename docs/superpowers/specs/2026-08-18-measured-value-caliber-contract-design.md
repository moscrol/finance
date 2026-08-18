# 量纲口径契约：让数值携带它的成立条件走完全链

- 日期：2026-08-18
- 触发：28 题验收集 trace-first 分诊（`docs/verification/2026-08-18-kc-acceptance-triage.md`）
- 状态：Phase 1–4 已接线（#199–#202）。4.5 口径绑定交付叠在 #202：C4/C5/A5 在 `deterministic_lane_answer` 取标的级表。C3 ✅；可判 6/15，I 未过。
- 前置阅读：`docs/trace-profile.md` §2 新增两条字段陷阱；`docs/prediction-ledger.md` `R-20260818-01..04`

## 0. 一句话

一个数值被生产出来时，它的**量纲 / 口径 / 来源**没有作为结构化字段跟着走，全靠自然语言承载；本 spec 把已经存在于 D0 和 `EvidenceAtom` 的契约接通到全链，并让判分器消费同一份注册表。

**这是接线，不是新建。** 两处地基已在。C4 证明的是标签可读，不是检索闸已建，见 §3.1。

---

## 1. 问题：同一个洞在四层显影

28 题里 12 道失败，逐题追到第一处错误变换后归层（证据见分诊报告 §Evidence）：

| 层 | 显影形态 | 题 | 一手证据 |
|---|---|---|---|
| **审查** | 裸数比裸数：答案「2.96万亿」vs 期望 `29569.03`（亿），差 0.10% 本在 ±1% 内 | B7 | `_extract_numbers` 实测抽出 `2.96` → 0 命中；按万亿归一后命中 `[2.96]` |
| **审查** | 裸措辞比裸措辞：答案「该日无行情数据」，拒答同义词表不含「无行情数据 / 休市」 | C1 | 答案全文一条不差满足 `expect_refusal` + 三个 `forbid_phrases` 全未触碰，仍判 FAIL |
| **检索** | 请求不带口径，取错表不报错 | A5 | 答案自述「按**主线数据**统计」给电力 8 家；判据要 `fact_theme_limit_heat_daily` 的储能 40 家 |
| **检索** | 口径粒度不匹配 | A7 | 答案给半导体 28 / 存储芯片 30 / CPO 22（板块粒度）；判据要「芯片概念」66（题材粒度） |
| **路由** | 盘面数值题落进知识库车道 | C4 / C5 | `synthesis reason_code=knowledge_lane_answer` |
| **降级** | 目标表为空，静默换表交付 | C3 | 目标 `fact_stock_technical_snapshot` 0 行，答案改用价格表拼出「技术面快照（数据截至2026-08-17收盘）」，未声明目标表不可得 |

**关键观察**：这六种形态没有一种是「模型笨」。数值都是真的、检索都真发生了、拒答措辞也是对的。坏的是**跨层传递时把成立条件丢了**，而**没有任何一层会因此报错**。

> 这与本仓已确立的可迁移原则同源：「授予的额度必须真的传到最下游执行者——只写进 telemetry 不生效，比不做更危险（仪表全绿、实际没人管）」。此处是同一句话的数据版：**口径只写进散文不进结构，等于没有**。

## 2. 直接回答三个分层问题

**是 harness 的问题吗？** 要分两个 harness：

- **评测 harness**（判分器 + 题集）：12 道失败里 **5 道**源在这（B7、C1 判官假红；A7 判据自相矛盾；B6 题面引用不存在的附件；A3 题面缺日期锚）。**问题最集中，且修起来最便宜**（零 LLM 成本，同一份 artifact 重算）。
- **产品 harness**（路由 / 工具装配）：C4 / C5 的车道路由。

**是检索还是合成？** 已确证各有：A5 是检索选错表；C3 是合成层交付时未披露降级。**但其余几道当前埋点判不出来**——`tool_result` 只落 `output_summary` 话术、不落原始载荷字段集（`trace-profile.md` §8 已记该缺口）。**「判不出来」本身是本 spec 要修的一项**，见 §4 Phase 3。

**是审查契约的问题吗？** 是，且最集中。但**修判分器只是止血**：它之所以判错，是因为在跟一个「没声明口径的输出」比对。两边都改成同一份注册表，才是根治。

## 3. 已有地基（禁止重造）

### 3.1 `market_timeseries.MetricSpec` —— 标签可读，闸未建

```python
@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str                 # "家" / "亿元"
    aliases: tuple[str, ...]  # 措辞等价类
    caliber: str              # 精确到「表.列」，如 fact_market_daily.limit_up
```

注册表注释写着：「新增指标只允许在这里登记（key → 固定查询口径），**不允许把用户问题文本拼进 SQL**」。

**C4 证明的是标签可读，不是闸已建。** 题要的是：看到 `fact_sector_daily.amount=6112588.6` 这行脏数，并质疑单位。产品实际走知识库车道 + D0「全市成交额」；模型读到口径散文后拒答，避免了把全市成交额当 MLCC 报出。检索请求从未带「我要 MLCC 板块成交额」，所以没碰到那行脏数，评测仍红（`amount_raw` 未观察 + `knowledge_lane_answer`）。

**当前边界**：只通了两处——`:283` 缺口告警、`:324` 渲染进数据块。不进证据行、不进合成上下文、判分器不知道它存在；**检索请求也不带 caliber**。Phase 4.1 要补的是检索期 fail-closed，不是把这段散文再写厚。

### 3.2 `research_contract.EvidenceAtom` —— schema 已正确，未接线

```python
@dataclass(frozen=True)
class EvidenceAtom:
    metric: str | None      # 指标名
    value: str|int|float|None
    unit: str | None        # 量纲
    period: str | None      # 时间口径
    source_id: str          # 来源口径
    provenance: dict
```

**形状完全正确**。但主链构造处 `answer_model.py:2672-2678` 传 `metric=None, unit=None`；`research_owner.py` 侧数字仍以散文待在 `claim_text` 里（`f"双红{row.get('double_red_days')}天"`）。

**结论：`value`+`unit` 这对字段全链在场率接近零，数字实际靠散文传递。**

## 4. 方案

### Phase 1 — 审查侧止血（`EVAL_ONLY`，零 LLM 成本，先做）

不动产品，先让判分器停止发假红。

1. **量纲归一**：`_fact_rule` 数值分支在 `_extract_numbers` 后补中文数量级候选（万亿 / 亿 / 万 → 同量纲展开）。**只加候选、不改原值**，与既有 `_decrease_signed_numbers` 同一手法（该手法已在仓内验证：中文把负号放在方向词上，故为负期望补候选）。
2. **措辞等价类外置**：拒答判定的 alternatives、`must_mention` 的同义词，从判分器内部硬编码提到 `intelligence/eval/cases/verdict_equivalence.json`，与 `MetricSpec.aliases` 用同一套等价类语义。C1 的「无行情数据 / 休市」进拒答类。
3. **失败时附证**：verdict FAIL 分支输出 `extracted_numbers`（前 20 个）与 `matched_aliases`。**这一条价值最高**：它让「产品没答」与「判官没认出」一眼可分，本次靠人工复算才发现的两处假红，以后自动可见。
4. **判据自洽门禁**：`pass_rule`（人读）与 `expect_facts`（机器）不得互相矛盾。A7 的 `pass_rule` 说「涨停家数**或**成交占比**之一**」，`expect_facts` 却要求两个精确值同时命中——加一条 CI 断言，新增/修改题目时检出。

**验收**：同一份 `20260818T051630Z.json` 重跑 board，B7 两条 fact 与 C1 转 PASS，其余 26 题真值列**逐题不变**；08-15 baseline 同样重跑，除这两题外不变。

B7 / C1 的 overlay 现为 `semantic_required`：只修量纲/措辞、不改 coverage，假红消掉后会停在「不可判」，到不了通过。Phase 1 须把这两题 overlay 改成 `structured`（与已绿的 C2 同形）。这不是改题问什么，是承认结构化规则已经够判。

### Phase 2 — 题集契约（`EVAL_ONLY`）

1. **日期锚必须下达**：`date` 与 `query` 分离导致 9 题产品按「今天」作答，该组 **0/9 通过**。二选一——拼进 `query`，或 runner 把 `date` 作为显式时间上下文传入。**两种都不改产品。**
2. **附件类题面必须有附件**：B6 题面说「把**这份**卖方材料提纯」却无材料，产品要求澄清是**正确行为**。要么补材料，要么改判据为「应当要求澄清」。
3. **相对时间题另立分组**：A8 / C6 用「现在」「最近」而期望值冻结在某日，结构性不可复现。单独分组、不进主判定分母。

**验收**：可判子集分母从 16/28 升到 ≥22/28；A3 的 `close=12.11` 出现在答案（A6 已证同数据可得）。

### Phase 3 — 观测：把「判不出来」变成「判得出来」（`HARNESS_FIX`）

`tool_result` 落盘增加 `dataset`、`caliber`、`payload_field_names`（字符串数组，非空）与 `payload_sha256`，**不落正文**（避体积与脱敏）。

字段名清单只能切开「取到了但没写进答案」和「根本没取到」。**切不开错表**：错表也可能有「家数」「成交额」这种同名字段。A5 这种「选错表」要靠 `dataset` / `caliber` 才能判。

**验收**：下一批同形 run 中，每条 fact 失败都能给出「retrieve 侧 / synthesize 侧」二选一，不再有 `DEPTH_INSUFFICIENT`；A5 能标出实际 dataset 与期望 caliber 不一致。

### Phase 4 — 产品侧接线（`DATA_CONTRACT_FIX`，前三阶段出数后再动）

1. **`MetricSpec` 提升为跨块注册表**：从 `market_timeseries` 提到独立模块，`evidence_registry` 的各 provider 登记自己产出的 `(metric, unit, caliber)`。**判分器消费同一份注册表**——这是根治的关键一步：题目声明 `caliber=fact_theme_limit_heat_daily`，检索请求带上它，取错表当场可检出（A5 / A7）。
2. **`EvidenceAtom` 的 `value`+`unit` 真填**：数值事实不再只以散文进 `claim_text`。合成层做量纲换算（亿 → 万亿）时，换算记录进 `provenance`。
3. **降级披露契约**（对应 C3，**优先级最高的产品项**）：目标 caliber 不可得时，**必须显式声明「你要的那张表是空的」**，不得静默换 caliber 交付。这条踩中产品自称的差异化优势——6 题基准里 Q6 我方胜出的理由正是「明说盘面系统无该板块独立行」，C3 上没做到。
4. **车道路由**（C4 / C5）：带明确指标名 + 日期 + 标的的查询不得落 `knowledge_lane_answer`。

**验收**：C3 复跑必须出现「目标表不可得」声明且不交付替代快照；A5 复跑命中题材口径；C4 / C5 不再落知识库车道。

## 5. 阶段依赖与优先级

```
Phase 1（判分器）──┐
Phase 2（题集）  ──┼→ 先跑一次 28 题，拿到「尺子修好后的真实读数」
Phase 3（埋点）  ──┘        ↓
                    Phase 4（产品）按真实读数排序再动
```

**先做 1+2+3 的理由**：它们全部 `EVAL_ONLY` / `HARNESS_FIX`，不动产品，且 Phase 1 可用同一份 artifact 零成本复算。**在尺子没修好之前动产品，等于拿一把读数不准的尺子指导施工**——本次「B7 回归」正是这样一个差点被写进主干的误判。

## 6. 明确不做

- **不为满足指标制造事件**：`trace-profile.md` §8 已有先例——`route` 在 codex 侧是结构性不存在，把结构差异写成埋点缺口会诱导造假事件。本 spec 的 Phase 3 加 `dataset` / `caliber` / 字段名清单，不造 span。
- **不改题集本体的题面语义**：Phase 2 只补日期锚与附件，不改题目问什么、不改判分器判什么。题面 sha256 前后入台账。
- **不在 Phase 1 之前动产品**：见 §5。
- **不引入第二份指标注册表**：Phase 4.1 是把 `MetricSpec` **提升**，不是在别处新建一份（本仓「不要另建第二份清单」纪律）。

## 7. 残余不确定

| 项 | 当前判不了的原因 | 补齐路径 |
|---|---|---|
| A5 / A9 / A10 / C4 / C5 是检索侧还是合成侧 | 旧 artifact 的 `tool_result` 只有话术摘要 | Phase 3 已接线；要等带四字段的新 28 题 run |
| 其余失败是否也踩量纲/措辞盲区 | Phase 1.3 已在 FAIL 上附抽出数 | 新 run 的 FAIL 理由里直接看 |
| 7 道「不可判」的成因 | 08-18 旧尺子 | Phase 1 尺子 + 新 run |

## 8. 实施记录（2026-08-18）

四层都已接线，不是「设计稿」。PR 叠栈：#199 Phase 1 判分器 → #200 Phase 2 题集 → #201 Phase 3 埋点 → #202 Phase 4 产品。未合入 main，未切 8792。

| Phase | 落点 | 状态 |
|---|---|---|
| 1 审查止血 | `acceptance_verdict` 万亿候选、拒答等价类、FAIL 附证、A7 门禁；B7/C1 overlay→structured | 同一份 `20260818T051630Z` 复算：B7/C1 ❌→✅，其余 26 真值列不变 |
| 2 题集契约 | 7 题 `date` 进 query；B6 改澄清；A8/C6 出主分母 | 新 run 可判 6/15，I 未过（分母到不了 22）。J 过（A3 有 12.11）。K 过（原 19 题不下降）。L 过 |
| 3 观测 | `tool_result` 的 `dataset`/`caliber`/`payload_field_names`/`payload_sha256` | episode 账本里 tool_result 四字段齐全、无路径。A5 能标 retrieve（主线表 ≠ 题材热度表）。C4/C5 无 episode tool_result |
| 4.1 注册表 | `intelligence/services/metric_spec.py`；判分器并入 aliases | 代码门绿。没有第二份注册表 |
| 4.2 EvidenceAtom | `bind_measured_value`；中期趋势填 `double_red_days` | 单测：2.96万亿 → 29600 亿元 + provenance |
| 4.3 C3 | `empty_caliber_disclosure` 罐头空表，不换价格表 | **新 run ✅**。原文声明 0 行 / 数据不可用，不用价格表 |
| 4.4 C4/C5 | `quick_fact` + `lane=research` | **不再 knowledge_lane_answer**。4.5 之前仍 ❌（全市总览+web） |
| 4.5 标的口径 | `bound_caliber_disclosure`：板块成交额 / 两日股价 / 题材涨停热度 | sidecar：C5 ✅；A5 正文储能 40 但 overlay 仍 ❔；C4 现库 611.26 vs 冻结算子 6112588.6 ❌ |

**还没做完、不要写成已绿：**

- Criterion I（可判分母 ≥22）未过：6/15。剩下的不可判主要是 semantic_required / 缺 observation。
- C4 冻结算子仍是 `amount_raw=6112588.6`；主库 07-21 MLCC 现为 611.26。脏行只剩 06-18 / 06-22。不要伪造 6112588.6。
- A5 overlay 仍 `semantic_required`，正文有储能 40 也停在 ❔。
- B6 本跑 ❌：要材料的澄清没打中 overlay 短语。
