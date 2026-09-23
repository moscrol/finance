# 评测方差基线 `20260921T105919Z-var1.json`

- live: `True`
- rev: `f2c3e9e1a24f42ae9b1d5a8cb9e501ababd1330a`
- N: 1 · 题数 2
- baseline_flip_rate: **0.0**
- judge_unavailable_rate: 0.0
- correlated_judge_rate: 0.0
- independent_judge_rate: 0.0
- independent_n: 0
- no_judge_rate: 1.0
- content_flip_rate: 0.0

观测差异小于基线翻转率，不得下回归/改善结论。judge_unavailable 类 degrade 单列，不计入内容质量。independent_n=0 时不得把判官结果当成独立验证（相关自审 / 缺字段都算）。

## 每题

- `material` n=1 mode=completed flip=0.0 judge_unavailable=0.0 correlated=0.0 independent=0.0 no_judge=1.0 counts={'completed': 1}
- `grounded` n=1 mode=completed flip=0.0 judge_unavailable=0.0 correlated=0.0 independent=0.0 no_judge=1.0 counts={'completed': 1}

per_question_flip_rate = count(primary_outcome != mode) / N; baseline_flip_rate = mean(per_question_flip_rate); mode = most frequent primary_outcome, ties broken by lexicographically smallest label; judge_unavailable_rate is mean(count(judge_unavailable)/N) and is NOT folded into content quality or into the A/B pass/fail call; correlated_judge_rate / independent_judge_rate are independence buckets and are NOT folded into content quality.
