# feat/cap07-method-flywheel · 2026-09-09 · 方法飞轮接线（能力升级任务包 07）

## 这个分支做什么
把 `feat/method-validation-loop`（未合 main）的固定双红协议收据接到日常使用：立场按收据派生、有信号 D0 登记
checkpoint、夜间回检自动结算并分类、`memory_lookup` / `[M]` / 日报段消费同一份摘要。任务书
`docs/superpowers/plans/2026-09-09-capability-upgrade/07-method-flywheel-goal-brief.md`（在 codex 分支），进度
`…/progress/07.md`，范围外 `…/blocked/07.md`，交付说明 `docs/verification/2026-09-09-method-flywheel-cap07.md`。

## 决策与被否方案
- 立场派生不存状态；摘要按输入指纹缓存 / 否了每次读 106MB 原件或加可变 status 字段。
- 观察登记进既有 `checkpoints.jsonl`（新 `object_type=method_observation`）/ 否了另开台账；环境变化与数据不足
  → unverifiable 不进分母 / 否了 partial 计分。
- 回检六类 + 环境标记（D+1..D+5 阶段离开适用集合）；选择梯子确定性四档 / 否了在本刀引入统计门。
- 只做「双红」关键词匹配，匹不上存候选草稿 / 否了通用编译。

## 当前状态
- 未提交（等续跑验收后一并 pathspec 提交）：`intelligence/services/method_validation/{flywheel.py(新),study.py,store.py,__init__.py}`、
  `checkpoints.py`、`checkpoint_resolvers.py`、`user_memory.py`、`episode_tools.py`、`workflows/daily_agent.py`、
  `api/daily_reports.py`、`scripts/method_validation.py`、`intelligence/tests/test_method_flywheel.py`(新)、
  `docs/learning/ledger-map.md`、`docs/workflows/method-validation-loop.md`、progress/blocked/verification 三份文档。
- 相关回归 242 passed、ruff 全仓通过、layer_audit ERROR 0；全仓 pytest 在跑（`~/.finance-runtime/cap07-acceptance/pytest-full.log`）。
- 验收实例 8807 在跑（`~/.finance-runtime/cap07-acceptance/`，用户目录 `~/.finance-runtime/cap07-users`）；14:57 第一发
  被网关 `model_cooldown`（sol / terra 双 429，约 16:01 解除）打掉，16:08 已排一次性提醒续跑两题。
- 能力图 `~/agent-memory/10_knowledge/finance-agent-capability-graph.md` 行已改指本分支符号（graph_audit 待跑）。

## 下一步
1. 16:08 续跑 `drive.py` 两题；核 `continuous-episode.json` 里 memory_lookup 调用与「方法验证读数」证据；结果写进
   verification 与 progress。
2. 全仓 pytest 收据 → pathspec 提交 → 用户确认后开 PR（不合 main、不切生产）。
3. 09-10 收盘且 daily-full 落库后跑一次 `method_validation.py daily`（命令在 workflow 文档）；09-17 前后再跑或等 03:50 夜间回检。

## 踩过的坑
- 同指纹重算摘要 `generated_at` 变化撞「不可覆盖」发布 → 派生缓存改 `replace_json`。
- `market_feature_store.db.DB_PATH` 按代码根算，另一棵工作树上不存在：`daily` 要 `--db-path` 指主库。
- readiness 503 时 urllib 直接抛错，驱动脚本要容忍；`market_data_consistency=false` 是主库 09-08 未落库（生产同状态）。
