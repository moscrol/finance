# scripts/archive

2026-07 模块审计归档：全仓无代码引用（或仅历史文档提及）的脚本，冻结不删，需要时移回 `scripts/` 即可。

- `render_sw_l1_theme_matrix_html.py` — 无任何引用
- `backtest_sector.py` / `detect_turning_points.py` — 仅互相引用，未接进任何 workflow
- `compare_theme_candidates.py` — 仅历史文档提及的一次性 QA 对照
- `compute_features.py` — 无活跃消费者，写死 Mac 数据库路径且 UP 线上限冻结在 2026-06-17
