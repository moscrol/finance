# 在途交接 · fix/perspective-distill-canonical-path

> 指针（2026-08-14）：本轮验收闭环完成，PR #331 已具备合并条件。剩余事项只有两个立案（见下一步），基线最后 1 红由 #335 收。

## 这个分支做什么

修 perspective-distill skill 第 0 步的 canonical 路径谎言（文档说 `~/agent-memory/.foresight`，生产 launcher 实际是 `~/.local/share/finance-workbench/users`），并同步 registry hash。

## 当前状态

- 全部已提交已推送，无未提交改动。registry-check 绿。
- workbench-check：合入 main（含 #332/#334 的 16 个修复）后重跑，剩 1 红
  `TestUnreadFieldsGate`，与 main 完全一致、由在途 #335 修——本分支零新增失败（4829 过）。

## 未验证 / 已知边界

- **perspective 在 continuous episode 主路径不进模型 prompt**：`_complete_continuous_turn` 不收视角参数、在 ask_options 构造前就返回。生产现状 = 视角只验证+存储，不影响答案。证据见 PR #331 评论。
- 8-13 夜间 sync 失败是瞬时双因：upstream limit-distribution 空返回 + PID 62525 握着 duckdb 写锁（该进程已退出，锁现在空闲）。数据已由 02:08 手动 daily-update 补齐（质检 OK），但**无持久修复**，下次夜间仍可能撞锁。

## 下一步

1. 立案：continuous 路径接视角注入（不接，画像永远是死数据）。
2. 立案：夜间 check 撞 duckdb 写锁应重试/降级，limit-heat 空返回应晚点重试。
3. #335 合并后基线全绿，本文件可转日期快照归档。

## 踩过的坑

- shell 里的 `FORESIGHT_USERS_DIR` ≠ launcher 实际值，以 launcher 脚本为准（本 PR 就是修这个；判据和命令已写进 SKILL.md 第 0/6 步，属手法固化，不需脚本——一条 rg 即可）。
- 改 SKILL.md 必须同步 skills.registry.json 的 computedHash，否则 registry-check 红。
- daily-update 依赖 akshare，`.venv-workbench` 没装，用 `/opt/homebrew/bin/python3` 跑。

## 已验证

- sptfei 生产可见（8792 `/api/perspectives` 实测）；两份 profile（生产 + agent-memory CLI 空间）字节一致。
- composer 真链路 smoke ×2（单视角 + 中性对照）无降级，8-13 回填后。
- sptfei 画像复核收口（用户授权代拍）：`筹码与结构`/`历史同构类比` 两处 ticker 为案例锚点**保留**——历史同构是该 KOL 方法论本体，规则原文自带「类比结构与节点而非标的」防误用；与被拒的 2 个事件性 patch 性质不同。known_gaps 空，无待办残留。
- agent-memory 原文/画像未进 git（版权红线复查过 HEAD 与 origin/main 树）。
