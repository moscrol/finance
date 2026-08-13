# 在途交接 · main

更新：2026-08-13 14:15 CST · #316/#317 已合并，8792 已切 `270d00fc`，双绿

## 这个分支做什么

生产基线。RAG 自愈修复已合并部署，无在途 PR（#307 他人 draft 除外）。

## 当前状态

- **8792 = `270d00fcf5c4`**（含 #317 自愈 + #314/#315 测试修复），
  loaded_code_root 指向新 worktree，runtime clean，pid 64134。
- `/api/health` healthy + `/api/readiness` **200 ready**，
  `rag.state=ready active=1`，本次预热 57s。
- 今日故障链已闭环：不是建索引（KB 索引 10:46 建完且对齐 HEAD f91cc96b）；
  是查询超时杀 worker 后永久 failed。人工 kickstart 救活 → #317 修根因。
- #317 机制：查询失败按预热配方（240s 窗）后台自愈，单飞 + 60s 冷却
  （`RAG_WORKER_RECOVERY_COOLDOWN_SECONDS`）+ 恢复失败不自我续期。

## 未验证 / 已知边界

- **#317 生产判决未做**：需要现网真实出现一次查询超时，观察 worker 是否
  自动回 ready 而不需要 kickstart。单测 15/15 已钉行为，但按本仓纪律
  「合并 ≠ 生产判决」。下次 readiness 红时先看是否自愈中（state=warming）。
- code_matches_repo=False 是预期（开发区在改，生产是冻结快照，非 critical）。

## 下一步

1. 等一次自然的查询超时给 #317 出生产判决（或压测诱发，需确认）。
2. 设计项：核验合成层预算（质量最大瓶颈，knevo 对照 9/2/0 的根源）、
   governor 升档。
3. flaky：`citations_survive_run_context_reload`。
4. 清理（需确认）：13 个 runtime worktree 留最近 2–3；杀 8795/8796/8801。

## 踩过的坑

- health 绿 ≠ readiness 绿；`lifecycle=startup_prewarm` 是写死标签别拿来归因。
- `rag update` 即使 embedded=0 也加载 391 分片，日志像建索引；判据是
  pid/lsof/`meta.json.built_at`。
- `monotonic()` 从开机起算：冷却戳初值用 -inf 别用 0.0。
- 首次预热 145s，热缓存 57–59s：判「预热异常慢」前先问页缓存冷热。

## 已验证

- 切换后 loaded=270d00fc、readiness 200 ready（14:14 实测）。
- 合并末态 test_rag_worker + test_rag_readiness 21/21。
- R20 A 组 10/10；R19 休市披露；R14/R16/R17 判决未变。
