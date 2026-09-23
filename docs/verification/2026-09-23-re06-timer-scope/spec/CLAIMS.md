# #73 作者主张清单：供 #75 独立验证

这是作者提交的审查输入，**不是审查结果**。以下状态全部 `not_verified`，指尚未由本轮独立审查者验证；不否认历史作者测试。不得把文件所在的 `spec/` 目录当作 Spec 轴已完成。

固定候选 `f9ce5c6b296492b423400ad66d333784a4be13bc`；基线 `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`。完整增量含原 E2、共用折叠、锁内复核和 B 方案，不能只审最后一次计时改动却签整个候选。作者树 `/Users/a77/fwp-wt-wave2-re06-0923`；实际审查须另建独占 detached 检出。本轮没有 PR，后续 PR 描述应引用本表。

以下路径相对固定候选的 `intelligence/`。

| ID | 可证伪主张 | 源码 / 可定位的作者测试 | 独立状态 |
| --- | --- | --- | --- |
| C1 | `local_only` 编号题按原题号冻结 `answer_qN`，来源绑定齐全不能掩盖缺答题正文。 | `services/material_delivery.py`、`services/research_contract.py`；`tests/test_e2_local_question_delivery.py` 的 original_questions / missing_or_invalid_question_bodies | not_verified |
| C2 | `material_only` 的零读取权限和 legal_gap 结清不放宽 `local_only` 的取数/交付义务。 | `services/episode_verifier.py`、`services/episode_semantic_verifier.py`；同测试的 local_gaps / ordinary_partial_review / source_io_purity | not_verified |
| C3 | 已带 `answer_q*` 的旧契约恢复时保护既有题号，未编号本地题和 full 模式不被强制改形。 | `services/episode_factory.py`；同测试的 restore / unnumbered_and_full_numbered | not_verified |
| C4 | 读写共用折叠，但保留无记录、参与者过滤和坏时间戳的既有差异。 | `services/product_value/consent.py`、`measure.py`、`services/research_evolution/run_observer.py`；`tests/test_re06_consent_fold_shared.py` | not_verified |
| C5 | 相同时刻撤回优先，未来生效记录不提前作用；复核以事件自身时刻为准。 | `consent.py::scopes_at`；折叠测试与 `tests/test_re06_consent_gate_toctou.py` 的 future_dated / event_time | not_verified |
| C6 | 锁外快筛到追加之间的撤回会被同锁内复核拦截；门关闭不争锁；三类自动测量事件共用这道门。 | `run_observer.py::_record`；TOCTOU 六项和 `tests/test_research_evolution_i11_consent.py` | not_verified |
| C7 | 计时控件的授权、停止、切会话和离开页撤回使用 `activity-timer` / v2，不再使用测量 scope。 | `webapp/src/components/ResearchActivityControl.tsx` 及同名 `.test.tsx`、`webapp/src/researchActivity.test.ts` | not_verified |
| C8 | 纯计时不算表达测量意愿；空 scope、其他部分授权和混合 scope 不错误回落自用默认。 | `consent.py::measurement_scopes`；`tests/test_re06_activity_consent_gate_effect.py` | not_verified |
| C9 | 旧 v1 仅完整原控件自用形状对称读取兼容；来源/协议/参与者/任务/scope 不匹配时不转换。 | 同分类器及 legacy_alias_requires_self_use_timer_shape / version_alone 测试 | not_verified |
| C10 | 真正测量撤回不能被重新计时覆盖；仅计时记录不产生试点测量授权；读取兼容不改写原始事件和内容摘要。 | timer_never_grants / real_withdrawal / legacy_and_new_records 测试；I11 三类事件测试 | not_verified |

## 不在本次主张内

- #76/P7 新会话、原始 T3、真实金融质量；独立工程 QC 不能代签。
- 生产 8792 已启用、生产历史记录已迁移或旧读数已重算；本轮均未操作。
- 任意全仓事务都不存在竞态。17 个业务事务的作者静态分类见 [同族核对](../../2026-09-23-re06-toctou-family.md)，需要审查者自行复核。
- `try_transaction` 的 timeout 参数不是整个业务事务的硬耗时上限；进程锁等待、文件锁等待与锁内工作不能混为同一个时钟合同。

## 分账与后续

历史作者 `4bb3bf0cb`：授权/API 89P、前端9P；不是当前候选的完整验收，也不是审查者自造探针。本轮作者新增行为测试为0，审查未启动，审查探针未生成或执行。后续 execute 场必须把既有作者测试、自造探针、必红阳性对照分别记账，并检查模型真实终稿，不能只看退出码。
