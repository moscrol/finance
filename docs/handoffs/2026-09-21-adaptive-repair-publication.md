# 修订受限时的公开发布上限与已解决审查边界

业务分支：`feat/adaptive-research-loop`。本片接续 `3c30eceb` 的同会话反馈/公开保真修复，处理一个真实回归：发布上限在历史研究场景中把“语义判官已将句子降级为 issue 并保留公开稿”误认成未完成修订，错误把 `completed` 降为 `partial`。

## 背景与发现顺序

1. `88a12753c` 新增 `with_unresolved_review_publication()`，用于防止无预算或模型忽略修订反馈后仍交付 `completed` 的残句。
2. 全量回归在 `test_history_finish_gap_survives_semantic_completion_and_publication[True-True]` 失败：历史样例的 `sentence_verdicts` 是 `stage=judge, decision=demoted_to_issue, reasons=[judge]`，原句仍是有意保留的公开限制，不是残句修订未完成。
3. 探针核对了私有账本和公开稿，排除“测试预期过时”：该样例没有删句后通过，而是语义质量句被降级进 issue；`judge_status=repaired` 本身不能单独作为发布判据。
4. 进一步覆盖了另一种真实退化：去掉发布上限时，无预算/忽略反馈的 16 个场景会错误恢复为 `completed`。

## 决策与被否方案

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 只看 `judge_status=repaired` 放行 | 状态同时覆盖语义删句、语义降级和机械问题，不能区分未完成行动 | 否 |
| 所有 `semantic_repair_feedback` 都降级 | 会误伤 `stage=judge` 已完成的删句/降级结果，历史合法完成态回归 | 否 |
| 恢复被拒句或把私有 issue 拼正文 | 重新引入无支持断言/私有诊断，不解决发布诚实性 | 否 |
| 以审查阶段和原因区分 | `stage=judge + reasons=[judge]` 表示语义判官已完成允许动作（删句或降级）；`preflight`、`before_backfill`、机械原因和 legacy claim 仍表示行动反馈未闭环 | 采用 |

实现仍不新增状态真本：`_unresolved_publication_feedback()` 只过滤已完成的 `judge` 语义记录，其他诊断继续走现有发布上限。公共正文仍不包含判官私有诊断；既有 `repair_goal`、预算、进度门和调用次数不变。

## 代码与验证

- `intelligence/services/episode_semantic_verifier.py`：发布上限只对未解决的机械/前置反馈生效；语义 `judge` 的 `deleted` 和 `demoted_to_issue` 均视为已完成内部处理。
- `intelligence/tests/test_episode_semantic_verifier.py`：补齐“前置删除仍未闭环 / judge 删除已闭环 / judge 降级已闭环 / mechanical lift / legacy”矩阵，并验证不改私有审查对象。
- `docs/agent-product-door.md`：更新发布上限边界。
- 关键定向回归：历史 4 passed；语义发布 21 passed；GLM/SDK、judge llm/off、weekday/numeric 组合 24 passed；Ruff passed。
- 最终作者侧撤线（非独立审查）：
  - 去掉发布上限：24 执行，16 失败，证明无预算/忽略反馈会错误交 `completed`；恢复 24 passed。
  - 把已解决语义修订误当未解决：22 执行，3 失败（历史场景 + 状态矩阵）；恢复 22 passed。
  - 最终隔离树恢复干净。
- 完整 Python 回归：`12096 passed / 85 skipped / 2 xfailed / 17 warnings`，收据 `/Users/a77/.finance-runtime/test-receipts/20260920T220029Z-7172ba30.json`，绑定精确 revision `7172ba30e32e686a45309ffa751412d5f07a2488`，exit 0。

## 收据与边界

本片新证据目录：`/Users/a77/.finance-runtime/adaptive-repair-publication-20260921/`。其中 `mutations-v2/results.json` 记录最终撤线，`full-pytest-7172ba30.log` 记录全量回归。此前 `adaptive-repair-delivery-20260921/` 等封存目录未修改。

17 个 warning 仍是既有市场模型数值运算和 `datetime.utcnow` 弃用；不能声称零 warning。脚本模型、SDK runner 和 judge 替身不证明自然模型会完整重写或持续改向；其他运行后端、真实模型公开保真、独立 Spec/Quality、合流和部署仍未验收。未 push、PR、合 main、部署、K3 或付费外审。
