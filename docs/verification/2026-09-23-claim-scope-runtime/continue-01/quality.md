# #75 claim-scope — GLM 独立审查 Quality 裁决（glm-session-03，report 阶段）

## 正确性缺陷（产品）

**本次审查范围内（候选 `14f885e01f4a538492b54a27f67ab5d33b58f875` 的 claim-scope 增量：`intelligence/services/{claim_scope_review,claim_scope_context,ask_claim_scope,answer_claim_scope}.py`、`episode_semantic_verifier.py` 相关段、`output_review.py` 相关段、`intelligence/runtime/{continuous_turn_adapter,conversation_orchestrator}.py` 相关段、`intelligence/{services/ask.py,services/ask_synthesis.py,workflows/ask.py}` 相关段、`scripts/{claim_scope_census,check_answer_claims}.py`）：未发现产品正确性缺陷。**

依据：
- 独立探针 15/15 绿（`probes.xml`，XML 解析计数 tests=15/failures=0/errors=0），探针按真实 API 构造、与执行会话逐字节一致（sha256 `0366c056…`），未 import 作者测试，未使用修正配额。
- 静态复核未发现主张与实现的背离：off 早退先于一切改动、advisory check 全部 advisory_only 且被 `warn_count`/`summary_lines`/`_review_notes_from_gate` 三处过滤、degraded 传播使 `clean=False`（`claim_scope_review.py:59`）、唯一 `claim-scope-review.json` 写点在终态认领后且 visibility=internal（`conversation_orchestrator.py:3941-3948`）、交付文本在收据生成后无再赋值（3753→3951 段核实）。

上述"无发现"**严格限定于**：静态阅读范围 + 独立探针动态压到的路径（C1-C6、C7 helper 级、C8 管道级、C10 合成 fixture）。A 侧集成恢复流、B 侧全链、终态落盘竞争、真实产物目录 census **未独立动态执行**，其质量不在本"无发现"结论之内。

## 非阻断观察（不构成主张违背，未动态触发）

1. **census 对缺键的 advisory 收据会抛 KeyError（低严重度，静态观察）**
   - 位置：`scripts/claim_scope_census.py:24-27`（`receipt["issue_count"]`、`receipt["rules_hit"]`、`receipt["degraded"]` 直接下标）。
   - 触发输入：`mode=="advisory"` 但缺 `issue_count`/`rules_hit`/`degraded` 任一键的产物文件。
   - 实际（推演）：未捕获 KeyError，census 以 traceback 退出，不产出计数。
   - 预期（若按健壮性要求）：计入异常桶或显式报错退非零。
   - 判定：产品运行时恒产出这三键（`claim_scope_review.py` advisory 分支必含），且 C10 主张不覆盖畸形 advisory 收据的处理；列为观察项，不构成 CHANGES_REQUIRED 依据。未运行动态验证（遵守"不运行未经批准的额外测试"约束）。

## 装置问题 / probe_bug（单列，不计产品缺陷）

1. **阳性对照预期红（分类：probe_bug，装置有效）**
   - 位置：`probe_positive_control.py:10`。
   - 实际：行内 `AssertionError: assert 1 == 2`（`positive.xml` tests=1/failures=1/errors=0）。
   - 判定：失败恰为装置控制断言本身，非收集/导入错误（errors=0），执行装置会真实报红、未吞失败。按规则单列为 probe_bug，不计入 C1-C10 证据，不构成 CHANGES_REQUIRED。

2. **explore.md 概述笔误"13 个用例"（文档问题，非产品/装置缺陷）**
   - explore.md 概述行称探针 13 个，与其自身分解式（合计 15）及 `probes.xml` 实测（15 个 test 函数）不符。execute.md 已勘误。不影响执行与裁决。

## 探针修正账

- 修正配额 0/1 使用：探针首轮（亦是唯一一轮）15/15 全绿，无修后分账，无 `probe_claim_scope.original.py` 需求。
