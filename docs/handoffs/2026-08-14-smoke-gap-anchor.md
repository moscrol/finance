# 2026-08-14 smoke 语义门锚点倒挂 — 已合 main

PR [#345](https://github.com/linxiaoqi5111-del/finance-workspace-private/pull/345) 已合入 `main`（merge `87f25bf1`，修复提交 `34c50277`）。**未切 8792。**

## 做了什么

`scripts/smoke_workbench_self_use.py` 的语义门原先奖励「复述题干然后拒答」、惩罚「给实质内容并具体说明缺口」。锚点改用上游已抽好的 `report.task_frame.subject`，并排除复述题干的段落（15 字阈值）。两处缺一不可。取不到 subject 时退回原行为，不 fail closed。

## 验证

- 真实收据：741 字实质回答 判红→通过；185 字复述拒答 通过→判红。
- 估值支现场（8799，瑞华泰 `run_20260814_155429_739306`）：`answer_status=partial`，估值支命中缺口句，issues 空。
- `tests/test_smoke_workbench_self_use.py` 含 2 条变异测试（拿掉 subject / 不排除复述）。CI workbench-check 绿。

## 遗留

- 反弹 / 因果两支没跑真实样本（改动对它们只加 subject，不收紧）。
- 合并后 smoke 判红率会变；部署前的红/绿读数不可与之后比较。
- 8792 仍是旧 revision，这道门生产上还没生效。
