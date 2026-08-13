# 在途交接 · main

更新：2026-08-13 16:00 CST · #323 已合并**未部署**；Mac 隧道 530 阻塞部署与注入

## 这个分支做什么

生产基线。今日待办循环推进中。

## ⚠ 阻塞（2026-08-13 15:40 CST 起）

- **Mac 隧道持续 HTTP 530**（exec-a77.industry7view.com 到源站断），
  15:29 起所有远程命令失败。非本轮操作所致：只杀过 8795/8796/8801 三个
  uvicorn，`.cc-exec/server.py`（pid 995）与 cloudflared 未动。
  疑似 Mac 休眠或 cloudflared 掉线，需用户在 Mac 侧查看。
- 被阻塞：①#323 部署（**8792 仍在 `13b5ddd1`，熔断还是 1**）；
  ②#317 受控注入判决（杀 worker 子进程验自愈）。
  隧道恢复后按蓝绿流程切 `dd3d6b64`，再做注入。

## 当前状态

- **8792 = `13b5ddd1`**，双绿（health + readiness 200）。含今日全部：
  #317 RAG 自愈、#319 修复窗满窗、#321 终态写序。
- **#319 生产判决（R22）**：B2 修复窗 24s→30s（收据 `granted=30.0`）机制生效；
  B4 首次主路径直接 `model_finish` 拿 10 证据。
- **#321 flaky 结案**：两轮全前缀二分（239 文件）不复现 → 不是顺序污染，
  是 claim(run=completed) 与 revise_message(citations) 之间隔着 3 份 artifact
  落盘的可见性竞态。写序调整 + 消息级终态轮询 + 写序 spy 回归（变异验证过）。
- **Mac 清理完成**：8795/8796/8801 已杀（8788 第二代码线保留）；
  runtime worktree 13→3（270d00fc 世代起保留链）+ standalone 未动。
- **云端全量验证（@13b5ddd1）：15F/4149P，flaky 不再出现**；15 红全部为
  已立案 pre-existing（ceiling fixture 族「RAG Python unavailable」14 +
  api_health unread 1，云端缺 RAG venv 的环境差异，Mac 全过）。

## 未验证 / 已知边界

- **#323（熔断 1→2）已合并未部署**：取证 86 ep 收据——升窗 45/60 被证伪
  （成功修复调用 max=27.8s，慢的是挂死型 stall），换新调用救回率 61%。
  grant_id 改按 (goal, attempt) 幂等。生产判决口径：收据出现两次
  `repair_model_retry` 且第二笔 grant_id 带 `-2` 后缀、第二发救回。
- #317 自愈的生产判决仍待注入或自然超时（被隧道阻塞）。

## 下一步

1. 隧道恢复 → 蓝绿切 `dd3d6b64`（#323）→ #317 受控注入判决。
2. #319/#323 满窗+双发对照判决：明早 10–11 时（超时集中时段）复跑 B 组。
3. knevo 接力（suggest_options 缺口镜像、report→track）：材料齐，等设计拍板。

## 踩过的坑

- 二分找 flaky 前先想「顺序污染 vs 时序竞态」：全前缀+目标不复现即可排除
  前者，别无限加组合。
- 「状态标志」与「状态内容」分两次写：读者按标志读内容必读到半成品。
- 变异验证要只回退产品代码：`git stash push -- <file>`，整树 stash 会把
  新测试一起收走，验了个寂寞。

## 已验证

- 8792 @ 13b5ddd1 双绿（15:32 实测）；R22 收据落盘
  `20260813T0700Z-r22-b2-window-verdict.json`。
- orchestrator 相关 372 条、repair 相关 117 条全绿。
