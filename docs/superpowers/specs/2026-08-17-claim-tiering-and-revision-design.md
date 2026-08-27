# 设计：绑定问题让模型改一轮，已取代证据降桶标注

日期：2026-08-17
状态：已点头，已实施
前序：`2026-08-17-delivery-gate-soften-design.md`（#144，已合入 `96446a93`）

## 0. 一句话

#144 把「整答退稿」换成了「记警告照发」，**中间那档（让模型改一轮）被顺手关掉了**；
同时把一条内容闸误归成了形式闸。本轮补回中间档，并把那条内容闸改成正文里可见的降桶。

## 1. 为什么

### 1.1 修订轮失联

`claim_binding_revision` 的触发条件是 `blocking_issues`（severity == error）。
#144 之后绑定类问题全是 `warning` → `blocking_issues` 恒空 → **这一轮再也不触发**。
处置从「退稿前先让模型改一次」退化成「不扔也不改，带病放行」。

真实案例（`live-ask-retrieval.json`，#144 自己的 live 收据）：模型输出了 **9 处
`claim_id=`**，但**完整格式 marker 为 0**——它写的是短式
`<!-- claim_id=summary:company-gap -->`，缺 `evidence_atom_ids` 和 `claim_type`。
`_STRUCTURED_CLAIM_MARKER_RE` 要三个字段齐全才认，于是：

- 解析器不认 → 整段判为「未绑定」（`unbound_claim_line_count=6`）
- 展示层也不认 → 那些行原样保留 → **`<!-- claim_id=... -->` 原封不动进了最终答卷**

**模型在配合，只是方言不对，而没有任何一条路径告诉它哪里不对。** 这正是修订轮该接住的。

依据：`~/ai-agent-book` 第 5 章——工具层错误「不终止会话，把错误变成模型的输入」，
「喂回的错误越结构化，模型自我纠正的成功率越高」。这是书里的默认做法，不是新发明。

### 1.2 一条内容闸被误归成形式闸

`llm_fact_only_superseded_evidence` 的语义是「这句事实**只**绑了已被取代/已证伪的
证据原子」。ID 写错、少标 marker 不代表内容错，而**拿已被推翻的证据当当前事实，
本身就是内容错**。#144 §1.1 把它和 5 个真形式码一起列进「claim 绑定」降级了。

但处置也不该是简单提回 error。knevo（`agent-memory/10_knowledge/knevo-*.md`，
同量纲的领域信源）的做法是**三桶分层**：结论桶 / 线索桶（「下一轮检索的燃料」）/
丢弃桶，配「缺数据标 gap 而不是编造」。证据不够不是把答案扔掉，是**把那句话降一个桶**，
且降级**在答案正文里可见**——记在 `warnings` 里是给工程师看的台账，用户读到的
仍是一句语气笃定的结论。

## 2. 改什么

### 2.1 修订轮按触发源分档（`ask_synthesis.py`）

| 触发源 | 谁触发 | 采纳门槛 | 理由 |
|---|---|---|---|
| `error` | `blocking_issues` 非空 | 修订版无 error 即采纳（**原行为不变**） | 初稿反正要退，不变差就值得换 |
| `warning` | `_BINDING_ISSUE_CODES` 命中的 warning | 无 error **且绑定问题数严格减少** | 初稿本来能发，必须真的变好才配顶掉它 |

`_BINDING_ISSUE_CODES` **不含** `llm_fact_only_superseded_evidence`——证据本身已被
取代，让模型重绑修不好它，反而可能逼它去攀附别的证据。

warning 触发的修订若改出 error：**丢弃修订版、保留初稿**并记一条警告。不能让
「本来能发」因为一次没要求的重写变成退稿。

遥测：`claim_binding_revision_trigger`（error/warning）、`claim_binding_revision_accepted`。
成本可读——这一轮多一次 LLM 调用，跑不跑、采不采纳都进台账。

### 2.2 降桶标注（`answer_model.py`）

`present_llm_answer` 对命中的 claim 在**正文行尾**追加
`STALE_EVIDENCE_TIER_NOTE = "（待核验：所据证据已被取代或证伪）"`。

判据抽成 `_claim_rests_only_on_stale_evidence`，门禁（`validate_llm_answer`）与
展示层共用**单一真本源**——改判据两处同时变，不会一处报警另一处不标。

`llm_fact_only_superseded_evidence` 的 severity 保持 `warning`（不退稿）。

## 3. 不改什么

- Grounded 那条（生产默认）的 12 条 error 一条没动。特别是
  `grounded_composer_added_number` / `_added_date` / `_added_company` /
  `_promoted_to_fact`——**它们逐句按「该句绑定的证据原子」算越界**
  （`allowed_text` ← `bound_atoms`），绑定没了这些闸不是放行而是全量误报。
  **形式闸是事实闸的输入，不是并列的另一类闸。**
- 展示层下限（前序 §1.4）、语义闸、层级审计、超时、8792、900。

## 4. 验收

- 绑定类 warning → 触发一轮修订；`revision_trigger == "warning"`
- 修订版绑定问题变少 → 采纳；**没变少 → 保留初稿**（对偶用例）
- 已取代证据的事实 → 正文出现降桶标注且**句子还在**；证据是当前的 → **不许标**（对偶用例）
- 四条各配变异测试：抽掉守卫红、写成无条件生效也红
