# 全树门禁收集中断修复（分支 `fix/gate-collection-0922`，PR #860，待用户确认合入）

一句话：**仓根 `pytest -q` 在 main 上从 2026-08-20 起停在 collection error、零用例执行；本分支修好收集面，
让收据自证「跑了多大一片」「来自哪棵树」。修后全树 12473P / 0F（无 --ignore）。**

## 状态（2026-09-22 23:45 CST，工单 #58 执行中）

- 已前向到 `gitea/main@f24a61a8a`（merge-tree 零冲突、零文件重叠，合并提交 `06f077a18`）；已 push；PR **#860** 已开。
- 四叶（python 无 --ignore / 前端+E2E / registry 五条）在独占 detached 检出
  `~/.finance-runtime/reviews/gate-collection-merge-20260922/trees/finance-workspace-private` 上跑；
  收据路径与阳性对照读数写该目录 `README.md` 并贴 PR #860 评论。本文件不重复读数。
- **未合、未部署**。合入需用户原话确认：`gitea_pr.py merge 860 --yes --expect-head <SHA> --record … --authorized-by … --authorization-source …`。
- 用户指示：四叶完成后不等合并、直接接 #59（main tip 四叶 + #851 留痕），其 python 叶用 `--ignore=scripts/archive` 并注明；#58 合入后复跑替换。
- 分支持有树 `~/fwp-wt-financial-comparison-0922`。作者证据 `~/.finance-runtime/reviews/gate-collection-20260922/`。

## 四个提交（基座 `f783f19c8`）

1. `999c1b1fb` 收集面：`a41e86dfc` 把活脚本 `check_kb_freshness.py` 的测试当孤儿归档，`sys.path.insert(自身目录)` 一挪即断，`norecursedirs` 不含 archive → 收集 Interrupted。测试移回 `tests/`，判据扩为「归档区不得含 pytest 收集物」+ 反向锁。
2. `661811b8a` 收据记收集面：新增 `scope` + `collected`，counts 补 xfailed/xpassed，`check_test_receipt --require-full-scope`（默认只报不拦；旧格式 fail closed）。
3. `e3e884560` AGENTS.md 一条：收据要能自证收集面。
4. `4cc731ebf` `latest-<树>.json`：conftest / session_facts / run_main_gate / check_test_receipt 一起改读本树指针；认领 `FWP_TEST_RECEIPT_DIR`。

## 口径纠正

08-20 后 187 张「≥10000 passed / exit 0 / target=仓根」收据，176 个 revision 带坏文件 → 全是收窄读数，收据未记收窄，不可回溯。PR 正文一句带过，不逐张审计。

## 明确没做到

- Gitea 不跑 Actions，`workbench-check.yml` 仍是纸；门禁人手跑。
- 同树 `fix/financial-comparison-0922` 的 13352P 绕开坏文件得出，合入后应重跑。
- 与 PR #814 在 `conftest.py`/`run_main_gate.sh` 文本冲突、语义互补，整合配方在作者证据 `README.md` 末节。
