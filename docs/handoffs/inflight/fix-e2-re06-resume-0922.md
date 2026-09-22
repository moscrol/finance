# fix/e2-re06-resume-0922（在飞）

base `a2c8d1f90`（gitea/main）。树：`/Users/a77/fwp-wt-e2-re06-resume-0922`。
P4/P5/P6、RE06 主批次与 I14 均已在 main；本轮做门页明列的剩余缺口
「local_only 原题号槽」。

## 本轮做完的
`local_only` 且用户自己编了号时，按原号冻结 `answer_qN` 必需槽（未编号本地题、
full 题形状不变）。一处实现同时供写作提示词、判官载荷、语义修复保号、公开稿复验。

分界只写在**结清口径**上，这是本轮唯一的设计判断：`material_only` 零读权限，
交代缺项是唯一诚实交付，故 `legal_gap` 可结清；`local_only` 手里有本地读工具，
再认 `legal_gap` 等于用「缺少X」买断取数义务。所以本地题的缺口回到普通
`required_output_gap`（`partial` + 进修复），「仅凭本轮材料」全缺口声明不套用，
语义放行走原 RELEASE_POLICY 而非材料结清分支。每题仍须真实本地证据，
claims 不替代证据，IO 纯度/读权限上限不变。

改动面（5 个文件）：
- `material_delivery.py`：新增 `question_delivery_scope()`；`material_question_outputs`
  按它取 material_only+local_only；`material_input_output_ids` 仍只认 material_only
  （修复可达性、claim 渲染靠它，本地题可达）；全缺口声明加 material_only 门；
  提示词规则按 scope 分两份。
- `episode_factory.py`：local_only + questions → 逐题槽 + evidence_boundary；
  evidence_types/evidence_plan 照常挂（有工具）。
- `episode_verifier.py`：`legal_gap` 加 material_only 门。
- `episode_semantic_verifier.py`：`_can_semantically_release_partial` 的材料结清分支
  加 material_only 门（本地题一答一缺时不至于整篇发不出去）。
- `research_contract.py`：契约里已有 `answer_q*` 时，跨轮恢复不得删除/降 optional/
  改推理槽。判据用「已有槽」而非「有编号问题」，否则改动前落盘的会话恢复即报错。

## 证据
- 新测试 `intelligence/tests/test_e2_local_question_delivery.py`（20 条，先红后绿：
  基线 15F/4P → 20P）。
- E2 定向 567 passed / 4 skipped；`intelligence` 全量 10606 passed / 23 skipped /
  2 xfailed。
- 变异验证 7/7 被杀（脚本 `/tmp/e2-local-mutation-0922.py`）。其中「全缺口声明
  漏到本地题」最初无人守，据此补了
  `test_all_gap_local_turn_is_not_framed_as_a_material_shortage`。

## 未做 / 边界
- 作者自验，非独立 QC；P7 隔离验收（全新会话+原始 T3 文本+真实模型交付）未做。
- 未合并、未推送、未部署；未跑正式 T2→T3 / Knevo。引擎 B 内部仍无合同意识。
- 未编号的本地多问题（散文提两问）仍落在 `direct_answer` 一格：本轮刻意不动，
  编号是唯一确定性判据，靠模型切题会引入新的漏答面。

## 下一步候选
P7 隔离验收（需真实模型，属用户决定）／RE06 任务级测量与真人试点／未编号
多问题的切题判据（先定判据来源，勿用词表）。
