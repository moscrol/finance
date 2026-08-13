# 在途交接 · main

更新：2026-08-13 · 三 PR 已合并（MERGED），8792 已干净切到 `1d45f5cf`

## 这个分支做什么

生产基线。夜间修复循环已收口并部署。

## 当前状态

- `main` @ `1d45f5cf` 含：#301 A3 冷启动、#302 RAG worker 缓存键、#303 A4 截断哈希、#304 A1-R2 冷启动扩判据。
- 8792 = `1d45f5cfa947`，worktree clean（热补丁已随切换退役），ready，RAG 预热 70s。
- 旧 runtime `09dacdeaca30` / `bcd3b6ce64f7` 保留可回滚。不要动 Mac 开发区。

## 下一步

1. 可选生产冒烟 A1/A3/A4（验证三修复的真实形状）。
2. A5 非本仓 bug；A7/A10、governor 升档是设计评审项。
3. #304 的 `model_unavailable` 判据偏宽（非瞬态异常也给一发冷启动），有 cycle/余量闸兜底；要收紧按 gap 里的异常类型滤。

## 未验证

- 三修复的生产真实形状（需等真实流量或跑验收）。

## 踩过的坑

- 切 8792 不要 `reset --hard`。预热同步，kickstart 后 2–3 分钟不监听。
- 饿死看 stop_reason；`model_finish` 不是饿死。
- 多 PR 都写 inflight/main.md 时顺序合必冲突；以合并末态覆写一次即可。

## 已验证

- 合并末态回归 192 passed（rag_worker/episode_protocol/adapter/coordinator/agent_episode）。
- 8792 health healthy、ready 无缺项、`workers.rag.state=ready`、runtime clean。
- 三 PR GitHub 状态 MERGED。
