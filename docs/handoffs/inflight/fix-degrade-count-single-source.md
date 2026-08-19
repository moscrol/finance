# fix/degrade-count-single-source

## 这个分支做什么
合入 W2+W3 后留下的口径分叉：`gate_receipt.classify_degrade_counts` 曾把 `judge_status is None` + timeout/exc 算进 `judge_unavailable`；W2 只认显式 `unavailable`。W7 抽取也不读 `gate_receipt`，ask 的 `not_applicable` 会变成 `None` 再被记成判官不可用。

## 当前状态
已实现、未合。`gate_receipt` 计数委托 `judge_degrade`；`extract_from_run_dir` 优先读 `report/summary.gate_receipt.judge_status`；`is_judge_unavailable` 只认 `unavailable`。夹具里那条历史 `"timeout"` 改成生产会写的 `"unavailable"`。

## 已验证
定向：`test_gate_receipt` / `test_judge_degrade` / `test_eval_variance_baseline` / `test_live_probe` 38 passed。未 live、未切 8792。

## 下一步
用户确认后合 main。不合 Track D、不切生产。
