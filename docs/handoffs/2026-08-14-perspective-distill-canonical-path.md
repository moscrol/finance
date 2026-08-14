# 2026-08-14 perspective-distill canonical 路径修复 — 已合 main

PR #331 已合入 `main`（`ad386ac3`）。基线已全绿（#335 已合）。

做了：修 skill 第 0 步的 canonical 路径谎言 + 同步 registry hash；并完成 #320 遗留的两项验收（composer 真链路、sptfei 画像复核）。

修的是什么：文档说 canonical 路径是 `~/agent-memory/.foresight`，生产 launcher 实际是 `~/.local/share/finance-workbench/users`——照文档走会把画像写到生产读不到的地方（sptfei 就这么隐身的）。

## 已知边界

- ~~perspective 在 continuous episode 主路径不进模型 prompt~~ **已由 #336 修**（注入链 + 生产 smoke 已验，见 `2026-08-14-continuous-perspective-injection.md`）。
- 8-13 夜间 sync 失败是瞬时双因：upstream limit-distribution 空返回 + PID 62525 握着 duckdb 写锁（该进程已退出）。数据已由手动 daily-update 补齐（质检 OK），但**无持久修复**，下次夜间仍可能撞锁。

## 遗留（未做）

- 夜间 check 撞 duckdb 写锁应重试/降级，limit-heat 空返回应晚点重试。**本轮唯一未闭环项。**

## 踩过的坑

- shell 里的 `FORESIGHT_USERS_DIR` ≠ launcher 实际值，以 launcher 脚本为准（本 PR 就是修这个；判据和命令已写进 SKILL.md 第 0/6 步，属手法固化，不需脚本——一条 rg 即可）。
- 改 SKILL.md 必须同步 skills.registry.json 的 computedHash，否则 registry-check 红。
- daily-update 依赖 akshare，`.venv-workbench` 没装，用 `/opt/homebrew/bin/python3` 跑。

## 已验证

- sptfei 生产可见（8792 `/api/perspectives` 实测）；两份 profile（生产 + agent-memory CLI 空间）字节一致。
- composer 真链路 smoke ×2（单视角 + 中性对照）无降级，8-13 回填后。
- sptfei 画像复核收口（用户授权代拍）：`筹码与结构`/`历史同构类比` 两处 ticker 为案例锚点**保留**——历史同构是该 KOL 方法论本体，规则原文自带「类比结构与节点而非标的」防误用；与被拒的 2 个事件性 patch 性质不同。known_gaps 空，无待办残留。
- agent-memory 原文/画像未进 git（版权红线复查过 HEAD 与 origin/main 树）。
