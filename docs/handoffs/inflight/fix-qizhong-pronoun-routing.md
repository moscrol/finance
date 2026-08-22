# fix/qizhong-pronoun-routing

## 这个分支做什么

解开 2026-08-22 医药/科技题的 common-mode 路由失败：`其中` 被 `_ENTITY_PRONOUN_RE` 吃成 `entity_pronoun`，controller 再一票否决已解析完整的 TaskFrame。

## 当前状态

干净树 `/Users/a77/fwp-wt-qizhong-pronoun-routing` ← `gitea/main@b4689295`。本提交落地 R-001；**未推、未切 8792**。

- 检测器保持粗粒度，**不做「其X」穷举词表**（用户纠偏：开集补不完）。
- controller：`entity_pronoun` 且 TaskFrame 已 resolved（有 subject、无 ambiguity、`proceed`）时不硬返回 clarify，落到 `_deterministic_decision` / `llm_refine`。这才是 LLM 兜底——事故里模型没上场，是因为 clarify 在调用前截断。
- `那它呢` / `这个逻辑呢` 无历史仍追问。

## 已验证

- 定向：`test_query_resolution` + `test_turn_controller` + `test_turn_control_core` → 151 passed（撤词表用例后）。
- 生产默认 resolver 复放原题：`lane=research`，`needs_retrieval=true`，`theme_analysis/医药`，无追问。
- ruff 过所改文件。

## 未做

- 未 push / 合 main。
- R-002 假绿契约（clarify 仍可能报 research complete）。
- 未重跑 8792/8796 live A/B。两边越过 controller 后才能测 reading-baseline。

## 主仓

脏树 `feat/reading-rules-baseline-batch1` 未碰。
