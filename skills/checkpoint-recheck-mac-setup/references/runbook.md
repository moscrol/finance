# Mac 可证伪点夜间回检 — 安装 / 接通共享大脑 / 排障 runbook

所有 Mac 侧命令经 `scripts/mac.py`（remote-exec 隧道）下发。下文 `MAC=...mac.py` 仅为缩写：

```bash
MAC="python3 skills/checkpoint-recheck-mac-setup/scripts/mac.py"
```

本机实测值（按你机器替换）：用户 `lbq`，macOS 15.7.4，`/usr/bin/python3`（3.9.6，含 duckdb）。
- evolve 工作区（含 1.1GB duckdb、可能有 backfill 在跑，**别碰**）：`~/Desktop/c c/金`
- duckdb：`~/Desktop/c c/金/db/market_feature_store.duckdb`
- main 独立 clone（cron 跑这份）：`~/finance-workspace-recheck`
- Obsidian vault 根：`~/Desktop/stu/ai/ai`（含 `.obsidian`）
- 共享台账根：`~/Desktop/stu/ai/ai/.foresight`
- foresight 用户：`linxiaoqi5111`

---

## 0. 前置：隧道连通 + 路径落盘

```bash
# 隧道活着？（断了是 Cloudflare 530/1033，须在 Mac 本地拉起 cloudflared，远端无法修）
$MAC 'echo ok; whoami; sw_vers -productVersion'

# 把 evolve 工作区绝对路径落盘（含「金」和空格，别当字符串参数传，会被吞多字节）
$MAC 'cd ~/Desktop/c\ c/金 && pwd > ~/.evolve_root && wc -c < ~/.evolve_root'
$MAC 'ls -la "$(cat ~/.evolve_root)/db/market_feature_store.duckdb"'
```

## 1. 多字节安全核对（隧道会吞回显，磁盘不损坏）

隧道回显可能把 `铜冠铜箔` 显示成「铜铜」、`回检并落盘` 显示成「回并盘」——这是**显示层**丢多字节，
磁盘字节是好的。核对中文一律走 codepoint / base64 旁路，别信肉眼：

```bash
# codepoint dump：逐字打印 Unicode 码点，mangle-proof
$MAC $'python3 -c \'s=open("/path/to/file").read(); print([hex(ord(c)) for c in s[:40]])\''
# 或 base64 整段取回本地再 decode 核对
$MAC 'base64 -i /path/to/file' | base64 -d | head
```

## 2. 另开 main 独立 clone（不碰 evolve 工作区）

`checkpoint` 子命令**只在 main 分支**。evolve 工作区可能在跑 backfill，**绝不**在它上面
`git checkout main` / `stash` / `reset`。另开一份 main：

```bash
$MAC 'cd ~ && git clone <repo-url> finance-workspace-recheck 2>&1 | tail -3'
$MAC 'cd ~/finance-workspace-recheck && git rev-parse --short HEAD && git branch --show-current'
# 确认 checkpoint 命令存在
$MAC 'cd ~/finance-workspace-recheck && python3 -m intelligence.cli checkpoint status --user linxiaoqi5111 --json 2>&1 | head'
# 确认 plist 模板在
$MAC 'ls ~/finance-workspace-recheck/intelligence/dream/com.financeworkspace.checkpoint-recheck.plist'
```

> `register --help` 会因仓库里某条中文 help 串触发 argparse ValueError 而崩——只影响 `--help`，
> 实际运行不受影响；要看参数直接读 `intelligence/cli.py` 的 `p_reg`/`p_re` 段。

## 3. dry-run 预览（不落盘）

```bash
$MAC 'cd ~/finance-workspace-recheck && FORESIGHT_USERS_DIR=~/Desktop/stu/ai/ai/.foresight \
  python3 -m intelligence.cli checkpoint due --user linxiaoqi5111'
# 不加 --apply = 只预览；--db-path 指向 evolve 的库（clone 里没库）
$MAC 'cd ~/finance-workspace-recheck && FORESIGHT_USERS_DIR=~/Desktop/stu/ai/ai/.foresight \
  python3 -m intelligence.cli checkpoint recheck --user linxiaoqi5111 \
  --db-path "$(cat ~/.evolve_root)/db/market_feature_store.duckdb"'
```

## 4. 生成并加载 plist（用 build_plist.py，别用 sed）

`build_plist.py` 跑在 **Mac 本地**：读 `~/.evolve_root` + clone 内模板，按需删空 env key、
在 `--apply` 后注入 `--db-path`，写到 `~/Library/LaunchAgents/`。经 stdin 下发（避免脚本正文
多字节被当参数吞）：

```bash
# 把脚本经 stdin 喂给 Mac 的 python3，配置走前置的 export
cat skills/checkpoint-recheck-mac-setup/scripts/build_plist.py | \
  $MAC $'FORESIGHT_USER=linxiaoqi5111 \
RECHECK_CLONE=~/finance-workspace-recheck \
FORESIGHT_USERS_DIR=~/Desktop/stu/ai/ai/.foresight \
SUBCONSCIOUS_VAULT=~/Desktop/stu/ai/ai \
python3 - '

# 校验 + 加载
$MAC 'plutil -lint ~/Library/LaunchAgents/com.financeworkspace.checkpoint-recheck.plist'
$MAC 'launchctl load ~/Library/LaunchAgents/com.financeworkspace.checkpoint-recheck.plist'
$MAC 'launchctl list | grep checkpoint-recheck'   # 出现该行 = 装好；LastExitStatus 应为 0
```

调度时间在模板里（本机 03:50）。

## 5. 立刻手动触发一次（不用等 03:50）

```bash
$MAC 'launchctl start com.financeworkspace.checkpoint-recheck; sleep 3; \
  echo "=out="; tail -8 ~/finance-workspace-recheck/logs/checkpoint-recheck.out.log; \
  echo "=err="; tail -8 ~/finance-workspace-recheck/logs/checkpoint-recheck.err.log'
$MAC 'ls -la ~/Desktop/stu/ai/ai/可证伪点回检/ 2>&1 | tail'
```

健康态：`out` 显示「回检并落盘 N 条」，`err` 空，`LastExitStatus=0`。**到期日在未来时今天就是
0 条到期、不写 `可证伪点回检/<日期>.md`**——正常，不是失败。

## 6. 接通共享大脑（register / recheck / foresight 同一本台账）

要让闭环真转，三处必须用**同一个** `FORESIGHT_USERS_DIR`，否则 cron 回检的是另一份空台账。

**a. cron 的 plist 补 env**（步骤 4 若已带 `FORESIGHT_USERS_DIR` 可跳过；补改用 PlistBuddy）：

```bash
$MAC $'PL=~/Library/LaunchAgents/com.financeworkspace.checkpoint-recheck.plist; \
launchctl unload "$PL"; \
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:FORESIGHT_USERS_DIR /Users/lbq/Desktop/stu/ai/ai/.foresight" "$PL" 2>/dev/null \
 || /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:FORESIGHT_USERS_DIR string /Users/lbq/Desktop/stu/ai/ai/.foresight" "$PL"; \
plutil -lint "$PL" && launchctl load "$PL"'
```

**b. 手动登点 / 跑 foresight 的那台**，写进 shell profile（幂等 marker block）：

```bash
# >>> foresight shared-brain (devin) >>>
export FORESIGHT_USER=linxiaoqi5111
export FORESIGHT_USERS_DIR="/Users/lbq/Desktop/stu/ai/ai/.foresight"
# <<< foresight shared-brain (devin) <<<
```

**c. 登一个点验证闭环**（实测命令；中文经 base64 传更稳）：

```bash
$MAC $'cd ~/finance-workspace-recheck && export FORESIGHT_USERS_DIR=~/Desktop/stu/ai/ai/.foresight && \
python3 -m intelligence.cli checkpoint register --user linxiaoqi5111 \
  --claim "铜冠铜箔 60日涨幅站上15%" --due 2026-09-30 --category 估值切换 \
  --stock 铜冠铜箔 --metric-type stock_return --op ">=" --target 15 --window-days 60'
# 用到期日预览证明确实进了台账、到期逻辑能选到它
$MAC 'cd ~/finance-workspace-recheck && FORESIGHT_USERS_DIR=~/Desktop/stu/ai/ai/.foresight \
  python3 -m intelligence.cli checkpoint due --user linxiaoqi5111 --date 2026-09-30'
# codepoint 核对落盘的中文逐字正确（别看回显）
$MAC $'python3 -c \'import json;r=[json.loads(l) for l in open("/Users/lbq/Desktop/stu/ai/ai/.foresight/linxiaoqi5111/checkpoints.jsonl")];c=r[-1]["claim"];print([hex(ord(x)) for x in c])\''
```

> 迁移提醒：若你之前在别处攒过 `users/<id>/`（judgments/interactions/profile）且没用过
> `FORESIGHT_USERS_DIR`，切共享前把那份拷进 `.foresight/<id>/`，否则 foresight 从零开始。
> 本机实测台账为空，无需迁移。

## 7. 排障速查

| 现象 | 原因 | 处理 |
|------|------|------|
| HTTP 530 / Cloudflare 1033 | Mac 的 cloudflared/exec 源站没起来 | 远端修不了；在 Mac 本地 `pgrep -fl cloudflared`、重启隧道 |
| Cloudflare 1010 | 请求缺 curl 样 User-Agent 被 WAF 拦 | `mac.py` 已带 `User-Agent: curl/8.5.0` |
| 中文显示成残字（铜铜/回并盘） | 隧道回显丢多字节（磁盘不损坏） | 用 codepoint dump / base64 核对，别信回显 |
| `checkpoint` 命令不存在 | 当前在 evolve 等非 main 分支 | 用 main 独立 clone `~/finance-workspace-recheck` |
| `register --help` 崩 | 中文 help 串触发 argparse ValueError | 跳过 `--help`，照 cli.py 的 `p_reg` 用参数 |
| recheck 报 unverifiable | duckdb 不在默认路径 | 加 `--db-path "$(cat ~/.evolve_root)/db/market_feature_store.duckdb"` |
| cron 每晚空跑 | `FORESIGHT_USERS_DIR` 没接到登点那本台账 | 三处用同一 `FORESIGHT_USERS_DIR`（见步骤 6） |
| 今天没生成回检 md | 到期日在未来，0 条到期 | 正常；到期那天才写 `可证伪点回检/<日期>.md` |
| kb_evidence 类回检不动 | 缺 `KNOWLEDGE_WIKI` | 给 plist 补 `KNOWLEDGE_WIKI` 指向 wiki 根；纯 stock_return 不需要 |

## 8. 卸载 / 重装

```bash
$MAC 'launchctl unload ~/Library/LaunchAgents/com.financeworkspace.checkpoint-recheck.plist'
# 改完重新 build_plist.py（步骤 4）→ plutil -lint → launchctl load
```

校验 plist 模板可解析可跑：`python3 -m unittest intelligence.tests.test_checkpoint_cron`。
