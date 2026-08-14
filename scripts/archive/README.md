# scripts/archive

2026-07 模块审计清单：下列条目是历史归档/退役定位，不代表当前现役入口；不要从旧实现恢复第二条写入链。

- `render_sw_l1_theme_matrix_html.py` — 无任何引用
- `backtest_sector.py` / `detect_turning_points.py` — 已迁移为 canonical 只读分析 CLI，不在 archive 中复制旧版本
- `sync_to_local.py` — 已正式退役；完整旧实现可用 `git show a84028e6:scripts/sync_to_local.py` 查阅，不复制可误运行的死脚本
- `compare_theme_candidates.py` — 仅历史文档提及的一次性 QA 对照
- `compute_features.py` — 无活跃消费者，写死 Mac 数据库路径且 UP 线上限冻结在 2026-06-17
