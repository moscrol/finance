# V8 语义删除权收窄（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-22-v8-semantic-deletion-rights-design.md`
> 代码：`feat/v8-semantic-deletion-rights`（实现 `06e5578a` + 本文档提交）
> 树：`/Users/a77/fwp-wt-v8-impl`
> 生产 `:8792` **未切**。live 探针本回合不跑（设计 §7.4 / §8：验收方跑，执行方不得 confirmed）。

## 一句话

语义质量类 issue 对必需块改为「句留下 + harness `【质检存疑】` + 批评进输出质检」；机械硬违规（无据数值、表外 E 号、星期/路径预检）删除权不动；`_repair` 函数体一字不改。

## 分流真值表落地位置

| 桶 | 句号来源 | 去向 | 代码 |
|---|---|---|---|
| 机械 | 数值闸 ∪ 星期/路径预检 ∪ 表外 E 闸（`cited_evidence_ordinals` − `evidence_ordinal_table`） | 现有 `_repair` | `_mechanical_sentence_indexes` / `_partition_rejected_indexes` `:2975` / `:2989` |
| 语义 ∩ 必需块 | LLM 拒句 − 机械集合，且句在 `required` × `grounding=evidence` 或 W1 判断格 | 留句 + `_annotate_semantic_rejects`（`:3084`）+ `_with_review_appendix` | `_plan_repair_indexes` `:731`；三处调用 `_repair` 之前：`:1062` / `:1248` / `:1395` |
| 语义 ∩ 非必需块 | 同上但不在必需接地块 | 维持现状可删（并入 `_repair` 句号） | 同 `_plan_repair_indexes` |
| 开关关 | `FINANCE_V8_SEMANTIC_DEGRADE=0/false/off/no` | 全并入 mechanical（回到今日） | `v8_semantic_degrade_enabled` `:2949` |

表外 E 闸：句号代码产，不解析 LLM 文案。`IssueCode.UNRESOLVED_EVIDENCE_ORDINAL` 已登记 `RELEASE_POLICY=BLOCK`。判官 `passed=True` 且稿里有表外 E → ADD-ALL；判官已拒句 → 不把未点名的 E 句补进 rejected（保 C 簇逐轮删）。**E 闸不进 preflight**（进了会一次删光所有 E 句，砸 `calls==2|3`）。

再审：后续轮次再走 `_plan_repair_indexes`；纯语义重复否决不回灌 `_repair`、不发起以删句为目的的再审。机械路径 monotonic rejudge / `MAX_SEMANTIC_JUDGE_ATTEMPTS` 原样。

## TDD 红绿

新文件 `intelligence/tests/test_v8_semantic_deletion_rights.py`（§7.1 ①–⑥ + 分流器不得读 issue 文案 + §7.3 重放）。

- 先红：实现前 `ImportError: SEMANTIC_QUALITY_DOUBT_MARK`。
- 后绿：实现后该文件 16 passed（含重放钉）。

重放夹具：`intelligence/tests/fixtures/v8-semantic-deletion/semantic-quality-kept.json`（before=句被删 / after=句在+标）。

## 变异击杀（改前已 commit `06e5578a`，打完还原）

| # | 变异 | 击杀（`test_v8_semantic_deletion_rights.py`） |
|---|---|---|
| ① | `_partition_rejected_indexes` 恒 `return canonical, ()` | **4F**：钉 1 + 主钉 + 重放 + W1 升格钉（句被删） |
| ② | `_annotate_semantic_rejects` 恒等（只留附录） | **4F**：同上四条（句在、无 `【质检存疑】`） |
| ③ | `_unresolved_evidence_ordinal_indexes` 恒空（信 LLM 文案） | **4F**：钉 3 + C 簇抽检 + W1 ④ C3 + W1 回归包装 |

击杀数：**3/3 变异成立，合计 12 条钉红**（每条变异 4F；钉 1 / 钉 3 均被各自目标变异击中）。还原后文件与 `06e5578a` 字节一致。

## `_repair` 零改动自证

```
git diff gitea/main -- intelligence/services/episode_semantic_verifier.py
```

- `gitea/main` 上 `_repair` 在 `:2200-:2249`；本树 `:2362-:2411`（上方插入分流函数 + `view()` 包裹，行号下移）。
- 函数体与 `gitea/main` **逐字节相同**。
- `git diff gitea/main -- intelligence/services/episode_semantic_verifier.py` 的 hunk **零处与 `_repair` 起止行重叠**。

`_project_semantic_quality_marks` 的 `public_answer=` 必须走 `view(TerminalFacts(...))`（`test_public_answer_assignments_all_go_through_view`），并登记进 `_VIEW_CALLERS`（`test_view_callers_are_registered`）。全量两轮各 1 红即此对门禁；已补，不是改 `_repair`。

## 钉手术对账

设计 §5.2 分类处置，不发明第三种改法。

| 类 | 设计条数 | 本单实际 | 处置 |
|---|---|---|---|
| A 语义产品 | 7 | **7** 改钉预期（句留+标+质检；单句语义否决不再走删空→rejected） | 按设计 |
| B 机械预检 | 19 | **0** 改 | 按设计 |
| C 再审/次数 | 17 | **16** 改夹具扳机为表外 E；`test_mixed_retryable_failures_*` 本无语义扳机，**未改** | 按设计（改扳机不改 `calls==2|3` / 稿变短断言） |
| D 列表卫生 | 4 | **0** 改 | 按设计 |
| W1 ④ C3 | 1 | **1**（`test_full_wipe_still_keeps_c3_banner` + verifier 内 `test_terminal_redaction_withholds` 同形机械连删） | 按设计 |
| W1 语义质量主钉 | 1 | **1** 升格为第 3 句留下+存疑标 | 按设计 |
| composer | 17 | **0** 改 | 按设计 |

邻域（设计 F，不是改 `_repair` 才会红，但语义不再进 `_repair` 会砸 C3/hygiene 夹具）：`test_episode_answer_hygiene` 2 条 withhold/rollback 夹具改机械 E 扳机；`test_repair_refuses_to_wipe_every_required_output` 三格加表外 E。另有若干产品钉（outlook 判断格 / 估值情景行 / shared_hash 边界句 / public_gap）因「语义留句」改预期——不是第三种改法，是合同要求句必须还在。

W1 ① 夹具原先只在 issue 文案写 `numeric_unsupported`、句本身不是机械违规；已改成真 `99999点` 条件句，否则 V8 会当语义留下。

## 诚实边界

- **live 未跑。** 不得把任何行标 `confirmed`。台账 `R-20260821-19` outcome=`pending`。
- **单测绿 ≠ confirmed。** 离线只证明分流 / 留句+标 / 机械仍删 / 再审安全网在机械扳机下仍绿。
- 生产 8792 未切；探针用户 `probe-v8-<mmdd>` 归验收方。
- 开关默认开；关时分区器全并入 mechanical，不是第二套删句机。
- 标注只打 `public_answer`；`verified.outcome.draft` 真值句不改。
