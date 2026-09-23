# Author claims, not evidence

Candidate `b24c86f87aaef6244dc6a2c6cf80f74ae1918943`; base `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`.

All ten claims remain `not_verified` by final independent QC. Engineering PASS and static exploration do not sign them. Paths below are relative to intelligence/.

| ID | Claim | Source locator | Independent state |
|---|---|---|---|
| C1 | `local_only` 编号题按原题号冻结 `answer_qN`，来源绑定齐全不能掩盖缺答题正文。 | `services/material_delivery.py`、`services/research_contract.py`；`tests/test_e2_local_question_delivery.py` 的 original_questions / missing_or_invalid_question_bodies | not_verified |
| C2 | `material_only` 的零读取权限和 legal_gap 结清不放宽 `local_only` 的取数/交付义务。 | `services/episode_verifier.py`、`services/episode_semantic_verifier.py`；同测试的 local_gaps / ordinary_partial_review / source_io_purity | not_verified |
| C3 | 已带 `answer_q*` 的旧契约恢复时保护既有题号，未编号本地题和 full 模式不被强制改形。 | `services/episode_factory.py`；同测试的 restore / unnumbered_and_full_numbered | not_verified |
| C4 | 读写共用折叠，但保留无记录、参与者过滤和坏时间戳的既有差异。 | `services/product_value/consent.py`、`measure.py`、`services/research_evolution/run_observer.py`；`tests/test_re06_consent_fold_shared.py` | not_verified |
| C5 | 相同时刻撤回优先，未来生效记录不提前作用；复核以事件自身时刻为准。 | `consent.py::scopes_at`；折叠测试与 `tests/test_re06_consent_gate_toctou.py` 的 future_dated / event_time | not_verified |
| C6 | 锁外快筛到追加之间的撤回会被同锁内复核拦截；门关闭不争锁；三类自动测量事件共用这道门。 | `run_observer.py::_record`；TOCTOU 六项和 `tests/test_research_evolution_i11_consent.py` | not_verified |
| C7 | 计时控件的授权、停止、切会话和离开页撤回使用 `activity-timer` / v2，不再使用测量 scope。 | `webapp/src/components/ResearchActivityControl.tsx` 及同名 `.test.tsx`、`webapp/src/researchActivity.test.ts`；实际发布物 `api/static/index.html` 与其引用的 `index-BobixB9S.js` | not_verified |
| C8 | 纯计时不算表达测量意愿；空 scope、其他部分授权和混合 scope 不错误回落自用默认。 | `consent.py::measurement_scopes`；`tests/test_re06_activity_consent_gate_effect.py` | not_verified |
| C9 | 旧 v1 仅完整原控件自用形状对称读取兼容；来源/协议/参与者/任务/scope 不匹配时不转换。 | 同分类器及 legacy_alias_requires_self_use_timer_shape / version_alone 测试 | not_verified |
| C10 | 真正测量撤回不能被重新计时覆盖；仅计时记录不产生试点测量授权；读取兼容不改写原始事件和内容摘要（`content_hash`，不是自然语言摘要）。 | timer_never_grants / real_withdrawal / legacy_and_new_records 测试；I11 三类事件测试 | not_verified |
