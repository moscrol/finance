# feat/contract-honor-p0c

## 这个分支做什么

兑现问句已经点名的信封格子（spec P0-C），不加检索、不改 `question_type`。

伞形 spec：`docs/superpowers/specs/2026-08-23-publication-and-contract-subtract-design.md`（Draft v1.1）

## 当前状态

代码已写。树：`/Users/a77/fwp-wt-contract-honor` ← `gitea/main@3ac070a2`。

| 检查 | 结果 |
|---|---|
| 本单理解/描述测试 | 95 passed |
| turn_controller + query_resolution | 108 passed |
| ruff | 过 |

## 做了什么

1. `_COMPANY_MAPPING_RE` 收「观察哪些个股 / 个股有哪些 / 个股的反馈」等。
2. `len(operators)>=2` 且含 `scenario_tree` 时，句式抽取 `A和B板块` → `subject=科技、医药`。不碰 `_theme_aliases()`。
3. cue 后口语「下」可剥；`下游/下跌/下旬/下修/下一代` 整段保留。单测锁 `下游化工` ≠ `游化工`。
4. `company_mapping` 描述要求代码 + 角色。

## 不要做

- 不合 main、不切 8792（P0-A 另支，等点头）。
- 不把「科技/医药」补进题材词表。
- 不无条件剥「下」。

## 下一步

P0-B 另开 `fix/judge-honesty-p0b`。本支只含合同兑现。
