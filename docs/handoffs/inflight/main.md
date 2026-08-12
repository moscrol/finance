# 在途交接 · main

更新：2026-08-13 · 用户确认合 #301；本轮：交接 → 合 → 蓝绿 8792 → 接下一批

## 这个分支做什么

repair 超时重试已上线。本轮把 A3 冷启动修复合进 main 并部署，再接下一批立案。

## 当前状态

- 8792 仍在 `bcd3b6ce`（#299）。#301 `cursor/repair-cold-restart-d7ac` @ `54887fc0`，用户已确认合并。
- 不要动 Mac 开发区；以 `loaded_code_root` 为准。旧 runtime 保留回滚。
- 生产 run：`FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`

## 下一步

1. 合 #301，蓝绿切 8792（新建 detached worktree → bootout → `ln -sfn` → bootstrap；禁止 `reset --hard` 旧 runtime）。
2. **A4**：15 位哈希像抄漏。口子「唯一前缀 → FORMAT（可回灌）」；0/多匹配仍 INTEGRITY。先测后改。
3. A7/A10 核验预算；A5 日期错位；governor 主动升档——均需评审，别顺手改。
4. knevo：suggest_options / report→track。
5. BUILD.md 候选：纠正层写收据、重试窗取当前权威、NULL 按业务语义、饿死看 stop_reason。

## 未验证

- #301 尚未合进生产 8792。8797/8794 隔离口可关。

## 踩过的坑

- 饿死判据用 `stop_reason=deadline_exhausted`+零证据，不用 trace（R9 证伪「试过工具」）。
- 本地 GLM = Coding Plan URL，不是 ollama；`ZHIPU_API_KEY` 走官方 429。
- 远程复杂脚本 stdin heredoc；长任务 nohup；不写 token。
- 切 8792 不要 `reset --hard` 旧 runtime。

## 已验证

- R12：饿死→冷启动带工具→证据 0→5→finalize 超时→瞬态重试→`repair_model_finish`。
- R7：#296/#297 生产通过。R8：A10 证据 0→3。
