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

### 1.4 展示层下限（1.1/1.2 的必要配套）

1.1 和 1.2 把退稿的决定权从门禁移交给了展示层——它丢无效 claim 行、丢含漏词的行。
两种输入会被抠成空串（实测）：marker 的 claim ID 全无效；单段散文里出现一个内部词。
没有下限就等于**发一张盖着 `validated` 章的空白答卷**，比整答退稿更差（退稿至少落
确定性答卷）。故：

- `synthesize_prepared_answer`：展示后无非空行 → 走既有 quality_gate 出口退稿，
  `llm_fallback_reason=quality_gate_rejected`（公开枚举不新增），诊断
  `reason_code=presentation_emptied`。另记 `presented_lines_dropped` 遥测，
  让「抠掉几行」从静默变成可读的数。
- `ask.py` WARN 回灌修订：它覆盖的是**已成型的初稿**，展示后为空则保留初稿不覆盖。
- Grounded 那条本来就有 `_grounded_body_line_count < 2` 下限，不动；本节是把同一条
  判据补到另外两条路上。

## 2. 不改什么

语义闸、休市/退役表罐头、结构 `episode_verifier`、`grounded_composer_added_number` / `_added_company` 等事实越界、`llm_added_number` 这类仍 error 的 fail-closed、层级审计、未读字段、超时、8792、900、市场复盘 `grounded_required_fallback`。

## 3. 验收

- 未绑定散文：`validate_llm_answer` 只有 warning；`synthesize_prepared_answer` 仍出 `synthesis`，warnings 含绑定问题
- 术语泄漏：警告 + 展示稿不含该行，不是 `quality_gate_rejected`
- 半篇未绑定数字：只删数字句；`stop_reason` 保持模型终态
- 全文只剩未绑定数字：公布缺口稿，仍不改写 `stop_reason`
- `llm_added_number` 仍整答退稿（未授权改这条）
- 展示层抠空：退稿而非发空白稿；WARN 回灌修订抠空时保留初稿。三条守卫各配一条
  变异能证伪的测试（抽掉守卫即红）
