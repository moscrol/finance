# 设计：交付门禁改力度（不整答退稿）

日期：2026-08-17
状态：已点头，实施中
前序：门禁盘点（claim 绑定 / 术语泄漏整答作废；数字血缘改写 `stop_reason`）

## 0. 一句话

防幻觉的契约继续记警告、继续抠问题行；**默认不再因为格式或漏词把整篇 LLM 答卷丢掉。**

## 1. 改什么

### 1.1 claim 绑定（`validate_llm_answer`）

下列 issue 的 severity 从 `error` 改为 `warning`：

- `llm_missing_claim_binding`
- `llm_invalid_claim_id`
- `llm_invalid_evidence_atom_id`
- `llm_claim_type_mismatch`
- `llm_fact_without_evidence_atom`
- `llm_fact_only_superseded_evidence`

`ask_synthesis` 只对 `severity == "error"` 整答退稿。警告写入 `result.warnings`，诊断仍为 accepted。无效 claim 行展示层本来就会丢；无 marker 的句子保留。

### 1.2 内部术语

- `llm_engineering_term_leak`、`grounded_composer_engineering_term_leak` 改为 `warning`
- `present_llm_answer` / `present_grounded_composer_answer` 抠掉含漏词的行
- 允许清单（methodology / review / general / causal 等）与现网一致，不放宽词表
- `evaluate_answer_spec` 的 `engineering_term_leak` **不动**（那是 registry 渲染，不是 LLM 出口）

### 1.3 数字血缘（benchmark）

`_numeric_lineage_projection`：有实质数字且 `source_ids` 空的句子删掉，留下已绑定的。删完若一篇不剩，才用缺口稿垫底。

**禁止**再把臂级 `stop_reason` 改写成 `numeric_lineage_gap`。缺口仍记在 `issues`（`numeric_lineage_gap:C1,...`）。`claims` 对公布正文重算。

## 2. 不改什么

语义闸、休市/退役表罐头、结构 `episode_verifier`、`grounded_composer_added_number` / `_added_company` 等事实越界、`llm_added_number` 这类仍 error 的 fail-closed、层级审计、未读字段、超时、8792、900、市场复盘 `grounded_required_fallback`。

## 3. 验收

- 未绑定散文：`validate_llm_answer` 只有 warning；`synthesize_prepared_answer` 仍出 `synthesis`，warnings 含绑定问题
- 术语泄漏：警告 + 展示稿不含该行，不是 `quality_gate_rejected`
- 半篇未绑定数字：只删数字句；`stop_reason` 保持模型终态
- 全文只剩未绑定数字：公布缺口稿，仍不改写 `stop_reason`
- `llm_added_number` 仍整答退稿（未授权改这条）
