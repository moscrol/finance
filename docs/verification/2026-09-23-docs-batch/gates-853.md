# PR #853（`chore/handoff-budget-gate`）四叶读数 · 工单 #77

独占干净树 `/Users/a77/fwp-wt-853-handoff-budget-gate`，解释器 `.venv-workbench`（3.12.13）。全量命令 `bash scripts/run_main_gate.sh --pytest-args "-q -p no:cacheprovider --ignore=scripts/archive"`（`--ignore=scripts/archive`：#58/#860 合入前仓根收集会 Interrupted，特此声明）。

| head | 来历 | python | frontend | e2e | registry |
|---|---|---|---|---|---|
| `54d0acdb7` | PR 原 head（base `e2ef0f095`） | ruff 0；目标 8P（`20260922T155932Z-54d0acdb.json`，dirty=false）；**全量无结论**：排队起跑时 main 落地 #863（162 非文档文件），按纪律作废，随后被系统低内存杀 | lint 0 / typecheck 0 / vitest 110P / build 0 | 34P / 2S | 0 |
| `a3ad91342` | 本地前向 main@`8e7989372`（未推） | 目标 8P（`20260922T164302Z-a3ad9134-e0ef7d5278ab.json`）；全量未起（main 又落地 #854） | lint 0 / typecheck 0 / vitest 118P / build 0 | 34P / 2S | — |
| **`4c730a8ba`** | 本地前向 main@`6fc6bfa94`（未推） | ruff 0；**14336 passed / 0 failed / 85 skipped / 2 xfailed**，收据 `~/.finance-runtime/test-receipts/gate-OeC40sBc/pytest.json`（dirty=false，`check_test_receipt --expect-revision 4c730a8ba --base-drift-max 5` 判可采信） | lint 0 / typecheck 0 / vitest 118P / build 0（`api/static` 无脏字节） | 34P / 2S（`WORKBENCH_PYTHON`=venv，8791） | 0 |

02:5x 核：main 已到 `72be60059`（#860 落地：`conftest.py` / `scripts/check_test_receipt.py` / `scripts/session_facts.sh` / 5 个测试文件），与 #853 文件集（`.pre-commit-config.yaml` / `scripts/check_handoff_budget.py` / `tests/test_handoff_budget_gate.py` / inflight）零交集；`4c730a8ba` 对 `72be60059` merge-tree 干净。
合入步骤：main 仍为 `72be60059` 时，推 `4c730a8ba` 到 `chore/handoff-budget-gate`，`merge --expect-head 4c730a8ba --expect-base 72be60059`；若 main 再动且非文档漂移 > 0，再前向一次并复跑四叶（约 30 分钟）后才合。

环境事件：02:2x 磁盘回收清掉了各 worktree 的 `intelligence/webapp/node_modules`、`~/Library/Caches/ms-playwright` 与被跟踪的 `.code-review-graph/{.gitignore,wiki-steering.json}`，首轮前端叶 4 秒内全部 `ELIFECYCLE`（无结论，非红）；重装 / 还原后复跑取数，上表为复跑读数。

## 2026-09-23 续检：main@`5f35da1723f7`

当前主干上的临时合流提交为 `5305d5d9dbad80478f589a62a6700fc97aca6848`，工作树干净。`.venv-workbench` 上 ruff、路径字面量、registry 均通过，目标测试 **8 passed in 4.76s**，收据 `~/.finance-runtime/test-receipts/20260923T051319Z-5305d5d9-d3d9f3919604.json`。

全量命令仍为 `bash scripts/run_main_gate.sh --pytest-args "-q -p no:cacheprovider --ignore=scripts/archive"`；本轮尚未在该最新候选启动全量 Python，等待并发全量任务结束后执行。前端 lint/typecheck/Vitest **120P**/build 0，E2E **34P/2S**（使用 `.venv-workbench`）。旧 `4c730a8ba` 的全量收据因当前 main 漂移不再适用；不得把历史 14336P 迁移到本轮。
