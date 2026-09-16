# 2026-09-09 episode store 单一家工单（占位）

> 来源：工单 #44（部署账本单一写入家，PR #688 已合 `gitea/main@dba3aa55`）落地记录「顺带发现」+ #687 CLI steer 交接「未验证 / 已知边界」。机制复用 #44 的三件：`default_*_path` 唯一家 + `legacy_*_candidates` 读取过渡 + `homes` / `migrate-homes` 门与迁移（`intelligence/runtime/deploy_ledger.py`、`scripts/audit_deploy_ledger.py`），照形状写，别复制正文。INDEX 编号 #45。

`intelligence/services/episode_store.py::resolve_episode_store_root` 的覆盖序是 `FORESIGHT_EPISODE_STORE` > `$FINANCE_WS/state/episodes` > `~/.finance-runtime/episodes`——中间那级与 #44 删掉的 `$FINANCE_WS/state/` 同构：解析随环境变量变，同一台机器上带不带 `FINANCE_WS` 的两个进程会写读两个目录。与 #44 的差别是**现在还只有一个家在用 [实测 2026-09-09]**：主树 `/Users/a77/finance-workspace-private/state/episodes/` 45 个 episode 目录（最新 `state.json` 2026-09-09 15:17，无未收口），`~/.finance-runtime/episodes/` 不存在。所以这是潜在缺口不是事故，优先级低于 #44；但两个读者已经建在这个根上——Workbench readiness 的 `open_episodes` 登记（`api/app.py::_open_episodes_registry`）与 CLI `steer`（`services/episode_steer.py`，靠「`events.jsonl` 不在就拒投并打出看过的根」兜住）。

**已知的定性结论（防重新发现）**：唯一家应与 #44 同址族 `~/.finance-runtime/`（机器上不随快照 / worktree / 环境变量变的位置），不选 `state/`；生产 episodes 现落主树 `state/episodes`，**搬家要连 45 个目录一起迁**，不能只改代码——否则 readiness 的 `open_episodes` 与 `restore` 立刻读不到历史；`FORESIGHT_EPISODE_STORE` 显式覆盖保留（测试与 CLI `--store-root` 用它）。第一步先核实生产进程的 `FINANCE_WS` 从哪来（launchd plist 里没有，`deploy_workbench_runtime.sh` 只在记账那一行临时带；`create_app` 侧另有读法），不然说不清 45 个目录为什么落在主树。

**交付草案**：1. 先量：谁在什么环境下写过 `state/episodes`（按 `configure` 事件里的 `argv` / 快照路径分组）；2. `default_episode_store_root` 唯一家 + 旧根降为候选；`_open_episodes_registry` / `episode_steer` / `JsonlEpisodeStore` 装配三处走同一函数；3. 迁移：整目录搬（`os.replace` 逐 episode 目录，幂等，旧根留 `.migrated-<日期>` 空标记），与 8792 切流同窗做——切流前旧代码仍往旧根写；4. 测试：三处同根 × `FINANCE_WS` 有无；`homes`-式门列两根各自的 episode 数与最新 `updated_at`。

**非目标**：❌ 不改 events.jsonl / state.json 格式（P2 合同）；❌ 不做 `restore` 自动恢复（§12 第 3 题只登记）；❌ 不动 `FORESIGHT_EPISODE_STORE` 语义。

验收：三处同根测试绿；`readiness.open_episodes` 与 `intelligence.cli steer --list` 在不带 `FINANCE_WS` 的 shell 里列出与生产进程同一批 episode；旧根只剩 `.migrated-*` 标记。分支独立（建议 `fix/episode-store-single-home`）、pathspec 提交、不合 main；与 8792 切流同窗执行迁移。
