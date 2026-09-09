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
- 实现提交 `3a2a2254`，前向合并 gitea/main（#687）→ `5db4e330`，merge-tree 无冲突。用户 15:10 拍板「可以合并的话就合并」。
- 等价 CI（合并树）：python 3 片 8373P/0F（归档测试收集错为主干既有，blocked #6）、frontend 全过、e2e 15 passed、
  data-quality 54 passed；registry-check 三项红为主干既有（blocked #7）。详见 verification 文档表。
- 验收实例 8807 在跑（`~/.finance-runtime/cap07-acceptance/`，用户目录 `~/.finance-runtime/cap07-users`）；真实对话验收
  被网关挡住两次：14:57 sol/terra 双 429 cooldown；16:05 sol 仍 cooldown、terra 502 `no auth available`。模型不参与的
  接缝（真实 `memory_lookup` runner、`[M]` 块）已实测出「方法验证读数」。
- 能力图行已改指本分支符号，`graph_audit` OK（74 条断言）。

## 下一步
1. 网关恢复后跑 `drive.py` 两题（命令在 verification 文档），核 `continuous-episode.json` 的 memory_lookup 调用与证据，
   结果补进 verification / progress（小文档修补可直接 main）。
2. 09-10 收盘且 daily-full 落库后跑一次 `method_validation.py daily`（命令在 workflow 文档）；09-17 前后再跑或等 03:50 夜间回检。
3. 生产生效沿原任务授权：生产用户目录 `register` + `history` 一次，`daily` 接进夜跑；本分支未装任何日程。

## 踩过的坑
- 同指纹重算摘要 `generated_at` 变化撞「不可覆盖」发布 → 派生缓存改 `replace_json`。
- `market_feature_store.db.DB_PATH` 按代码根算，另一棵工作树上不存在：`daily` 要 `--db-path` 指主库。
- readiness 503 时 urllib 直接抛错，驱动脚本要容忍；`market_data_consistency=false` 是主库 09-08 未落库（生产同状态）。
