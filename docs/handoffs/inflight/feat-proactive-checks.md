# feat/proactive-checks

## 这个分支做什么

本轮主动检查（漏检闸）：复盘 / 主线 / 冰点题强制核 SPT-P12..P15。不是默认 SPT 视角。

## 当前状态

干净树 `/Users/a77/fwp-wt-proactive-checks`，从 `feat/reading-rules-baseline-batch1@78391e8e` 长出。**未提交、未推、未合、未切 8792。**

已接四面：ask 合成、episode payload、CLI `_answer_market_review`、工作台 `daily-review` `output_contract`。

定向：`test_proactive_checks` + episode/baseline/ask_compose/daily_skills/layer_audit = 120 passed。

spec：`docs/superpowers/specs/2026-08-22-proactive-checks-design.md`

## 刻意没做

- 不翻 `perspective_mode` 默认，不把 SPT 设成主视角（用户说「后面」再升格）。
- 4 条不进 `reading_baseline.py`。
- 不做 DuckDB 自动 HIT/MISS、不做前瞻出卡。

## 下一步

1. 用户确认后 pathspec 提交。
2. live：工作台问「目前市场怎么看」应看见漏检闸，个股基本面题不应看见。
3. 升格 SPT 主视角另开窗（A/B + 改「neutral 逐字节不变」契约）。
