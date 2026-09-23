# 2026-09-22 门禁收集面修复合入工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
本单是 09-22 收口批（#58–#77）的**第一张**：它合入之后，其余各单的「全量绿」收据才有 `scope` 字段可审。其余单不必等它，但等它合入后再出的收据才算「可审计全量」。姊妹：#59（main 顶端四叶收据补齐）在本单合入后立即接跑。

## 背景与动机

- 2026-09-22 复核实测：`scripts/archive/test_kb_freshness_fix.py` 自 2026-08-20 `a41e86dfc`（「24 个零引用孤儿脚本移入 archive」）起留在收集面内，`pytest.ini` 的 `norecursedirs` 不含 `scripts/archive`，该文件 `import check_kb_freshness` 失败。仓根执行
  `.venv-workbench/bin/python -m pytest -q` 直接 `Interrupted: 1 error during collection`，零用例执行。主检出树与一棵报过「12534 passed / target=树根」的树（`~/fwp-wt-mutation-timeout-evidence-0922`）上都复现。
- 后果：收据 `target` 只记位置参数，`--ignore / -k / -m / --deselect` 一个不入账。08-20 之后所有「≥10000 passed、exit 0、target=仓根」的收据都只可能来自某种收窄，而收据本身证明不了收窄了什么。今天所有分支的全量绿因此都是「口径未知」。
- 修复已在本地分支 `fix/gate-collection-0922`（HEAD `b450d1db9`，基座 `f783f19c8`，5 个提交，未推）：测试移回 `tests/`、归档区禁含 pytest 收集物的判据、收据新增 `scope` 与 `collected`、`check_test_receipt --require-full-scope`、`latest.json` 按树隔离为 `latest-<树>.json`。证据 `~/.finance-runtime/reviews/gate-collection-20260922/README.md`。
- **已定的形态决策**：修法是「把活测试移回收集面 + 归档区守卫」，不是「把 `scripts/archive` 加进 `norecursedirs` 藏起来」。理由：后者让「归档等于删除测试」再次静默发生。收据按树隔离用文件名而不是子目录，三个消费者（`session_facts.sh`、`run_main_gate.sh`、`check_test_receipt.py`）一起改。

## 目标

1. `fix/gate-collection-0922` 前向到最新 `gitea/main`、推送、开 PR，PR 描述含本单编号与证据目录。
2. 在独占干净检出上，用**不带任何 `--ignore`** 的仓根 `pytest -q` 拿到一张收据，收据含 `scope` 段与 `collected`，`check_test_receipt.py --expect-revision <PR head> --require-full-scope` exit 0。
3. 四叶齐绿（python / frontend / e2e / registry），收据 revision 全等于 PR head。
4. 用户确认后用 `gitea_pr.py merge --yes --expect-head --record` 合入，授权原话与出处进记录。
5. 合入后 `AGENTS.md` 与 `docs/workflows/acceptance-workflow.md` 的门禁命令段与新收据字段一致（分支已带一条，核对即可）。

## 非目标（写死认领）

- ❌ 不逐张审计 08-20 以来那 187 张收据各自收窄了什么。收据当时没记，回溯不出来；结论写进 PR 描述一句即可。
- ❌ 不顺手清理 `scripts/archive/` 里其他文件。归档守卫只禁 `test_*.py / *_test.py / conftest.py`，别的另立单。
- ❌ 不改 `pytest.ini` 的 `norecursedirs` 去遮住 archive（见形态决策）。
- ❌ 不修今天各分支报出的负载敏感红（`test_rag_worker` 暖 worker 超时、`test_skill_timeout_degrades…`、`test_ask_watchdog…`、`test_late_malformed_rejudge…`）。它们是负载问题，归 #59 分诊表。
- ❌ 不动主检出 `/Users/a77/finance-workspace-private`（detached `b4a35fa2c`，约 190 个他人未提交改动）。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/gate-collection-20260922/README.md`、`summary.json` | 断在哪、187 张收据回查、四个提交各改什么 |
| 分支 `fix/gate-collection-0922` 的 `docs/handoffs/inflight/fix-gate-collection-0922.md` | 作者自述的读数与「明确没做到」 |
| `gitea/main:pytest.ini` 与 `scripts/archive/test_kb_freshness_fix.py` | 复现点：仓根 collect 必红 |
| `conftest.py` 收据写入段（分支上的 `_collection_scope()`） | `scope` / `collected` 怎么进收据 |
| `scripts/check_test_receipt.py`（分支版） | `--require-full-scope` 判据 |
| `scripts/session_facts.sh`、`scripts/run_main_gate.sh` | 三个 `latest` 消费者是否都改读 `latest-<树>.json` |
| `docs/workflows/acceptance-workflow.md` §3 | 四叶命令与 `--expect-revision --base-drift-max 5` 的完成判据 |

## 步骤

1. 开工三连：`git status --short && git branch --show-current && git worktree list`。本单不在主检出里做；新开 `git worktree add ~/fwp-wt-gate-collection-merge-0922 fix/gate-collection-0922`（若该分支已被 `~/fwp-wt-financial-comparison-0922` 检出，先 `git -C 那棵树 branch --show-current` 确认，不要两棵树同时持有同一分支）。
2. `git fetch gitea && git merge-tree --write-tree gitea/main fix/gate-collection-0922` 探冲突；有冲突逐处按双方意图解，不用 `-X ours/theirs`。前向后 `git push gitea fix/gate-collection-0922`，`python3 scripts/gitea_pr.py open --head fix/gate-collection-0922 --title "fix(gates): 全树门禁收集面修复 + 收据记收集面 + latest 按树隔离（工单 #58）"`。
3. 先看 `uptime` 与 `df -h /System/Volumes/Data`：load 1 分钟均值 > 8 或可用 < 8G 就等，写进交接。今天峰值 load 82、11 个 pytest 并发，那种条件下的红绿都不算读数。
4. 独占干净 detached 检出 PR head，跑 python 叶：`bash scripts/run_main_gate.sh --pytest-args "-q -p no:cacheprovider --basetemp=<树外目录>"`，**不带 `--ignore`**。收据须出现 `scope` 与 `collected`，`counts` 含 `xfailed/xpassed`。
5. 前端叶：`.venv-workbench/bin/python scripts/run_frontend_gate.py --tree <检出根> --expect-revision <完整 SHA> --output <树外目录> --workbench-port 18981 --re06-port 18984`（端口先 `lsof -i :18981 -i :18984` 确认空闲）。registry 叶：`build_registry.py check-parseability / check / backfill-tables / generate-views` 四条加 `scripts/audit_ledger_spec_crosswalk.py`，逐条 exit 0。
6. `check_test_receipt.py <收据> --expect-revision <PR head> --require-full-scope` exit 0；把三张收据路径与 `collected` 数写进 PR 评论。
7. 合入需用户确认。拿到确认后：`python3 scripts/gitea_pr.py merge <PR号> --yes --expect-head <SHA> --record <目录>/merge-record.json --authorized-by "<用户原话>" --authorization-source "<会话文件名 + 时间戳>"`。
8. 合入后在 `gitea/main` 新 tip 上复跑第 4 步一次（这一步即 #59 的开头，可直接接手 #59）。交接 inflight ≤3K；INDEX #58 行改状态。

## 验收

- [ ] 独占干净检出上仓根 `pytest -q` 不再 Interrupted，`collected` > 12000 且与 passed+failed+skipped+xfailed+xpassed 对平。
- [ ] 收据含 `scope`，`check_test_receipt.py --require-full-scope` exit 0；把 `--ignore=scripts/archive` 加回去再跑一次，`--require-full-scope` 必须 **exit 非 0**（阳性对照）。
- [ ] `tests/test_scripts_module_references.py::test_archive_holds_nothing_pytest_would_collect` 在往 `scripts/archive/` 临时放一个 `test_x.py` 时变红，删掉后绿（阳性对照）。
- [ ] 两棵树并跑 pytest 后各自的 `latest-<树>.json` 互不覆盖；`session_facts.sh` 报的是本树读数。
- [ ] 四叶收据 revision 全等于 PR head；合并记录 JSON 含 `authorized_by` 与来源。
- [ ] INDEX #58 行更新为合入提交 SHA。

## 红线

- 只用 pathspec 提交（`git add -- <文件>` / `git commit -- <文件>`），不 `git add -A`；合入 main 必须等用户确认，不强推。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；宿主 python3 会多出几十条环境红。
- 不在主检出树里做任何写操作；不删、不改其他 agent 的工作树与证据目录。
- 全量前先看 `uptime` 与磁盘；被负载打断的收据不当部分绿，也不当红。
- 台账号一律 `python3 scripts/claim_ledger_id.py claim --branch <分支>`；不写明文密钥。
