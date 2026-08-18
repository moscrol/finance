# Phase 1 判分器止血读数（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-p1` `fix/caliber-phase1-scorer`
- 设计：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md`（#198）
- 派单：`docs/handoffs/2026-08-18-caliber-contract-phase1-3-dispatch.md`
- 未切 8792，未动产品代码，未重跑 28 题

## 改了什么

1. `_evaluate_fact` 对「N万亿」加亿元候选（×10000），原值保留。「2.96亿」不乘。
2. `verdict_equivalence.json` 拒答等价类；只挂在 `expect_refusal` 题的已声明短语上。
3. B7 / C1 overlay：`semantic_required` → `structured`。
4. fact FAIL 附 `extracted_numbers`（前 20）与 `matched_aliases`。
5. `pass_rule` 含「之一」且 `expect_facts` ≥2 条 → 契约 diagnostics（A7 阳性）。

## 验收

| 判据 | 读数 |
|---|---|
| A. 08-18 B7 | ❌ 失败 → ✅ 通过 |
| B. 08-18 C1 | ❌ 失败 → ✅ 通过 |
| C. 其余 26 题 | 真值列零变化。解析 28/28 非空（改前基线 + 复算） |
| D. 08-15 | B7 ❔ 不可判 → ✅ 通过；C1 ❌ → ✅；其余 26 题不变。解析 28/28 非空 |
| E. 正反单测 | `2.96万亿` 命中 29569.03±1%；`2.96亿` 不命中 |
| F. 变异 | 注释掉万亿展开后 08-18 B7 回到 ❌ 失败（抽出 `[2.96, …]`）；恢复后重回 ✅ |
| G. A7 门禁 | `test_a7_pass_rule_or_vs_two_facts_is_a_contract_diagnostic` 绿 |

artifact：`20260818T051630Z.json`（#198 入库）、`20260815T1005Z-r5-clean-baseline-3.json`（本树已有）。
复算输出：`/tmp/caliber-p1/after-0818.txt`、`/tmp/caliber-p1/after-0815.txt`。

pytest：`test_acceptance_verdict` 42；acceptance 相关 160 passed。
