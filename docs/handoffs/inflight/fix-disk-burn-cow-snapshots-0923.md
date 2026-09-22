# fix/disk-burn-cow-snapshots-0923 · 门禁与修库不留现场

## 这个分支做什么
改掉「日烧 30–45 GB 盘」的三个生产者：整库改前快照走 APFS 克隆、门禁绿即删显式 basetemp、detached 门禁树一条命令批量拆；AGENTS.md 加一条规则。清理本身（回收 98.8 GB）不在分支里，收据在 `~/.finance-runtime/reviews/disk-cleanup-20260923/`。

## 决策与被否方案
- 复用 `db.clone_to_staging` 作唯一快照原语 / 否了新起 `clone_db_file` / 4 个调用点 + 6 处测试 monkeypatch 钉着旧名。
- basetemp 只认显式 `--basetemp=DIR`，绿删红留，`GATE_KEEP_BASETEMP=1` 可留 / 否了清默认编号目录 / 并发下分不清归属；红的是证据。
- `cleanup_gate_trees.sh` 默认 dry-run 人工触发 / 否了 launchd 定时扫 / 用户 09-23 明确拒绝自动清扫。
- 删树前对 LaunchAgents 与 `~/.local/bin` 引用 / 否了只看干净+mtime / `.devin-worktrees/ima-queue-auto-triage`、`kb-runtime` 是 detached 树却是定时任务代码根。
展开见 `docs/handoffs/2026-09-23-disk-cleanup-and-burn-fix.md`。

## 当前状态
- 已提交两笔（`git log -2`）：`a2ec1fcc7` 主体（9 文件）；其后一笔给 `cleanup_gate_trees.sh` 的 lsof 加 `-d '^mem'` + 看门狗超时真杀 + `LSOF_TIMEOUT`。
- 交接与日期快照随后单独提交；之后不再加提交（四叶读数对 revision）。全量门禁读数贴 PR 评论。

## 已验证
ruff；`check_path_literals.py` 无新增；`bash -n`；`tests/test_db_snapshot_clone.py` 3 条 + basetemp 4 条通过，test_main_gate_receipt.py 其余 88 条通过；pre-commit 11 道过；`cleanup_gate_trees.sh` dry-run 66 s 跑完，0 候选（第四轮已拆），94 棵按四类理由跳过。

## 未验证 / 已知边界
- `cp -c` 对 3.4 GB 生产库的真实节省没量；非同卷退回整份 copy2。
- run_main_gate.sh「basetemp 包含仓库树则保留」分支无测试：pytest 启动会清空显式 basetemp，造不出安全夹具。
- `cleanup_gate_trees.sh --apply` 没在真树上跑过。
- 前端 / e2e 叶子没跑：不碰 `intelligence/webapp`，读数同 gitea/main；补不补由用户定。

## 下一步
1. 等全量 python 读数（PR 评论），红集与 gitea/main 对齐再提合并；合并等用户确认。
2. 合并后隔天 `bash scripts/cleanup_gate_trees.sh`（先 dry-run）：今天很多已合树 mtime 被第三轮删缓存顶成今天。
3. 仓外修库脚本（`~/.finance-runtime/db-repair/*/verify_*.py` 一类）下次改走 `clone_to_staging`。

## 踩过的坑
- bash 3.2：`"$real（…"` 在 set -u 下报 `real\xef: unbound variable`，孤立 `\xef` 让 subprocess text=True 解码崩。变量后跟非 ASCII 一律 `${var}`。
- 全量 `lsof -Fn` 在这台机器会停 10 分钟以上（内存映射条目占大头）；`-d '^mem' -nP` 后 0.4 秒。看门狗超时必须 `pkill -P` 杀管线，且子 shell 输出甩 /dev/null，否则调用方 `| head` 等到它自然结束。
- 测试名含 "basetemp" 会进收据路径，`"basetemp" not in stdout` 必红；锁具体句子。
