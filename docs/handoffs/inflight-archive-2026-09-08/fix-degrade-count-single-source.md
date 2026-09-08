# fix/degrade-count-single-source

## 这个分支做什么
合入 W2+W3 后留下的口径分叉：`gate_receipt.classify_degrade_counts` 曾把 `judge_status is None` + timeout/exc 算进 `judge_unavailable`；W2 只认显式 `unavailable`。W7 抽取也不读 `gate_receipt`，ask 的 `not_applicable` 会变成 `None` 再被记成判官不可用。

## 当前状态
**已合 #241。** `gate_receipt` 计数委托 `judge_degrade`；`extract_from_run_dir` 优先读 `report/summary.gate_receipt.judge_status`；`is_judge_unavailable` 只认 `unavailable`。

## 下一步
不切生产。旧产物缺 `judge_status` 不再进判官桶（有意 fail closed）。
