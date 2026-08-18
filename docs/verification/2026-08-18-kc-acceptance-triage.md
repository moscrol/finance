# Agent Run Triage Report

## Verdict

- outcome: ROOT_CAUSE_CONFIRMED
- mode: M1
- failure_criterion: 28 题验收集的确定性判分器（`acceptance_verdict.py`）对 `expect_facts` 给出 FAIL/UNJUDGEABLE；以 `board --run` 输出的「真值」列为准
- trace_coverage: 28 case / 36 run 目录，每 run 含 `trace.jsonl` + `continuous-episode.json` + `answer.md` + `report.json`；缺工具原始载荷全文（trace 只落摘要）
- trace_depth: D3
- completion_status: PARTIAL_SUCCESS
- confidence: high

## Prior prediction closure

| prior report | recommendation ID | verification_prediction（原文） | prediction_outcome | evidence | implication |
|---|---|---|---|---|---|
| 2026-08-15 轨道 A Round 5 F-003 | `R-20260815-25` | 新的 `tool_error` 且 `error=tool_exception` 的事件 `detail` 非空，形如 `ClassName: first line`，且不含 `/Users/`。再出现 `detail=""` 即 refuted | still_pending | E-008 | 本批 36 个 run **零** `tool_exception` 事件，没有同形样本可测。**不得因「没出现空 detail」记 confirmed**——那是没触发，不是验证通过 |
| 2026-08-15 标准 M1 F-001 | `R-20260815-04` | 空 draft 的 turn 其 `draft_source` 非空 | still_pending | — | 本批无空 draft turn（28/28 completed），无同形样本 |
| 2026-08-16 outlook M1 F-001 | `R-20260816-01` | 首轮 finalize `model_turn` payload 含 `timeout_asked` | still_pending | — | 本批无超时 run，未触发该路径 |

- ledger: `/Users/a77/finance-workspace-runtime/docs/prediction-ledger.md`
- fix_type_refuted_streak: 0（本次无 refuted）

## Executive finding

第一处错误变换不在被审 agent 里，而在**判分器**：`acceptance_verdict.py` 的数值比对没有「万亿/亿」单位归一，B7 答案已写出正确成交额（`2.96万亿` / `2.19万亿`，与期望 `29569.03` / `21949.97` 亿相差 0.10% / 0.23%，均在 ±1% 容差内），却被判 `not observed within tolerance`。该题在 08-15 基线为「不可判」、本次变「失败」，因此**被记为一次回归的，实际是产品答得更完整之后撞上判分器盲区**。

## Expected vs actual path

| L1 step | expected | actual span/action | status | evidence |
|---|---|---|---|---|
| retrieve | 取 07-21/07-23 的 `total_amount` | `finance_query` 返回带标签载荷 `市场成交额=29569.03` / `=21949.97` | ok | E-001 |
| observe | 载荷进入合成上下文 | 两值均出现在 episode 上下文 | ok | E-001 |
| synthesize | 答案给出两日成交额 | 答案写「两市成交约2.96万亿」「成交2.19万亿」，单位换算+四舍五入 | ok | E-002 |
| stop | 判分器按容差裁定 | `_extract_numbers` 抽出 `2.96`/`2.19`，与 `29569.03`/`21949.97` 比对，0 命中 → FAIL | **fail** | E-003, E-004 |

## Failure detection

| failure span | L0 | L1 | exact L2 | evidence excerpt | confidence |
|---|---|---|---|---|---|
| `acceptance_verdict.py::_fact_rule`（B7 两条 fact） | HARNESS | observe | `execution-error-category-formatting` | `期望 29569.03 ±295.69 → 命中 0 个 []`；`按万亿口径找 2.9569 ±1% → 命中 [2.96]` | high |
| A5/A7/A9 fact 缺失 | UNCLEAR | retrieve | `DEPTH_INSUFFICIENT(D4)` | 带标签正则在 trace 中 0 命中，但 trace 不落工具载荷全文 | low |

## Hypotheses

| ID | ranked hypothesis | falsifiable prediction | evidence/probe | status | probe_if_absent | why |
|---|---|---|---|---|---|---|
| H1 | B7 是本批十张 PR 引入的产品回归 | 若成立，B7 答案应缺失或写错两日成交额 | E-002 | REJECTED | — | 答案两值都在且数值正确，仅单位不同 |
| H2 | B7 是「仪表变好后暴露的旧病」（产品一直答不对） | 若成立，按万亿归一后仍不应命中 | E-003 | REJECTED | — | 归一后 `[2.96]`/`[2.19]` 均命中且在容差内 |
| H3 | B7 失败源于判分器缺单位归一 | 若成立，`_extract_numbers` 抽不出万亿级原值，且代码中无 万亿/亿 换算 | E-003, E-004 | **CONFIRMED** | — | 实测 0 命中 + 源码只处理负号方向词与别名窗口，无单位分支 |
| H4 | 其余 fact 失败（A5/A7/A9/A10/C4）主因是「检索没捞到」 | 若成立，工具载荷里不应存在该字段值 | E-006 | INCONCLUSIVE | 在 `episode_tool_batch` 的 `tool_result` 落盘完整 payload（或加 `payload_sha256`+字段名清单）；若期望字段名出现在 payload 而未进答案，则改判 synthesize 侧 | trace 只落 `output_summary` 话术，profile §8 已记该缺口；「trace 里没有」不等于「没检索到」 |
| H5 | 题面不带日期锚是失败的充分条件 | 若成立，带日期的题应全部通过 | E-005 | REJECTED | — | 带日期 19 题中仍有 9 题失败；**但不带日期的 9 题 0 通过**，故它是必要不充分条件 |

## Causal findings

### PRIMARY

- failure_span_id: `20260818T051630Z/B7-volume-sentiment-evolution/verdict.fact:2026-07-21.total_amount`
- root_location: `intelligence/eval/acceptance_verdict.py::_fact_rule`（数值分支，`tol_pct` 比对处）
- excerpt: `期望 29569.03 ±295.69 → 抽出的数里命中 0 个 []` / `若按「万亿」口径找 2.9569 ±1% → 命中 [2.96]`
- l0: HARNESS
- l1: observe
- l2: `execution-error-category-formatting`
- l3: n/a
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-004, E-007]
- explanation: 判分器把答案文本抽成裸数值后直接与期望比容差，未做中文数量级单位（万亿/亿/万）归一。产品已正确检索并正确表达两日成交额，但因表达单位为「万亿」而被判失败。后果不是单题误判：它使「回归/改善」的方向在台账上被记反——B7 从 08-15 的「不可判」变「失败」，被写进验收报告当作本批唯一回归。

### SECONDARY

- failure_span_id: `20260818T051630Z/{A3,B6,C3,A8,B1,B2,B3,B8,C6}/query` 无日期锚
- root_location: 题集 `acceptance_cases.json` 的 `query` 与 `date` 分离，日期未随查询下达产品
- excerpt: `带日期=否  ❌ 失败 3 题 [A3, B6, C3]` / `带日期=否  ❔ 不可判 6 题 [A8, B1, B2, B3, B8, C6]` / `带日期=否 ✅ 通过 0 题`
- l0: HARNESS
- l1: configure
- l2: `configuration-mismatch-category-tool-definition`
- l3: n/a
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION, INCORRECT_PATH]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-005]
- explanation: 9 道题的 `query` 不含日期，产品按「今天」作答，而 `expect_facts` 冻结在 case 的 `date`。实证：A3（立新能源，冻结日 07-23）答案给 08-17 收盘 14.40 元；同一实体在带日期的 A6 里答出 12.11 元——正是 A3 期望而未出现的值。该组 0/9 通过，是判定分母被压缩的主因之一。

### TERTIARY

none

## Evidence → Finding → Path

### Evidence

#### E-001
- title: B7 检索侧已取得两日成交额（带字段标签）
- run_id: `run_20260818_130434_991215`
- step_or_span_id: `trace.jsonl` / `continuous-episode.json` 内 `finance_query` 结果载荷
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.finance-runtime/live-probe-traceability/users/live-probe/runs/run_20260818_130434_991215/`
- observed_at: 2026-08-18T13:04:34+08:00
- raw_excerpt: |
    日期=2026-07-21；市场阶段=反弹阶段；…；市场成交额=29569.03；成交额环比=9.44；…
    日期=2026-07-23；市场阶段=反弹阶段；…；市场成交额=21949.97；成交额环比=-17.27；…
- observation: 两个期望值以「字段=值」形式出现在检索载荷中，各 11 处
- confidence: high

#### E-002
- title: B7 答案已表达两值，单位为万亿
- run_id: `run_20260818_130434_991215`
- step_or_span_id: `cases[B7].turns[0].answer`
- native_or_normalized: native
- source_type: transcript
- source_ref: `intelligence/eval/runs/20260818T051630Z.json`
- observed_at: 2026-08-18T13:04:34+08:00
- raw_excerpt: |
    07-21（E4）：…两市成交约2.96万亿、环比+9.4%…
    07-23（E2）：…成交2.19万亿、环比-17.3%…
- observation: 答案含 2.96万亿 / 2.19万亿；换算为亿分别是 29600 / 21900，与期望相差 0.10% / 0.23%
- confidence: high

#### E-003
- title: 判分器数值抽取实测
- run_id: `run_20260818_130434_991215`
- step_or_span_id: `acceptance_verdict._extract_numbers`（对 B7 答案实跑）
- native_or_normalized: normalized
- source_type: log
- source_ref: 本次分诊实跑输出
- observed_at: 2026-08-18
- raw_excerpt: |
    期望 29569.03 ±295.69 → 抽出的数里命中 0 个 []
    期望 21949.97 ±219.50 → 抽出的数里命中 0 个 []
    抽出的数：[-17.3, -11.8, …, 1.94, 2.19, 2.65, 2.96, …]
    若按「万亿」口径找 2.9569 ±1% → 命中 [2.96]
    若按「万亿」口径找 2.1950 ±1% → 命中 [2.19]
- observation: 原口径 0 命中；万亿归一后两值均命中且在 ±1% 内
- confidence: high

#### E-004
- title: 判分器无数量级单位归一分支
- run_id: n/a
- step_or_span_id: `acceptance_verdict.py:680-696`
- native_or_normalized: native
- source_type: code_reading
- source_ref: `/Users/a77/finance-workspace-runtime/intelligence/eval/acceptance_verdict.py:680-696`
- observed_at: 2026-08-18
- raw_excerpt: |
    numbers = _extract_numbers(candidate_text)
    if float(expected) < 0:
        numbers = numbers + _decrease_signed_numbers(candidate_text)
    …
    matched = any(abs(value - float(expected)) <= tolerance + 1e-9 for value in numbers)
- observation: 数值分支只补负号方向词候选，无 万亿/亿/万 换算；别名窗口与字面量各有专门处理，唯独缺单位
- confidence: medium（code_reading 封顶；已由 E-003 实测佐证到 high）

#### E-005
- title: 日期锚分组统计
- run_id: n/a
- step_or_span_id: 28 case × (`query` 含日期?) × 真值
- native_or_normalized: normalized
- source_type: file
- source_ref: `intelligence/eval/cases/acceptance_cases.json` + `board --run` 输出
- observed_at: 2026-08-18
- raw_excerpt: |
    带日期=否  ❌ 失败  3 题  ['A3-stock-deep-dive','B6-sellside-distillation','C3-empty-table']
    带日期=否  ❔ 不可判 6 题  ['A8','B1','B2','B3','B8','C6']
    带日期=是  ✅ 通过  4 题；带日期=是 ❌ 失败 9 题
- observation: 不带日期的 9 题通过数为 0；带日期的 19 题中仍有 9 题失败
- confidence: high

#### E-006
- title: A5/A7 期望字段在 trace 带标签形式零命中
- run_id: `run_20260818_125255_270990`（A5）
- step_or_span_id: `trace.jsonl` + `continuous-episode.json`
- native_or_normalized: native
- source_type: trace
- source_ref: 同 run 目录
- observed_at: 2026-08-18
- raw_excerpt: |
    /储能[^；"]{0,20}?(\d+)/ → 0 处
    /风电[^；"]{0,20}?(\d+)/ → 0 处
- observation: 裸数字 `40`/`29` 在文件中有大量命中，但全部落在 `content_hash` 十六进制与 token 计数里；带实体标签的形式 0 命中
- confidence: medium

#### E-007
- title: B7 在 08-15 基线为「不可判」
- run_id: `20260815T1005Z-r5-clean-baseline-3`
- step_or_span_id: `board --run` 真值列
- native_or_normalized: normalized
- source_type: file
- source_ref: `intelligence/eval/runs/20260815T1005Z-r5-clean-baseline-3.json`
- observed_at: 2026-08-15
- raw_excerpt: |
    B7-volume-sentiment-evolution  ❔ 不可判 → ❌ 失败
- observation: 同题真值由不可判变失败，聚合数（通过4/失败12/不可判12）两批完全相同
- confidence: high

#### E-008
- title: 本批零 `tool_exception` 事件
- run_id: 全部 36 个 live-probe run
- step_or_span_id: `trace.jsonl` 全扫
- native_or_normalized: native
- source_type: trace
- source_ref: `/Users/a77/.finance-runtime/live-probe-traceability/users/live-probe/runs/`
- observed_at: 2026-08-18
- raw_excerpt: |
    tool_exception 事件数: 0
- observation: 无同形样本，`R-20260815-25` 的 live 臂本批仍未触发
- confidence: high

### Findings

#### F-001
- title: 判分器缺中文数量级单位归一，把正确答案判成 fact 缺失
- status: validated
- failure_span_id: `20260818T051630Z/B7/verdict.fact`
- root_location: `acceptance_verdict.py::_fact_rule` 数值分支
- l0: HARNESS
- l1: observe
- l2: `execution-error-category-formatting`
- l3: n/a
- violated_authority: tool_contract
- causality: PRIMARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION]
- failure_detection_timing: SILENT_UNDETECTED
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-001, E-002, E-003, E-004, E-007]
- confidence: high
- explanation: 产品正确检索并正确表达了两日成交额，但表达单位为「万亿」；判分器抽裸数比容差，无单位归一 → 判 FAIL。影响不止一题：它让台账把一次表达改善记成回归。

#### F-002
- title: 题面与冻结日分离，9 题无日期锚，产品按今日作答
- status: validated
- failure_span_id: `20260818T051630Z/{A3,B6,C3,A8,B1,B2,B3,B8,C6}/query`
- root_location: `acceptance_cases.json` 的 `date` 未随 `query` 下达
- l0: HARNESS
- l1: configure
- l2: `configuration-mismatch-category-tool-definition`
- l3: n/a
- violated_authority: tool_contract
- causality: SECONDARY_FAILURE
- propagation_impact: [QUALITY_DEGRADATION, INCORRECT_PATH]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-005]
- confidence: high
- explanation: 该组 0/9 通过。A3 与 A6 是同实体对照：A6 带日期答出 12.11 元，A3 不带日期答出 08-17 的 14.40 元——同一份数据，日期锚决定成败。

#### F-003
- title: 其余 fact 失败的「检索侧 vs 合成侧」当前不可判
- status: candidate
- failure_span_id: `20260818T051630Z/{A5,A7,A9,A10,C4}`
- root_location: 未定
- l0: UNCLEAR
- l1: retrieve
- l2: `DEPTH_INSUFFICIENT(D4)`
- l3: n/a
- violated_authority: none
- causality: UNCLEAR
- propagation_impact: [UNCLEAR]
- failure_detection_timing: ONLY_AT_TASK_END
- completion_status: PARTIAL_SUCCESS
- evidence_ids: [E-006]
- confidence: low
- explanation: trace 只落工具 `output_summary` 话术，不落原始载荷全文（profile §8 已记该缺口）。因此「带标签形式零命中」只能排除「已进入落盘载荷」，不能排除「工具取到了但未落盘」。

### Path

#### P-001
- title: B7 从正确检索到被判失败
- start: `finance_query` 返回 `市场成交额=29569.03` / `=21949.97`（正确状态）
- goal: 判分器给出 `expected fact ... not observed within tolerance`
- steps:
  1. 检索取得两日成交额，带字段标签 — evidence: E-001 — finding: none
  2. 合成把两值以「万亿」单位写入答案，数值正确（误差 0.10%/0.23%） — evidence: E-002 — finding: none
  3. **第一处错误变换**：判分器抽裸数 `2.96`/`2.19`，与 `29569.03`/`21949.97` 比容差，无单位归一 → FAIL — evidence: E-003, E-004 — finding: F-001
  4. 台账把该题记为「本批唯一回归」 — evidence: E-007 — finding: F-001（传播）
- residual_uncertainty: 同一单位盲区是否也影响 A5/A10/C4 等其余 fact 题，尚未逐条排除

## Fix recommendations

| ID | finding | fix_type | recommendation | verification prediction | regression guard |
|---|---|---|---|---|---|
| R-20260818-01 | F-001 | `EVAL_ONLY` | `_extract_numbers` 后增加中文数量级归一：识别数字紧邻的「万亿/亿/万」并展开为同一量纲候选（与 `_decrease_signed_numbers` 同样只加候选、不改原值） | 同一份 `20260818T051630Z.json` 重跑 board，B7 两条 fact 由 FAIL 转 PASS，且 A1（原生「亿」表述）保持 PASS 不变 | 单测钉「2.96万亿 命中 29569.03±1%」「2.96亿 不得命中 29569.03」；对 08-15 与 08-18 两份 artifact 各跑一次，除 B7 外真值列逐题不变 |
| R-20260818-02 | F-002 | `EVAL_ONLY` | 对 `date` 与 `query` 分离的 9 题，二选一：把冻结日拼进 `query`，或在 runner 里把 `date` 作为显式时间上下文下达产品；两种都不改产品 | 重跑后该 9 题中至少 A3 的 `close=12.11` 出现在答案（A6 已证同数据可得） | 冻结题面 sha256，改动前后逐字 diff 入台账；带日期的 19 题真值不得变差 |
| R-20260818-03 | F-003 | `HARNESS_FIX` | `episode_tool_batch` 的 `tool_result` 落盘增加 `payload_field_names` 与 `payload_sha256`（不落全文，避免体积与脱敏问题） | 下一批同形 run 中，对每条 fact 失败可判定期望字段名是否出现在工具返回字段集 | 断言字段名列表非空且不含正文；体积增幅 <5% |
| R-20260818-04 | F-001 | `NO_SYSTEM_FIX` | 在修好 R-01 之前，**不得**据 B7 判定本批引入回归，也不得据此调产品 | 下一份自称修「B7 回归」的 PR diff 不含产品侧（`ask*.py` / `episode*.py`）改动 | 出现产品侧改动且无新证据 → 本预测 refuted |

## Observability prescription

| blind_spot | 挡住了哪个判定 | 最小埋点（一个变量+阈值） | 埋在哪 | 埋完能判定什么 | 成本 |
|---|---|---|---|---|---|
| 工具返回只落 `output_summary` 话术，无原始载荷字段集 | F-003：A5/A7/A9/A10/C4 的失败是 retrieve 侧还是 synthesize 侧 | `tool_result.payload_field_names`（字符串数组，非空）+ `payload_sha256` | `episode_tool_batch` 落盘处 | 期望字段名在不在工具返回里；在=synthesize 侧丢失，不在=retrieve 侧未取 | 低（每事件 +1 数组） |
| 判分器不记录「抽出了哪些候选数」 | F-001 这类单位/格式误判只能靠人工复算发现 | verdict 失败时附 `extracted_numbers`（前 20 个） | `acceptance_verdict._fact_rule` 的 FAIL 分支 | 一眼可见是「产品没答」还是「判官没认出」 | 极低 |

## Limits and counterevidence

- **本报告不是 M2。** 08-15 与 08-18 两份 artifact 之间的差异变量不止一个（十张 PR + 数据快照日期 + 判分器版本），不满足单变量 ablation，故 B7 的「本批引入 vs 旧病」不能用 A/B 差分回答，只能用本次的 trace + 判分器实测直接判定——所幸后者已足够决定性。
- **12 个失败中只有 B7 被完全定性。** 其余 11 个未逐条追到第一处错误变换；F-003 明确标 low/UNCLEAR。
- **「12 个不可判」未全部分类。** 已知 A8/C6 属日期锚（F-002），B1/B2/B3 属 `agent_eval TurnInput` 埋点缺失（判分器自述），其余（A2/A4/A6/B4/B5/B8/C9）本次未查。
- **反证**：若判分器另有上游把「万亿」预处理成「亿」，F-001 不成立。已读 `_fact_rule` 全分支未见此处理，但未通读 `_extract_numbers` 的全部调用链。
- 本次未改被审系统任何 prompt / 工具 / 路由 / 生产配置（Stop-the-Line）。

## Next-step menu

1. 按 `R-20260818-01` 给判分器加单位归一，用**同一份** artifact 重跑 board —— 零成本复算，可立刻确认 B7 及可能的同族误判（最高信息增益：不用重跑 LLM）。
2. 按 `R-20260818-02` 给 9 道无日期锚题补日期后重跑，看可判子集分母能升多少。
3. 按 `R-20260818-03` 补 `payload_field_names` 埋点，然后重跑一次，即可给 F-003 定性。
4. 逐条排查另外 11 个失败是否也踩单位/别名盲区（先用第 1 步的 `extracted_numbers` 输出扫一遍）。
5. 把 `R-20260818-01..04` 写入 `docs/prediction-ledger.md`，并把本次三条 `still_pending` 的闭环结论回填。
6. 修完第 1 步后，重新出具本批的「回归/改善」结论——当前台账里「B7 回归」一行需要撤回或改写。
