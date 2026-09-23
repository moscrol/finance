# 2026-09-23 · 磁盘四轮清理 + 治本改动（fix/disk-burn-cow-snapshots-0923）

## 背景

460 GB 的盘 09-23 凌晨用到 98%（容器空闲 3.1 GB）。同机另一会话 01:39 做了第三轮清理，只清可再生缓存
（.code-review-graph ×200、pycache、~/.cache、node_modules，13.4 + 4.9 GiB），结论「一次性清理追不上产出，
日烧 30–45 GB」；用户在那轮**明确拒绝**两件事：每日自动清扫、工作树积压处置（清单或按时间归档）。
本轮用户的话是「磁盘又要满了，你帮我看看怎么释放空间，你可以看下整个电脑」，然后在 AskUserQuestion 里选了
「A 档 + B 档都删」和「开分支做治本改动，合并前给我看」。清理收据、脚本、整机分布表都在
`~/.finance-runtime/reviews/disk-cleanup-20260923/`（round4-plan.sh / round4-inventory.md / round4-receipt.json / 日志）。

## 按发现顺序

1. `du` 分层下钻：`~/.finance-runtime` 116 GB（reviews 62、db-repair 37）、`~/Library` 47、178 棵 `fwp-*` 45、主树 22、
   pytest 临时 17、`~/.cursor/chats` 14、Gitea 备份 13。Docker.raw 表面 460 GB 是稀疏文件，实占 4 GB。
2. 全盘找 >500 MB 的 `*.duckdb*`：20 份、68 GB，全是 3.4 GB 整库拷贝——hithink 修库 11 份（09-12~14，分支已合）、
   两条未合分支 tmp/ 里 5 份取证、reviews 里 2 份、生产库 + 昨晚回滚点 2 份。**这是烧盘主因**。
3. `market_feature_store/db.py` 做 staging 已经用 `cp -c`（APFS clonefile），但 `scripts/db_baseline_export.py`、
   `scripts/db_delta_pull.py` 和修库脚本的「改前快照」仍是 `shutil.copy2` 整份。
4. dry-run 跑出 B 档候选后交叉对 `~/Library/LaunchAgents/*.plist` 与 `~/.local/bin/*`：两棵 detached 树
   `~/.devin-worktrees/ima-queue-auto-triage`、`~/kb-runtime` 是定时任务代码根——删了就断 launchd 作业。加了引用守卫，
   真删时又拦下 5 棵 `~/.finance-runtime/finance-*` 与 `~/finance-workspace-sync`。
5. 第一次 B 档 dry-run 卡住 11 分钟无子进程无输出，未查明（lsof 在这台机器上时有停滞）；给 lsof 加 `-S 2` 与 120 秒
   看门狗，拿不到「谁在用」就整轮拒绝删，而不是退化成盲删。
6. 真删：A 档 63.9 GB + B 档 34.9 GB = 98.8 GB，280 个路径 + 56 棵树，0 失败；可用 42 → 101 GiB（76%）。
7. 写治本改动时踩到 bash 3.2：`"$real（…"` 在 set -u 下报 `real\xef: unbound variable`，stderr 带孤立 `\xef`
   让 `subprocess.run(text=True)` 抛 UnicodeDecodeError——看起来像 Python 解码问题。

## 决策

| 决策 | 选了 | 否了 | 为什么 |
|---|---|---|---|
| 清理边界 | A 档过期现场 + B 档按 git 逻辑安全的树/备份 | 处置 137 棵未合树；动取证库；动 Cursor/Devin 聊天库 | 前者用户上一轮明确拒绝；`fwp-wt-market-recovery-0921/tmp` 交接原文「不得提交、覆盖或删除」；后者是个人数据 |
| L2 两天 7z 9.7 GB | 留 | 删（可从百度分享重下） | 库里 L2 表最新 09-18，这两份还没解算，是管线输入不是垃圾 |
| reviews 里的临时区 | 只删 basetemp / pytest-temp / browsers / ruff-cache 子目录 | 删整个 gates 目录 | gates/ 里有 run.json / junit.xml / stdout.log 收据 |
| 「谁在用」判据 | 一次 `lsof -S 2 -Fn` 做子串匹配 + 目录 mtime 非今天 | 每棵树 `lsof +D` | 205 个 review 目录逐个递归要几分钟；子串匹配偏保守只会多跳过 |
| worktree 删法 | 自查干净后 `git worktree remove --force` | 不带 --force | 缓存被清留下的 ` D .code-review-graph/*` 让 git 认为脏，但那不是改动 |
| basetemp 自动清 | 只认显式 `--basetemp=DIR`，绿即删，红保留 | 也清默认编号目录；跑前清 | 编号目录并发下分不清归属；红的 basetemp 是证据（仓里就有 `pytest-temp-preserved.tar.gz` 这种刻意保留） |
| detached 树治本 | 新脚本 `scripts/cleanup_gate_trees.sh` 默认 dry-run + AGENTS.md 一条规则 | 定时任务自动扫 | 用户拒绝自动化；生产者（跑门禁的人）自己清是另一件事 |
| 快照原语 | 复用 `clone_to_staging`，只改文档 | 新起 `clone_db_file` 再让旧名转发 | 4 个调用点 + 6 处测试 monkeypatch 都钉着旧名，改名是纯噪音 |

## 验证与收据

- 治本分支：ruff 全绿；`scripts/check_path_literals.py` 无新增家目录字面量；
  `tests/test_db_snapshot_clone.py`（3 条）+ `tests/test_main_gate_receipt.py` 四条 basetemp 用例通过；
  同文件其余 88 条通过（改动前一轮 92 passed / 2 failed，两条红都是我新加的、已修）。全量门禁读数贴 PR 评论。
- 清理：`round4-20260923T025946.log` 逐条 RM / WT-RM / SKIP；`round4-receipt.json` 汇总。
- **n=1 不许读**：cp -c 对本仓生产库的实际节省没量过（只验证了字节一致与 method 字段）；
  「日烧 30–45 GB」是第三轮会话按当天增量估的，不是趋势。

## 后续要做 / 不要做

- 要：合并后在下一次修库 / 基线导出时看 `clone_to_staging` 收据里 `method=clonefile`；把仓外修库脚本
  （如 `~/.finance-runtime/db-repair/*/verify_*.py` 这类）也改走它。
- 要：隔天再跑一次 `round4-plan.sh B` 或 `scripts/cleanup_gate_trees.sh`——今天很多已合树的 mtime 被第三轮删缓存顶成了今天，被保守跳过。
- 不要：把 `cleanup_gate_trees.sh` 装进 launchd。用户明确拒绝自动清扫；它的价值是让人一条命令可见可控。
- 不要：删 `fwp-wt-market-recovery-0921/tmp/recovery-20260921/`（PR #859 交接保留声明）和 `state/l2-cache/*.7z`。
