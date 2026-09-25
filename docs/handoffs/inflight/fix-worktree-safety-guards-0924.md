# fix/worktree-safety-guards-0924 · 拆树工具的两道守卫从「永远 0 棵」修成可用

## 这个分支做什么
`scripts/cleanup_gate_trees.sh`（#876）在 2026-09-24 02:30 对 360 棵树 dry-run 报 **0 棵可删**：125 棵被 ignored 里的
`__pycache__/.pytest_cache/.ruff_cache/node_modules/.venv*` 挡住（脚本把一切 ignored 当「有内容」）；47 棵被「有进程打开」挡住，
其中绝大多数是一个 Claude Code 会话在 ~210 棵树里持有的 3000+ 个 kqueue 目录监视句柄。本枝只改共享采样器 `scripts/worktree_safety.py`
与脚本本身，看板 `worktree_board.py` 同步受益（它读同一份 blockers）。

## 决策与被否方案
- ignored 只豁免**可再生缓存**（`is_cache_path`：`__pycache__` / `.pytest_cache` / `.ruff_cache` / `.mypy_cache` / `node_modules` / `.venv*` / `*.pyc` / `.DS_Store`）。
  其余 ignored（`tmp/` 取证 DuckDB、`intelligence/users/`、`db/snapshots`）**继续阻塞**——工具不替用户判定数据可丢。否了「按大小阈值放行」：大小不是价值。
- 进程「在用」加一个否定条件：`lsof` 记录里 **fd 是数字且类型 DIR** 的是目录监视器，不算使用；`cwd` / `rtd` / `txt` / 任何普通文件仍算。
  否了「按进程名排除 claude」：编辑器、Spotlight 同样持目录句柄，按形状判比按名单判稳。lsof 多取一个 `t` 字段（`-Fpcftn`）。
- 上锁的树：默认 **SKIP 并打出锁的理由**（此前 `worktree remove --force` 对锁树直接失败、报 FAIL）；新增 `--release-merged-locks`，
  只在候选已进基线（分支已合，或 detached HEAD 是基线祖先）时 unlock 再拆。HEAD 不在基线的锁树永远不动。

## 已验证
- `tests/test_worktree_safety.py`（+2）、`tests/test_cleanup_gate_trees.py`（+4，含「锁树默认跳过」「只解已进基线的锁」「缓存不阻塞」「DIR 监视句柄不阻塞」）、
  `tests/test_worktree_board.py`：三文件 65P/0F（`.venv-workbench`，收据 `20260924T060447Z-a54fed0d-*.json`，未提交阶段）；Ruff 绿；`bash -n` 绿。
- 对真实仓 dry-run（112 棵，`--days 0 --release-merged-locks`）：0 棵可删，SKIP 分布 上锁 14 / 未提交 16 / 启动器引用 7 / ignored 非缓存 8，
  **「有进程」一栏从 47 降到 0**；记录在 `~/.finance-runtime/reviews/pi-session-inventory-20260924/cleanup/cleanup-gate-trees-fixed-dryrun.txt`。
  0 棵是因为同日已用旁路脚本按同样口径拆掉 200 余棵，见该目录 `README.md`。

## 未验证 / 已知边界
- 未跑全量 Python / 前端 / e2e；四叶留给合前门禁。`--help` 的 sed 行号随头注释扩到 2,26。
- `is_cache_path` 是路径组件白名单，`dist/` 之类构建产物刻意不豁免。

## 下一步
开 PR，合入等用户确认；合入后用 `--release-merged-locks` 收掉 #868 / #884 / RE06 合入后留下的 14 棵锁树。
