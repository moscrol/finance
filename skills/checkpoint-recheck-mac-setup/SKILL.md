---
name: checkpoint-recheck-mac-setup
metadata:
  pattern: tool-wrapper
  also: [runbook]
description: 在 Mac 上经 remote-exec 隧道安装「可证伪点夜间回检」launchd 定时任务、并接通跨机共享大脑（.foresight）台账的安装/排障 runbook。Use when the user asks to 装夜间回检、安装 checkpoint recheck 定时、可证伪点回检 cron、launchd 装回检、远程在 Mac 上跑命令、remote-exec 隧道、隧道多字节乱码核对、codepoint 校验、共享大脑台账、.foresight 台账接通、登点回检闭环、多机台账一致. 触发词：夜间回检、checkpoint recheck、可证伪点回检、launchd 安装、远程执行、remote-exec、隧道乱码、codepoint 校验、共享大脑、foresight 台账、多机一致、登点闭环。注意：只是登点/打分/校准等台账操作本身用 intelligence.cli checkpoint 子命令即可；本 skill 专管「在 Mac 上经隧道把这套定时跑起来 + 多机台账接通 + 多字节安全核对」的安装与排障。
---

# Mac 可证伪点夜间回检安装（remote-exec + launchd + 共享大脑）

## Overview

把 `intelligence.cli checkpoint recheck --apply` 装成 Mac 上每晚自动跑的 launchd
任务，并让 `register / recheck / foresight` 三处共用同一份 `.foresight` 台账（跨机
共享大脑）。所有 Mac 侧命令经 Cloudflare remote-exec 隧道下发，路径含多字节（如
`金`）与空格，**核对数据一律走 codepoint/base64 旁路**，不信隧道回显。

详细分步见 `skills/checkpoint-recheck-mac-setup/references/runbook.md`；两个助手脚本
在 `skills/checkpoint-recheck-mac-setup/scripts/`。

## Mandatory start

下发任何 Mac 命令前，先确认隧道活着、并把工作区路径落到文件（避免多字节当参数传被吞）：

```bash
# 隧道连通性（断了会是 Cloudflare 530/1033，需在 Mac 本地把 cloudflared 拉起来）
python3 skills/checkpoint-recheck-mac-setup/scripts/mac.py 'echo ok; sw_vers -productVersion'

# 把 evolve 工作区（含 db/market_feature_store.duckdb）绝对路径落盘，后续脚本读它，
# 不要把含「金」「空格」的路径当字符串参数传（隧道会吞多字节）
python3 skills/checkpoint-recheck-mac-setup/scripts/mac.py 'cd ~/Desktop/c\ c/金 && pwd > ~/.evolve_root && cat ~/.evolve_root | wc -c'
```

`mac.py` 需要环境变量 `CC_REMOTE_EXEC_TOKEN`（Bearer）；端点默认 `https://exec.industry7view.com/api/exec`，可用 `CC_REMOTE_EXEC_URL` 覆盖。

## Core rules

- **不碰正在跑的工作区**：现网 evolve 工作区可能有 backfill 在跑。`checkpoint` 命令只在
  `main` 分支，**另开一份 main 独立 clone**（默认 `~/finance-workspace-recheck`）跑 cron，
  用 `--db-path` 指向 evolve 工作区里现有的 `db/market_feature_store.duckdb`。绝不在 evolve
  工作区 `git checkout main` / `stash` / `reset`。
- **多字节走旁路核对**：隧道回显会吞多字节字符（`铜冠铜箔` 可能显示成「铜铜」），但**磁盘字节从不损坏**。
  核对中文数据用 `python3 -c "print([hex(ord(c)) for c in s])"` 的 codepoint dump 或 base64，
  **不要**用肉眼看回显下结论。
- **台账要三处一致**：cron 的 plist、手动登点的那台、跑 foresight 的那台，必须用**同一个**
  `FORESIGHT_USERS_DIR`（如 `<vault>/.foresight`），否则 cron 回检的是另一份空台账。
- **plist 用 Python 生成，不用 sed**：路径含多字节/空格时 `sed` 模板替换不可靠；用
  `scripts/build_plist.py`（条件性删空 env key + 注入 `--db-path`），生成后必过 `plutil -lint`。
- **due 在未来=今天空跑属正常**：到期日没到就是 0 条到期、不写 `可证伪点回检/<日期>.md`、
  `LastExitStatus=0`、err 空——这是健康态，不是失败。

## 一次性安装（摘要，细节见 runbook）

```bash
# 1. 另开 main 独立 clone（不动 evolve 工作区）
python3 skills/checkpoint-recheck-mac-setup/scripts/mac.py 'cd ~ && git clone <repo> finance-workspace-recheck 2>&1 | tail -2; cd finance-workspace-recheck && git rev-parse --short HEAD'

# 2. 生成并加载 plist（FORESIGHT_USERS_DIR / SUBCONSCIOUS_VAULT 经 env 传入 build_plist.py）
#    见 references/runbook.md「步骤 4」

# 3. 立刻手动触发一次 + 看结果（不用等 03:50）
python3 skills/checkpoint-recheck-mac-setup/scripts/mac.py 'launchctl start com.financeworkspace.checkpoint-recheck; sleep 3; tail -5 ~/finance-workspace-recheck/logs/checkpoint-recheck.*.log'
python3 skills/checkpoint-recheck-mac-setup/scripts/mac.py 'launchctl list | grep checkpoint-recheck'
```

## Iteration rule

隧道吞字符、plist 生成踩坑、台账路径对不上等只要复发，先把本 skill / 脚本补上再继续，
别盲目重试。校验 plist 模板可解析可跑 `python3 -m unittest intelligence.tests.test_checkpoint_cron`。
