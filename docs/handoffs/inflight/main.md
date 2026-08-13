# 在途交接 · main

更新：2026-08-13 15:35 CST · 待办推进：#319/#321 已合并部署，flaky 结案

## 这个分支做什么

生产基线。今日待办循环推进中。

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

- **R22-B2 残余**：修复窗已是 30s 满窗仍两发超时（`repair_deadline_exhausted`）。
  30s 单笔帽对大 prompt 修复合成可能不够——升帽要先取延迟分布样本论证，
  属 governor 升档设计项，勿凭单题就改。
- #317 自愈的生产判决仍待自然查询超时。

## 下一步

1. governor 升档设计：取修复调用延迟分布（收据里有 asked/granted/结果），
   论证 30s 帽是否升到 45/60（R22-B2 满窗仍两发超时是入口证据）。
2. knevo 接力项（suggest_options 缺口镜像、report→track）。
3. #317 自愈、#319 满窗的自然生产判决（等真实流量形状）。

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
