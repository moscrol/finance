# 在途交接 · main

更新：2026-08-13 14:05 CST · RAG 已救活（kickstart），自愈修复 #317 待合

## 这个分支做什么

生产基线。夜间修复 PR 已全部合入；本轮新增 #317 待用户确认合并。

## 当前状态

- **8792 已恢复绿**：14:00 kickstart（新 pid 47143），预热 59s（索引在页缓存），
  `/api/readiness` = 200 ready，`rag.state=ready active=1`。
- loaded 仍 `02028b29`，runtime clean。origin/main = `6d9c6328`（文档/测试，
  运行时等价，不必切）。
- 今早红灯根因已钉死：**不是在建索引**（KB `.rag_index` 10:46 建完，
  `source_git_revision=f91cc96b` 对齐 KB HEAD）。是查询超时杀 worker 后
  永久 failed——预热窗 240s > 查询窗 90s，加载 ~145s，懒恢复必二次超时。
- **#317**（`cursor/rag-worker-self-heal-d7ac`）：查询失败按预热配方后台自愈，
  单飞 + 60s 冷却 + 不自我续期；close() 先无锁杀子进程防停机挂预热窗。
  新增 4 测试，rag 套件 15/15。**未部署**——合并后下次切生产生效。
- #316：本轮取证与交接修正（本分支）。唯一他人 PR #307 draft 未动。

## 未验证 / 已知边界

- #317 只有云端单测判决；生产判决要等合并 + 切 8792 后复现「查询超时」形状。
- 在此之前再遇超时仍需人工 kickstart。
- `test_api_health` unread-fields 一条红为 pre-existing（stash 验证同红）。

## 下一步

1. 用户确认后合 #316/#317；切 8792 到合并末态（detached worktree + 软链）。
2. 设计项：核验合成层预算（质量最大瓶颈）、governor 升档。
3. flaky：`citations_survive_run_context_reload`。
4. 清理（需确认）：12 个 runtime worktree 留 2–3；杀 8795/8796/8801。

## 踩过的坑

- health 绿 ≠ readiness 绿；`lifecycle=startup_prewarm` 是写死标签别拿来归因。
- `rag update` 即使 embedded=0 也加载 391 分片，日志像在建索引；判据是
  pid/lsof/`meta.json.built_at`，不是日志形状。
- `monotonic()` 从开机起算：冷却戳初值用 -inf，别用 0.0（CI 容器会误判）。

## 已验证

- kickstart 后 readiness 200 ready（14:01 实测）。
- #317 分支：test_rag_worker 15/15、workbench_api readiness/rag 11/11。
- R20 A 组 10/10；R19 休市披露；R14/R16/R17 判决未变。
