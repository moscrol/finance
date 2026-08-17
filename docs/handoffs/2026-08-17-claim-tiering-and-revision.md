# 交接：绑定问题让模型改一轮 + 已取代证据降桶标注

- 日期：2026-08-17
- 树：`/Users/a77/fwp-wt-delivery-gate`
- 分支：`fix/claim-tiering-and-revision`
- 基线：`gitea/main` `96446a93`（#144 合入后）
- spec：`docs/superpowers/specs/2026-08-17-claim-tiering-and-revision-design.md`
- 代码：`a68f640f`

## 0. 一句话

#144 把「整答退稿」换成「记警告照发」，**中间那档（让模型改一轮）被顺手关掉了**——
本轮补回来；并把 `llm_fact_only_superseded_evidence` 从「误归的形式闸」改成正文里
可见的降桶标注。Grounded 那条（生产默认）一条没动。

## 1. 改了什么

| 项 | 现在 |
|---|---|
| 修订轮触发 | 绑定类 `warning` 也触发一轮（原本只有 `error` 触发，降级后永不触发） |
| 修订版采纳门槛 | `error` 触发：无 error 即采纳（原行为）；`warning` 触发：**绑定问题数严格减少**才采纳 |
| 修订改出 error | warning 触发时丢弃修订版、保留初稿 + 警告；不让「本来能发」变退稿 |
| `llm_fact_only_superseded_evidence` | 仍 `warning`（不退稿），但正文行尾标 `（待核验：所据证据已被取代或证伪）` |
| 判据归属 | 抽成 `_claim_rests_only_on_stale_evidence`，门禁与展示层共用单一真本源 |
| 新遥测 | `claim_binding_revision_trigger`、`claim_binding_revision_accepted` |

入口：`intelligence/services/ask_synthesis.py`、`answer_model.py`。

**成本提醒**：warning 触发意味着旧合成链上绑定不全的答案会多一次 LLM 调用。
只在 `deadline.remaining() > 0` 且非市场复盘时跑，两个遥测字段可直接统计发生率与
采纳率——先看台账再决定要不要加开关。

## 2. 怎么验的

`intelligence/tests` 全量 **4770 passed / 11 skipped / 0 failed**，clean tree，
收据 `~/.finance-runtime/test-receipts/20260817T081049Z-a68f640f.json`。

四条变异逐条证伪（正反成对，防假门禁）：

| 变异 | 变红的测试 |
|---|---|
| 降桶标注永不加 | `test_superseded_fact_is_tiered_in_the_body_not_dropped` |
| 降桶标注无条件加 | `test_current_evidence_fact_carries_no_tier_note` |
| 修订轮退回「只有 error 才触发」 | `test_binding_warning_triggers_a_revision_round` |
| 采纳门槛去掉「必须变好」 | `test_revision_that_did_not_improve_is_discarded` |

**未跑 live。** 本轮全是单测 + 变异，没有真实答卷收据。修订轮的实际效果
（模型收到结构化的绑定错误后能不能把短式 marker 改成完整式）**没有实测过**——
这是下一任第一件该做的事，一发 `WORKBENCH_GROUNDED_PRESENTER=0` 的 live 就够。

## 3. 依据

- 修订轮：`~/ai-agent-book` 第 5 章——「不终止会话，把错误变成模型的输入」，
  「喂回的错误越结构化，自我纠正成功率越高」。
- 降桶：knevo（`agent-memory/10_knowledge/knevo-reverse-engineering.md` §3.2）
  三桶分层 + 「缺数据标 gap 而不是编造」。**只借形状不借数字**——knevo 文档自己
  列了「不应直接复制的部分」（confidence 阈值、排序权重等）。

## 4. 下一任不要做的

- 不要把 Grounded 那条的 `grounded_composer_added_number` / `_added_date` /
  `_added_company` / `_promoted_to_fact` 改成 warning。**它们逐句按「该句绑定的
  证据原子」算越界**（`allowed_text` ← `bound_atoms`）：绑定没了，这些闸不是放行
  而是**全量误报**。形式闸是事实闸的输入，不是并列的另一类闸。
- 不要把 `llm_fact_only_superseded_evidence` 塞进 `_BINDING_ISSUE_CODES`——
  证据本身已被取代，重绑修不好，只会逼模型攀附别的证据。
- 不要在没有 live 收据的情况下写「修订轮有效」。
- 不要开 900、不要切 8792。
