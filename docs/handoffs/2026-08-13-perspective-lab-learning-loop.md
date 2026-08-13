# 2026-08-13 Perspective Lab 学习闭环 — 已合 main

PR #320 已合入 `main`（`bd91acf5`）。

做了：P1 学习闭环（文章→卡片→patch→人工确认）+ 视角运行时补强
（D6 门控放宽、题材宽松匹配+停用词、composer/修复轮注入视角）+
`perspective-distill` skill。

未验：composer 真链路（需 DuckDB 无写锁、非模板降级）；sptfei 画像待用户复核；
Mac 三仓在场时跑一次 `build_registry.py scan`（main 上注册表另有 12 处滞后，
CI registry-check 在合入前已红，非本 PR 引入）。

再用：发原文说「蒸馏视角」走 skill。Workbench 单视角 sptfei 问同一句做 smoke。
