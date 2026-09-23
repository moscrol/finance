# 2026-09-22 main 顶端四叶收据补齐与 #851 合入后补验工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#58（门禁收集面修复）。#58 未合前本单也能跑，但 python 叶要显式 `--ignore=scripts/archive` 并把这句写进收据说明；#58 合入后重跑一次不带 ignore 的版本替换之。与 #65、#66、#74 等合入准备单**串行**：它们都要求「main 顶端有干净四叶收据」作为基线。

## 背景与动机

- 2026-09-22 复核 `~/.finance-runtime/test-receipts/`：main 最后一张干净全量收据是 #848 合入后的 `a2c8d1f90`（`20260921T191851Z-a2c8d1f9.json`，12511 passed）。其后 main 前进了 #851（`53bd332c1`）与三笔文档提交到 `f24a61a8a`，**没有任何一张 main 顶端收据**。
- #851 合入时的门禁读数：两张目标收据（`…112608Z-f900c1f3` 196 passed、`…114039Z-078f7eb4` 143 passed，均干净树），全量 12528 passed 跑于提交前脏树、无收据、含 1 条 `test_rag_worker` 负载红；前端 / E2E / registry 三叶无记录。这不满足 AGENTS.md「任一叶子红或无结论都不合」。
- #851 的用户授权存在但不在仓库里：Pi 会话 `~/.pi/agent/sessions/--Users-a77-finance-workspace-private--/2026-09-22T11-34-44-398Z_01a0c8e5-95ac-73af-8a8b-1df8e9f5d949.jsonl`，用户消息 `2026-09-22T12:15:42Z`「合并，然后按照最优推进」，合并发生于 20:16:27 CST。PR 正文与 merge commit 均无授权记录，`gitea_pr.py merge --record` 未被使用。
- **已定的形态决策**：不回滚 #851。它的改动（`db.read_snapshot` 只读事务、`publish_snapshot` 按日唯一）有目标收据与变异证据，问题是合入程序不是内容。本单补齐程序性证据并把主干读数恢复到「可对照」状态。

## 目标

1. `gitea/main` 当前 tip 上四叶各一张收据，全部可采信（python 收据 `--expect-revision $(git rev-parse gitea/main)` exit 0；前端收据 `exit_code=0 / complete=true / identity_stable=true / dirty=false`；registry 五条 exit 0）。
2. 一张分诊表：main tip 若有红，逐条归类为「负载敏感既有红」或「真回归」，每条附单跑与低负载复跑读数。真回归即刻升级为阻塞，并在 INDEX 与 `docs/handoffs/inflight/main.md` 写明「在修好前不再合任何 PR」。
3. #851 补留痕：一条 PR 评论，含（a）授权原话、会话文件名、UTC 时间戳；（b）合入时实际存在的门禁读数与缺失的叶子；（c）本单在 main tip 上取得的四叶收据路径。
4. 台账：`docs/workflows/acceptance-workflow.md` 引用的门禁台账追加一行 main tip 读数（找不到既有台账行就在 `docs/verification/<日期>-main-tip-gate/README.md` 落盘并在 inflight 指过去）。

## 非目标（写死认领）

- ❌ 不修分诊出的负载敏感红。四条已知：`intelligence/tests/test_rag_worker.py::test_warm_worker_survives_first_timeout_and_drains_the_late_response`、`test_workbench_conversation_integration::test_skill_timeout_degrades_one_module_and_continues`、`test_conversation_orchestrator::test_ask_watchdog_returns_partial_and_suppresses_late_progress`（#848 已治）、`test_late_malformed_rejudge_cannot_masquerade_as_deadline_recovery`。修它们另立单，本单只归类。
- ❌ 不改 #851 的代码，不为它补前端测试。
- ❌ 不改写 merge commit、不 force-push 任何东西去「补」授权记录。留痕只走 PR 评论 + 文档。
- ❌ 不给其他 PR 跑门禁；那是各自合入准备单的事。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/test-receipts/20260921T191851Z-a2c8d1f9.json` | 上一张 main 干净全量收据的形状与读数，作对照基线 |
| `~/.finance-runtime/test-receipts/20260922T112608Z-f900c1f3.json`、`…120046Z-b9a93b0c.json`、`…121855Z-53bd332c.json` | #851 相关的仅有收据，全是目标收据 |
| `gitea/main:docs/handoffs/2026-09-22-hithink-sector-closeout.md` | #851 改了什么、变异证据、作者自述的负载红 |
| `docs/workflows/acceptance-workflow.md` §3 | 完成判据命令、`--base-drift-max 5`、前端门命令 |
| `scripts/run_main_gate.sh`、`scripts/run_frontend_gate.py`、`scripts/build_registry.py`、`scripts/audit_ledger_spec_crosswalk.py` | 四叶入口 |
| `~/.finance-runtime/reviews/research-tail-union-resume-20260922/README.md` | 「负载下 2400 秒被 SIGTERM 的收据怎么读」的现成范例 |

## 步骤

1. 开工三连；`git fetch gitea`；`sha=$(git rev-parse gitea/main)`；独占 detached 检出 `git worktree add --detach ~/.finance-runtime/reviews/main-tip-gate-<日期>/tree $sha`。
2. 资源准入：`uptime` 1 分钟 load ≤ 8、`df` 可用 ≥ 8G、`pgrep -fl pytest | wc -l` ≤ 2；不满足就等，把等待写进 `README.md`。
3. python 叶：`bash scripts/run_main_gate.sh --pytest-args "-q -p no:cacheprovider --basetemp=<树外目录>"`（#58 未合时加 `--ignore=scripts/archive` 并记录）。收据 `check_test_receipt.py <收据> --expect-revision $sha --base-drift-max 5`。
4. 前端叶 `run_frontend_gate.py --tree … --expect-revision $sha --output … --workbench-port 18981 --re06-port 18984`；registry 五条。
5. 有红：先在同一检出单跑该用例 3 次，再在 load ≤ 4 时整文件跑 1 次；三绿一绿判「负载敏感既有红」，否则判「真回归」并停下升级。
6. #851 评论：`python3 scripts/gitea_pr.py show 851` 取身份后用 Gitea API 贴评论（token 只从 Keychain `security find-generic-password -s gitea-local -a a77-token -w` 取，不进历史与文件）。评论正文用第 3 节目标 3 的三段。
7. 台账行 + inflight `docs/handoffs/inflight/main.md` 一行指针；INDEX #59 行改状态。

## 验收

- [ ] 四张收据文件名里的 SHA 与 `git rev-parse gitea/main` 全等，且 fetch 时间在收据之前。
- [ ] `check_test_receipt.py … --expect-revision --base-drift-max 5` exit 0。
- [ ] 分诊表里每条红都有「单跑 ×3 + 低负载整文件 ×1」四个读数；没有红则写明「0 红」并附 `collected`。
- [ ] #851 PR 页可见评论，含会话文件名与 UTC 时间戳，不含任何 token。
- [ ] 阳性对照：把 `--expect-revision` 换成 `a2c8d1f90` 再跑 check，必须 exit 非 0。

## 红线

- 只用 pathspec 提交；不改 main 历史；不合任何 PR（本单无合入动作）。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不在主检出树里做写操作；不动其他会话的检出、证据目录与运行中的 pytest 进程。
- 前端门端口用前 `lsof` 核空闲；跑完确认测试服务已退出。
- 台账号一律 `claim_ledger_id.py claim`；不写明文密钥。
