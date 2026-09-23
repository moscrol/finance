终审完成。FINAL.md 与 FINAL.json 已写入 `work/e2/`。

## 裁决摘要（e2 组 · C1–C3 · stage=report）

**执行事实核对**（以实际收据为准，宿主核对件仅证日志/JUnit/退出码/哈希，未复利其作语义结论）：
- positive_control：exit=1，junit 恰好 1 条 failure（`test_positive_control_must_fail` 的 `assert 1 == 2`）→ **首红 1 例成立**，分类 `probe_bug/expected_positive_control`，**不计入业务失败**，证明执行链存活。
- reviewer：冻结初稿 `test_reviewer.py`（sha256=b4c6296f…，sources_unchanged=true）**收 19 / 19 passed**，exit=0，无 v2 修复、无 candidate_bug。
- author：`test_e2_local_question_delivery.py` **收 20 / 20 passed**，exit=0，与独立探针**分账**，未并入 reviewer_runs。三笔收据哈希与宿主核对件全部吻合。

**独立语义抽核**（本会话亲读，非照抄）：冻结探针 311 行经真实消费链 `understand_query → build_episode_context → verify_episode_outcome / validate_episode_finish`；源码抽核 `material_delivery.py:172-190`（重复小节/占位符/memo 超限→空正文）、`:212-228`（绑定+正文双判）、`research_contract.py:1128-1138`（以「已有 answer_q* 槽」为恢复保护判据，兼容旧 direct_answer 会话）均与探针断言语义一致。

**逐条裁决**：
| 主张 | 状态 | 关键独立证据 | 主要 limits |
|---|---|---|---|
| C1 | **verified** | 7 探针实跑通过 + material_delivery.py 抽核 | 中文「第N题」、混绑同槽未探 |
| C2 | **verified** | 3 探针（partial 绝无 legal_gap；frozen data scope 拒外呼证据） | 语义裁决层 6720 行未读、material_only 正向对照未建 |
| C3 | **verified** | 4 探针（删/降/改 3 例均抛 ResearchContractError）+ research_contract.py 抽核 | stale 多余槽恢复未探 |

**Quality：PASS_WITH_LIMITS**。无缺陷、无 candidate_bug；维护性正面（恢复保护判据注释意图明确）。回归提示（非缺陷）：compile_material_contract 不查重与 from_dict 拒重的不对称靠连续编号约束闭合，建议后续一并查重。19 例为横截面，不推广为全部业务无缺陷。

**blocking_issues：无**。历史保留（不计入本轮）：v2 作者收集被 .agents stat 阻断；更早期沙箱 ps 失败既非对照成功亦非候选缺陷。complete=true 仅表示报告完整，不代表候选全局 PASS；C7/consent 不在本组范围，不代签别组。
