# EXPLORE — K3 独立审查 · stage=explore · group=e2（C1–C3）

- revision: a30e7e4594ac09310271739c8beb30ee8b2cd3ef（候选只读）
- baseline: 03352758cf9b31e3f5d179b517be48cb89588679
- 候选根: `…/qc-bounded-02/candidate/finance-workspace-private`（下称 `$CAND`，源码路径相对 `$CAND/intelligence/`）
- 工作根: `…/qc-bounded-02/work/e2`
- 本阶段仅 read/write 静态核查；未运行 pytest / 业务 API / 网络。所有“待执行”结论均为 **not_verified**，不以静态一致性替代执行证据。

## 0. 输入定位与已读事实

- `inputs/` 实际位于 `qc-bounded-02/inputs/`（非 `work/e2/inputs/`）：已读 `source-map-e2.md`（292 行全文）、`source-identity-e2.json`、`probe-migration-e2.patch` 开头部分。
- 探针 `work/e2/probes/test_reviewer.py`（311 行全文已读）、`work/e2/probes/test_positive_control.py`（全文已读，故意 `assert 1 == 2`，预期 FAILED，属执行链校验件，非产品缺陷）。
- 候选源码已读：`services/material_delivery.py`（284 行全文）、`services/episode_verifier.py` 93–604（`verify_episode_outcome` 全文）、`services/research_contract.py` 1019–1129、`services/episode_factory.py` 1–360、`services/episode_protocol.py` 1–120、`services/material_grounding.py` 1–120、`services/user_task.py` 920–1039、`services/material_contract.py` 100–196、作者测试 `intelligence/tests/test_e2_local_question_delivery.py`（289 行全文）。
- **未读/被阻断**（本阶段不再补读，列为下阶段前置）：`research_contract.py` 1130–1257（local_only 冻结槽恢复校验主体 + `to_dict`/`from_dict`；一次读取因本人路径笔误越界被拒）、`episode_factory.py` 361–1228（含 `build_episode_context` 702–974）、`episode_protocol.py` 121–1372（`build_episode_input`、`validate_episode_finish`）、`material_grounding.py` 121–353（`claim_finish_format`、`grounding_scope`、`binding_source_errors`）、`user_task.py` 的 `_NUMBERED_ITEM_RE` 定义、`episode_semantic_verifier.py` 实质内容。
- 身份记录（`source-identity-e2.json`，宿主客观记录，不作语义结论）：5 个主张文件中仅 `material_delivery.py` 与上一审查轮相同；`research_contract.py`、`episode_verifier.py`、`episode_semantic_verifier.py`、`episode_factory.py` 均已变化 ⇒ 任何旧轮结论一律不继承，探针必须跑当前字节。
- `probe-migration-e2.patch` 观察到的 hunk 仅把探针 docstring 中旧 revision 改为当前 revision（机械迁移），未见其他 hunk；patch 是否更长得补读确认 —— **部分 not_verified**。

## 1. 探针独立性判定（接受/改写/补充）

裁决：**接受 `test_reviewer.py` 作为本组探针**，理由（均经比对作者测试 289 行全文核实）：
- 自造夹具与作者测试不同：作者 QUERY 从「1.」起、memo 200 字；探针 QUERY_FROM_Q2 从「2.」起、memo 120 字，另新增 q0 起始、跳号「1.…3.…」、重复编号「1.…1.…」、遗留 `direct_answer` 恢复形状等作者测试没有的攻击面；证据 hash、缺口文案均自造。
- 断言路径独立：C1 主打 `material_delivery_missing_outputs` 直查；作者测试走 `validate_episode_finish` 抛错。仅 C2 纯度探针与作者 `source_io_purity` 同用 `pytest.raises(match="frozen data scope")`，属同 API 的正当复用而非复制。
- `test_positive_control.py` 保持独立且故意失败，不得修改。

裁决保留意见（探针弱点/风险点，见 §2 各条 W）：探针正确性不能全靠静态阅读背书，执行阶段必须如实记录每条结果；若失败需判定产品缺陷还是探针错误，特别是 W1。

## 2. 主张 → 探针 → 源码证据映射

### C1 — local_only 编号题按原题号冻结 answer_qN；绑定齐全不能掩盖缺答题正文

覆盖探针（7 条）与已核源码：

| 探针 | 静态核对结果（文件:行） |
|---|---|
| `test_c1_user_numbering_starting_at_2_is_frozen_not_rebased` | `material_question_outputs`（material_delivery.py:77–93）以 `question_id` 原文拼 `answer_qN`，无重排；`user_task.py` 题组循环（920–1039 已读）`expected` 初值 None，起始号任意，q2 后跟 q3 满足 `number+1` ⇒ 解析得 [q2,q3] 与探针预期一致。memo 判定（_MEMO_REQUEST_RE/_CHAR_LIMIT_RE，material_delivery.py:34–35）对「写一份不超过120字的备忘录」得 memo/120 ✔。槽来自 `build_episode_context`（episode_factory.py:702–974 **未读**），经 `material_question_outputs(contract)` 间接断言 —— 见 W3。 |
| `test_c1_q0_is_a_valid_original_number_end_to_end` | `_HEADER_RE`（36–42）`q\d+` 接受 q0 ✔；`_read_question_sections`（104–150 全读）小节切分 ✔。`_NUMBERED_ITEM_RE` 是否接受「0.」**未读其定义 ⇒ 该断言静态 not_verified**（W4），须执行定夺。 |
| `test_c1_complete_draft_with_bindings_has_no_missing`（正控方向） | `material_delivery_missing_outputs`（210–227 全读）：三条件为「无绑定 ∨ 无正文 ∨ 披露缺口不符」，正文齐全+绑定齐全→`()` ✔。 |
| `test_c1_duplicate_section_still_missing_even_with_binding` | `question_sections`（153–163）重复小节并列保留；`question_body`（175–190）`len(blocks)!=1 → ""` ⇒ 重复即缺 ✔，绑定不救（缺失判定不看绑定有无）。 |
| `test_c1_binding_cannot_hide_missing_or_invalid_body`（empty/placeholder/quoted_only/memo_overflow） | 占位符集合 `{"待补","待回答","略","暂无","tbd"}`（175–190 实读）✔；引用行 `>` 在 `_read_question_sections`（实读 ~128–131）被跳过 ✔；memo 超限 `len(去空白渲染)>max_chars → ""` ✔（探针 121 字 > 120）。 |
| `test_c1_skipped_numbering_is_never_rebased_to_q1` | `user_task.py` 实读：`followed_by_next_item` 要求下一编号恰为 `number+1`；「1.…3.…」首题不成组、「3.」以 `expected=None` 单独成 q3；绝不重排为 q1 ✔ 与探针注释（user_task.py:966 规则）一致。 |
| `test_c1_duplicate_user_numbering_cannot_collapse_in_factory` | 「1.…1.…」首题不组、第二「1.」以 `expected=None` 成唯一 q1 ⇒ 重复 qid 到不了 `material.questions` ✔；旁证：`material_contract.from_dict`（~105）拒重复 qid（"duplicate material question"），`compile_material_contract`（149 起）不查重——不对称存在但塌缩路径不可达，探针只钉不变量（唯一性），口径恰当。 |

**C1 小结**：除 `_NUMBERED_ITEM_RE` q0 边界（W4）与 factory 产出（W3）两点外，全部断言与当前源码静态一致；`material_delivery.py` 自上轮起未变（身份记录），但执行证据仍缺 ⇒ **not_verified（待执行）**。

### C2 — material_only 的零读取/legal_gap 结清不放宽 local_only 取数/交付义务

| 探针 | 静态核对结果 |
|---|---|
| `test_c2_material_only_exemptions_do_not_reach_local_contract` | `material_input_output_ids`（material_delivery.py:50–60）仅 `data_scope=="material_only"` 且非待澄清才非空 ⇒ local_only 得 `frozenset()` ✔。`material_delivery_payload`（279–284）+ `_LOCAL_ONLY_RULES`（实读，含「local_only」且不含「legal_gap」，与 `_MATERIAL_ONLY_RULES` 相反）✔。但 `claim_finish_format(contract) is None` 的实现（material_grounding.py:121–353 **未读**）与 `build_episode_input` 的 payload 装配（episode_protocol.py **未读**）⇒ 该两点静态 not_verified（W2），作者测试 `test_writer_and_finalizer_…` 同断言仅作旁证。 |
| `test_c2_local_gap_is_partial_never_legal_gap` | `verify_episode_outcome`（episode_verifier.py 全读）：binding.gap 分支中 `spec` 仅当 `grounding_scope(contract)=="material_only"` 才取，否则 None ⇒ local_only 永不 `legal_gap`，落 `missing`+`REQUIRED_OUTPUT_GAP`（实读 ~261–283）；`verified_status` 只降不升，partial 保持 partial（573–579）；`missing_outputs` 排除的仅是 {fulfilled, legal_gap}（~553–555）✔。探针断言 `verified_status=="partial"`、`answer_q2 ∈ missing_outputs`、无 `legal_gap` 状态，与源码一致。 |
| `test_c2_frozen_data_scope_rejects_external_evidence` | 依赖 `validate_episode_finish` 对 `io_effect="external_or_mixed"` 抛 `ValueError("frozen data scope")` —— episode_protocol.py 实现 **未读**（>1372 行，本阶段只读 1–120）；`binding_source_errors`（material_grounding.py）引用见 episode_verifier.py 但定义未读 ⇒ 静态 not_verified（W2）。作者测试 `test_numbered_delivery_does_not_relax_source_io_purity`（local_read 放行 / unknown、external_or_mixed 抛错）旁证存在该行为。 |

**C2 小结**：结构判官侧的「不结清、不升级」已直接读到源码，豁免不外溢的方向与源码一致；协议层（finish 校验/输入装配）未读 ⇒ **not_verified（待执行）**。

### C3 — 已带 answer_q* 的旧契约恢复时保护既有题号；未编号本地题与 full 模式不被强制改形

| 探针 | 静态核对结果 |
|---|---|
| `test_c3_frozen_contract_round_trips_with_original_numbers` | 依赖 `to_dict`/`from_dict`（research_contract.py:1155–1257 **未读**，读取被阻断）⇒ not_verified。 |
| `test_c3_restore_cannot_erase_or_weaken_frozen_question`（drop/optional/reasoning） | 已读到 `__post_init__` 中 local_only 守卫的注释起头（research_contract.py 实读至 1129：「已按原题号冻结的本地题：跨轮恢复不得删掉、降成可选或改成推理槽。」），**但执行体 1130–1153 未读** ⇒ 守卫是否真按 output_id 逐一比对、报错信息是否含「local_only」均 not_verified。作者测试 `test_restore_cannot_erase_or_weaken_a_local_question`（remove/optional/reasoning → `ResearchContractError` match "local_only"）旁证。 |
| `test_c3_restore_accepts_legacy_direct_answer_shape` | **W1（关键风险）**：探针假设恢复校验以「既有 answer_q* 槽」为判据 —— 把 local_only 契约的全部 required_outputs 换成单个 `direct_answer`/`model_reasoning` 应被接受。若实现实际是「material.questions 非空 ⇒ 必须有 answer_qN 槽」（与 material_only 段 1114–1124 同款逐题比对），此探针会失败。判据主体在未读的 1130–1153 ⇒ 本探针结论完全待执行裁决；若失败须区分产品缺陷（旧会话恢复被拒）与探针误解。 |
| `test_c3_unnumbered_local_and_full_numbered_keep_slot_shape` | 依赖 `build_episode_context` 对无题组 local_only / full 编号输入不长 answer_qN 槽（episode_factory.py:702–974 **未读**）⇒ not_verified；作者测试 `test_local_unnumbered_and_full_numbered_tasks_keep_existing_slot_shape` 旁证。 |

**C3 小结**：保护语义有注释与作者测试双重旁证，但守卫代码主体未读、W1 探针方向未定 ⇒ **not_verified（待执行）**。

## 3. 覆盖缺口（诚实列出，不升级为 PASS）

1. **语义层零独立覆盖**：主张文件列 `episode_semantic_verifier.py`，但本组探针不含语义判官路径（`_material_questions_settled` 4181–4200、`_can_semantically_release_partial` 4203–4242 等仅见 source-map 名录）。作者测试的 `ordinary_partial_review` 覆盖了 partial 语义放行；若主张口径要求独立复核语义层，需下阶段补写新探针，否则该项保持缺口。
2. **可补充探针（建议，非必须）**：恢复时的「改号攻击」——把 answer_q2/answer_q3 篡改重排为 answer_q1/answer_q2，现有 drop/optional/reasoning 三变异未直接覆盖 renumber；如守卫按「每题存在唯一必需 answer_qN」实现则 drop 已蕴含拒绝，优先级低。
3. `_NUMBERED_ITEM_RE` 对 q0、全角编号形态的接受度未读，仅由探针执行裁决。
4. 探针未断言 `required_outputs_without_substance`（episode_output_substance）与 C1 空正文的联动；当前口径下 C1 已由 `material_delivery_missing_outputs` 直证，可不加。

## 4. 下一阶段执行路径（需执行，当前全部 not_verified）

1. 前置补读（本次被阻断/超预算）：`research_contract.py:1130–1257`（重点裁决 W1）、`episode_protocol.py` 的 `validate_episode_finish`/`build_episode_input`（W2）、`material_grounding.py:121–353` 的 `claim_finish_format`/`grounding_scope`（W2）、`episode_factory.py:702–974`（W3）、`user_task.py` 的 `_NUMBERED_ITEM_RE`（W4）、`episode_semantic_verifier.py` 4143–4242（缺口 1 评估）。
2. 正控先行：`pytest work/e2/probes/test_positive_control.py` —— 预期 **FAILED**；若通过则探针链不可信，`test_reviewer.py` 结果作废。
3. 主探针：`pytest work/e2/probes/test_reviewer.py -q`（候选根为 cwd，`intelligence` 可导入），逐条记录 pass/fail；失败条目先按 §2 的 W1/W2/W4 指引定位是产品缺陷还是探针错误。
4. 身份断言（可选，执行阶段提出）：按 `source-identity-e2.json` 复核 5 个文件当前 sha256 与记录一致后再采信结果；`material_delivery.py` 未变不等于其余文件可继承旧结论。
5. 不以作者测试（289 行已读，含 original_questions / missing_or_invalid_question_bodies / local_gaps / ordinary_partial_review / source_io_purity / restore / unnumbered_and_full_numbered）替代独立探针结论；作者测试仅作 API 形状与行为旁证。

## 5. 局限声明

- 本阶段无执行（bash 被控制器拒绝）、无 pytest、无网络；一切「与源码一致」均为静态阅读判断，不等于运行通过。
- 多个关键函数体未读（§0、§4.1），对应断言保持 not_verified；EXPLORE.md 交付完成不等于候选通过。
- `probe-migration-e2.patch` 仅读到首个 hunk；identity 文件为宿主记录，未手算校验（本阶段不要求）。
