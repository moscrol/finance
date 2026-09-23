# K3 e2 组（C1–C3）stage=explore 补交场 · 探索说明

revision=8eac9b3b55c563b1eb3be58686fcc0918464f69a
baseline=b59d6eed0356ae093b52bd291ab328628de8790e
候选（只读）：`candidate/finance-workspace-private`
上场报告：`inputs/e2-prior-independent-explore.md`（无探针、无测试，不当 PASS）

本场任务：补交上场漏交的探针与探索说明，不重做全仓阅读。只补读了探针必需的
API 小段与旧疑点①的可达性判定段。**本场未运行 pytest**；为降低探针期望偏差，
断言曾用普通解释器直调做冒烟核对（非 pytest、不计通过数），全部与实现一致；
正式 pytest 执行与计数属下一阶段。

## 交付物

- `work/e2/probes/test_reviewer.py` — 13 条自造探针（含参数化展开 17 例），全部针对当前实现行为
- `work/e2/probes/test_positive_control.py` — `assert 1 == 2`，预期 FAILED，
  记 `expected_positive_control/probe_bug`
- 本文件

## 探针 → 主张映射与源码位置

### C1（material_delivery.py、episode_factory.py、user_task.py）

| 探针 | 检查点 | 源码依据 |
|---|---|---|
| `test_c1_user_numbering_starting_at_2_is_frozen_not_rebased` | 用户从 2 编号 → `answer_q2/answer_q3`，不重排为 q1 起；memo 题 max_chars=120 | `episode_factory.py:721-733` 冻结分支按 `q.question_id` 建槽；`material_delivery.py:80-95` memo/字数提取 |
| `test_c1_q0_is_a_valid_original_number_end_to_end` | q0 边界：解析、冻结、`## q0` 小节识别全通 | `user_task.py:557` `_NUMBERED_ITEM_RE` 接受 `0.`；`material_delivery.py:36-42` `_HEADER_RE` 接受 `q\d+` |
| `test_c1_complete_draft_with_bindings_has_no_missing` | 正控方向：正文+绑定齐全 → 无缺 | `material_delivery.py:212-228` |
| `test_c1_duplicate_section_still_missing_even_with_binding` | 重复 `## q3` 小节 + 绑定齐全 → 仍缺 answer_q3 | `material_delivery.py:172-176` `len(blocks)!=1 → ""` |
| `test_c1_binding_cannot_hide_missing_or_invalid_body`（4 例） | 空正文/占位符「待补」/纯引用/memo 超限，绑定齐全仍缺 | `material_delivery.py:170-190` `question_body`；引用剔除在 `_read_question_sections`（:104-151） |
| `test_c1_skipped_numbering_is_never_rebased_to_q1` | 跳号「1.…3.…」：q1 不保留、3 不重排成 1（实际解析得 questions=[q3]） | `user_task.py:966` `expected is None or int==expected`；`:968-985` 成组终点要求下一编号为 number+1 |
| `test_c1_duplicate_user_numbering_cannot_collapse_in_factory` | 旧疑点①可达性：重复编号「1.…1.…」不产生重复 qid（实际解析得唯一 q1），factory 输出无重号 | 见下「疑点核查」 |

### C2（episode_verifier.py、material_delivery.py、episode_protocol 路径）

| 探针 | 检查点 | 源码依据 |
|---|---|---|
| `test_c2_material_only_exemptions_do_not_reach_local_contract` | `material_input_output_ids(local)==∅`；`claim_finish_format is None`；交付 rules 含 local_only 不含 legal_gap | `material_delivery.py:52-60`（material_only 才返回非空）。冒烟所见 rules 原文明示「本地题没有可结清的合法缺口」，与主张同向 |
| `test_c2_local_gap_is_partial_never_legal_gap` | 本地题披露缺口 → partial + answer_q2 missing，输出状态无 legal_gap（冒烟实测 statuses=['missing','fulfilled','fulfilled']） | `episode_verifier.py:239-257`（legal_gap 仅 material_only；上场已读） |
| `test_c2_frozen_data_scope_rejects_external_evidence` | 外呼 io_effect 证据被 `frozen data scope` 拒；local_read 放行 | `episode_protocol.validate_episode_finish`（作者测试同口径，自造证据文本） |

### C3（research_contract.py、episode_factory.py）

| 探针 | 检查点 | 源码依据 |
|---|---|---|
| `test_c3_frozen_contract_round_trips_with_original_numbers` | to_dict→from_dict 往返保持 q2/q3 槽 | `research_contract.py:1125-1138` |
| `test_c3_restore_cannot_erase_or_weaken_frozen_question`（3 例） | 删 answer_q2 / 降可选 / 改 model_reasoning → ResearchContractError("local_only") | 同上，判据为「已有 answer_q* 槽」 |
| `test_c3_restore_accepts_legacy_direct_answer_shape` | 无 answer_q* 槽的旧 direct_answer 形状恢复不误伤 | 同上，`:1128` 前置 `any(output_id.startswith("answer_q"))` |
| `test_c3_unnumbered_local_and_full_numbered_keep_slot_shape` | 未编号本地题、full 编号题均无 answer_q* 槽（full 实测输出 direct_answer/evidence_boundary/aggregate_count/prime_quote） | `episode_factory.py:721` 分支条件 `local_only 且 material.questions 非空` |

## 疑点核查（上场比赛点 → 本场结论）

1. **重复题号塌缩（旧疑点①，C1/C3 边界）→ 可达性闭合，不升级为缺陷。**
   `compile_material_contract`（material_contract.py:149 起）确实不查重而
   `from_dict:105` 拒重（不对称存在）；但唯一读到的生产路径
   `classify_top_level_regions`（user_task.py:966-1005）用 `expected=number+1`
   强制编号连续：重复/跳号编号进不了 `regions.question_ids`，
   `episode_factory.material_descriptions` 的 dict 塌缩无输入可达。
   解释器冒烟确认：「1.…1.…」解析为唯一 q1，「1.…3.…」解析为唯一 q3。
   探针 `test_c1_duplicate_user_numbering_cannot_collapse_in_factory` 用真实
   解析路径钉死该不变量。残余风险：若存在其它未读调用方直接构造
   TopLevelRegions 喂重复 qid——未发现此类路径，按指令不猜测为缺陷。
2. **_HEADER_RE 边界（旧疑点②）** → q0/跳号已由探针覆盖；中文「第N题」
   形式未探（正则明示接受，低风险）。
3. **混绑（gap+hashes 同槽）**（旧疑点③）→ 未探，留给下一阶段。
4. **stale answer_q7 槽恢复**（旧疑点④）→ 未探；恢复校验只正向检查当前
   questions 的槽，多余槽疑似良性。

## 未覆盖范围（明确标记）

- `episode_semantic_verifier.py`（6720 行）实现未读；语义裁决层无探针。
- material_only 正向结清（legal_gap 在 material_only 下成立）未建对照探针：
  构造 material_only 上下文需材料载体，本场预算内未完成。
- `validate_episode_finish` 的 completed+缺口拒收路径未自造（作者测试已覆盖，
  本场探针走 verifier 层）。
- IO 纯度仅探 `external_or_mixed` 一种 effect；`unknown` 等其它值未探。
- 中文「第N题」答案小节形式未探。
- **本场未运行 pytest**：断言经普通解释器直调冒烟核对（非 pytest）全部符合
  期望，但正式 pytest 执行、正控失败确认与通过计数均属下一阶段；
  本说明不构成候选 PASS。

## 下一阶段命令

```bash
cd /Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/candidate/finance-workspace-private
# 1) 正控：必须 FAILED（expected_positive_control/probe_bug）；若通过则执行链坏
python -m pytest /Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/e2/probes/test_positive_control.py -q
# 2) 审查探针
python -m pytest /Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/e2/probes/test_reviewer.py -q
```
