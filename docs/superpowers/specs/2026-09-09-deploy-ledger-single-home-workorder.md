# 2026-09-09 部署账本单一写入家工单（占位）

> 来源：`docs/handoffs/inflight-archive-2026-09-08/fix-board-ledger-freshest-switch.md`「下一步」第 2 条（PR #675 合入时留的「另立单」，此前一直没立）+ 2026-09-09 两日质检 B 组第 8 条。机制复用 `scripts/worktree_board.py::resolve_ledger_path`（读取侧「存在的候选里取该 port 末次 switch 最新」的候选枚举与 `_last_switch_unix`）。INDEX 编号 #44。

部署账本 `deploy-ledger.jsonl` 有两个家 **[实测 2026-09-09]**：主检出树 `/Users/a77/finance-workspace-private/state/`（281 行）与 `~/.finance-runtime/`（24 行）。写入侧 `intelligence/runtime/deploy_ledger.py:35 resolve_ledger_path` 的覆盖序是：显式 `--ledger` > `FINANCE_DEPLOY_LEDGER` > `$FINANCE_WS/state/` > `<repo_root>/state/`（`create_app` 传入的代码根）> `~/.finance-runtime/`；`record_*` 在 `deploy_ledger.py:148` 用同一函数取路径。读取侧 `scripts/worktree_board.py:232` 抄同一序（SessionStart 在宿主 python3 下跑，不能 import 包），#675 后改成「存在的候选里取 8792 末次 switch 最新的那份」；审计侧 `scripts/audit_deploy_ledger.py:85` 直接 import 写入侧的解析。三处各自解析路径，只靠 docstring「改覆盖序时一起改」对齐，没有测试锁。

**为什么会分家 [推断，本单第一步核实]**：`worktree_board.py` 的 docstring 说主树那份来自从主树起的 dev server（`repo_root` 非空 → 第 4 级），`~/.finance-runtime` 那份来自生产快照（快照目录无 `state/`，走末级回落）；另有记忆「`audit_deploy_ledger.py check` 不带 `FINANCE_WS` 会假红 `missing_ledger_row`」，说明审计读数也依赖环境变量而不是一个确定的家。09-08 的事故形状：两份都在时按固定顺序取第一份，SessionStart 把 8792 报成一天前的 rev，而生产早切了两次；读取侧已治（#675），写入侧的分家没治。

**交付草案**：
1. 先量：按 `argv / pid / snapshot_path / port` 字段给两份账本的行分组计数（确定性脚本，不猜），写清每一组是谁写的、为什么落到这一家。
2. 拍一个家。推荐 `~/.finance-runtime/deploy-ledger.jsonl` 作唯一默认（跨快照、跨 worktree 都存在的目录），`<repo_root>/state/` 从默认序里去掉、只保留显式覆盖两级；写死后 `worktree_board.resolve_ledger_path` 与 `audit_deploy_ledger` 同步改。反向（以 `state/` 为家）也可，但要说清生产快照没有 `state/` 时怎么办。
3. 一次性并入：把另一家的行按 `unix` 去重并入唯一家，原文件改名 `.migrated-<日期>` 保留不删。
4. 测试：同一环境下 writer / reader / auditor 三处解析同一路径（现在只有注释）；两家并存时 reader 仍取末次 switch 最新（#675 的用例不退）。

**非目标（写死认领）**：❌ 不动 `last_switch_for_port` 的「未归属行」逻辑（#572 的范围）；❌ 不动 8792 切流规程与 `kill -9` 演练（工单 #38）；❌ 不改 `health` 的 `source_revision`（滞后标签，取证只认指纹，已有结论）。

验收：三处同路径的测试绿；`python3 scripts/worktree_board.py --this` 与 `python3 scripts/audit_deploy_ledger.py check`（不带 `FINANCE_WS`）对 8792 报同一 rev；两家只剩一家在被写。分支独立（建议 `fix/deploy-ledger-single-home`）、pathspec 提交、不合 main。
