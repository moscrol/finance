# 2026-09-09 部署账本单一写入家工单

> 状态：🟡 代码已落、门禁绿、PR 待确认（2026-09-09，分支 `fix/deploy-ledger-single-home`，基线 `gitea/main@5eb24515`，提交 `0aea8a19`）。落地记录见文末。
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

## 落地记录（2026-09-09）

**先量 [实测，真机两份账本按 action / port / 来源目录 / argv[0] 分组]**：主树 `state/` 282 行 = 100 条 8792 `startup`（生产 uvicorn 进程，argv0 `__main__.py`，快照目录）+ 43 条 8792 `switch` + 18 条无 port 的老 `switch`（`audit_deploy_ledger.py`，部署脚本带 `FINANCE_WS="${FINANCE_WS:-$REPO}"`）+ 各 dev server 端口（8796–8823）的 startup；`~/.finance-runtime` 24 行 = 23 条 8792 `switch` + 1 条 startup，全部 argv0 `audit_deploy_ledger.py`——即链切规程 `acceptance-workflow.md` 里显式 `--ledger ~/.finance-runtime/deploy-ledger.jsonl` 那一步（2026-09-07 0907g 为了让看板读得到而补的）。主树那份末次 8792 switch 停在 09-07 08:42 `b594a5e7`，生产真实 rev `0060da5c` 的 switch 只在 `~/.finance-runtime`。**「为什么会分家」的推断被证伪**：不是 dev server vs 快照，而是同一件事（记 switch）两条路径带不带 `FINANCE_WS` / `--ledger` 走到了两个目录；解析随环境变量与调用者所在目录变，就一定分家。

**拍家**：`~/.finance-runtime/deploy-ledger.jsonl` 作唯一默认（`default_ledger_path`），只保留显式 `--ledger` / `FINANCE_DEPLOY_LEDGER` 两级覆盖；`$FINANCE_WS/state/` 与 `<repo_root>/state/` 从默认序删除，降为 `legacy_ledger_candidates`（读取过渡 + 迁移用）。理由：这台机器上唯一不随快照 / worktree / 环境变量变的位置，hook（宿主 python3、无 FINANCE_WS）、launchd 生产进程、部署脚本、手工链切四种写读者零配置落到同一文件；episode store 的末级也是它。反向（以 `state/` 为家）被否：快照目录没有 `state/`，仍要靠环境变量指回主树，正是病根。

**落地**：`intelligence/runtime/deploy_ledger.py`（`default_ledger_path` / `resolve_ledger_path` 收窄、`repo_root` 保留签名不参与、`legacy_ledger_candidates`、`read_rows`、`merge_ledgers`：并集去重、按 `unix` 缺则 `ts` 稳定排序、原子覆写、旧文件改名 `.migrated-<日期>`、目标在读与替换之间被写则放弃不吞行）；`scripts/worktree_board.py` 读取侧唯一家优先、过渡期仍看三个旧家、存在候选里取末次 8792 switch 最新（#675 读法不退）；`scripts/audit_deploy_ledger.py` 新 `homes`（列唯一家与旧家行数 / 末次 switch·startup，旧家有行 exit 1，可当门）与 `migrate-homes`（默认 dry-run，`--apply` 才动），`--repo-root` 废弃为 no-op 并提示；`acceptance-workflow.md` 链切注释改写（`--ledger` 冗余但保留以防回滚旧快照；切完跑 `homes`）。测试：`tests/test_deploy_ledger_homes.py` 6 条（写入 / 读取 / 审计三处同路径 × FINANCE_WS 有无、`--repo-root` 忽略并提示、`homes` 门 + 迁移干跑 / 真并入 / 幂等、无时刻老行排最前、并发改动放弃）、`test_deploy_ledger.py` +2、`test_worktree_board.py` 「旧家优先」那条改为「唯一家优先」。

**真机干跑**：`homes` exit 1（旧家 282 行）；`migrate-homes` 计划：24 + 282 → 306 行、0 重复。**`--apply` 刻意没跑**：8792 仍在旧代码 `0060da5c`，切流前生产进程每次重启还会往主树 `state/` 写 startup，现在并入只是把「两个家」暂时变成「一个家 + 一个不断再生的旧家」；迁移幂等，等本单合入且 8792 切到含它的 rev 之后跑一次 `python3 scripts/audit_deploy_ledger.py migrate-homes --apply`，再用 `homes` 当门。目前读取侧不受影响：#675 的「取末次 switch 最新」已让看板报对 `0060da5c`。

**顺带发现，不在本单**：episode store（`resolve_episode_store_root`）保留了 `$FINANCE_WS/state/episodes` 一级，与本单删掉的那级同构——CLI steer（#687）用「events.jsonl 不在就拒投」兜住了，但根治是同样收成一个家；生产 episodes 现落主树 `state/episodes`，搬家要连数据一起，另立单。
